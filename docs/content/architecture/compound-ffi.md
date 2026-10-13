# Compound FFI boundaries

This pass compares representative compound conversions in direct C, raw
Mojo calls, and the public API against the same cached cvc5 1.4.1 libraries.
The eight Mojo build configurations agree with C. Two native C defects were
reproduced and documented below; no binding implementation changed in this
pass. The earlier [return-conversion cleanup fix](return-conversion.md)
remains covered by the contract suite.

## Protocol and scope

`tests/binding/compound.c` is an independent semantic control compiled against
the cached headers. `tests/smoke/test_compound.mojo` runs in raw and public
modes. Raw mode uses public wrappers to construct and own fixtures, then
calls the generated C entry point at the crossing being tested. It is not
an independent implementation of the entire ownership layer. Public mode
exercises the generated argument and result conversions.

The existing contract runner compiles C at each requested optimization level,
compares the complete output with both Mojo modes, and checks the libraries
actually mapped into every process by content hash. Nonzero exits, crashes,
timeouts, missing completion markers, different observations, and library
mismatches fail. Unit tests cover that classification. Source, package,
dependency, and test hashes are retained in the report.

| Boundary | Cases and invariants |
|---|---|
| Numeric out-parameters | Signed 32/64-bit minimum numerators with unsigned maximum denominators; sentinel values around each raw output detect adjacent writes. Public arbitrary-precision rationals preserve the same values. |
| Handle/scalar tuples | Floating-point exponent/significand widths and returned bit-vector, plus cardinality sort and maximum 32-bit upper bound. Wrong-type getter fails, clears the error, and permits a subsequent valid call. |
| Returned arrays | Empty assertions; model arrays of lengths 0, 1, 2, 7, 31, and 257; every element and its position checked. Saved exports remain usable after another native array-returning call. |
| Result plus array | Timeout-core result is unsatisfiable and its one term is false. Both the result and term references are released. |
| Input-sized outputs | Datatype sort arrays of lengths 1 and 7, whose size comes from the input count rather than an output length; saved sorts survive another bulk call. |
| Nested input arrays | Recursive definitions with rows of arity 0, 1, and 2, different bodies, and solver checks of all three results. Invalid bound-variable type fails and a valid definition subsequently succeeds. |
| Optional Boolean flag | Omitted and explicit false definitions disappear after `pop`; explicit true definitions remain. |
| Optional names | Omitted, `None`, empty, and Unicode names across constants, variables, parameter sorts, uninterpreted sorts, and sort constructors. Symbol presence is checked separately from its text. |
| Struct layout | Guarded native option-information structs carry maximum `UInt64`, negative signed integer, double, and Boolean fields; public decoded variants match. |
| Unsafe outer shapes | Public guards reject mismatched function/bound-row/body lengths and record-field name/sort lengths. No corresponding unsafe C call is made: C cannot inspect the allocated lengths of those buffers. |

The fixtures share native error, trace, and mapping helpers with the existing
ownership controls. Mojo mapping capture lives in `memory_support.mojo`.
This avoids introducing separate execution or library-identity mechanisms.

## Native findings

### Anonymous parameter sorts

The cached header documents a nullable symbol for `cvc5_mk_param_sort`, but
the implementation checks `CVC5_CAPI_CHECK_NOT_NULL(symbol)` before calling
the C++ API. The loaded release binary rejects null with `unexpected NULL
argument`. Raw and public Mojo correctly surface and clear that C error.

The cached Python 1.4.1 oracle accepts both `mkParamSort()` and
`mkParamSort(None)`, producing a sort whose `hasSymbol()` is false. An explicit
empty string succeeds in both C and Python, but `hasSymbol()` is true and
`getSymbol()` returns an empty string. Substituting `""` for `None` would
therefore change observable semantics. The binding does not make that
substitution. Pass an explicit symbol when creating parameter sorts through
the current C API.

All other optional-name observations match the Python oracle. In particular,
an unnamed uninterpreted sort constructor has an empty symbol in both APIs;
it is not treated as another discrepancy. Python is used here only as a
semantic oracle, not as a matched-build memory or performance baseline.

### Sort inequality writes to stdout

**Binding fix, 2026-10-13.** Public `Sort != Sort` now negates the native
equality result. A targeted contract checks null, equal, and distinct sorts
and requires exact stdout, so stray native prints fail the test. The raw
inequality entry point remains a direct binding to cvc5. The observations
below describe the original investigation.

The cached `cvc5_sort_is_disequal` implementation contains `printf("1\n")`
on its null branch and `printf("2\n")` on its nonnull branch. A minimal direct-C
program comparing an integer sort with itself, then null with that sort,
prints `2` and `1` despite having no user output statements. The equivalent
public Mojo comparisons reproduce exactly that output. Both load the same
native library bytes.

The Boolean results are correct, but this unsolicited output is a production
limitation. Public `Sort != Sort` inherits it. `not (a == b)` uses the native
equality entry point and avoids the output. The compound tuple check uses
equality in all three layers. It does not filter or normalize stdout to hide
the discrepancy. The native implementation is outside this repository's
scope, and this pass leaves the generated inequality mapping unchanged.

## Results on 2026-10-07

All eight compound configurations pass: source and precompiled imports,
O0/O3, and assertions enabled/disabled. Each runs both raw and public modes,
giving **16 Mojo executions against two C controls**, with 42 semantic
observations per execution. Per-element, sentinel, and error checks provide
additional assertions beyond the printed observations. The mapped main
library has SHA-256
`61206e6d5f36585cfe682a1ec97ad2c1c548e1fa772925d5205fcad4ae7a7a24`.

The broader validation passed all 28 O3 contract configurations, nine short
matched result/proof/command ownership runs, 33 generator/runner analysis
tests, and all 16 documentation-example configurations. Strict documentation
and link checks passed. The matched runs also recheck tracing and library
identity after extracting shared test helpers. The full translated upstream
suite and heap profiling were not rerun in this pass.

An initial raw fixture crashed because an untracked solver pointer outlived
the fixture's last use of its owning Mojo wrapper. Explicitly retaining the
owner through the call fixed the fixture. Public receiver borrowing already
handled that lifetime correctly. A second initial mismatch was the native
sort-inequality output above, triggered by a test assertion's internal use
of `!=`. Both diagnostics were investigated before accepting the final
matrix; neither was counted as a passing expected failure.

Local evidence:

- `.cache/compound-matrix-02/report.json`: final comparison matrix, builds,
  observations, loaded-library checks, and source/dependency hashes;
- `.cache/compound-verification/oracle.json`: all 20 optional-name
  observations from the cached Python oracle;
- `.cache/compound-verification/native-inequality.json`: minimal C and Mojo
  output reproductions, with their local sources alongside the report;
- `.cache/compound-verification/summary.json`: regression results and the
  investigation index;
- `.cache/compound-matrix-01` and `.cache/compound-pilot-02`: retained
  diagnostic failures before correcting the fixtures.

This is representative behavioral coverage, not an exhaustive ABI proof,
allocation audit, or performance measurement. No new binding-specific leak
or conversion defect was reproduced. Native synthesis and grammar-formatting
growth from the [family controls](family-controls.md) remains open. The
binding source hashes are unchanged from the previous pass.

## Running the checks

Use the existing runner directly to avoid fetch task dependencies:

```sh
pixi run --locked python scripts/run_contract_tests.py --only compound --optimization 0,3 --output .cache/compound-new --jobs 4
```

The regular contract gate includes these comparisons at O3. CI and the cvc5
update workflow also run them at O0. This gate tests current C behavior;
the documented parameter-sort rejection is not a claim of Python parity.

## Next step

The subsequent [runtime pass](runtime-validation.md) checks concurrent
initialization, independent-thread error isolation, and loading failures.
Next add deterministic differential operation sequences for numeric
boundaries, returned collections, and lifetimes after rejected operations.
