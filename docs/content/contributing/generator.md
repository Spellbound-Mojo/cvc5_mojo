# Working on the generator

The generator, `bindgen/`, extracts facts from the pinned cvc5 release. It
joins each Python method to the C functions that call the same C++ method,
and records the result in the snapshot, `api/cvc5-api.json`. From the
snapshot, it generates the Mojo
[raw layer](../architecture/layers.md#raw-layer) and
[base API](../architecture/layers.md#base-api).
[Inputs and extraction](../architecture/inputs.md) and
[mapping Python to C](../architecture/join.md) explain these steps. This page
covers the changes you make to the generator.

## Modules

| Module | Role |
|---|---|
| `bindgen/config.py` | Holds the paths, and reads `cvc5-version.toml` and `overrides.toml` |
| `bindgen/fetch.py` | Downloads and verifies the binary and source archives |
| `bindgen/c_headers.py` | Extracts the C function prototypes, checked by the compiler, and the C types they use |
| `bindgen/c_library.py` | Finds the library that exports each C function |
| `bindgen/enums.py` | Takes the enum values from a compiled C program, and writes `enums.mojo` |
| `bindgen/cpp_api.py` | Extracts the C++ API vocabulary from `cvc5.pxd`, and the methods with `map` types |
| `bindgen/c_impl.py` | Extracts the C++ calls of each C function, the parameters it tests for NULL, and handle ownership |
| `bindgen/python_api.py` | Extracts the Python API from `cvc5.pxi`, with the parameter each C++ argument reads |
| `bindgen/snapshot.py` | Runs the [join](../architecture/join.md#the-join-through-c) and the [completeness gate](../architecture/join.md#the-completeness-gate), and writes `api/cvc5-api.json` |
| `bindgen/gen_raw.py` | Generates the raw layer from the snapshot, and writes `_c/raw.mojo` |
| `bindgen/gen_api.py` | Generates the base API from the snapshot and `bindgen/manual/`, and writes the class modules and `__init__.mojo` |
| `bindgen/report.py` | Produces the coverage summaries for the gate and this site |
| `bindgen/reference.py` | Renders the API reference pages from the snapshot |
| `bindgen/docstrings.py` | Converts reStructuredText to Markdown |
| `bindgen/diff.py` | Summarizes the API changes between two snapshots |
| `bindgen/bump.py` | Moves the pin to a new release |
| `bindgen/translate.py` | Translates cvc5's Python unit tests and examples to Mojo, and writes `tests/cvc5/` |
| `bindgen/oracle.py` | Records what cvc5's Python examples print under the official bindings, and writes `tests/cvc5/examples/*.out`. It runs in the `oracle` environment. |

Each extractor runs on its own and prints a summary. For example, run
`pixi run --locked python -m bindgen.c_headers`.

## Resolving an unresolved method

A Python method is unresolved when none of the
[binding statuses](../architecture/join.md#binding-statuses) applies to it,
and the completeness gate then fails. `pixi run --locked check-api` prints
each unresolved method. To resolve one:

1. Find what its Python implementation calls, in
   `third_party/cvc5-src/src/api/python/cvc5.pxi`.
2. Find the C function that does the same, in
   `third_party/cvc5/include/cvc5/c/cvc5.h`.
3. Add one entry to `bindgen/overrides.toml`:

```toml
[methods."Solver.getTermManager"]
c = ["cvc5_get_tm"]

[methods."Term.notTerm"]
c = ["cvc5_mk_term"]
kind = "NOT"

[methods."Term.__iter__"]
c = ["cvc5_term_get_num_children", "cvc5_term_get_child"]

[methods."Term.toPythonObj"]
skip = "Converts to Python objects; Mojo has typed getters."
```

Choose the key that fits the method:

- **`c`** when the generator can bind the C functions directly. With
  `c = ["cvc5_mk_term"]`, **`kind`** makes a `Term` method that builds a term
  of that kind from the receiver and its `Term` arguments, as the C++
  `Term::notTerm` and its siblings do. For `__iter__`, `c` names a count
  function and a get-by-index function. The generator tells them apart by
  their signatures.
- **`manual`** when the Mojo body must be written by hand, in
  `bindgen/manual/<Class>.mojo`. See [below](#writing-a-manual-method).
- **`alias`** to reuse another class's method.
- **`skip`** with a reason when the method has no meaning in Mojo.

When the same pattern covers several classes, prefer a generic `[[rules]]`
entry.

## Writing a manual method

A *fragment*, `bindgen/manual/<Class>.mojo`, holds a class's hand-written
methods: the methods whose binding is `manual`.
`bindgen/manual/Statistics.mojo` is the example. A fragment has three parts:

1. Imports, which go into the generated module.
2. `struct <Class>:` with the methods, without docstrings or traits. The
   generator splices them into the generated class and adds cvc5's
   docstring to each Python method. A private helper, such as `_read`, needs
   its own docstring.
3. Other definitions, appended to the generated module. The public ones,
   such as `Stat`, are exported from the package.

The fragment is not compiled on its own. Its methods use the generated
class's fields, such as `self._api` and `self._h`. `bindgen.gen_api` derives
the generated module's imports of the raw layer and `ffi.mojo` from what the
code uses.

Fragments may also add overloads to an existing generated Python method.
`bindgen.gen_api` rejects unknown public method names and C calls not allowed
by their bindings, and requires every listed manual C function to be used.

For a fixed-width native variant that must not be a public overload, add it
to the method's `c` list and map its name with `private = { c_function =
"_native_helper" }` in `overrides.toml`. The normal emitter then generates
its argument conversion, error checking, and handle receipt. Names must be
unique, start with `_native_`, and refer to functions in that binding.
The public signature inventory excludes these helpers. The
[numeric conversion paths](../architecture/numeric-conversions.md) use this
to preserve exact APN inputs without duplicating native-call implementations.

## Leaving out a translated test

`pixi run --locked cvc5-tests` builds and runs cvc5's unit tests, translated
into `tests/cvc5/`. Every test there must pass. A translated test may fail
because it relies on Python behavior that cannot exist in Mojo. Leave such a
test out with an entry in `bindgen/overrides.toml`, keyed by file and test,
and give the reason, failure phase, and diagnostic fragment:

```toml
[tests]
"test_symbol_manager.test_constructor" = { reason = "the deprecated SymbolManager(Solver) is not mirrored", phase = "compile", match = "cannot be converted from 'Solver' to 'TermManager'" }
```

Then run `pixi run --locked generate`. When the test should pass, fix the
translator or the bindings instead.

`pixi run --locked cvc5-tests` builds each left-out test on its own, and it
fails once that test passes, or fails in a different way. Crashes and timeouts
never satisfy an expected failure. It also fails on an entry for a test that no
longer exists, or for a test that the translator does not translate anyway.

An example whose output cannot match Python's can be left out by its name in
`[examples]`. For a non-unique model, `[example_checks]` can instead select
`"model"`: the generated program evaluates every asserted formula in each
SAT model and checks each printed model value's sort and equality to its
term in that model. The runner normalizes only the value fields discovered
in the Python source. Solver results, explanatory text, line order and exit
status still match exactly. A test or example that the translator does not
handle needs no entry. The
[coverage report](../reference/coverage.md#cvc5s-unit-tests) lists it, with
the construct that the translator does not handle.

`TypeError` and `ValueError` blocks in runnable tests also become generated
compile-fail fixtures. So do known argument-type or arity mismatches inside
expected-error blocks. They must produce a diagnostic at the marked call;
unrelated compiler errors do not count. An inner call's expected runtime
error is retained when a static mismatch prevents compiling its outer call.
The legacy exceptions example uses the same classification, stopping at the
first rejected call before unreachable names in its Python source.

APN's lack of a float constructor no longer excludes the real-value test.
The translator converts `Fraction(0.3)` to the exact ratio of the binary
float, and `Fraction("0.3")` to the decimal ratio. Large integer locals use
`Integer` before Mojo can infer a machine-width `Int`.

For a focused check, select individual tests and their compile-failure blocks:

```sh
pixi run --locked cvc5-tests --test test_term.test_get_real
pixi run --locked cvc5-tests --test test_solver.test_get_option_info --test test_solver.test_get_statistics
pixi run --locked cvc5-tests --only floating_point
```

Add `--update-calls` to extend `calls.json` with native calls from a successful
targeted run. It preserves the same-release baseline; only a full run can
remove previously recorded calls. Without that flag, targeted runs leave the
committed trace inventory alone.

The `[generation]` tables explicitly account for unsupported raw functions
and base methods. New and stale omissions fail both generation and
`check-api`. A Python `None` default is never silently coerced to `False`:
use a manual method or an explicit policy extracting the matching C++ default.

## Changing an extractor

The extractors use regular expressions, so every change needs its check:

- The compile check in `c_headers.verify` catches a signature change.
- A change to the join shows in the coverage numbers and in the gate.

After a change, run `pixi run --locked generate` and review the snapshot
diff. When a change moves many methods between binding statuses, also look
at `pixi run --locked api-diff`.

## Generators

`bindgen/gen_raw.py` writes the [raw layer](../architecture/layers.md#raw-layer)
from the snapshot alone. To change how a C type crosses between C and Mojo,
change `mojo_type()` in that file and its static assertions in `check()`.

`bindgen/gen_api.py` writes the [base API](../architecture/layers.md#base-api)
from the snapshot and the hand-written methods in `bindgen/manual/`. Its
rules are in its module docstring. For
every mirrored method, `classify()` says which overloads it generates, or why
it generates none. The coverage report and the API reference render that.

`Model.received` owns generated handle receipt expressions, including those in
specialized iterator and term-builder emitters. Resolve their templates with
`Model.bind_receiver` against the actual receiver; use `receiver_context` for
its API, term-manager, and native-handle expressions. Receipt mode and exporter
facts come from the snapshot. See the [receipt audit](../architecture/handle-receipt.md)
for anchor validation and mutation coverage.

Only running generated code proves it. `mojo precompile` does not
instantiate everything, so a new rule needs a check in
`tests/smoke/test_api.mojo`.

Generated Mojo starts with a `# Generated by bindgen … Do not edit.` header.
Public names are exactly the Python names, and raw-layer names are exactly
the C names. Internal helpers use `snake_case` with a leading underscore.
