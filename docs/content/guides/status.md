# Support and limitations

## Scope

The bindings target **Mojo 1.1.0 on Linux x86-64, Linux ARM64, and macOS Apple Silicon**, with cvc5 1.4.1. Install the
[conda package](../start/installation.md#install-the-package) or work from a
source checkout. The
[verification chapter](../architecture/verification.md) describes the checks
and what their results establish.

| Item | Status |
|---|---|
| Compiler | Mojo 1.1.0, pinned through Pixi. Other versions are not supported. |
| cvc5 | 1.4.1. Older releases terminate the process when the API is misused, so they are not supported. |
| Linux x86-64 | Supported and tested |
| Linux ARM64 | Supported; the package's tests run on a native ARM runner, and the full development gate runs on Linux x86-64. See [platform validation](../architecture/packaging.md#platform-validation) |
| macOS Apple Silicon | macOS 15+. Supported and tested; some development checks are [Linux-only](../contributing/development.md#environment) |
| Intel Macs, 32-bit ARM | Not supported |

## What works

- **Python's base API.** The bindings generate 392 of the 458 methods of
  cvc5's Python API, in all 19 of its classes. A few are hand-written in
  `bindgen/manual/` and spliced into the generated classes. The
  [coverage report](../reference/coverage.md#base-api) counts them, and the
  [API reference](../reference/index.md) shows every Mojo signature.
- **The C API.** An internal raw layer binds all 476 of cvc5's 476 C functions
  one to one, with a distinct type for each kind of handle. The
  [coverage report](../reference/coverage.md#raw-layer) verifies that none are omitted.
- **cvc5's own tests.** 366 of cvc5's 377 Python unit tests are translated
  to Mojo and pass. 22 of its 23 Python examples run: 21 match the official
  Python output exactly, and the floating-point example checks its models
  while matching the remaining output. Nine compile-failure fixtures check
  invalid arguments. The [tutorial](../examples/tutorial.md) explains these
  comparisons. The
  [coverage report](../reference/coverage.md#cvc5s-unit-tests) lists the
  tests and examples that do not run, and why.
- **Following cvc5 releases.** The bindings are generated from the pinned
  release. Local upgrade commands regenerate the bindings and summarize
  API changes. A twice-yearly upgrade workflow exists but is currently disabled;
  see [upgrading cvc5](../architecture/upgrades.md#automation).

The [transcendental tutorials](../tutorials/transcendentals/index.md) cover
exponential and trigonometric terms, logarithm encodings, and rigorous bounds.
A supported constructor does not guarantee that every formula containing it
will be decided; see [solver limits](../tutorials/transcendentals/results.md).

## Known boundaries

| Area | Current behavior |
|---|---|
| Deprecated methods | The 65 methods that cvc5 1.4.1 deprecates, such as the `Solver.mk*` duplicates of `TermManager` methods, are not mirrored. Use the `TermManager` versions. |
| Python objects | `Term.toPythonObj` is not mirrored. Use the typed getters, such as `getIntegerValue` and `getRealValue`. |
| Plugins | Supported through the [`Plugin` trait](../reference/plugin.md). Registration retains callback state; names are static per type. Callback errors invalidate the solver. |
| Oracle functions | Supported through [`Oracle.evaluate` and `Solver.declareOracleFun`](../reference/oracles.md). The API is experimental; callbacks must be deterministic and stay with the registering solver. |
| Null objects | `Result()` and `SynthResult()` answer status queries as Python does. `Proof()` returns the unknown rule, a null conclusion, and empty children/arguments. `Proof().getRewriteRule()` raises a clear error; the pinned Python implementation crashes on that undefined query. |
| Printing | Values print as in Python: terms in SMT-LIB, enums as `Kind.ADD`, statistics and option information as Python's dictionaries. Null formatting is safe; classes whose Python null formatter fails print `Class(null)`. A Mojo list of strings prints without quotes. |
| Grammar formatting | Repeated native grammar formatting grows memory on the cached release. `String(grammar)` invokes the native formatter twice on Mojo 1.1.0, amplifying that growth; an explicit single `write_to` call into a String avoids the duplication. See the [matched reproduction and limits](../architecture/binding-controls.md#grammar-formatting-remains-an-open-finding). |
| Strings | Default `mkString` and `getStringValue` preserve Unicode and embedded NUL. Other C string arguments reject embedded NUL. Explicit escape flags retain upstream restrictions. |
| Widths and indices | Literal values are checked before narrowing. Values already narrowed by caller code cannot be reconstructed. |
| Anonymous parameter sorts | `mkParamSort()` and `mkParamSort(None)` raise because the cached C implementation rejects a null name, despite its header allowing one. Python accepts these calls. An explicit empty name creates a sort with an empty symbol, which is observably different from an anonymous sort. See the [compound FFI investigation](../architecture/compound-ffi.md#anonymous-parameter-sorts). |
| Sort inequality output | Public `Sort != Sort` negates native equality and is silent. Direct raw calls to the native inequality function still print debugging output; see the [native reproduction and binding fix](../architecture/compound-ffi.md#sort-inequality-writes-to-stdout). |
| Synthesis memory | Repeated synthesis with a shared term manager grows memory in cvc5 1.4.1 in both Python and Mojo. Bound both solver and term-manager lifetimes for repeated jobs; also release handles that retain them. |
| Changing expressions | A long-lived arithmetic solver grew under continually new constants even after pop removed all assertions. Recycling the solver in bounded batches kept the tested workload stable with its term manager retained; see [soak results](../architecture/soaks.md). |
| Big numbers | `Integer` and `Rational` come from the released apn_mojo 1.0.1 package, installed from modular-community and locked by Pixi; see [installation](../start/installation.md#big-numbers-apn_mojo). |
| Threads | Each worker needs its own term manager, solver, and associated values. Shared object graphs are not supported. |
| Library location | The main and parser libraries must be in the same directory. Initialization checks the loaded version against the pin; see [installation](../start/installation.md#where-the-library-is-found). |
| The pythonic layer | `cvc5.pythonic`, the z3-style API, is out of scope. |

For common build and run errors, see [Troubleshooting](troubleshooting.md).

The [memory follow-up](../architecture/memory-followup.md) gives current
matched measurements, native allocation profiles, and steps to bound the
two reproduced growth cases.
