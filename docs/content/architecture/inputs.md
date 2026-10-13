# Inputs and extraction

Every input comes from the cvc5 release pinned in `cvc5-version.toml`.
`pixi run --locked fetch` downloads the pinned archives of that release into
`third_party/`, which git ignores, and checks their sha256:

- **The official shared-library builds** provide the headers and native
  libraries for Linux x86-64, Linux ARM64, and macOS Apple Silicon. The host build is used for C ABI
  extraction and tests; both archives supply packaging inventories.
- **The source archive of the same tag** provides the C API implementation,
  the Python bindings, and the Python tests and examples. Only the paths
  listed in `bindgen/fetch.py` are extracted.

## What is extracted

Each extractor in `bindgen` reads one part of the release and records a set
of facts. The last column says how those facts are checked or used.

| Input | Extractor | Facts | Check |
|---|---|---|---|
| `include/cvc5/c/*.h` and the enum headers | `bindgen.c_headers` | 476 C functions, each with its signature, section, deprecation, and doc comment | A generated C file assigns every function to a pointer of exactly the parsed type, and it must compile with `-Werror` |
| The same headers | `bindgen.c_headers.types` | The C types the signatures use: handles, opaque structs, structs with a visible layout, and enums | For each type it maps, `bindgen.gen_raw` compiles a static assertion of its size, and of its signedness where that matters |
| The same headers | `bindgen.c_headers.layouts` | The fields of the structs with a visible layout, with their offsets and sizes. Also the values of the C enums that only those fields use (`Cvc5OptionInfoKind`) | A generated C program checks each parsed field type with `__builtin_types_compatible_p`, then prints every offset, size, and value. Layouts are never computed from the parse |
| `lib/libcvc5*.so` / `lib/libcvc5*.dylib` | `bindgen.c_library` | For each C function, the library that exports it | LLVM exported-symbol tables, checked across all pinned platforms. Missing or conflicting exports fail extraction |
| Kind header comments | `bindgen.enums` | Operator descriptions in `enum_docs.Kind` | Tutorial directives require names and descriptions in the snapshot |
| `src/options/*_options.toml` and the pinned binary | `bindgen.options` | Option names, aliases, defaults, value kinds, bounds, modes, and descriptions | The C metadata reader compiles against pinned headers; every reported name must join to a source declaration |
| Enum headers | `bindgen.enums` | 14 enums, 1,158 values | A generated C program runs and prints every enumerator. Values are never parsed |
| `src/api/c/cvc5.cpp` and `cvc5_parser.cpp` | `bindgen.c_impl` | For each C function, the C++ API methods it calls | The completeness gate, which fails when a Python method joins no C function. Functions that call no C++ API method, such as `cvc5_term_copy`, have an empty list |
| The same files | `bindgen.c_impl.null_tested` | For each C function, the pointer parameters its body tests for NULL (`null_tested` in the snapshot). These accept NULL, although the header does not say so | Where Python's default is `None`, `bindgen.gen_api` makes such a `const char*` an `Optional[String]`, and `test_api.mojo` passes `None` |
| `src/api/c/cvc5_c_structs.cpp`, its header, and `cvc5_parser.cpp` | `bindgen.c_impl.handles` | For each handle type, its exporters and ownership mode; solver allocation and release protocol | Structural checks plus lifetime and retention regressions |
| C++ header defaults, explicitly selected in `overrides.toml` | `bindgen.cpp_api.none_bool_defaults` | Boolean defaults for opted-in Python `None` flags | Ambiguous or missing defaults fail extraction |
| Pinned official Python wheel | `bindgen.oracle.null_values` | Null-object formatting, in `api/null-values.json` | Isolated probes record text, errors, or signals; all null Writable classes have Mojo regressions |
| `src/api/python/cvc5.pxd` | `bindgen.cpp_api` | The C++ API vocabulary (344 method names) | Used as a filter, so helper calls such as `push_back` never join |
| The same file | `bindgen.cpp_api.maps` | The 4 C++ methods that return or take a `map[K, V]`, which Python turns into dicts (`cpp_maps` in the snapshot) | `bindgen.gen_api` checks `K` and `V` against the element types of the C function's two arrays |
| `src/api/python/cvc5.pxi` | `bindgen.python_api` | 458 public Python methods in 19 classes, each with its parameters, docstring, deprecation, C++ calls, the parameter each argument of those calls reads (`cpp_args`), and delegations. Also the 4 methods that return a C++ string as a Python `int` or `Fraction`, and the class docstrings and constructor parameters | The [completeness gate](join.md#the-completeness-gate) |
| `test/unit/api/python/` | `bindgen.translate` | 17 unit-test files with 377 tests, translated to Mojo | They run as tests (`pixi run --locked cvc5-tests`) |
| `examples/api/python/` | `bindgen.translate` | 23 examples, translated to Mojo | Each must print what it prints in Python (`pixi run --locked cvc5-tests`) |
| PyPI `cvc5==1.4.1` (pixi environment `oracle`) | `bindgen.oracle` | What each Python example prints and its exit status, recorded in `tests/cvc5/examples/` | Exact output comparisons, or explicit model checks with identical remaining output, as recorded in `translation.json` |

The counts are for cvc5 1.4.1. The [coverage report](../reference/coverage.md)
always shows the current ones.

## Why checks matter for regex extraction

The extractors use regular expressions, not a C or Cython parser, so that
they need no dependencies. A regular expression can misread a declaration.
The compile check is what makes this approach safe: a misread signature does
not compile against the headers.

While the extractors were being written, the check caught two parser bugs
that would otherwise have produced wrong bindings:

- a `deprecated` attribute absorbed into a return type;
- a function-pointer parameter split at its inner commas.

## Docstrings

cvc5's docstrings are written in reStructuredText. `bindgen.docstrings`
converts the subset they use to Markdown, both for this site and for the
docstrings of the generated Mojo API. The subset is:

- `:param:` and `:return:` fields;
- `warning`, `note`, and code directives, including nested ones;
- literal blocks;
- cross-reference and math roles.

The docstrings mix indentation levels, so the converter delimits each
construct relative to the line that opens it.

## The snapshot

`bindgen.snapshot` combines the extracted facts and the [join](join.md),
which maps each Python method to its C functions, into one file,
`api/cvc5-api.json`. This file, the *snapshot*, holds:

- every C function, with the library that exports it;
- checksums, aliases, and ELF or Mach-O dependencies for each platform's native libraries;
- every C type the signatures use;
- every enum value;
- Kind descriptions used by tutorial operator tables;
- solver option metadata and its source declarations;
- handle ownership;
- every Python class and method, with its
  [binding](join.md#binding-statuses).

The snapshot is committed. Moving to a new cvc5 release changes it, and
`pixi run --locked api-diff` summarizes that change as Markdown for review.
