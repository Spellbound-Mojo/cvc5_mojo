# Statistics snapshot costs

`Statistics.get` reads every selected statistic into a temporary
`List[Tuple[String, Stat]]`, then copies the names and values into a dictionary.
Those value copies include strings and histogram dictionaries. This pass
measures that cost and evaluates changes against preserved baseline binaries.

## Retain the shared snapshot traversal

The manual `Statistics` fragment remains the owner of statistics conversion.
The retained change reserves the result dictionary's capacity using the
snapshot's known length. The native traversal, intermediate list, value copies,
and public iterator implementation remain in place. Public signatures,
filtering defaults, insertion order, and eager snapshot behavior are unchanged.
There is no extra native count pass.

The existing `_StatReference` guard releases the current native reference on
success or unwinding. Names are copied before another native call can invalidate
the name buffer. Decoded values belong to the snapshot, so a later decoding
failure destroys already decoded strings and histograms. Successful `get`
results remain independently owned values.

A shared traversal specialized to build either a dictionary or a list was
also evaluated. It removed the intermediate list and value copies, but the
initial fixture showed an apparent iteration slowdown for both that design
and the capacity-only change. Since the latter leaves iteration untouched,
those measurements did not isolate the intended library change. They are
retained as diagnostic artifacts, not accepted speedup or regression evidence.
The more complex direct builder was not retained; the final comparison below
uses separate compiled timing loops and the smaller capacity change.

The pinned Mojo compiler also rejects transferring individual tuple members
through the existing accessor. Consuming the snapshot without copying its
members would need a different internal representation or traversal design.
That is not part of the retained capacity change.

## Behavior and failure checks

The existing `returned_collections` fixture now checks all four filter
combinations for solver and term-manager statistics. It compares dictionary
order and values with filtered iteration and independent indexed lookups.
It interleaves reads through copied statistics handles, then checks that saved
iterators still contain their full snapshot. Dictionaries and iterators are
used after the native statistics, solver, and term-manager wrappers disappear.
All four value types are exercised; mutating one dictionary's string or nested
histogram must leave a separately obtained snapshot intact.

The existing return-conversion adapter adds malformed names during iteration,
histogram decoding inside `get`, and string decoding at the first, middle, and
last string-valued statistics. Name failures during `get` remain covered.
Each failure checks exported references by address, requires matching releases
without native copies, and repeats the valid operation after disabling the
fault. These complement direct string/histogram lookup failures already in
the fixture. Production code has no error-injection hooks.

## Measurement protocol

`scripts/benchmark_statistics.py` builds against cached dependencies and reuses
the existing workload builder, input fingerprints, library identity checks,
timing validator, and paired bootstrap statistics. Its fixture independently
counts native filtered entries before timing. Each mode has its own
compile-time specialization of a non-inlined timing function, so dictionary
and iterator paths do not share a runtime branch inside the timed loop.
Checksums require the public
result to contain exactly that many entries. Detailed values and mutation
semantics are checked by the contract fixture outside the timing loop.

The fixed arithmetic problem is solved once before timing. Each operation
reads an already obtained statistics snapshot. Modes cover all four filter
combinations and iteration. The benchmark is a public-wrapper before/after
comparison; it does not claim a matched C dictionary implementation or measure
solver throughput. It also does not count allocations in Mojo's allocator.

When passed `--baseline`, the runner checks the saved binary hash and requires
identical fixture and dependency hashes. It re-times that binary alongside
the current binary, shuffling modes and revision order per repetition. Both
use the same operation counts and warmup. Native call traces are collected in
separate instrumented binaries, using differences between one and three
operations to exclude fixture setup.

## Results, 2026-10-07

Cached Mojo 1.1.0 and cvc5 1.4.1. The final fixture uses separate compiled
timing functions for its five modes. Each source/package comparison used nine
shuffled before/after pairs, 4,096 operations after 100 warmup operations,
and CPU 4. All **180 comparison processes** passed. Compilation and other
test campaigns were stopped during timing.

Times are separate medians in microseconds. Percentage savings are medians
of paired observations, not ratios of those separate medians.

| Operation | Entries | Package before → after | Source before → after | Supported interpretation |
|---|---:|---:|---:|---|
| `get()` | 1 | 5.406 → 4.711 | 4.388 → 4.404 | Inconclusive in both routes |
| `get(True, False)` | 49 | 31.071 → 27.357 | 29.496 → 28.754 | 11.7% less time in package; source inconclusive |
| `get(False, True)` | 47 | 33.010 → 28.830 | 31.528 → 30.636 | Inconclusive in both routes |
| `get(True, True)` | 505 | 282.499 → 261.302 | 279.700 → 247.666 | 7.1% less time in package; source inconclusive |
| Iteration control | 505 | 247.314 → 226.152 | 224.721 → 218.482 | Inconclusive in both routes; implementation unchanged |

The descriptive bootstrap intervals for median paired savings are
**1.252–5.335 µs** for packaged internal/non-defaulted reads and
**7.275–41.398 µs** for packaged full reads. The corresponding source intervals
are **−0.933–3.595 µs** and **−0.156–65.484 µs**. Every other savings interval
crosses zero. These results support two localized package improvements;
they do not establish a source-import or whole-solver speedup.

Native traces are identical before/after. Reading all entries requires
**3,952 native calls**, including 505 statistic exports and 505 releases,
with no native statistic copies. Each checked call also retains its existing
error check. Capacity reservation does not remove that work. Mojo heap
allocation counts were not measured, and the independent `Stat` copies remain.

Final timing and trace artifacts:

- `.cache/statistics-isolated-baseline-{package,source}/report.json` and their
  preserved binaries: baseline source/dependency fingerprints and fixture checks.
- `.cache/statistics-isolated-capacity-{package,source}/report.json`: every
  paired observation, loaded-library hashes, variation and bootstrap intervals.
- `.cache/statistics-probe/regenerate.json`: deterministic regeneration hashes.

The runner is included in CI and the dependency-update workflow as a short
semantic check with **no timing threshold**. Performance comparisons remain
isolated experiments, because shared-machine variation is material here.

## Final correctness and cleanup validation

All **16 targeted contract configurations** passed: snapshot and injected
failure fixtures, each built from source and package, at O0/O3, with assertions
enabled and disabled. The final failure campaign ran 100 measured complete
graphs after ten warmup graphs in each configuration: **800 measured graphs
and 22,400 injected failures**. Every tracked native reference was released,
with no unmatched releases or native statistic copies. Post-warmup RSS growth
was **340–408 KiB**, below the existing 4 MiB growth budget.

The existing API smoke suite also passed from source and package at O3 with
assertions enabled, including its exact statistics value checks. All **35
binding-analysis unit tests** and **10 generator tests** passed. Regeneration
from the cached snapshot left all **23 Mojo source files** identical. Mirrored
class method declarations are unchanged. Source, dependency, and preserved
benchmark binary fingerprints were verified.

Reports are in `.cache/statistics-final-snapshots`,
`.cache/statistics-final-cleanup`, and `.cache/statistics-api`, each with
`report.json`; unit logs and input verification are in
`.cache/statistics-probe`. Earlier prototype and fixture-compilation failures
remain in their separate diagnostic directories and are not counted as passes.

These are targeted statistics and API integration checks. The complete
translated-upstream, runtime-loading, thread, and documentation-example
campaigns were not repeated in this pass. Address-level accounting establishes
cleanup of the instrumented references; RSS is not whole-heap attribution or
proof of leak freedom. Earlier native growth findings remain open.

## Reproduction

The commands below do not fetch dependencies. Use a fresh output directory for
each run and preserve the baseline binary until comparison is complete.

```sh
pixi run --locked python scripts/benchmark_statistics.py \
  --output .cache/stats-before --route package --cpu 4 --operations 4096
# Apply the change and regenerate from the cached snapshot.
pixi run --locked python -m bindgen.gen_api
pixi run --locked python scripts/benchmark_statistics.py \
  --output .cache/stats-after --route package --cpu 4 --operations 4096 \
  --baseline .cache/stats-before/report.json
pixi run --locked python scripts/run_contract_tests.py \
  --only returned_collections --optimization 0,3 \
  --output .cache/stats-snapshots --jobs 4
pixi run --locked python scripts/run_contract_tests.py \
  --only return_conversion --optimization 0,3 --conversion-iterations 100 \
  --output .cache/stats-cleanup --jobs 4
```

Repeat the timing commands with `--route source` to check direct imports.
CPU affinity reduces placement variation but does not reserve the CPU. Keep
timing campaigns separate from compilation and other test processes.

## Next priority

The [general binding benchmark](binding-overhead.md#workload-isolation-2026-10-07)
now applies the same workload isolation and verifies compiled-loop coverage.
The [handle-receipt audit](handle-receipt.md) consolidates receipt/anchor
generation while preserving generated runtime output. Next audit pointer-owned
construction and borrowed-owner state initialization, including failure cleanup.
Whole-heap allocation attribution and earlier native grammar-formatting and
repeated-synthesis growth findings remain open.
