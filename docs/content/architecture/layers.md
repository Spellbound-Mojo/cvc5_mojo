# Generated layers

The generator turns the [snapshot](inputs.md#the-snapshot), the committed
file `api/cvc5-api.json` of facts extracted from the pinned cvc5 release, into
three parts of the Mojo package:

- the [enums](#enums), one struct per cvc5 enum;
- the [raw layer](#raw-layer), an internal one-to-one binding of cvc5's C
  API;
- the [base API](#base-api), the public classes, which follow cvc5's Python
  API and call the raw layer.

## Enums

`src/cvc5_mojo/enums.mojo` is generated. Each cvc5 enum is a Mojo struct that
holds an `Int32`. The struct has one `comptime` member per entry, named as
in Python, which is the C name without its prefix: `Kind.ADD` is C's
`CVC5_KIND_ADD`. `Kind.ADD` is `Kind(20)`, just as `cvc5.Kind.ADD.value` is
20 in Python.

Enums print as Python's enums do. `print(Kind.ADD)` writes `Kind.ADD`, and
`repr(Kind.ADD)` is `<Kind.ADD: 20>`. The text comes from a table of the
member names. Enums also hash, so they can be dictionary keys. The
[enum reference](../reference/enums.md) lists all values.

## Raw layer

The raw layer, `src/cvc5_mojo/_c/raw.mojo`, binds the C API one to one.
`bindgen.gen_raw` generates it from the `c_functions` and `c_types` entries of
the snapshot. The file is internal: the base API calls it, and user code does
not.

### Calling C functions

**Resolved once.** The process has one `CApi`, which the generated function
`c_api()` creates on first use. The `CApi` loads each library that exports C
API functions: `libcvc5.so`, and `libcvc5parser.so` for the parser. It
resolves every function from the library that exports it. A missing symbol
therefore raises when the `CApi` is created, not at the first call. The
snapshot records which library exports each function, as found by the dynamic
linker (`bindgen.c_library`). See [runtime](runtime.md#loading-the-library)
for how the libraries are loaded.

**Types are generated, not inferred.** `get_function[R](name)` types only
the result, and the argument types
are inferred at each call site. A wrong argument type would therefore compile,
and then corrupt memory at run time. To prevent this, `CApi` stores each
resolved function as a private `_DLCallable` and exposes one method per C
function, named as in C. The parameter and result types of each method come
from the compiler-checked signature. These methods are the only call sites
of the resolved functions.

**Distinct types.** Every C handle type (`Cvc5Term`, `Cvc5Sort`, …) is its own
Mojo struct around the pointer. So is every opaque owner type (`Cvc5`,
`Cvc5TermManager`, …). Enums are the generated enum structs. As a result, none
of these mistakes compiles: passing a `Cvc5Sort` where cvc5 expects a
`Cvc5Term`, a solver where it expects a term manager, or a `SortKind` where it
expects a `Kind`.

**Errors.** Every method checks `cvc5_has_error()` after its C call. If cvc5
reports an error, the method raises `Error("cvc5: " + message)`. The methods
of the three [error-state functions](c-api.md#errors) are the only
exceptions.

**Tracing.** Every method first calls `ffi.trace` with its C name. When a
program is built with `-D CVC5_MOJO_TRACE=<file>`, this call appends the name
to the file. Without the define, `ffi.trace` is empty and compiles away. This
also holds for the precompiled package, because the define is read when the
program is built. `pixi run --locked cvc5-tests` uses tracing for the
[coverage report](../reference/coverage.md#c-functions-the-tests-reach).

### C types in Mojo

The raw layer maps C types to Mojo types as follows. `T'` stands for the
Mojo type of the C type `T`. A type that "crosses as" another passes
between Mojo and C as that other type.

| C | Mojo |
|---|---|
| handle typedefs (`Cvc5Term`, …) | the struct of the same name, holding the pointer |
| pointers to opaque structs (`Cvc5*`, `Cvc5TermManager*`, …) | the struct named after the C struct (`Cvc5`, `Cvc5TermManager`) |
| enums (`Cvc5Kind`, …) | the generated enum (`Kind`, …), which crosses as its `Int32` |
| `bool` | `Bool`, which crosses as a `UInt8` holding 0 or 1 |
| `char`, `int`, `int32_t`, `uint32_t`, `int64_t`, `uint64_t`, `size_t`, and `double` | `Int8`, `Int32`, `Int32`, `UInt32`, `Int64`, `UInt64`, `UInt`, and `Float64`, respectively |
| `wchar_t` and `char32_t` (through pointers) | `Int32` and `UInt32`, respectively |
| `T*` parameter | `Pointer[T', _]`, with `mut=True` unless C declares the pointee `const` |
| `T*` result | `Pointer[T', MutUntrackedOrigin]` |
| a pointer to a struct whose layout callers see (`Cvc5OptionInfo*`) | `Pointer[T', _]` to a Mojo struct of the measured size and alignment, with one reader per field (`info_int_max()`) at its measured offset |
| C enums that only struct fields use (`Cvc5OptionInfoKind`) | an enum struct in the raw layer, its members without the common prefix (`Cvc5OptionInfoKind.INT64`) |
| callback structs (`Cvc5Plugin`) | measured storage with typed readers and setters; function pointers use `thin abi("C")` and signatures extracted from the headers |
| direct oracle function callbacks | ABI-checked thin C function pointers; a shared callback registry retains high-level `Oracle` instances |

Three crossings need care:

- **`bool` arguments.** Mojo passes a `Bool` to C as an LLVM `i1`, without
  the zero extension that the C ABI requires. A C `bool` therefore crosses as
  a `UInt8` that is exactly 0 or 1. Results are read as a `UInt8` and
  compared with 0.
- **Pointer parameters keep the caller's origin.** `Pointer[T, _]` accepts
  `List.unsafe_ptr()` with its origin, so Mojo keeps the list alive until the
  call returns. Pointers stored *inside* an array, such as a string array,
  are untracked. The caller keeps their buffers alive.
- **Out-parameters must be mutable.** cvc5 writes through a pointer parameter
  whose pointee is not `const`. A read-only pointer does not compile in that
  position.

**Struct layouts are measured.** Mojo does not document a C-compatible layout
for its structs, so the fields of `Cvc5OptionInfo` are not mirrored as Mojo
fields. Instead, `bindgen.c_headers.layouts` parses the fields from the
header. A compiled C program then checks each parsed type and prints every
offset and size. The raw layer's struct has the measured size and alignment,
which a `comptime assert` checks, and reads each field at its offset. The
generator refuses a field whose size is not the size of its Mojo type.

**Checks.** For every C type that the bound signatures use, `bindgen.gen_raw`
compiles a static assertion of its size and, where it matters, its
signedness. `tests/smoke/test_raw.mojo` calls at least one method per
crossing and direction, and checks that the values arrive. The
[coverage report](../reference/coverage.md#raw-layer) lists the functions
that the raw layer does not bind.

## Base API

The base API is the package's public API, which mirrors cvc5's Python base
API. `bindgen.gen_api` generates it from the `python` entry of the snapshot.
It writes one module per Python class (`src/cvc5_mojo/term_manager.mojo`, …)
and the package's `__init__.mojo`. Classes, methods, and parameters have
cvc5's Python names. Every docstring is cvc5's, converted by
`bindgen.docstrings`.

The snapshot gives each Python method a
[binding](join.md#binding-statuses): a status, such as `auto` or `manual`,
and the C functions that implement the method. A generated method has one
Mojo overload per C function of its binding. Each overload is built
parameter by parameter from the C signature.

The [coverage report](../reference/coverage.md#base-api) lists the methods
that are not generated yet, with the reason. The
[API reference](../reference/index.md) shows every generated signature.

### Classes

The base API has two kinds of class, which differ in what an object holds
and in how copies behave.

**Handle classes** (`Term`, `Sort`, `Result`, `Op`, the datatype classes, …)
wrap a C handle. An object holds the pointer to the `CApi`, the pointer of
its term manager, and one cvc5 reference. Copying is implicit, as Python shares
objects, and calls `{prefix}copy`. Destroying calls `{prefix}release`. Here
`{prefix}` is the class's C function prefix, such as `cvc5_term_` for `Term`.

Like Python's wrappers, a handle object remembers its term manager, which
`Term.notTerm` and its siblings need. cvc5 keeps a term manager alive while
objects it made exist. A returned handle is received by its type's
[ownership mode](runtime.md#handle-ownership): the object either wraps the
returned reference (`own`) or adopts it while retaining its solver (`anchor`).

Handles may be NULL. A parser returns a null `Command` at the end of its
input, so copying and releasing skip NULL, and `isNull()` tests for it. A
no-argument constructor makes a null object, as Python's `Sort()` does. For a
null object, `isNull()` is true, and `==` compares as the C API defines. Null
objects hash alike, because they are equal. Their other methods raise.
Printing a null object uses the text extracted from Python's null formatter,
or `Class(null)` if that formatter fails. It does not pass a null handle to
the native formatter. Ordering a null object still aborts when the native
comparison rejects it, because the comparison trait cannot raise.

**Pointer-owned classes** (`TermManager`, `Solver`, `SymbolManager`, and
`InputParser`) hold a pointer to a cvc5 object. Each is created by its C
`_new` function, with the Python constructor's parameter names. Copies share
the object, which is deleted with its last copy. An object that such a class
*returns*, such as `Solver.getTermManager()`, is borrowed: it is not deleted,
and it keeps the object that returned it alive.

### Marshaling rules

The generator builds each method from its C signature with these rules. `T'`
is the Mojo type of the C type `T`, as in the
[raw layer's table](#c-types-in-mojo).

| C | Mojo |
|---|---|
| the first parameter | the receiver |
| handle | the generated class |
| enum | the generated enum |
| `bool` | `Bool`. A Python `None` default requires an explicit policy or a manual binding; it is not silently coerced. |
| `int32_t`, `uint32_t`, `int64_t`, and `size_t` | `Int`, range-checked into the C type. A value out of range raises an error that names it. |
| `uint64_t` and `double` | `UInt64` and `Float64`, respectively |
| `const char*` | `String`, or `Optional[String] = None` where Python's default is `None` and the C parameter accepts NULL. A parameter accepts NULL when cvc5 documents it as "may be NULL", or when its implementation tests it (`c_impl.null_tested`). |
| `size_t n` followed by const arrays | one `List` per array. Their lengths must agree. |
| a Python `*args` mapped to the last list | also a variadic overload, because Mojo cannot pass a `List` as `*args` |
| `size_t sizes[]` and `const T* arrays[]` inside such a group | one `List[List[T']]`, from which the inner lengths and pointers are built for C |
| a returned array with its `size_t*` count, or with the length of the input list | a `List`, whose handles are received by their ownership mode |
| a count and two out-arrays, where the C++ method returns a `map[K, V]` | a `Dict[K, V]` in cvc5's order, whose handles are received by their ownership mode |
| a size and two const arrays, where the C++ method takes a `map[K, V]` | one `Dict[K, V]` parameter. Python's default `{}` becomes an empty `Dict`. |
| other out-parameters | returned with the result in a `Tuple`, in C order, with the C result last |
| `const char** error_msg` out-parameter | raises `Error("cvc5: " + message)` when cvc5 sets it |
| `const char32_t*` result | requires a manual length-preserving conversion; the zero-terminated C getter alone cannot preserve embedded NUL |
| a `const char*` result that Python returns as an `int` or a `Fraction` (`return int(....decode())`) | apn_mojo's `Integer` or `Rational`, parsed from cvc5's decimal text |
| a method with `kind` in `overrides.toml` (`Term.notTerm`, …) | `cvc5_mk_term` of that kind, with the receiver and the method's `Term` arguments |
| `__iter__` with a count function and a get-by-index function | an `OwnedIterator` that moves out every element. The elements are read when the loop starts, and each is received by its ownership mode. |

Input arrays reserve their known element count before conversion. Nested rows
reuse the flat converter; string and nested pointer arrays keep their backing
storage alive through the native call. See [collection input buffers](collection-inputs.md).
Returned lists and dictionaries reserve known native counts. Counted iterators
share the list builder, and string arrays use `to_strings` for owned copies;
see [returned collections](returned-collections.md).

Python's special methods (dunders) map to Mojo traits:

| Python | Mojo trait |
|---|---|
| `__eq__` and `__ne__` | `Equatable` |
| the comparisons | `Comparable` |
| `__hash__` | `Hashable` |
| `__str__` or `__repr__` | `Writable`, plus explicit single-pass `toString()` |

Mojo requires the trait methods to be non-raising, as it does destructors and
copy constructors. They abort if cvc5 reports an error, which cvc5 does
not do for valid handles. The other mirrored methods raise.

For an owned formatted string, use `value.toString()`. The eleven generated
helpers share `Writable`'s null text and non-raising error behavior;
`write_to` delegates to that same conversion. `Command` already has a
mirrored, raising `toString()` method, whose contract is preserved.
Mojo 1.1's `String(value)` still invokes `write_to` twice; see
[single-pass formatting](single-pass-formatting.md) for behavior and measurements.

Python returns a dict where the C++ method returns a `std::map`, and takes a
dict where the C++ method takes a map. `cvc5.pxd` declares these maps, and
`bindgen.cpp_api` extracts them, so the rule needs no list of methods. For
example, it gives:

- `Solver.getDifficulty() -> Dict[Term, Term]`;
- `SymbolManager.getNamedTerms() -> Dict[Term, String]`;
- `Solver.proofToString(proof, format, assertionNames: Dict[Term, String])`.

`Term` keys work because `Term` is `Hashable`. The generator checks the map's
key and value types against the C arrays.

Python selects an overload by checking argument types at run time. For
example, `mkInteger(val)` calls `cvc5_mk_integer` for a `str` and
`cvc5_mk_integer_int64` for an `int`. Mojo resolves overloads statically, so
the bindings have `mkInteger(val: String)` and `mkInteger(val: Int)`.

An overload's parameter takes the name of the Python parameter that Python
passes as that argument of the C++ call (`cpp_args`, extracted by
`bindgen.python_api`). If Python passes none, the parameter takes the name of
the Python parameter at its position. For example, in the term form of `defineFunRec`,
Python passes `glbl` and ignores `t`, so the flag is named `glbl`. A Python
name that names alternatives, such as `kind_or_op`, gives way to the C names
(`kind` and `op`).

### Hand-written methods

A method whose binding status is `manual` is written by hand in Mojo. Its code
is a fragment in `bindgen/manual/<Class>.mojo`, which is spliced into the
generated class with cvc5's docstring. See
[writing a manual method](../contributing/generator.md#writing-a-manual-method).
The coverage report counts these methods among the generated ones.

**Statistics.** Python returns a statistic as a dict with the keys
`default`, `internal`, and `value`. The entry under `value` is an int, a
float, a string, or a histogram. Mojo cannot type such a dict, so a statistic
is a `Stat` with those three fields. Its `value` field is a
`Variant[Int, Float64, String, Dict[String, UInt64]]`. The table compares the
two APIs:

| Python | Mojo |
|---|---|
| `stats.get(internal=False, defaulted=False)`, a `dict` | `stats.get(...)`, a `Dict[String, Stat]` |
| `stats["name"]`, a `dict` | `stats["name"]`, a `Stat` |
| `stats["name"]["value"]` | `stats["name"].value[Int]` (or `Float64`, `String`, or `Dict[String, UInt64]`) |
| `for name, info in stats:` | `for name, stat in stats:` |
| `print(stats["name"])` | `print(stats["name"])`, which prints the same text |

A `Stat` prints as Python prints the dict. Strings are quoted and escaped as
Python's `repr` does, and a float has the same shortest form. For the 505
statistics of a small problem, the printed lines matched those of the official
Python bindings, except for timings. Python escapes a few non-ASCII characters
beyond Latin-1 that Unicode classifies as not printable. A `Stat` writes those
characters as they are. A whole `Dict[String, Stat]` prints in Mojo's `Dict`
format, which does not quote keys.

A `Stat` is a value. Its cvc5 handle is read and released when the statistic
is returned. Iteration reads every statistic when the loop starts, because
the C API keeps a single iterator in the statistics object.
`get` reserves dictionary capacity from the snapshot length before copying
its independent values; see [statistics snapshots](statistics-snapshots.md).

**Options.** `Solver.getOptionInfo` is hand-written too. Python returns a
dict whose keys depend on the option's value type. An `OptionInfo` has every
key as a field. Where Python leaves a key out, the field is `None`, or an
empty list for `modes`.

| Field | Type | Python |
|---|---|---|
| `name`, `aliases`, `setByUser`, and `category` | `String`, `List[String]`, `Bool`, and `OptionCategory`, respectively | the same keys |
| `type` | `Optional[String]`: `"bool"`, `"str"`, `"int"`, `"float"`, or `"mode"` | `bool`, `str`, `int`, `float` (the classes), `'mode'`, or `None` |
| `current`, `default`, `minimum`, and `maximum` | `Optional[OptionInfo.Value]`, a `Variant[Bool, String, Int, UInt64, Float64]` | the values. `minimum` and `maximum` appear only for numbers. |
| `modes` | `List[String]` | only for modes |

Python's `int` is `Int` for int64 options and `UInt64` for uint64 options.
For example, `bv-abstraction-size` has the maximum 2^64−1. An `OptionInfo`
prints as Python prints the dict. For all 535 options of cvc5 1.4.1, the
printed lines are identical to those of the official Python bindings.

**Big numbers.** A fragment can also add overloads to a generated method.
Python takes some inputs as an `int` of any size or as a `Fraction`.
`bindgen/manual/TermManager.mojo` adds overloads for these inputs:

- `mkInteger(Integer)`;
- `mkReal(Rational)` and `mkReal(Integer, Integer)`;
- `mkFiniteFieldSort(Integer)` and `mkFiniteFieldElem(Integer, Sort)`;
- `mkBitVector(Int, Integer)`, and Python's zero form `mkBitVector(Int)`.

Fitting integer, rational, and nonnegative bit-vector values use
[direct numeric conversion](numeric-conversions.md). Wider values and finite
fields retain exact decimal text. `Term.getIntegerValue` and `getRealValue`
also use native scalar getters when representable and parse decimal text
otherwise; their APN return types are unchanged.

Python's `mkReal` formats a numerator and a denominator alike, so each may
also be a `String`. A `float` passes its shortest text, which Mojo's
`Float64` writes too, so `mkReal(0.3)` is exactly 3/10.

The fragment also has Python's other argument forms:
`mkFunctionSort(Sort, Sort)` with a single domain sort, and
`mkRecordSort(*fields)` with `(name, sort)` pairs.

Mojo converts an integer literal that does not fit an `Int` to an `Int`
without a diagnostic. For this reason, `mkInteger` and `mkReal` also take an
`IntLiteral`, which is kept exact. Both test the exact literal's range
and delegates to the typed `Int` constructor when it fits, retaining the
arbitrary-precision path otherwise; see [integer literals](integer-literals.md).
`overrides.toml` gives private generated helper names to the int64
`mkReal(Int, Int)` and uint64 `mkBitVector(Int, UInt64)` overloads that a
literal would otherwise reach publicly. Exact APN overloads call those
helpers only after validating the value.

### Callbacks

`Solver.addPlugin` registers a retained implementation of the `Plugin`
trait. `Solver.declareOracleFun` registers an `Oracle` implementation as a
C-only extension. Both use the shared callback registry and error guards;
see the [plugin](../reference/plugin.md) and
[oracle](../reference/oracles.md) tutorials for their contracts.
