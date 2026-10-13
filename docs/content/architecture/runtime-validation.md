# Initialization, loading, and thread isolation

This pass strengthens the existing loading runner and POSIX-thread fixture
using the cached Mojo 1.1.0 and cvc5 1.4.1 dependencies. All eight build
configurations pass. No binding implementation defect was reproduced, and
the 23 binding source files are unchanged from the
[compound FFI pass](compound-ffi.md).

## What changed

`scripts/check_runtime_loading.py` now builds both loading and thread
fixtures from source and precompiled imports, with assertions enabled and
disabled. O3 remains the default; O0 is selectable and also runs in CI.
Every case runs in a fresh process with an explicit timeout. The runner
reuses the existing build/process helpers, source fingerprinting, and
loaded-library identity checks. It saves each invocation in a fresh child
directory and writes its completed report to the requested output directory.

The loader fixture exercises the public cached API twice. Instrumented
failure cases additionally construct the internal `CApi` directly 20 times
to force repeated initialization and unwinding. Direct construction is a
test mechanism, not a new public loading or recovery API.

| Loading case | Required result |
|---|---|
| Explicit absolute and relative library paths | Successful calls using the cached library bytes |
| Checkout fallback | Successful loading from the repository root |
| Installed-layout prefix containing spaces and Unicode | Successful loading from outside the repository root |
| Explicit selection plus incomplete prefix | Explicit selection wins |
| No selection outside a checkout | Recoverable not-found error |
| Bare library filename without a directory | Recoverable path-validation error |
| Nonexistent explicit library | Recoverable load error, without fallback |
| Missing parser beside explicit main library or prefix main library | Recoverable error, without borrowing the checkout's parser |
| Missing early/late main-library symbol or late parser symbol | Eager failure naming the missing symbol |
| Wrong version | Rejection before the API is exposed |
| Invalid UTF-8 in the version string | Recoverable decoding failure with bootstrap cleanup |

The missing-symbol fixtures derive symbol names and library assignments from
the existing extracted snapshot and raw classification. Their exported
bodies abort if called: these fixtures test resolution failure before any
fabricated API implementation is used. Version fixtures forward real
bootstrap constructors and destructors to the cached cvc5 library, replacing
only the version result. They are isolated test libraries, not changes to
cvc5 or to production loading.

## Cleanup evidence

Test DSOs append constructor/destructor events to an isolated file. The Mojo
fixture then writes a checkpoint before returning from `main`. Failed
initializations must have unloaded every instrumented DSO **before that
checkpoint**; cleanup deferred until process exit fails. Serial cached
failure must initialize once, while direct construction must initialize and
unwind all 20 times. Concurrent initialization may make multiple attempts.

Version fixtures also record completed creation and destruction of the
temporary solver and term manager used to read the version. Function
signatures and owner lifecycle pairs come from the snapshot and the existing
lifecycle extractor. Each owner category must balance independently of DSO
events, with no destruction preceding creation.

This checks native bootstrap ownership and final DSO reference release on
the instrumented failure paths. It does not count every `dlopen` reference
while a successful cached API remains resident, instrument Mojo heap
allocations, or establish that every library path is leak-free. The cached
successful API intentionally lives until process exit.

## Thread protocol

`tests/smoke/test_threads.mojo` starts 16 workers together at a barrier.
Successful workers verify that all calls return the same cached `CApi`
pointer, while each worker creates and owns its own native object graph.
Every round does the following:

1. Half the workers call an unchecked native function to leave an error
   pending; the other half leave their native error state clean.
2. All workers rendezvous before checking their state. Only the designated
   workers may observe an error. Roles alternate each round.
3. The binding's `_check` must raise and clear each pending error. Its
   message must contain that worker's unique identifier, round, and Unicode
   text. Clean workers must remain clean.
4. After another rendezvous, every worker uses the normal public API to
   trigger, catch, and clear its own error, then successfully checks both a
   satisfiable and an unsatisfiable formula.

The private unchecked call is limited to the test's deliberate pending-error
phase. Production calls retain their normal checks. Context storage and
input buffers remain alive across untracked pointers, all workers are
joined, and the barrier is destroyed. An unexpected worker failure aborts
the isolated test process so other workers cannot remain stranded at a
barrier and appear successful.

Every loading failure also runs with 16 concurrent first users. Each worker
repeats access 50 times and must receive the same cached diagnostic; the
parent compares messages across workers. Once initialization fails, its
error remains cached for that process. Correct loading configuration before
starting the process; no retry/reset API was added.

## Results on 2026-10-07

| Measure | Result |
|---|---|
| Build configurations | 8: source/package × O0/O3 × assertions enabled/disabled |
| Executables | 16: loading and threads in each configuration |
| Isolated processes | 272 passed: 168 serial loader cases and 104 thread cases |
| Successful concurrent runs | 24 fresh processes, three per build configuration |
| Error/recovery rounds | 19,200 across successful workers, including 38,400 solver checks |
| Cached-failure accesses by workers | 64,000 across 80 failure processes |
| Direct initialization failures | 960 attempts across the six instrumented failure cases |
| Cleanup-checked processes | 144 passed |
| Instrumented bootstrap owners | 592 solvers and 592 term managers created and destroyed before the checkpoint |

All version-failure thread runs exercised 16 competing initializers. Every
temporary native owner was released, and the instrumented library was
unloaded before the parent checkpoint. No cross-thread error contamination,
inconsistent cached API pointer, unexpected crash, or timeout occurred in
the final matrix. An early pilot had a missing test import for `abort`; it
failed compilation and was corrected before the accepted matrix.

The failure-classification unit tests reject crashes, timeouts, unrelated
diagnostics, incomplete thread counts, wrong round counts, missing cleanup,
double destruction, and cleanup postponed until exit. Native growth and C
API limitations from previous passes remain open; no engine workaround or
public API change was introduced here.

Broader validation passed all 28 O3 contract configurations, 37 generator
and runner analysis tests, all 16 documentation-example configurations, and
strict documentation/link checks. The full translated upstream suite and
heap profiling were not rerun in this pass.

Local evidence:

- `.cache/runtime-matrix-01/report.json`: matrix, commands, source and
  dependency hashes, native fixture builds, outputs, events, and successful
  process library mappings;
- `.cache/runtime-verification/summary.json`: investigation index and
  broader regression results;
- `.cache/runtime-pilot-01` and `.cache/runtime-pilot-02`: initial pilot
  diagnostics and corrected serial/concurrent checks.

## Running the checks

This direct command uses cached dependencies without invoking a fetch task:

```sh
pixi run --locked python scripts/check_runtime_loading.py --output .cache/runtime-new --optimization 0,3 --jobs 4 --repetitions 3 --rounds 50
```

`--repetitions` controls fresh successful thread-start processes, and
`--rounds` controls work per worker. The regular `runtime-test` task runs
both import routes and assertion modes at O3; CI and the cvc5 update workflow
also run O0. The ordinary smoke task still runs the same strengthened thread
fixture once.

## Next step

The subsequent [generated-sequence pass](generated-sequences.md) adds
deterministic C/raw/public operation streams with an independent arithmetic
model and bounded failure reduction. Next measure binding overhead against
the same cached C build, preserving these correctness checks as regression
gates.
