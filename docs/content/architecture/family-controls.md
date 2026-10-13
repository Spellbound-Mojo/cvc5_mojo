# Datatype, statistics, and synthesis controls

The [2026-10-13 follow-up](memory-followup.md) adds fresh targeted controls
and native heap profiles for the remaining growth cases.

This follows the [initial ownership audit](ownership-audit.md). The matched
C/raw/public controls now cover datatype declarations and resolved datatype
exports, statistics lookup and iteration, synthesis-result copies, repeated
synthesis queries, and complete graph cleanup. **96 extended runs passed.**
Twelve repeated-query synthesis runs failed the memory budget in all three
layers, including direct C. No new binding defect was reproduced, and the
public API and generated implementation are unchanged.

## Fixtures and protocol

The controls reuse the [matched baseline](binding-controls.md) build, watchdog,
checkpoint, and provenance infrastructure with the same cached Mojo 1.1.0 and
cvc5 1.4.1 dependencies. Actual loaded library bytes must match. The memory
budgets remain 4 MiB absolute growth after warmup and 1 MiB of Mojo growth
above its paired C control; C must satisfy the absolute budget too.

`--lifetime live` remains the default: one graph stays alive while exported
handles are repeatedly discarded. The new `--lifetime round` mode creates,
exercises, and releases a complete graph per iteration. It tests constructor
and destructor behavior; it introduces no automatic lifecycle policy in the
binding. Both modes record a final cleanup checkpoint. RSS need not return
to its starting value when the allocator retains released storage.

| Fixture | Repeated operation |
|---|---|
| `datatype-declarations` | Construct a declaration and constructor declaration, copy them, add a Boolean selector and constructor, check the name/count, release references |
| `datatypes` | Reuse one resolved datatype sort; export/copy/release its datatype, constructor, selector, and selector codomain sort |
| `statistics` | Export/copy/release a solver statistics snapshot; look up and convert integer, floating-point, string, and histogram statistics |
| `statistics-iter` | Export/copy/release term-manager statistics; iterate and convert the returned collection (47 entries on this fixture) |
| `synthesis-copy` | Keep one synthesis result, repeatedly copy/inspect/release references, then release the stored result and owners |
| `synthesis` | Repeat the same contradictory Boolean synthesis query, copy/inspect/release each returned result |

Statistics checks compare types, flags, histogram keys and shape. Timer and
other numeric values are excluded from checksums because they may vary;
existing API regressions separately check concrete statistic values. C and
raw Mojo consume copied strings/histogram keys within an iteration; the public
API additionally builds Mojo value containers. These are matched native
ownership operations, not an allocation-count or timing comparison of
identical container implementations.

The trace validator extracts copy/release pairs for **all handle types** from
the API snapshot, including the private native statistic handle. Apart from
balanced value-copy differences and the separately reported formatter
amplification, every native call count must match C. This includes exports,
type queries, and owner construction/deletion. Ambiguous handle lifecycles
fail validation. Unit regressions check every extracted pair and reject
missing exports or owner deletion. Call counts do not establish per-pointer
heap reachability.

## Results on 2026-10-07

### Passing extended matrices

All runs below used precompiled Mojo imports, O3, and assertions enabled.
There were two repetitions per layer and operation count.

| Fixture and lifetime | Measured iterations per run | Maximum C growth, KiB | Maximum raw Mojo growth, KiB | Maximum public Mojo growth, KiB |
|---|---|---:|---:|---:|
| Declaration construction, live | 200,000 and 1,000,000 | 1,180 | 1,500 | 1,500 |
| Resolved datatype exports, live | 200,000 and 1,000,000 | 28 | 344 | 344 |
| Stored synthesis-result copies, live | 200,000 and 1,000,000 | 28 | 4 | 4 |
| Statistics lookup, live | 10,000 and 50,000 | 32 | 344 | 8 |
| Statistics iteration, live | 10,000 and 50,000 | 28 | 8 | 16 |
| All six fixtures, complete graph per iteration | 1,000 | 336 | 432 | 880 |

These **96 runs passed**, totaling **22,356,000 measured iterations**, including
36,000 complete graph-cleanup cycles. Live-owner runs used 2,000 warmup
iterations; graph-cleanup runs used 40. Maximum Mojo growth above paired C
was 320 KiB for the live-owner matrices and 544 KiB for graph cleanup. The
declaration fixture's growth was effectively unchanged between 200,000 and
one million iterations. This supports a bounded increase on these runs;
it does not identify the underlying allocator or native cache.

Native reference traces passed. The public declaration fixture elides a
copy/release pair that the explicit C/raw fixtures perform. Statistics lookup
performs four native statistic exports/releases per iteration; iteration
performs 47. Stored synthesis results perform two copies and two releases per
iteration. The sensitivity control still uses a live solver even when the
selected fixtures test graph cleanup, so owner destruction cannot hide the
deliberately retained result reference.

### Repeated synthesis queries fail the memory budget

Twelve additional live-owner runs completed 1,000 and 5,000 queries, twice
per layer, after 50 warmup queries. **All twelve failed the absolute memory
budget**, including direct C. At 5,000 queries, peak growth was 35,684 KiB in
C, 35,776 KiB in raw Mojo, and 35,744 KiB in public Mojo. Maximum paired Mojo
excess was 92 KiB. At 1,000 queries C grew by 8,656 KiB.

Every iteration in every layer made one synthesis query, one result copy,
two result inspections, and two releases. There is no additional binding
reference imbalance in this fixture. Stable stored-result copies isolate
copy/release behavior, and stable complete-graph tests exercise final cleanup.
Neither observation makes the growing live-query fixture pass or attributes
every native allocation. This confirms growth through the same cached native
C build even with fixed inputs; it does not establish an unreachable native
leak. The [grammar-formatting finding](binding-controls.md#grammar-formatting-remains-an-open-finding)
also remains unresolved.

### Other validation and limits

The updated CI commands passed 30 live-owner and 18 complete-graph cases.
Small 33-iteration matrices passed for source O0 with assertions and package
O3 without `ASSERT=all`, 18 cases each. These small matrices verify compilation,
semantics, and native-call equivalence; they are not long-duration memory
evidence. No heap allocation profile was collected, and diagnostic timings
do not justify a binding speedup claim. The full translated upstream suite
was not rerun in this step.

All 12 matched-control analysis tests, nine generator regressions, 11 soak
analysis tests, and the API smoke test passed. All 16 documentation-example
builds/runs and the strict documentation/link checks passed. Six short grammar
formatting cases also passed with the strengthened trace validator; this does
not resolve the documented growth at larger operation counts. SHA-256 checks
against the preceding ownership report confirm all 23 binding source files
are unchanged.

Evidence is in `.cache/families-live`, `.cache/families-statistics`,
`.cache/families-round`, and `.cache/families-synthesis`. Reports retain
binary/source/dependency hashes, actual loaded-library identity, commands,
checkpoints, checksums, and native-call counts. The short matrices are under
`.cache/families-debug`, `.cache/families-release`, `.cache/families-ci-live`,
and `.cache/families-ci-round`. `.cache/families-report` indexes the completed
investigation. Cache directories are local artifacts, not tracked source.

## Reproducing the extended runs

These commands use cached dependencies directly. Use a fresh output directory
for each run:

```sh
pixi run --locked matched-controls --modes datatype-declarations,datatypes,synthesis-copy --operations 200000,1000000 --repetitions 2 --output .cache/families-live-new
pixi run --locked matched-controls --modes statistics,statistics-iter --operations 10000,50000 --repetitions 2 --output .cache/families-statistics-new
pixi run --locked matched-controls --modes datatype-declarations,datatypes,statistics,statistics-iter,synthesis,synthesis-copy --lifetime round --operations 1000 --warmup 40 --repetitions 2 --output .cache/families-round-new
pixi run --locked matched-controls --modes synthesis --operations 1000,5000 --warmup 50 --repetitions 2 --output .cache/families-synthesis-new
```

The last command reports failure on the measured cached release. It remains
a separate diagnostic; growing C memory is not an expected-success exemption.
CI runs the stable live-owner subset at 20,000 iterations, and complete-graph
fixtures at 100 iterations after 40 warmup iterations.

## Next step

The [partial return-conversion pass](return-conversion.md) is now complete:
it fixes pending references after failed named-term decoding and adds failure
and recovery checks for dictionaries, string arrays, statistics, and temporary
buffers. Next are compound FFI boundary checks. Representative fixtures still
do not cover every operator, datatype shape, statistic, or synthesis outcome.
Allocation instrumentation is needed to attribute retained native memory
beyond RSS and API counts.
