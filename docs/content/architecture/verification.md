# Verification

The checks cover the extracted facts, the generated code, cvc5's own tests
and examples, and this site. This page lists them, the commands that run
them, and what they do not establish.

## Test layers

✓ marks the layers that run today.

| Layer | What it checks | Status |
|---|---|---|
| Extraction | Every C signature compiles against the headers. Every enum value comes from a compiled program. Every declared function is exported by a library of the release. | ✓ |
| Raw-layer types | Static assertions, compiled against the headers, of the size of every C type the [raw layer](layers.md#raw-layer) maps, and of its signedness where that matters | ✓ |
| Completeness gate | Every Python method has a [binding status](join.md#binding-statuses), no override is stale, and the automatic join stays above its minimum ([the completeness gate](join.md#the-completeness-gate)) | ✓ |
| Reproducibility | CI regenerates everything and requires the committed files to match | ✓ |
| Generation policy | Unexpected or stale raw/base API omissions fail generation. Unit regressions mutate the native release protocol and C++ defaults and check that extraction refuses them | ✓ |
| Boundary contracts | `pixi run --locked contracts` builds string, null-formatting, single-pass formatting, literal-range, collection-input, returned-collection, retention, ownership, return-conversion, compound FFI, and generated-sequence regressions from source and package at O3 with `--Werror`, with assertions enabled and disabled (44 configurations). CI also runs strings, integer boundaries, collection inputs/returns, formatting, ownership, return-conversion, compound, and sequence fixtures at O0. [Formatting checks](single-pass-formatting.md) enforce native-call counts and failure behavior; [injected decoding failures](return-conversion.md) check pending-reference cleanup; [statistics checks](statistics-snapshots.md) cover filtering, order, detached values, and partial decoding; [compound comparisons](compound-ffi.md) and [seeded sequences](generated-sequences.md) check C/raw/public observations, with an independent exact-arithmetic model for sequences | ✓ |
| Runtime loading | `pixi run --locked runtime-test` checks selection precedence, missing libraries/symbols, version rejection, invalid version text, stable cached failures, and cleanup before process exit. Source/package and assertion matrices run at O3; CI also runs O0. See the [initialization report](runtime-validation.md) | ✓ |
| Raw layer | `tests/smoke/test_raw.mojo` calls at least one generated method for each crossing and direction, and checks the values. The crossings are handles, owners, enums, `bool`, each integer width, strings, string and handle arrays, out-parameters, 32-bit strings, and an error | ✓ |
| Base API | `tests/smoke/test_api.mojo` covers each marshaling rule of `bindgen.gen_api` and each generated class of the [base API](layers.md#base-api), and checks the values. It includes optional strings, variadic and `List` overloads, range checks, tuples, a borrowed term manager, datatypes, the parser and its errors, proofs, and synthesis | ✓ |
| Smoke | `tests/smoke/test_smoke.mojo` builds terms, calls `checkSat`, gets an unsat core, and raises and recovers from an error | ✓ |
| Threads | `tests/smoke/test_threads.mojo` starts 16 independent workers together, verifies one shared cached API, deliberately overlaps pending native errors and clean threads, checks worker-specific Unicode diagnostics, and solves after recovery. The runtime matrix also checks concurrent cached loading failures | ✓ |
| Lifetimes | `tests/smoke/test_lifetimes.mojo` checks that a result outlives its solver, that a term outlives its term manager value, and that `print(solver.checkSat())` works | ✓ |
| Leaks | `tests/smoke/test_leaks.mojo` exercises repeated owner lifetimes. `test_retention.mojo` exercises 200,000 discarded query results with a live solver, repeated proof and grammar exports, and bounded solver and term-manager lifetimes for synthesis. Resident growth must stay within the test budgets | ✓ |
| Matched ownership | Independent C, raw Mojo, and public Mojo fixtures use the same loaded native libraries. CI checks complete graph cleanup; the live-owner controls for results, proofs, unformatted grammars, commands, datatypes, statistics and synthesis-result copies run locally, because their growth budget is not stable on GitHub's runners. Grammar formatting and repeated synthesis queries remain failing native-growth diagnostics. See [matched binding controls](binding-controls.md), the [ownership audit](ownership-audit.md), and [family controls](family-controls.md) | ✓ |
| Documentation examples | Every program on this site is built from source and from the precompiled package, at O0 and O3 with `--Werror`, and its output is compared with the recorded output | ✓ |
| Translated cvc5 tests | cvc5's Python unit tests (17 files, 377 tests) are translated to Mojo by `bindgen.translate` into `tests/cvc5/` and run by `pixi run --locked cvc5-tests`. The [coverage report](../reference/coverage.md#cvc5s-unit-tests) lists, with its reason, each test that the translator does not handle or that `bindgen/overrides.toml` leaves out because it cannot pass in Mojo. A left-out test that passes fails the run | ✓ |
| Differential | cvc5's Python examples (23) are translated by `bindgen.translate` into `tests/cvc5/examples/`. Each must satisfy its comparison policy and match the Python exit status: exact output for deterministic examples; assertion and model-value checks with exact remaining output for floating-point witnesses. `bindgen.oracle` records the Python output during `pixi run --locked generate`, in the `oracle` environment (PyPI `cvc5==1.4.1`), and `pixi run --locked cvc5-tests` compares the two. The comparison policy is selected by `[example_checks]` in `bindgen/overrides.toml`; exclusions remain explicit in `[examples]` | ✓ |
| Coverage | The C functions that cvc5's translated tests and examples call. The raw layer records them at run time in builds with `-D CVC5_MOJO_TRACE`, and they are saved in `tests/cvc5/calls.json`. The [coverage report](../reference/coverage.md#c-functions-the-tests-reach) lists the generated methods that none of them reaches | ✓ |

The translated tests and examples are regenerated at every cvc5 bump, so
the tests that run are always those of the pinned release.

[Production-like soaks](soaks.md) add sustained CAS-style workloads, RSS
trends, per-request timing, and process watchdogs. They run separately from
the ordinary CI gate; `soak-check` tests their analysis, checkpoint reader,
and batch-selection policy. `batch-benchmark` reuses the same checked integer
workload and monitoring helpers to compare recycling intervals sequentially.

The five `pytest.raises(TypeError/ValueError)` blocks in the runnable upstream
tests also generate isolated compile-fail modules. Each must report a compiler
diagnostic at the rejected call. Excluded tests specify a failure phase and
diagnostic in `overrides.toml`; an unrelated error, crash, or timeout fails the
suite. The excluded floating-point example must compile and exit normally
before its known output difference can count as expected. A newly passing
exclusion is stale and also fails the suite.

## Commands

| Command | Checks |
|---|---|
| `pixi run --locked test` | Completeness, generator, boundary-contract, runtime-loading, smoke, lifetime, thread, leak, and translated-upstream gates |
| `pixi run --locked binding-check` | Matched-control analysis, reference accounting, and loaded-library identity regressions |
| `pixi run --locked matched-controls --output .cache/matched-<n> --modes results,proofs,grammar-empty,grammar-rules,commands --operations 20000 --repetitions 1` | Cached-only core C/raw/public ownership subset; CI also runs the [family and graph-cleanup controls](family-controls.md) |
| `pixi run --locked cvc5-tests` | Translated tests, examples, compile-fail blocks, and classified exclusions. The command rewrites `tests/cvc5/calls.json` only after a successful full run; CI requires it to be unchanged |
| `pixi run --locked docs-test --output .cache/docs-<n>` | Every documentation example on both import routes and at both optimization levels |
| `pixi run --locked -e docs docs-check` | The documentation audit, a strict site build, and the site's links, anchors, and search index |

## Definition of done

A change is done when:

- `pixi run --locked generate` leaves no difference in the committed
  generated files, `tests/cvc5/` included;
- `pixi run --locked test` passes;
- `docs-test` and `docs-check` pass when pages, examples, or the snapshot
  changed;
- the documentation describes the change (see
  [maintaining the docs](../contributing/documentation.md)).

## What is not established

The checks give evidence for the paths and inputs they run. They do not
establish the following:

- **Other platforms and versions.** Only Linux x86-64 with Mojo 1.1.0 and
  cvc5 1.4.1 is checked.
- **Paths no test runs.** The
  [coverage report](../reference/coverage.md#c-functions-the-tests-reach)
  lists the generated methods that no cvc5 test or example reaches.
- **Identical output on every build.** The examples are compared with the
  PyPI build of cvc5, not with the release binaries the bindings load. Model
  values can differ between builds, which is why `floating_point` is left
  out.
- **Other ways of using threads.** Several threads are tested only with one
  term manager and one solver per thread.
- **Every leak.** RSS budgets catch sustained growth on these workloads, not
  every leaked allocation. Repeated synthesis with a shared term manager
  still grows in the upstream engine; see [runtime](runtime.md#arrays-and-leaks).
  The matched C grammar formatter also grows; public `String(grammar)` makes
  twice as many native formatting calls on the pinned Mojo compiler. See the
  [open formatting finding](binding-controls.md#grammar-formatting-remains-an-open-finding).
  Fixed-input synthesis queries also fail the memory budget in the matched C
  build; [copy and graph-cleanup controls](family-controls.md) distinguish the
  tested ownership paths from that native query growth.
