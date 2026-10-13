# Returned collections and iterators

Counted native results now reserve their known size before conversion. The
generator shares one list-building policy for explicit result counts, counts
inferred from input arrays, and count/getter iterators. String arrays share one
runtime decoder with option-information aliases and modes. Public signatures
and eager snapshot behavior are unchanged.

## Conversion and ownership

`bindgen.gen_api._list_result` emits the counted list loop. It appends each
converted value once, retaining the existing `_received` adoption and owner
anchor expressions. Generated iterators read their count once, fetch every
element, then return `OwnedIterator`. That iterator still reverses its private
list and moves elements out with `pop`; it has no new state or lazy native
access. It implements `__next__`, not a second `__iter__` interface.

`_c.ffi.to_strings` is the single decoder for a counted array of native string
pointers. It reserves space and calls the existing validated `to_string` for
each element. The manual `Solver` fragment uses it for option information,
and the generator uses it for returned string arrays. The previous local
`Solver._strings` implementation is removed. Each returned string owns its
bytes before the native storage can be reused.

Generated dictionaries and statistic histograms reserve their native counts
too. Pending-reference cursors and `finally` cleanup in paired output arrays
are unchanged: those native functions export all handles before conversion
starts. If decoding fails, adopted wrappers clean up themselves and the guard
releases the remaining exports.

Count/getter iteration differs: a failed getter has not exported that element
or any later element. Earlier exports are already owned by the temporary
list and are released during unwinding. No tail-release loop is added there.
Allocation failure that aborts the process and malformed raw pointers remain
outside the recoverable-error contract.

The statistics iterator has no native count and retains its existing growing
snapshot. `Statistics.get` still copies that snapshot into a dictionary; this
is a separate measured follow-up, not a reason to introduce a second native
traversal or change snapshot semantics in this pass.

## Boundary and failure checks

The new `returned_collections` fixture exercises term iterators from zero to
257 children, order and repeated exhaustion, detached parent/manager wrappers,
partial consumption, and exception unwinding. Datatype constructors and
selector iterators are also used after their originating wrappers disappear.
Returned assertion arrays survive reset, a subsequent getter, and solver
destruction. Counted string arrays preserve empty and UTF-8 values after the
pointer storage and source bytes are changed and destroyed.

The existing return-conversion adapter now also injects a real native
out-of-range getter error at the first, middle, or last child. It tracks
exports, copies, and releases by address while the parent remains alive.
The successful three-child case exports/releases three references with no
copies. Failure at positions 0, 1, and 2 exports/releases exactly 0, 1, and 2
references. Every case must leave zero outstanding references and successfully
repeat the operation after injection is disabled.

The existing malformed-UTF-8 cases still cover named-term dictionaries,
option-name arrays, option information, statistics, and histograms. The fixture
now checks seven successful conversions and 19 injected failures per graph,
each followed by recovery. CI runs both collection fixtures at O3 and O0;
the existing `--only collections` substring selects input and return fixtures.

## Measurement protocol

The maintained C/raw/public benchmark adds `children-8`, `assertions-32`, and
`option-names`, alongside the existing `values-8`. Controls materialize owned
collections before reading them. The option-name C control checks that every
name is ASCII before treating its byte copy as valid UTF-8; a changed native
character set fails that control. Its checksum checks for `produce-models`;
complete string content and lifetime checks live in the semantic fixtures.

Before and after binaries use the same updated fixture and cached dependencies.
Timings exclude call tracing, allocation instrumentation, and concurrent test
builds. Separate call traces check that native exports and releases match;
the limited libc probe cannot observe Mojo's TCMalloc buffers or establish
whole-heap leak freedom. Paired comparison includes an unchanged scalar
control and validates checksums and loaded-library fingerprints.

## Results, 2026-10-07

Cached Mojo 1.1.0 and cvc5 1.4.1; 50,000 operations after 2,000 warmup
operations per process. The four-layer before/after campaigns passed all
**224 timing observations**. Native-call counts were identical before/after
and matched checked C/raw/public: one count call and eight exports/releases
for iteration, one assertion getter and 32 releases, one model-value getter
and eight releases, and one option-name getter. Native-visible allocation
counts were unchanged; the affected Mojo buffers are outside that probe.

Nine shuffled before/after pairs per workload and import route passed all
**180 comparison processes**. Package runs used CPU 0 and source runs CPU 4;
affinity does not reserve a CPU. Median times below are in microseconds.
Percentage savings are medians of paired observations, not ratios of the
separate medians.

| Operation | Package before → after | Source before → after | Paired interpretation |
|---|---:|---:|---|
| Eight child snapshots and iteration | 1.401 → 1.249 | 1.140 → 1.030 | 16.5% / 11.3% less time; positive savings intervals in both routes |
| 32 returned assertions | 8.001 → 6.975 | 6.633 → 5.838 | 3.4% / 9.2% less time; only the source interval excludes zero |
| Eight model values | 9.152 → 7.935 | 6.988 → 6.475 | Savings intervals cross zero in both routes |
| Option-name string array | 56.010 → 56.076 | 48.978 → 45.695 | Savings intervals cross zero in both routes |
| Unchanged scalar control | 0.032 → 0.029 | 0.029 → 0.029 | Savings intervals cross zero in both routes |

Descriptive bootstrap intervals for median paired savings on iteration are
**0.198–0.416 µs** (package) and **0.051–0.502 µs** (source). The assertion
array intervals are **−0.666–2.952 µs** and **0.326–1.070 µs**. These support
an iteration improvement; they do not establish a general returned-collection
or string-array speedup. Dictionaries and option information have correctness
and failure coverage here, without dedicated timing data. These measurements
also do not predict whole-solver throughput or prove total allocation savings.

Artifacts:

- `.cache/returned-{baseline,after}-package/report.json`: four-layer timings,
  call traces, limited allocation diagnostics, and provenance.
- `.cache/returned-{baseline,after}-source/inputs.json`: source build metadata.
- `.cache/returned-probe/paired-comparison.json`: every paired observation,
  variation and bootstrap interval; `compare.py` beside it retains the
  experiment using the maintained measurement/statistics/identity helpers.

## Repeated failure cleanup

All eight source/package, O0/O3, and assertion configurations completed
100 measured complete graphs after ten warmup graphs each. These **800
measured graphs include 15,200 injected failures**, with zero outstanding
tracked native references and no unmatched or duplicate releases. The checks
run while the originating owners are alive; whole graphs are then destroyed.

Post-warmup RSS growth ranged from **68 to 136 KiB**, within the existing
4 MiB test budget. The address-level counts establish release of the
instrumented references; RSS also exercises repeated allocation and cleanup
of partial Mojo collections. This does not prove whole-heap leak freedom or
resolve earlier native growth findings. Per-configuration results and binary
runs are recorded in `.cache/returned-soak/report.json`.

## Integration verification

The full O3 contract suite and targeted O0 snapshot, return-conversion, and
compound checks passed **56 distinct fixture/route/assertion/optimization
configurations**. The repeated-failure campaign above strengthens the
return-conversion subset. All **34 binding-analysis unit tests** and **10
generator tests** passed.

The translated upstream suite passed **346 tests in 17 files**, **20 examples**
with matching Python output, and **five compile-fail checks**. Its **ten existing
documented failures** were reproduced, with no unexpected or stale exclusions.
The recorded inventory remains 366 C functions and is byte-identical to the
pre-pass inventory. All **16 documentation-example configurations** passed.

A second cached-snapshot generation left all 23 Mojo source files identical.
Mirrored class method declarations are unchanged. Recorded source, dependency,
and benchmark binary hashes were checked against the files used for this pass.

Reports are in `.cache/returned-integration`, `.cache/returned-debug`,
`.cache/returned-compound-debug`, `.cache/returned-upstream`, and
`.cache/returned-docs`; each contains `report.json`. Unit-test logs,
regeneration hashes, and input verification are in `.cache/returned-probe`.
This pass did not rerun the separate runtime-loading or concurrency campaigns,
and it does not provide whole-heap allocation attribution.

## Reproduce with cached dependencies

These runners do not invoke the dependency-fetch task:

```sh
pixi run --locked python scripts/run_contract_tests.py \
  --only returned_collections --optimization 0,3 \
  --output .cache/returned-<fresh-name> --jobs 4
pixi run --locked python scripts/run_contract_tests.py \
  --only return_conversion --optimization 0,3 --conversion-iterations 100 \
  --output .cache/returned-failures-<fresh-name> --jobs 4
pixi run --locked binding-benchmark \
  --modes values-8,children-8,assertions-32,option-names \
  --output .cache/returned-benchmark-<fresh-name> --route package \
  --operations 50000 --warmup 2000 --repetitions 7 --cpu 0
```

## Next priority

The [statistics pass](statistics-snapshots.md) measures `Statistics.get`'s
intermediate snapshot and value copies and reserves result dictionary capacity
while preserving filtering, order, independent values, and failure cleanup.
The [general benchmark](binding-overhead.md#workload-isolation-2026-10-07) now
isolates compiled workloads. The [handle-receipt audit](handle-receipt.md)
centralizes receipt and anchor generation. Next audit pointer-owned construction
and borrowed-owner state initialization. Whole-heap allocation
attribution and the native grammar-formatting/repeated-synthesis growth findings
remain open.
