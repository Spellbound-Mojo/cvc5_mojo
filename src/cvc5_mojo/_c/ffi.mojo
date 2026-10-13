"""Runtime support for the generated code: finding the libraries, strings,
NULL, range checks, iteration and printing as Python does.

The raw layer (`raw.mojo`, generated) loads the libraries, calls the C API
and turns errors cvc5 records into Mojo errors; the base API converts
values with the helpers here.
"""

from std.os import getenv
from std.os.path import dirname, exists
from std.sys import CompilationTarget, get_defined_string, is_defined
from apn_mojo import Integer

comptime Ptr = Pointer[NoneType, MutUntrackedOrigin]
"""Opaque cvc5 handle (`Cvc5Term`, `Cvc5Sort`, `Cvc5*`, ...)."""

comptime CChars = Pointer[Int8, MutUntrackedOrigin]
"""A `const char*` passed to or returned by cvc5."""

comptime TRACE_DEFINE = "CVC5_MOJO_TRACE"
"""Build with `-D CVC5_MOJO_TRACE=<file>` to record every C function called."""

comptime LIBRARY_ENV = "CVC5_MOJO_LIBRARY"


def library_path(stem: String) raises -> String:
    """Locate a release library by stem, such as `libcvc5`.

    Order: `$CVC5_MOJO_LIBRARY`, the path of the main library, whose directory
    holds the other libraries; the conda package layout
    `$CONDA_PREFIX/lib/cvc5_mojo/lib/`; the development checkout
    `third_party/cvc5/lib/`.
    """
    comptime suffix = ".dylib" if CompilationTarget.is_macos() else ".so"
    var file = stem + suffix
    if stem != "libcvc5":
        var directory = dirname(library_path("libcvc5"))
        var sibling = directory + "/" + file
        if not exists(sibling):
            raise Error("cvc5_mojo: " + sibling + " not found beside libcvc5" + suffix)
        return sibling
    var explicit = getenv(LIBRARY_ENV)
    if explicit.byte_length() > 0:
        if dirname(explicit).byte_length() == 0:
            raise Error("cvc5_mojo: " + LIBRARY_ENV + " must include the library directory")
        return explicit
    var prefix = getenv("CONDA_PREFIX")
    if prefix.byte_length() > 0:
        var packaged = prefix + "/lib/cvc5_mojo/lib/" + file
        if exists(packaged):
            return packaged
    var dev = "third_party/cvc5/lib/" + file
    if exists(dev):
        return dev
    raise Error(
        "cvc5_mojo: " + file + " not found; set " + LIBRARY_ENV + " or run `pixi run fetch`"
    )


def c_bytes(s: String) raises -> List[Int8]:
    """Return a nul-terminated copy of `s` for passing as `const char*`.

    Reject embedded NUL instead of letting C silently read only a prefix.
    The caller keeps the list alive for the duration of the C call.
    """
    var bytes = s.as_bytes()
    if UInt8(0) in bytes:
        raise Error("cvc5_mojo: embedded NUL in a C string argument")
    # Reserve the terminator too, so appending it cannot grow the buffer.
    # Reinterpret byte signedness without changing the UTF-8 bit patterns.
    var out = List[Int8](capacity=len(bytes) + 1)
    out.extend(Span(unsafe_ptr=bytes.unsafe_ptr().unsafe_bitcast[Int8](), length=len(bytes)))
    out.append(0)
    return out^


def to_string(p: CChars) raises -> String:
    """Copy a nul-terminated C string into a Mojo `String`.

    cvc5 strings are only valid until the next C API call, so they are
    always copied immediately.
    """
    var i = 0
    while p[unsafe_offset=i] != 0:
        i += 1
    # Borrow only for the validated String construction, which owns its copy.
    # Avoid an intermediate list and its byte-at-a-time growth/copying.
    return String(from_utf8=Span(unsafe_ptr=p.unsafe_bitcast[UInt8](), length=i))


def to_strings(items: Pointer[CChars, MutUntrackedOrigin], count: UInt) raises -> List[String]:
    """Copy a counted C string array into independently owned, validated strings.

    Keep native storage alive through the call. Earlier decoded strings are
    destroyed if a later element fails UTF-8 validation.
    """
    var out = List[String](capacity=Int(count))
    for i in range(Int(count)):
        out.append(to_string(items[unsafe_offset=i]))
    return out^


def null[T: AnyType]() -> Pointer[T, MutUntrackedOrigin]:
    """A NULL pointer, for C parameters that cvc5 documents as "may be NULL".

    Mojo 1.1 cannot construct a null `Pointer`; an empty `Optional[Pointer]`
    is a NULL pointer in memory, which `tests/smoke/test_raw.mojo` checks.
    """
    var none = Optional[Pointer[T, MutUntrackedOrigin]](None)
    return Pointer(to=none).unsafe_bitcast[Pointer[T, MutUntrackedOrigin]]()[]


def is_null[T: AnyType](p: Pointer[T, MutUntrackedOrigin]) -> Bool:
    """Whether `p` is NULL."""
    return p == null[T]()


def to_c_int32(value: Int) raises -> Int32:
    """Convert to a C `int32_t`, raising when `value` does not fit."""
    # Literal bounds: `Int(UInt32.MAX)` folds wrongly in some Mojo 1.1 contexts.
    if value < -2147483648 or value > 2147483647:
        raise Error("cvc5_mojo: " + String(value) + " is out of range for int32_t")
    return Int32(value)


def to_c_uint32(value: Int) raises -> UInt32:
    """Convert to a C `uint32_t`, raising when `value` does not fit."""
    if value < 0 or value > 4294967295:
        raise Error("cvc5_mojo: " + String(value) + " is out of range for uint32_t")
    return UInt32(value)


def to_c_uint32(value: Integer) raises -> UInt32:
    """Range-check exact variadic indices before converting them to C."""
    if value < 0 or value > 4294967295:
        raise Error("cvc5_mojo: " + String(value) + " is out of range for uint32_t")
    return UInt32(Int(value))


def fits_int_literal(value: IntLiteral) -> Bool:
    """Whether an exact literal fits Int on the supported 64-bit platform."""
    return value >= -9223372036854775808 and value <= 9223372036854775807


def fits_native_integer[dtype: DType](value: Integer) -> Bool:
    """Check exact APN range without narrowing or constructing an error."""
    comptime assert dtype == DType.int64 or dtype == DType.uint64
    return value >= SIMD[dtype, 1].MIN and value <= SIMD[dtype, 1].MAX


def checked_int_literal(value: IntLiteral) raises -> Int:
    """Check a literal before Mojo's implicit conversion can discard high bits."""
    if not fits_int_literal(value):
        raise Error("cvc5_mojo: integer literal is out of range for Int")
    return Int(value)


def to_c_size(value: Int) raises -> UInt:
    """Convert to a C `size_t`, raising when `value` is negative."""
    if value < 0:
        raise Error("cvc5_mojo: " + String(value) + " is out of range for size_t")
    return UInt(value)


def escape_smt_string(s: String) -> String:
    """Encode string data as ASCII SMT-LIB escapes, without enclosing quotes.

    Escaping backslashes prevents literal escape-looking text from being
    interpreted. NUL and Unicode survive a zero-terminated C argument.
    """
    var out = String()
    comptime digits = "0123456789abcdef"
    for c in s.codepoints():
        var n = Int(c.to_u32())
        if n >= 0x20 and n <= 0x7e and n != 0x5c:
            out += chr(n)
        else:
            out += "\\u{"
            var started = False
            for shift in range(28, -1, -4):
                var digit = (n >> shift) & 15
                if digit or started or shift == 0:
                    out += digits[byte=digit]
                    started = True
            out += "}"
    return out


def unescape_smt_string(literal: String) raises -> String:
    """Decode a quoted SMT-LIB string, including doubled quotes and NUL.

    Used for cvc5's lossless printed constants: its C UTF-32 getter has no
    length and cannot distinguish embedded zero code points from the end.
    Unexpected or invalid representations raise instead of losing data.
    """
    var data = literal.as_bytes()
    var end = len(data) - 1
    if end < 1 or data[0] != 34 or data[end] != 34:
        raise Error("cvc5_mojo: expected a quoted SMT-LIB string value")
    var out = List[UInt8]()
    var i = 1
    while i < end:
        var byte = data[i]
        i += 1
        if byte == 34:
            if i >= end or data[i] != 34:
                raise Error("cvc5_mojo: invalid quote in an SMT-LIB string value")
            i += 1
            out.append(byte)
        elif byte == 92:
            if i >= end or data[i] != 117:
                raise Error("cvc5_mojo: unexpected escape in an SMT-LIB string value")
            i += 1
            var braced = i < end and data[i] == 123
            if braced:
                i += 1
            var value = 0
            var count = 0
            while i < end and (data[i] != 125 if braced else count < 4):
                var digit = Int(data[i])
                if digit >= 48 and digit <= 57:
                    digit -= 48
                elif digit >= 97 and digit <= 102:
                    digit -= 87
                elif digit >= 65 and digit <= 70:
                    digit -= 55
                else:
                    raise Error("cvc5_mojo: invalid Unicode escape in an SMT-LIB string value")
                if count >= 6:
                    raise Error("cvc5_mojo: oversized Unicode escape in an SMT-LIB string value")
                value = value * 16 + digit
                count += 1
                i += 1
            if (braced and (count == 0 or i >= end or data[i] != 125)) or (not braced and count != 4):
                raise Error("cvc5_mojo: incomplete Unicode escape in an SMT-LIB string value")
            if braced:
                i += 1
            if value > 0x10ffff or (value >= 0xd800 and value <= 0xdfff):
                raise Error("cvc5_mojo: string value contains a non-Unicode code point")
            var encoded = chr(value)
            for b in encoded.as_bytes():
                out.append(b)
        else:
            out.append(byte)
    return String(from_utf8=Span(out))


def write_python_repr(mut writer: Some[Writer], s: String):
    """Write `s` as Python's `repr` writes a `str`.

    The quote is `'`, or `"` when `s` contains `'` and no `"`. Backslashes,
    the quote, control characters and the Latin-1 characters that Python
    does not print (U+0080 to U+00A0, U+00AD) are escaped. Other non-ASCII
    characters are written as they are, where Python also escapes the few
    that Unicode classifies as not printable.

    Args:
        writer: The writer.
        s: The string.
    """
    var quote = "'"
    if "'" in s and '"' not in s:
        quote = '"'
    writer.write(quote)
    for c in s.codepoints():
        var n = Int(c.to_u32())
        if n == ord("\\"):
            writer.write("\\\\")
        elif n == ord(quote):
            writer.write("\\", quote)
        elif n == ord("\t"):
            writer.write("\\t")
        elif n == ord("\n"):
            writer.write("\\n")
        elif n == ord("\r"):
            writer.write("\\r")
        elif n < 0x20 or (n >= 0x7F and n <= 0xA0) or n == 0xAD:
            comptime digits = "0123456789abcdef"
            writer.write("\\x", digits[byte=n >> 4], digits[byte=n & 15])
        else:
            writer.write(c)
    writer.write(quote)


struct OwnedIterator[T: Copyable & Deinitable](Iterator, Movable):
    """Iterates over a list it owns, moving each element out.

    The base API's `__iter__` methods read every element when the loop
    starts and return this iterator, so an element is never copied: a handle
    keeps the one cvc5 reference it was received with.
    """

    comptime Element = Self.T
    var _items: List[Self.T]

    def __init__(out self, var items: List[Self.T]):
        """Iterate over `items`, in order.

        Args:
            items: The elements.
        """
        items.reverse()
        self._items = items^

    def __next__(mut self) raises StopIteration -> Self.Element:
        """Return the next element.

        Returns:
            The element, moved out of the list.

        Raises:
            StopIteration: After the last element.
        """
        if not self._items:
            raise StopIteration()
        return self._items.pop()


@always_inline
def trace(function: StaticString):
    """Record a call of the C function `function`: in a build with
    `-D CVC5_MOJO_TRACE=<file>`, append its name to that file. Without the
    define this is empty and compiles away. Every generated raw method calls
    it; `pixi run cvc5-tests` uses it to report which C functions cvc5's
    translated tests and examples reach.

    Args:
        function: The C function's name.
    """
    comptime if is_defined[TRACE_DEFINE]():
        try:
            with open(get_defined_string[TRACE_DEFINE](), "a") as file:
                file.write(function, "\n")
        except:
            pass  # a trace must not change what the program does
