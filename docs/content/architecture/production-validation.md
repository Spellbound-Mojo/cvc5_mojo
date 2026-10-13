# Production validation of the bindings

This closes the scheduled audit work for the cached Linux x86-64 toolchain,
with bounded claims about the tested behaviors. Packaging, solver lifecycle
policy, native engine changes, and new public APIs remain outside this work.
The underlying reports preserve commands, dependency hashes, outputs, and
failures. Native findings and instrumentation limits remain explicit below.

## Constructors and borrowed state

`Model.owner_tm` now supplies the term-manager expression for both owned and
borrowed state. `Model.borrowed` requires an extracted keeper relationship
before wrapping a pointer-owned return. Keeper cycle validation now includes
self-edges. Generator mutation tests reject missing parents, unknown keeper
relationships, and self-cycles before they can emit invalid code.

The initial constructor audit preserved generated runtime output; the later
approved parser guard below adds the only runtime change in this follow-up.
Constructors marshal arguments before
calling native creation, check the native error before adopting the pointer,
and immediately place a successful result in its owning state. Borrowed states
mark the pointer non-owning and retain the returning state. Their destructors
do not delete the borrowed pointer. The native solver/parser/symbol-manager
relationships retain their native parents independently.

The new `test_ownership_construction.mojo` fixture fails each native owner
constructor in turn inside a partially initialized four-field object. It
checks attempted creation, successful creation, deletion, null deletion, and
valid construction after recovery, with implicit and external symbol managers.
The test adapters derive signatures, libraries, and lifecycle functions from
the canonical generator model. They do not contain another native API inventory.
Eight O0/O3, source/package, assertion-mode configurations passed.

The fault is injected before native allocation. This checks binding cleanup
and error propagation; it does not simulate every allocation failure inside
native cvc5 or recoverable exhaustion of Mojo's allocator.

## Behavioral coverage inventory

This is an inventory of tested contracts, not a claim that calling a method
proves every behavior of that method. Function reach remains owned by
`bindgen/report.py` and the [coverage report](../reference/coverage.md).

| Boundary category | Positive evidence | Rejection or failure evidence |
|---|---|---|
| ABI widths, enums, layouts, scalar out-parameters | Compiler-checked snapshot; `test_raw`, C/raw/public `compound` fixture | Generator mutations reject changed signatures/layouts; compound canaries detect writes beyond outputs |
| Counted, parallel, nested and returned arrays | `collections`, `returned_collections`, `compound`; empty and nonempty cases, iterator snapshots | Mismatched sizes, malformed nested inputs, invalid elements, and first/middle/last conversion faults |
| Exact numeric conversion | `integer_boundaries`, mathematical model in `sequences`, compound rational/bitvector outputs | Compile-fail literal limits, runtime overflow, zero denominators, invalid bases/widths; recovery afterwards |
| Strings and native buffers | `strings`: empty values, Unicode, embedded NUL data, page/allocation boundaries, independent snapshots | Rejected NUL in C arguments, invalid native UTF-8, malformed escapes, non-ASCII native diagnostics |
| Defaults and optional arguments | `compound` compares omitted, explicit false/true, absent/empty symbols and nested definitions across C/raw/public | Invalid option values, lengths and nested input combinations |
| Nulls, equality, hashing and ordering | `null_printing`: public null formatters, null/live dictionary keys, copies; translated comparison tests | Null/live inequality and rejected invalid getters; nonraising formatter errors checked in separate crashing subprocesses |
| Return-conversion cleanup | `return_conversion`: actual exports and per-address reference accounting | Injected native iterator and decoding faults, including pending array elements; repeated fault/recovery loops |
| Owner creation and borrowed graphs | `ownership`, `ownership_construction`: detached chains, containers and recovered construction | Native errors, partial user-object initialization and failures at each owner constructor |
| Loading and independent threads | `check_runtime_loading`: both import routes, concurrent initialization, per-thread owner graphs | Missing library/symbol, wrong version, bootstrap cleanup, thread-local error recovery |

Every generated ownership category has a lifetime/cleanup test. Pointer owners
use the construction and borrowed-chain fixtures. Terms, sorts, operators and
datatype handles use translated, collection, ownership and matched family
tests. Results, proofs and proof children, grammars, synthesis results and
commands use detached-handle/container tests and matched live-owner controls.
Statistics and copied `Stat` values use snapshot/iterator tests and injected
conversion failures. The temporary manual `_StatReference` guard is checked
by address-level release accounting.

All categories have representative positive and rejection paths. Exhaustive
cross-products of methods, inputs and native engine states are not claimed.
Unsupported callbacks and translated-test omissions remain in their existing
explicit inventories; this pass does not broaden the public contract.

## Allocation attribution and sanitizer scope

The cached Mojo compiler supports AddressSanitizer at O1. The sensitivity
fixture proves detection of a Mojo heap buffer overrun, a deliberately leaked
Mojo allocation, and a leaked `malloc` allocation in an uninstrumented native
DSO. A separate deliberate leak verifies the explicit leak-check checkpoint.
A normal clean process must also pass; a signal or an unrelated diagnostic
cannot satisfy these controls.

The first instrumented conversion run exposed a test-harness limit: its
fixed 256-address reference ledger relied on allocator address reuse. ASan's
quarantine exhausted that ledger while iterating statistics. The ledger now
grows, retains all recorded addresses for duplicate-release detection, and
frees its storage when the shim unloads. The failed run is preserved; the
affected O0/O3 and sanitizer configurations are rerun after this correction.

Instrumented contracts run through a small driver which calls the fixture,
waits for its locals and test shims to unwind, then calls
`__lsan_do_leak_check`. Process globals, including the shared `CApi`, still
exist at this point. This tests lost binding allocations during an ordinary
live process. It does not scan for reachable retained state; the matched
live-owner controls and native reference accounting cover that separately.

The native DSOs were not rebuilt with instrumentation. Address checks therefore
cover instrumented Mojo accesses, not every memory access inside cvc5. Leak
checking observes intercepted heap allocations, including the demonstrated
native control. Successful checks do not prove absolute heap leak freedom.
Sanitizer allocation costs also invalidate the ordinary RSS budgets, so the
RSS retention fixture remains in the production-allocator matrix.

### Native findings retained separately

| Finding | Attribution and scope | Reproduction |
|---|---|---|
| Two 8-byte allocations lost at native library unload | Reproduces with only C `dlopen`/`dlclose`, without Mojo or cvc5 API calls; loader-stack frames identify native library initialization | `tests/binding/sanitizer_loading.c`; unsuppressed result in sanitizer report's `native_shutdown` |
| `cvc5_new(NULL)` crashes | Native constructor dereferences the absent mandatory term manager; public Mojo `Solver` construction requires a valid `TermManager` | Direct call to the pinned C constructor; binding fault fixture instead uses a checked native error |
| Grammar formatting growth | Reproduces in matched direct C; repeated `String(grammar)` invokes the native formatter twice under Mojo 1.1 | [Matched binding controls](binding-controls.md) |
| Repeated synthesis-query growth | Reproduces in direct C as well as Mojo | [Family controls](family-controls.md) |
| Anonymous parameter-sort creation and sort-inequality output | Existing native C limitations | [Compound FFI report](compound-ffi.md) |

The native unload leak is **not** reported as a clean test. Its separate
diagnostic accepts either clean shutdown or the exact known 16-byte/two-object
finding; crashes and changed findings fail classification. It uses no leak
suppression. The binding gate checks its fixture-scope allocations separately.
No engine patch, library preloading workaround, or solver recycling policy is
introduced into the bindings.

### Mixed parser term managers: early rejection

`InputParser(solver, sm)` previously accepted a solver and symbol manager created
from different term managers. The pinned native parser permits this, but terms
it creates belong to the solver's manager. The C symbol-manager getter exports
them through the symbol manager's manager. Direct C can therefore retrieve a
term and immediately fail to use it with the exporting manager, even with all
owners still alive. Using the solver's original manager succeeds.

`tests/binding/mixed_managers.c` reproduces both the shared-manager success and
the mixed-manager inconsistency. The recorded command and output are in
`.cache/autonomous-mixed-managers/report.json`. This rules out changing the
borrowed wrapper's remembered manager to the symbol manager's as a sufficient
fix. No such metadata change is retained. Detached mixed-manager handles do not
have an established lifetime guarantee in the native interface.

The approved binding policy now raises an early recoverable error from
`InputParser(solver, sm)` when an explicit `sm` has a different native manager
pointer from `solver`. It compares native identity, so copied and borrowed
wrappers of the same manager remain valid. The error is
`cvc5_mojo: InputParser solver and symbol manager must share a term manager`
and occurs before calling the native parser constructor. Omitted symbol
managers and explicit `None` keep the existing path.

`Model.owner_guards` derives the owner parameters from their generated types
and checks additional owners against the first required owner's manager.
In the pinned API only `InputParser` has multiple such parents. The generator
adds no wrapper state, native lookups, or extra references. Regeneration changes
only `input_parser.mojo`; the snapshot and dependency lockfile stay unchanged.

The extended constructor fixture checks rejection for owned, copied and
borrowed mismatched parents, with zero native parser-constructor attempts.
It verifies recovery, all shared-parent forms, omitted/explicitly absent symbol
managers, and parsed terms surviving the entire wrapper graph. The mismatch
regression failed as intended on all four O3 configurations before the fix.
After the fix all 16 O0/O3 ownership/constructor configurations passed.
All four O1 sanitizer constructor configurations also passed, following all five
sensitivity controls. These reports are `.cache/parser-guard-contracts` and
`.cache/parser-guard-sanitizers`; the failing-before-fix report remains at
`.cache/parser-guard-red`. The separate native shutdown diagnostic still reports
the known 16-byte leak.

## Remaining generator review

The audit covered argument marshaling, return receipt, overload dispatch,
checked native calls, trait-required nonraising methods, and manual fragments.
The preceding collection/receipt work and this constructor pass now share the
duplicated mechanisms that warranted consolidation.

Ordinary overloads still use `Model.input_params`, `Model.results`, and the shared
call emitter. List and variadic variants share the input conversion policy.
Raw native-error handling is centralized in the raw generator. Nonraising
copy/destruction/formatting traits deliberately abort after a checked error;
raising methods propagate it. Their different surrounding control flow does
not justify another runtime layer merely to shorten emitted code. Manual
statistics traversal retains its scope-bound reference guard and shared value
decoder. No additional public API or owner-anchor redesign was needed.

## Repeatable commands and artifacts

After the pinned dependencies are installed, these commands do not fetch:

```bash
pixi run --locked verify-binding --tier core --output .cache/verify-core
pixi run --locked verify-binding --tier extended --output .cache/verify-extended
```

The core tier regenerates from cached inputs, checks completeness and generator
mutations, runs every contract at O0/O3 across both import and assertion modes,
checks loading, smoke/lifetime/thread/leak tests, translated upstream tests,
documentation examples, and the strict rendered-site audit. The docs environment
must already exist at `.pixi/envs/docs`. Generated files and translated call
accounting must remain unchanged. Full fetching and refreshing the Python
oracle remain separate, existing workflows.

The extended tier adds sensitivity-qualified O1 sanitizer contracts, 1,000
conversion-failure rounds, 5,000 ownership rounds, six seeds with 2,048 generated
operations each, independent-thread stress, and larger paired memory runs.
Live-owner controls use 200,000 and 1,000,000 iterations for eight handle
workloads, and 20,000 and 100,000 iterations for statistics workloads. Whole
graphs use 100 and 1,000 iterations. Counts reflect workload cost: an initial
million-snapshot statistics probe exceeded its three-minute timeout after
750,000 iterations with 8 KiB RSS growth. That incomplete run is preserved,
not counted as a pass; the replacement controls retain the same memory budgets.
The overhead benchmark runs last, with nine repetitions. `--list` prints the
commands; `--only` selects exact gate names. Reports are checkpointed, incomplete
runs cannot pass, and a failed gate stops the runner with a nonzero status.
Use a fresh output directory for each run.

`.github/workflows/binding-extended.yml` runs weekly or manually and uploads
reports, traces, mappings, sequence reproducers and timing baselines for 30 days.
It prepares pinned dependencies explicitly before invoking the cached runner.
The workflow has been defined locally; no remote run or publication is claimed.

The overhead runner accepts `--baseline <saved-report.json>`. It rejects
incompatible protocols, machines, compilers, relevant settings, dependency/fixture hashes, failed
runs, and reports with fewer than seven repetitions. It compares the existing
paired wrapper-minus-checked-C bootstrap intervals. Nonoverlap is a candidate
change to confirm on the same idle host, not a universal regression threshold.
Between-run drift and multiple comparisons remain limitations. CI preserves
the measurements without introducing a flaky percentage gate.

## Verification results

The translated upstream suite passed **346 tests in 17 files**, **20 examples**,
**five compile-fail checks**, and **ten documented failures** reproduced as
expected. It reached 366 native functions without changing `calls.json`.
Cached regeneration preserved all binding sources, snapshot files, translated
tests, and the dependency lockfile against the pre-pass hashes.

The cached matrix completed on 2026-10-08:

| Gate | Result | Evidence under `.cache/` |
|---|---|---|
| Core contracts | 96 O0/O3 configurations passed; updated null/value and conversion fixtures each passed their eight-configuration rerun | `autonomous-core/contracts`, `autonomous-value-semantics`, `autonomous-conversion-corrected` |
| Runtime/loading, smoke, lifetimes and threads | Eight runtime build configurations and all five ordinary smoke targets passed | `autonomous-core` |
| Standalone leak fixture | 520 KiB growth over 200 rounds, below the 4,096 KiB fixture budget | `autonomous-leaks-standalone` |
| Sanitizer contracts | 40 selected O1 configurations pass after corrected conversion and updated value-semantics reruns; all five sensitivity controls passed | `autonomous-sanitizers`, `autonomous-sanitizers-corrected` |
| Extended ownership and conversion | 5,000 borrowed/error graph rounds per ownership configuration; 1,000 conversion-failure rounds per conversion configuration | `autonomous-extended/ownership-stress`, `autonomous-conversion-stress-corrected` |
| Extended generated sequences | Six seeds × 2,048 steps, across four Mojo build configurations and raw/public layers, checked against direct C and the independent model | `autonomous-extended/sequences-long` |
| Extended independent threads | 320,000 worker rounds across four build configurations and ten fresh processes each | `autonomous-extended/threads-long` |
| Matched live-owner memory | 96 runs, 57.6 million iterations; maximum binding excess growth over C 344 KiB | `autonomous-memory/matched-live` |
| Matched statistics memory | 24 runs, 1.44 million iterations; maximum excess growth 344 KiB | `autonomous-memory/matched-statistics` |
| Matched whole-graph memory | 72 runs, 39,600 graphs; maximum excess growth 560 KiB | `autonomous-memory/matched-round` |
| Performance baseline | All 17 workloads passed, nine repetitions, with call-trace and allocation diagnostics | `autonomous-performance/overhead` |
| Generator/tooling/docs | 15 generator, 41 binding-tooling and 11 soak-tooling unit tests; 16 compiled documentation configurations; strict site audit | `autonomous-closeout`, `autonomous-core/docs-examples` |

The three matched memory matrices passed their retained-reference sensitivity
controls and native-call comparisons. Their 4,096 KiB absolute-growth and
1,024 KiB excess-growth budgets are fixture checks, not a recommended worker
memory limit. Sanitizer scope and native shutdown findings remain as described
above.

Initial failed/incomplete reports are preserved. `autonomous-core` initially
failed its docs invocation because it used the default Python environment;
the corrected docs gate uses the cached docs environment. The standalone leak
fixture was rerun using the manifest's compiled-binary command, avoiding JIT
compiler memory masking the RSS measurement. The original sanitizer/conversion
failure was the fixed reference-ledger capacity limit. The incomplete extended
statistics run was replaced by the bounded statistics matrix described above.
Counts use the corrected reruns for affected configurations; the original root
reports are not relabeled as successful.

This pass's generator consolidation preserves generated runtime bytes, so no
runtime speedup is claimed for it. The final baseline measures approximately
23.6 ns for a public scalar getter versus 22.8 ns for checked C, 66.2 versus
60.9 ns for handle copy/release, and 1.40 µs for `term.toString()` versus
2.85 µs for `String(term)`. The latter still performs two native formatting
calls under Mojo 1.1, while benefiting from the earlier shared-buffer changes.
These are local baseline medians, not portable timing guarantees.

The mixed-parser-manager decision was subsequently approved and implemented
as described above. Reuse these gates on supported toolchain bumps. Packaging
and changes to native cvc5 remain outside the approved plan.

## Review of accumulated changes

The follow-up reviewed the accumulated generator/extraction changes, raw error
and loading paths, owner anchors and receipt, manual string/statistics/numeric
conversions, generated-output consistency, test failure classification,
benchmark evidence, and CI commands. It found a verification-tooling defect:
the shared command helper killed only the immediate process on timeout and
discarded its output. A child could remain running and affect subsequent tests
or timings. A regression reproduced this before the correction.

The helper now starts each command in its own process group, preserves captured
output on timeout, and uses the same group-stop routine as the soak monitor.
Cleanup finishes with SIGKILL even if the leader has already exited after
SIGTERM, so an ignoring descendant cannot keep running in that group. Processes
that create a separate session remain their own supervisor's responsibility.
The regression checks both the ignoring descendant and ordinary exit-code and
stream preservation. Timeout still has `returncode: null` and cannot pass.
The review's generator/tooling regressions passed 69 tests (15 generator,
43 binding-tooling, 11 soak-tooling). Follow-up regeneration, upstream and docs
verification is recorded in `.cache/parser-guard-review`.

No further blocking binding defect was found in the reviewed changes. This is
bounded by the pinned Linux toolchain and the instrumentation limitations above.
Native findings remain open; the earlier evidence is not a claim that all native
engine allocations or unsupported platforms have been audited. The subsequent
clean-source validation is recorded below; publishing and packaging remain
separate actions.

## Clean-source local CI, 2026-10-08

All **25 executable CI-equivalent gates passed** in a fresh source/build export.
The export contained the current 285 tracked and untracked source files, with
independent copies of 153 cached dependency files. It started without project
build outputs, test reports or Python bytecode caches, and reused the installed
locked toolchain environments. No dependencies were fetched or updated.

The run regenerated the Python oracle with the already installed pinned Python
bindings, including null-formatting observations and example `.out` files.
It then ran the existing core verification tier and the CI workflow's additional
benchmark, matched-control and module-precompilation commands. Task bodies were
used without their fetch dependency DAG. Because the reviewed changes are still
uncommitted, source hashes supplied the regeneration check in place of CI's
clean-Git-status check.

| Gate | Clean-source result |
|---|---|
| Regeneration and source integrity | No generated-output drift; all 285 exported source files, the original working files, and all copied dependency inputs retained their hashes during validation |
| Generator and tooling regressions | 69 tests passed |
| Contracts and runtime loading | 96 O0/O3 contract configurations and eight runtime build configurations passed |
| Smoke, lifetime, thread and standalone leak checks | All passed; standalone leak fixture growth was 512 KiB over 200 rounds against a 4,096 KiB budget |
| Translated upstream suite | 346 tests, 20 examples, five compile-fail checks and ten documented failures reproduced as expected; 366 native functions reached with unchanged `calls.json` |
| Documentation | 16 compiled example configurations and the strict rendered-site audit passed |
| Benchmark semantics | All 17 general workloads and five statistics workloads passed; one repetition checks semantics and does not establish a new timing baseline |
| Matched live-owner controls | 30 runs / 600,000 iterations passed; maximum excess growth over C was 344 KiB |
| Matched whole-graph cleanup | 18 runs / 1,800 graphs passed; maximum excess growth was 372 KiB |
| Module build | The CI `package` task precompiled `cvc5_mojo.mojoc`; distribution recipe work remains deferred |

Both matched-control matrices also passed retained-reference sensitivity and
native-call comparisons. The full run took about 23 minutes. No binding or
verification-code correction was needed. This result summary was added to the
documentation afterwards and checked separately.

`.cache/clean-ci-location.json` in the original checkout identifies the export.
Its `.cache/clean-ci/manifest.json` records source and dependency hashes, and
`.cache/clean-ci/report.json` records commands, output and outcomes. The original
checkout also retains `.cache/clean-ci-evidence.json` with the report hash.

This was a local equivalent of the build and documentation CI checks on the
cached Linux toolchain. It did not exercise GitHub Actions infrastructure, a
fresh dependency installation, artifact publication or deployment. The next
step is a committed revision and hosted CI before release. No commit or push
was performed; the known native findings above remain separately tracked.
