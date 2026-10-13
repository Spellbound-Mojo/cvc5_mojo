"""Generate src/cvc5_mojo/_c/raw.mojo, the raw layer, from the API snapshot.

The raw layer binds the C API one to one:

* one Mojo struct per C handle type (`Cvc5Term`) and per opaque C type
  (`Cvc5TermManager`, used through a pointer), each holding the pointer, so
  that passing a `Cvc5Sort` where cvc5 expects a `Cvc5Term` does not compile;
* one struct, `CApi`, that loads the libraries and resolves every C function
  once, and `c_api()`, which returns the process's one `CApi`, loaded on
  first use;
* one method per C function, named as in C, with parameter and result types
  from the compiler-checked signature. It unwraps its arguments, calls the
  resolved function, and raises when cvc5 records an error.

`OwnedDLHandle.get_function[R]` types only the result and infers the
arguments at each call site. The
generated methods are therefore the only call sites, and their types come
from the signatures. Storing a resolved function needs `std.ffi._DLCallable`,
a private type, with its origin rebound to `MutUntrackedOrigin`; the
callables never outlive the library handle stored next to them. Mojo 1.1 has
no global variables, so the process's `CApi` is kept with `std.ffi._get_global`,
also private: concurrent first uses may each load one, the runtime publishes
one and passes the others to `_unload`.

How each C type crosses is decided by `mojo_type()`. `check()` compiles a
static assertion for every C type the bound signatures use, so the C compiler
confirms sizes and signedness against the release's headers. A C `bool`
argument crosses as a `UInt8` holding 0 or 1, because Mojo passes `Bool` as
an LLVM `i1` without the zero extension the C ABI requires.

A struct whose layout callers see (`Cvc5OptionInfo`) is passed by pointer to
a Mojo struct of the same size and alignment, which reads each field at the
offset the C compiler measured (`c_types` in the snapshot, from
`bindgen.c_headers.layouts`). Mojo does not document a C-compatible layout
for its own structs, so the fields are not mirrored as Mojo fields. The C
enums such structs use (`Cvc5OptionInfoKind`) are emitted here, because
Python does not have them. Callback structs also have typed setters. Their
function pointers use `thin abi("C")`; callback signatures and state fields
are extracted from the headers and checked by the C compiler.

Usage: python -m bindgen.gen_raw   (reads api/cvc5-api.json)
"""

import json
import os

from . import c_headers, config, enums

ORIGIN = "MutUntrackedOrigin"

# C scalar types: Mojo type, size in bytes, and whether the C type is signed.
# None leaves the sign unchecked: for floating point, and for char and
# wchar_t, whose signedness C leaves to the platform (both are unsigned on
# Linux ARM64). Those two cross only behind pointers, as bytes and code
# points, which `check` enforces.
SIGN_BY_PLATFORM = ("char", "wchar_t")
SCALARS = {
    "char": ("Int8", 1, None),
    "int": ("Int32", 4, True),
    "int32_t": ("Int32", 4, True),
    "uint32_t": ("UInt32", 4, False),
    "int64_t": ("Int64", 8, True),
    "uint64_t": ("UInt64", 8, False),
    "size_t": ("UInt", 8, False),
    "double": ("Float64", 8, None),
    "wchar_t": ("Int32", 4, None),
    "char32_t": ("UInt32", 4, False),
}

# How a value crosses the call: what the resolved function is declared to
# return, how an argument is passed, and how a result is wrapped.
CALLABLE_RESULT = {"handle": "Ptr", "enum": "Int32", "bool": "UInt8", "void": "NoneType"}

# Mojo and Python keywords that C parameter names may not use.
RESERVED = {
    "and", "as", "assert", "async", "await", "break", "case", "class", "comptime", "continue", "def",
    "del", "deinit", "elif", "else", "except", "finally", "fn", "for", "from", "global", "if", "import",
    "in", "inout", "is", "lambda", "match", "mut", "nonlocal", "not", "or", "out", "owned", "pass",
    "raise", "raises", "read", "ref", "return", "self", "struct", "trait", "try", "type", "var", "while",
    "with", "yield",
}

# The error-state functions, which `_check` calls after every other method
# (bindgen.c_headers puts them in the "Error" section).
ERROR_FUNCTIONS = ("cvc5_has_error", "cvc5_get_error_message", "cvc5_reset_error")


class Unmapped(Exception):
    """A C type the raw layer does not represent; the function is hand-written."""


def _split(ctype):
    """`const Cvc5Term*` -> ("Cvc5Term", 1, True): base, pointer depth, and
    whether the outermost pointee is const."""
    tokens = ctype.replace("*", " * ").split()
    depth = tokens.count("*")
    before_last = tokens[: len(tokens) - 1 - tokens[::-1].index("*")] if depth else []
    pointee_const = bool(before_last) and (before_last[-1] == "const" or (depth == 1 and "const" in before_last))
    return " ".join(t for t in tokens if t not in ("*", "const")), depth, pointee_const


def _pointer(mojo, depth, param, pointee_const):
    """A pointer type `depth` levels deep. A parameter's outermost pointer
    keeps the caller's origin (`_`), so the memory it points to stays alive
    through the call, and must be mutable unless C declares the pointee const."""
    for level in range(depth):
        if param and level == depth - 1:
            return f"Pointer[{'' if pointee_const else 'mut=True, '}{mojo}, _]"
        mojo = f"Pointer[{mojo}, {ORIGIN}]"
    return mojo


def mojo_type(ctype, c_types, param=False):
    """Return (Mojo type, crossing) for a C type spelling.

    The crossing is "handle" (a struct around the pointer), "enum" (the
    generated enum, an `Int32`), "bool", "void" or "plain" (passed as is).
    Raises Unmapped for types the raw layer does not represent.
    """
    base, depth, pointee_const = _split(ctype)
    info = c_types.get(base)
    if info is not None:
        kind = info["kind"]
        if kind == "struct":
            if depth == 0:
                raise Unmapped(f"passes the struct `{base}` by value")
            return _pointer(base, depth, param, pointee_const), "plain"
        if kind == "opaque":
            if depth == 0:
                raise Unmapped(f"passes the opaque `{base}` by value")
            depth -= 1  # the Mojo struct stands for the pointer
        name = info.get("enum", base)
        if depth:
            return _pointer(name, depth, param, pointee_const), "plain"
        return name, "enum" if kind in ("enum", "c_enum") else "handle"
    if base == "bool":
        if depth:
            raise Unmapped("uses a pointer to bool")
        return "Bool", "bool"
    if base == "void":
        return (_pointer("NoneType", depth, param, pointee_const), "plain") if depth else ("NoneType", "void")
    if base in SCALARS:
        return _pointer(SCALARS[base][0], depth, param, pointee_const), "plain"
    raise Unmapped(f"uses the unknown C type `{ctype}`")


def _identifier(name, index):
    if not name:
        return f"arg{index}"
    return name + "_" if name in RESERVED else name


def classify(snap):
    """Return ({C function: binding}, {C function: reason it is hand-written})."""
    bound, excluded = {}, {}
    for name, f in snap["c_functions"].items():
        try:
            params = [(_identifier(p["name"], i), *( (callback_type(p, snap["c_types"]), "callback")
                       if p.get("callback") else mojo_type(p["type"], snap["c_types"], param=True)))
                      for i, p in enumerate(f["params"])]
            returns = mojo_type(f["returns"], snap["c_types"])
        except Unmapped as e:
            excluded[name] = str(e)
            continue
        bound[name] = {
            "library": f["library"],
            "params": params,
            "returns": returns,
            "checks": f["section"] != "Error",
            "deprecated": f.get("deprecated"),
        }
    return bound, excluded


def check(snap, bound):
    """Compile a static assertion per C type the bound signatures use."""
    used = set()
    for name in bound:
        f = snap["c_functions"][name]
        for base, depth, _ in map(_split, [f["returns"]] + [p["type"] for p in f["params"]]):
            if base in SIGN_BY_PLATFORM and depth == 0:
                raise ValueError(f"{name} passes {base} by value; its sign differs between platforms")
            used.add(base)
    lines = []
    for base in sorted(used):
        kind = snap["c_types"].get(base, {}).get("kind")
        if kind == "handle":
            lines.append(f'_Static_assert(sizeof({base}) == sizeof(void*), "{base} is one pointer");')
        elif kind == "enum":
            lines.append(f'_Static_assert(sizeof({base}) == 4, "{base} crosses as an Int32");')
        elif kind == "struct":
            info = snap["c_types"][base]
            lines.append(f'_Static_assert(sizeof(struct {base}) == {info["size"]} && _Alignof(struct {base}) == '
                         f'{info["align"]}, "{base} is mirrored by its size and alignment");')
        elif base == "bool":
            lines.append('_Static_assert(sizeof(bool) == 1, "bool crosses as a UInt8");')
        elif base in SCALARS:
            mojo, size, signed = SCALARS[base]
            sign = "" if signed is None else f" && ({base})-1 {'<' if signed else '>'} 0"
            lines.append(f'_Static_assert(sizeof({base}) == {size}{sign}, "{base} crosses as {mojo}");')
    c_headers.compile_check(lines, "Raw-layer type mapping check")
    return len(lines)


STORAGE = {1: "UInt8", 2: "UInt16", 4: "UInt32", 8: "UInt64"}


def _c_enum(name, info):
    """A C enum that only struct fields use, its members without the common prefix."""
    prefix = os.path.commonprefix(list(info["values"]))
    prefix = prefix[: prefix.rfind("_") + 1]
    entries = [(n.removeprefix(prefix), v) for n, v in info["values"].items()]
    return enums.emit_enum(name, entries, f"The C enum `{name}`, read from struct fields; Python does not have it.")


def callback_type(field, c_types):
    """A thin C function pointer; value handles cross as their native pointer."""
    def abi(ctype):
        mojo, crossing = mojo_type(ctype, c_types)
        return {"handle": "Ptr", "enum": "Int32", "bool": "UInt8"}.get(crossing, mojo)
    return "def(" + ", ".join(abi(p["type"]) for p in field["params"]) + ') thin abi("C") -> ' + abi(field["returns"])


def _layout_struct(name, info, c_types):
    """A struct of the measured size and alignment, with a reader per field.

    A reader is named after the field (`info_int.max` -> `info_int_max`) and
    reads it at its measured offset; its size must be the size of its Mojo
    type, and its offset a multiple of it.
    """
    size, align = info["size"], info["align"]
    storage = f"Array[{STORAGE[align]}, {size // align}]"
    out = ["", "", f"struct {name}(Movable):",
           f'    """A `{name}`: {size} bytes, aligned to {align}, as the C compiler measured.',
           "",
           "    cvc5 fills it through a pointer; each method reads one field at its",
           "    measured offset.",
           '    """', "", f"    var _storage: {storage}", "",
           "    def __init__(out self):",
           '        """A zeroed struct for cvc5 to fill."""',
           f'        comptime assert size_of[Self]() == {size} and align_of[Self]() == {align}, "{name} layout"',
           f"        self._storage = {storage}(fill=0)", "",
           "    def _read[T: ImplicitlyCopyable](self, offset: Int) -> T:",
           "        return Pointer(to=self._storage).unsafe_bitcast[T]()[unsafe_offset=offset // size_of[T]()]"]
    for f in info["fields"]:
        mojo, crossing = ((callback_type(f, c_types), "callback") if f.get("callback")
                          else mojo_type(f["type"], c_types))
        read = {"bool": "UInt8", "enum": "Int32"}.get(crossing, mojo)
        expected = {"bool": 1, "enum": 4, "callback": 8}.get(crossing) or (8 if mojo.startswith("Pointer[") else SCALARS[_split(f["type"])[0]][1])
        if f["size"] != expected or f["offset"] % expected:
            raise SystemExit(f"{name}.{f['name']}: {f['size']} bytes at offset {f['offset']} do not read as {mojo}")
        out.append("")
        if f["deprecated"]:
            out.append(f"    @deprecated({json.dumps(f['deprecated'])})")
        value = f"self._read[{read}]({f['offset']})"
        out += [f"    def {_identifier(f['name'].replace('.', '_'), 0)}(self) -> {mojo}:",
                f"        return {_result(value, mojo, crossing)}"]
        if any(field.get("callback") for field in info["fields"]):
            out += ["", f"    def set_{f['name']}(mut self, value: {mojo}):",
                    f'        comptime assert size_of[{mojo}]() == {f["size"]}, "{name}.{f["name"]} ABI"',
                    f"        Pointer(to=self._storage).unsafe_bitcast[{mojo}]()[unsafe_offset={f['offset']} // size_of[{mojo}]()] = value"]
    return out


def _argument(name, mojo, crossing):
    if crossing == "handle":
        return f"{name}.ptr"
    if crossing == "enum":
        return f"{name}.value"
    if crossing == "bool":
        return f"UInt8(1) if {name} else UInt8(0)"
    return name


def _result(local, mojo, crossing):
    if crossing in ("handle", "enum"):
        return f"{mojo}({local})"
    if crossing == "bool":
        return f"{local} != 0"
    return local


def _callable(mojo, crossing):
    return f"_DLCallable[{CALLABLE_RESULT.get(crossing, mojo)}, {ORIGIN}]"


def _method(name, b):
    mojo, crossing = b["returns"]
    params = "".join(f", {p}: {m}" for p, m, _ in b["params"])
    signature = f"    def {name}(self{params})" + (" raises" if b["checks"] else "")
    signature += "" if crossing == "void" else f" -> {mojo}"
    call = f"self._{name}(" + ", ".join(_argument(*p) for p in b["params"]) + ")"
    local = "result"
    while local in {p for p, _, _ in b["params"]}:  # cvc5_result_* take a `result`
        local += "_"
    out = []
    if b["deprecated"] is not None:
        out.append(f"    @deprecated({json.dumps(b['deprecated'])})")
    out.append(signature + ":")
    out.append(f'        trace("{name}")')  # nothing unless built with -D CVC5_MOJO_TRACE
    if crossing == "void":
        out.append(f"        {call}")
    else:
        out.append(f"        var {local} = {call}")
    if b["checks"]:
        out.append("        self._check()")
    if crossing != "void":
        out.append(f"        return {_result(local, mojo, crossing)}")
    return out


# The process's CApi: Mojo 1.1 has no global variables, only the runtime
# globals of `std.ffi._get_global`, keyed by name.
PROCESS_API = """

comptime CApiPtr = Pointer[CApi, MutUntrackedOrigin]
\"\"\"A pointer to the process's `CApi`, which lives until the process exits.\"\"\"


struct _Loaded(Movable):
    \"\"\"The process's C API, or why loading it failed.\"\"\"

    var api: Optional[CApi]
    var error: String

    def __init__(out self):
        try:
            self.api = CApi()
            self.error = String()
        except e:
            self.api = None
            self.error = String(e)


def _load() -> Optional[Ptr]:
    return rebind[Ptr](OwnedPointer(_Loaded()).unsafe_take_allocation().unsafe_leak())


def _unload(loaded: Optional[Ptr]):
    if loaded:
        _ = OwnedPointer[_Loaded](unsafe_from_opaque_pointer=loaded.value())


def c_api() raises -> CApiPtr:
    \"\"\"The C API of this process, loaded on first use.

    Concurrent first uses may each load it; one is kept and the others are
    unloaded. A failure to load is kept too, and raised on every use.
    \"\"\"
    var loaded = rebind[Pointer[_Loaded, MutUntrackedOrigin]](_get_global["{key}", _load, _unload]().value())
    if not loaded[].api:
        raise Error(loaded[].error)
    return Pointer(to=loaded[].api.value()).unsafe_origin_cast[MutUntrackedOrigin]()"""


def version_probe(snap, bound):
    """Bootstrap only opaque owners, then validate before exposing the C API."""
    cls, method = snap["runtime"]["version_method"].split(".")
    getters = snap["python"][cls]["methods"][method]["binding"].get("c", [])
    if len(getters) != 1:
        raise SystemExit("runtime version method must bind exactly one C function")
    getter = getters[0]
    cf = snap["c_functions"]
    owner = snap["python"][cls]["section"]
    new, delete = c_headers.owner_lifecycle(cf, owner)
    params = cf[new]["params"]
    if len(params) != 1 or not params[0]["type"].endswith("*"):
        raise SystemExit("runtime version owner's constructor no longer takes one opaque owner")
    parent = params[0]["type"][:-1]
    parent_new, parent_delete = c_headers.owner_lifecycle(cf, parent)
    if (cf[parent_new]["params"] or cf[getter]["returns"] != "const char*"
            or [p["type"] for p in cf[getter]["params"]] != [owner + "*"]):
        raise SystemExit("runtime version bootstrap signatures changed")
    if any(name not in bound for name in (getter, new, delete, parent_new, parent_delete)):
        raise SystemExit("runtime version bootstrap requires an unbound C function")
    expected = snap["cvc5"]["version"]
    library = cf[getter]["library"]
    return ["", "    def _verify_version(self) raises:",
            '        """Check the pinned release and release both bootstrap owners on failure."""',
            f"        var parent = self.{parent_new}()",
            f"        var owner = {owner}(null[NoneType]())",
            "        var actual = String()", "        var failure = String()",
            "        try:", f"            owner = self.{new}(parent)",
            f"            actual = to_string(self.{getter}(owner))",
            "        except e:", "            failure = String(e)",
            "        if not is_null(owner.ptr):", f"            self.{delete}(owner)",
            f"        self.{parent_delete}(parent)",
            "        if failure:", "            raise Error(failure)",
            f'        if actual != "{expected}":',
            f'            raise Error("cvc5_mojo: expected cvc5 {expected}, loaded " + actual + " from " + library_path("{library}"))']


def emit_mojo(snap, bound, excluded):
    version = snap["cvc5"]["version"]
    c_types = snap["c_types"]
    enums = [info["enum"] for info in c_types.values() if info["kind"] == "enum"]
    out = [
        f"# Generated by bindgen.gen_raw from the cvc5 {version} API snapshot. Do not edit.",
        "# Regenerate with `pixi run --locked generate`.",
        f'"""The cvc5 {version} C API, bound one to one; see bindgen/gen_raw.py.',
        "",
        "Every function is resolved once per process, when `c_api()` first loads the",
        "libraries. Each method takes and returns typed handles and raises",
        "`Error(\"cvc5: ...\")` when cvc5 records an error.",
        '"""',
        "",
        "from std.ffi import OwnedDLHandle, _DLCallable, _get_global",
    ] + (["from std.hashlib import Hasher"] if any(i["kind"] == "c_enum" for i in c_types.values()) else []) + [
        "from std.memory import OwnedPointer",
        "from std.sys import align_of, size_of",
        "",
        "from .ffi import Ptr, library_path, to_string, trace, null, is_null",
        "from ..enums import " + ", ".join(enums),
    ]
    for c_name, info in c_types.items():
        if info["kind"] not in ("handle", "opaque"):
            continue
        what = "a handle" if info["kind"] == "handle" else "a pointer to an opaque object"
        out += ["", "", "@fieldwise_init", f"struct {c_name}(ImplicitlyCopyable, Movable):",
                f'    """A `{c_name}{"" if info["kind"] == "handle" else "*"}`: {what} of the cvc5 C API."""',
                "", "    var ptr: Ptr"]
    for c_name, info in c_types.items():
        if info["kind"] == "c_enum":
            out += ["", ""] + _c_enum(c_name, info)
    for c_name, info in c_types.items():
        if info["kind"] == "struct":
            out += _layout_struct(c_name, info, c_types)
    libraries = {lib: "_" + lib for lib in sorted({b["library"] for b in bound.values()})}
    out += ["", "", "struct CApi(Movable):",
            '    """The loaded cvc5 libraries, with every bound C function resolved.',
            "",
            "    `c_api()` returns the process's instance.",
            '    """', ""]
    out += [f"    var {field}: OwnedDLHandle" for field in libraries.values()]
    out += [f"    var _{name}: {_callable(*b['returns'])}" for name, b in bound.items()]
    out += ["", "    def __init__(out self) raises:",
            '        """Load the libraries and resolve every bound function from its own."""']
    out += [f'        self.{field} = OwnedDLHandle(library_path("{lib}"))' for lib, field in libraries.items()]
    for name, b in bound.items():
        t = _callable(*b["returns"])
        result = t.removeprefix("_DLCallable[").rsplit(",", 1)[0]
        out.append(f'        self._{name} = rebind[{t}](self.{libraries[b["library"]]}.get_function[{result}]("{name}"))')
    out.append("        self._verify_version()")
    out += version_probe(snap, bound)
    out += ["", "    def _check(self) raises:",
            '        """Raise the error the last call on this thread recorded, and clear it."""',
            "        if self._cvc5_has_error() != 0:",
            '            var message = String("invalid UTF-8 in cvc5 error message")',
            "            try:",
            "                message = to_string(self._cvc5_get_error_message())",
            "            except:",
            "                pass  # Even malformed native diagnostics must clear the error state.",
            "            self._cvc5_reset_error()",
            '            raise Error("cvc5: " + message)']
    for name, b in bound.items():
        out += [""] + _method(name, b)
    out += PROCESS_API.format(key=f"cvc5_mojo.CApi.{version}").splitlines()
    if excluded:
        out += ["", "", "# Hand-written, not bound here:"]
        out += [f"# - {name}: {reason}" for name, reason in excluded.items()]
    return "\n".join(out) + "\n"


def main():
    from . import generation_policy
    snap = json.loads(config.SNAPSHOT_FILE.read_text(encoding="utf-8"))
    bound, excluded = classify(snap)
    generation_policy.check(excluded, snap["generation"]["unbound_c"], "raw C API")
    errors = sorted(n for n, f in snap["c_functions"].items() if f["section"] == "Error")
    if errors != sorted(ERROR_FUNCTIONS) or not all(n in bound for n in errors):
        raise SystemExit(f"the C API's error-state functions changed: {errors}; update gen_raw's `_check`")
    asserted = check(snap, bound)
    config.RAW_FILE.write_text(emit_mojo(snap, bound, excluded), encoding="utf-8")
    print(f"wrote {config.RAW_FILE.relative_to(config.ROOT)}: {len(bound)} of {len(snap['c_functions'])} "
          f"C functions; {asserted} C types checked by the C compiler")
    for name, reason in excluded.items():
        print(f"  hand-written: {name} {reason}")


if __name__ == "__main__":
    main()
