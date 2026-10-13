# Production-like soaks

**Scope update, 2026-10-07:** these are historical diagnostic experiments.
The active [binding development plan](../contributing/roadmap.md#binding-development-plan)
focuses on API correctness, ownership, matched C/Mojo memory measurements,
and binding overhead. Solver recycling and CAS worker policies are outside
the current project work; no automatic recycling was added to the bindings.

The soak harness exercises service lifetimes and checks results throughout
each run. These are synthetic CAS workloads, not a replay of an application
corpus. They complement the upstream tests and the shorter boundary
regressions described in [verification](verification.md).

## Running with cached dependencies

The `soak` task never calls `fetch`. It uses the installed Mojo environment,
the apn_mojo package installed by Pixi, and the cached cvc5 libraries.
Reports record the installed apn_mojo version, build, URL, and archive
checksum, and hash its precompiled artifact alongside the workload inputs.
Each run requires a new output directory:

```sh
pixi run --locked soak --output .cache/soak-01 --seconds 180 --warmup 15 --jobs 3 --seeds 1,4093
```

Use `--only bounded-jobs` to select a workload, and `--route source` to build
against source instead of the precompiled package. Short probes can use
`--seconds 3 --warmup 1`; runs shorter than one minute check correctness but
do not establish a memory plateau. The starting offsets are deterministic;
they are not random fuzzing seeds.

`report.json` records input and dependency hashes, the compiled binary hash,
toolchain pins, concurrency, budgets, and per-workload results. Each workload
also writes per-second TSV checkpoints, stdout, stderr, and its own JSON
record. The checkpoints survive a watchdog stop.

## Workloads

| Mode | A request checks | Owner lifetime |
|---|---|---|
| `incremental` | Two exact integer model values, a nested contradiction, an unsat core and proof children, then successful solving after pop | One solver and term manager; constants cycle through a bounded vocabulary |
| `term-churn` | The same checks, with fresh integer constants on every request | One solver and term manager; exposes retention of new expressions |
| `algebra` | Rational distributivity is valid; dropping the cross term from a square has a verified counterexample | One solver and term manager; bounded rational coefficients |
| `parser` | Reused SMT-LIB input, exact integer and Unicode/NUL string models, push/pop, and recovery after a malformed command | One parser, solver, symbol manager, and term manager |
| `bounded-jobs` | Eight changing-constant integer requests and one algebra request | Fresh owner graphs for each job |
| `solver-batches` | The same bounded-job checks | Integer solvers are recreated after eight requests while their term manager remains alive |
| `synthesis-bounded` | A finite grammar for affine integer functions, both solution and no-solution cases; a separate SMT solver verifies every returned solution | Fresh term manager and solvers per request |
| `resource-limits` | A hard query returns `unknown` with `RESOURCEOUT`; after resetting assertions, the same solver proves a simple contradiction unsatisfiable | One solver with a fixed per-query resource limit |
| `synthesis-shared-tm` | The same synthesis specification as the bounded case | Diagnostic control: fresh solvers share one term manager |

The generated bindings are built at O3 with `--Werror` and assertions enabled.
Workers are separate processes. This does not test sharing cvc5 objects
between threads; each worker owns its object graph.

## Measurements and gates

Warmup runs before the measured window. Afterward, the harness records RSS,
completed requests, cumulative request time, maximum request time, and a
base-two latency histogram. Reported percentiles are histogram upper bounds,
not exact quantiles. A request includes term construction, native calls,
conversion, and correctness assertions. The workloads do different amounts
of work, so their request rates are not directly comparable. Concurrent
workers and other activity also affect latency.

The default memory budgets are set before the run:

- peak RSS growth after warmup: at most 32 MiB;
- median RSS drift between the first and last quarters: at most 8 MiB;
- RSS slope in the second half: at most 64 KiB/second;
- absolute per-process RSS: at most 512 MiB, including warmup.

Most solvers have a one-second per-query time limit. An outer watchdog stops
a process that exceeds its warmup and measurement time by 20 seconds.
`resource-limits` deliberately exercises a much smaller resource budget.
Unexpected results, assertion failures, crashes, and watchdog timeouts fail
the run. `unknown` is accepted only where the workload explicitly expects
resource exhaustion.

The shared-term-manager synthesis control is reported separately, including
any deliberate RSS stop. It cannot turn an unrelated runtime failure into a
passing control. The changing-term workload is a required gate: its known
growth makes a full sweep fail on the current native release. A passing
bounded-job run must not be presented as proof that arbitrary long-lived
solver usage is bounded.

RSS budgets detect sustained growth in these workloads; they are not an
allocation proof or an hours-long reliability qualification. Bounded-input
tests deliberately separate wrapper retention from legitimate growth in an
application's retained expression graph. The changing-term case checks what
happens when the application drops its per-request values but keeps owners.

## Operational guidance

Treat `unknown` separately from `sat` and `unsat`. Set resource limits before
the solver is initialized; cvc5 rejects changing `rlimit-per` afterward.
The tested recovery path resets assertions with the original limit still in
place. It does not establish rollback for arbitrary failed operations.

Release results, proofs, grammars, terms, parser commands, and borrowed owners
when retiring a job. These values can keep an owner graph alive. Returning a
small application value or serialized result lets that graph be released.
In the tested arithmetic workload, recycling the solver every eight requests
kept memory stable while retaining its term manager. `pop()` removed all
assertions but did not bound memory. The Python controls also grew with
periodic `resetAssertions()` and with proof production disabled. The tested
batch size is evidence for the lifecycle choice, not an optimum for throughput.
Repeated synthesis requires bounding both solver and term-manager lifetimes
on the tested native release. See [runtime](runtime.md#arrays-and-leaks).

`tests/soak/native_oracle.py`, run in the cached `oracle` environment, repeats
the synthesis and changing-term checks through the official Python bindings.
It reuses the same measurement analysis while implementing the specifications
independently. The Python wheel and the release libraries used by Mojo are
different builds, so these controls establish whether growth also appears
outside Mojo; they are not matched-build speed comparisons.

## Measurements on 2026-10-06

The baseline matrix used two starting offsets, 15 seconds of warmup, and
180 measured seconds per workload, with three concurrent workers. Follow-up
controls and compilations overlapped parts of the run. The cloud container
had a four-CPU quota, so the recorded latency includes contention. All runs
used the cached Mojo 1.1.0 and cvc5 1.4.1 dependencies.

The twelve baseline runs completed **6,199,348 checked workload iterations**.
No incorrect result, crash, or unexpected native timeout was observed.

| Baseline workload | Iterations across both runs | Largest post-warmup RSS growth | Memory gate |
|---|---:|---:|---|
| Incremental models, cores, and proofs | 934,603 | 36 KiB | Passed |
| Algebraic equivalence and counterexamples | 2,419,280 | 24 KiB | Passed |
| Parser and string models | 634,819 | 20 KiB | Passed |
| Bounded jobs | 16,339 | 368 KiB | Passed |
| Bounded synthesis | 40,658 | 424 KiB | Passed |
| Resource exhaustion and recovery | 2,153,649 | 516 KiB | Passed |

The initial matrix used bounded constants inside bounded jobs. Follow-up runs
used the current changing-constant job implementation. Each lasted another
180 measured seconds after warmup:

| Follow-up | Completed work | Post-warmup RSS growth | Result |
|---|---:|---:|---|
| Fresh owner graphs per job | 6,222 jobs | 40 KiB | Passed |
| Recycle integer solver every eight requests; retain term manager | 6,782 jobs | 116 KiB | Passed |
| Keep solver alive while introducing new constants, offset 1 | At least 162,425 requests in 88 measured seconds | 407.6 MiB | Stopped by the 512 MiB RSS watchdog |
| Same growing workload, offset 4093 | At least 164,363 requests in 150 measured seconds | 412.2 MiB | Stopped by the 512 MiB RSS watchdog |

The stopped runs failed the memory gate. Their counts come from the last
complete checkpoint before termination and exclude warmup. They do not count
as completed 180-second runs. The watchdog cap includes the process's initial
RSS; the table reports growth after warmup.

The shared-term-manager synthesis controls completed 1,112 and 2,485 requests
in 30 measured seconds, growing by 29.5 and 65.2 MiB. Official Python controls
reproduced both growth patterns: changing-term arithmetic added 79.2 MiB in
30 seconds, and shared-term-manager synthesis added 115.4 MiB in 60 seconds.
Bounded Python controls remained stable. These observations support a native
owner-lifetime limit rather than a Mojo-specific retained-handle defect.

The source import route passed short correctness probes for all nine modes;
the sustained runs used the precompiled package route. The six analysis
regressions and strict documentation check passed. The complete sweep is
**not memory-clean**: the changing-term failure remains a deliberate visible
gate. This pass changes tests and operational guidance, not the native engine
or the public binding API.

The follow-up at that time was the batch-size experiment below. These runs
do not qualify hours-long service uptime or arbitrary growing application
caches. The scope update above defines the current development direction.

## Comparing recycling intervals

The `batch-benchmark` task isolates the changing-integer workload from the
additional algebra check in `solver-batches`:

```sh
pixi run --locked batch-benchmark --output .cache/batch-screen --requests 8192
```

It reuses the workload's exact model, core, proof, and push/pop checks, the
cached build, and the soak watchdog and trend analysis. A request contains
three `checkSat` calls. A term manager remains alive throughout each process;
only its solver and request-local handles are retired between batches. No
binding API or default owner lifetime is changed.

Every size sees the same monotonically increasing integer input sequence for
each starting offset, beginning again after 512 warmup requests. Batches do
not overlap input indices. The default offsets, 1 and 1,048,576, give two
repetitions, with size order shuffled reproducibly within each repetition.
The default sizes are 1, 8, 32, 128, 512, 2,048, and 8,192. Workers run
sequentially; keep other benchmarks and builds idle during measurements.

With `--seconds 0`, each run completes exactly `--requests` requests, including
a final partial batch if necessary. A positive `--seconds` sets an additional
minimum duration and finishes the last full batch. Use that mode to validate
memory after screening, for example:

```sh
pixi run --locked batch-benchmark --output .cache/batch-validation --sizes 512 --requests 8192 --seconds 180 --timeout 600
```

Throughput uses measured wall time, including solver construction, teardown,
correctness checks, and checkpoint recording. Per-request histograms charge
construction to the first request; use wall throughput when comparing the
full recycling cost. Linux's process lifetime RSS high-water mark (`VmHWM`)
includes warmup and captures peaks between periodic samples. Checkpoints also
retain current RSS so plateau checks can distinguish growth from a peak.

The provisional selection rule is the smallest measured batch reaching 95%
of the fastest eligible median throughput while every repetition fits a
128 MiB absolute process RSS budget. Missing or failed repetitions cannot win.
The existing growth, drift, and slope budgets also apply when a run is long
enough to assess them. These are experimental comparison budgets, not an
application SLO. A short screen's candidate remains provisional until longer
validation establishes a plateau. Timings measure this synthetic workload
and machine, not general binding performance or actual CAS queries.

## Batch-size screen on 2026-10-07

The sequential screen completed 8,192 measured requests for each of seven
batch sizes at each of two starting offsets: **114,688 requests**, with all
correctness checks passing. It used cached Mojo 1.1.0 and cvc5 1.4.1, the
precompiled package route, O3, and assertions. No other benchmark or build
ran concurrently. The container had a four-CPU quota; the host was not
reserved, so repetition ranges matter.

| Requests per solver | Median requests/s | Range across two offsets | Largest lifetime peak RSS |
|---:|---:|---:|---:|
| 1 | 59.5 | 58.8–60.3 | 39.38 MiB |
| 8 | 398.5 | 384.6–412.4 | 37.95 MiB |
| 32 | 1,022.8 | 961.7–1,083.9 | 36.36 MiB |
| 128 | 1,975.0 | 1,940.8–2,009.1 | 34.57 MiB |
| 512 | 2,177.1 | 2,059.1–2,295.1 | 34.48 MiB |
| 2,048 | 2,075.5 | 1,840.9–2,310.1 | 38.45 MiB |
| 8,192 | 1,911.1 | 1,589.6–2,232.5 | 54.84 MiB |

The 512-request case achieved **5.46×** the eight-request median in this
comparison. This is amortized solver setup and teardown on one workload;
it is not a speedup to the binding implementation. Larger batches increased
memory without improving the median. Most screen runs lasted less than a
minute, so their memory observations alone do not establish a plateau.
Raw records and TSV checkpoints are in `.cache/batch-screen/report.json` and
its directory; reports remain local artifacts rather than source fixtures.

### Refinement

The next sweep used 65,536 measured requests per run, sizes 256, 512, 1,024,
and 2,048, and three offsets (1, 1,048,576, and 2,097,152). All **786,432
requests** passed. Reproduce it with:

```sh
pixi run --locked batch-benchmark --output .cache/batch-refinement --sizes 256,512,1024,2048 --requests 65536 --seeds 1,1048576,2097152
```

| Requests per solver | Median requests/s | Range across three offsets | Largest lifetime peak RSS |
|---:|---:|---:|---:|
| 256 | 1,722.2 | 1,673.8–1,980.1 | 35.02 MiB |
| 512 | 2,238.0 | 2,189.8–2,289.9 | 35.13 MiB |
| 1,024 | 2,110.5 | 2,046.3–2,234.6 | 36.34 MiB |
| 2,048 | 2,323.5 | 2,235.7–2,380.2 | 39.03 MiB |

**512 requests per solver** is the smallest measured interval satisfying
the selection rule: 96.3% of the fastest eligible median throughput, with
all repetitions below 128 MiB. The nonmonotonic rates and repetition ranges
are reasons to treat this as a measured starting policy, not an exact
universal optimum. The screen and refinement use different input lengths;
compare batch sizes within a phase rather than mixing their rates.

Keep per-query resource limits and an external process RSS watchdog alongside
count-based recycling. A request count cannot bound the memory of an arbitrary
large query. Retire all request-local handles before replacing the solver;
escaped values can retain its state. Retaining the term manager is supported
by this arithmetic workload. Synthesis still requires a bounded term-manager
lifetime, as established by the separate controls above.

### Sustained validation of 512

Two further runs each lasted at least 180 measured seconds, completing the
last batch before stopping. Both passed correctness and all memory budgets:

| Starting offset | Requests | Requests/s | Lifetime peak RSS | Post-warmup peak growth | Quarter drift | Second-half RSS slope |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 395,264 | 2,193.5 | 35.45 MiB | 2,824 KiB | 552 KiB | 2.97 KiB/s |
| 1,048,576 | 345,600 | 1,917.1 | 35.63 MiB | 2,736 KiB | 624 KiB | 1.88 KiB/s |

Across the screen, refinement, and validation, **1,641,984 measured requests**
passed (three solver checks per request), excluding warmup and correctness
pilots. The selected policy stayed below 36 MiB in both sustained runs,
against the provisional 128 MiB budget. The residual RSS drift is small but
nonzero; these observations do not prove indefinite memory stability. The
largest timed request in validation was 66.3 ms, and both p99 histogram upper
bounds were 4.195 ms. No application latency SLO has been qualified.

The raw validation is in `.cache/batch-validation/report.json`. The combined
summary, flat CSV, and PNG/SVG figures are in `.cache/batch-report/`; the
refinement records are in `.cache/batch-refinement/`. The eleven analysis
regressions, source-route correctness probes, and strict documentation check
cover the harness changes. The source probes check correctness only; their
timings are not part of the benchmark comparison.

The previously proposed follow-up on concurrent CAS workers is superseded
by the binding development plan. These results remain diagnostics and are
not a binding default or a plan to add application lifecycle management.
