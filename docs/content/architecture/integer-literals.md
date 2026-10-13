# Integer literal construction

`TermManager.mkInteger(42)` now takes the same direct native constructor as
`TermManager.mkInteger(Int(42))`. Literals outside signed 64-bit range retain
the exact arbitrary-precision conversion. Call sites, result types, and
error behavior are unchanged.

## Range and ownership contract

Check the **exact `IntLiteral` before converting it to `Int`**. Mojo 1.1 can
otherwise narrow a literal silently; for example, a value above 64 bits can
become a small integer with no diagnostic. The supported platform is 64-bit.

The shared `fits_int_literal` predicate in `_c/ffi.mojo` owns the range test.
`checked_int_literal` reuses it for width/index validation and keeps the same
out-of-range error. The `TermManager` manual fragment also uses it to choose:

- Signed 64-bit literals, including both endpoints: delegate to the generated
  `Int` overload, which calls `cvc5_mk_integer_int64`.
- Larger positive or negative literals: retain `Integer(value)` and the
  existing decimal-string overload, which calls `cvc5_mk_integer`.

This avoids duplicating the native call, error checks, or returned-reference
adoption. No wrapper field, owner anchor, or cache is added. Explicit `Integer`
and `String` overloads retain their existing paths; `mkReal` and bit-vector
value construction are unchanged. The manual source is regenerated through
`bindgen.gen_api` against the cached snapshot.

## Boundary and native-call checks

The existing integer-boundary fixture now checks 18 exact values: zero,
positive/negative small values, 32-bit crossings, both signed 64-bit endpoints
and their neighbors, unsigned 64-bit crossings, a negative 70-bit value,
and `2**256 - 1`. Every result must match both an independently parsed exact
integer and construction from its decimal text. Copy/destruction, borrowed
manager construction, and recovery after a malformed numeric-string error
are also exercised. Existing oversized width/index rejections still run.

The contract runner extracts constructor names from the API model and the
case inventory from the fixture. Python independently decides which values
fit the range. Each case must emit exactly one expected native call, with
complete trace markers and no missing, duplicate, or unknown case. Mutation
regressions reject wrong constructor routes and absent/repeated calls.

All eight combinations of source/package, O0/O3, and assertions on/off pass:
11 fitting and seven wide values each, **144 checked construction routes**.
CI runs the fixture in the normal O3 gate and an additional O0 invocation.

```sh
pixi run --locked python scripts/run_contract_tests.py \
  --only integer_boundaries --optimization 0,3 \
  --output .cache/integer-literal-<fresh-name> --jobs 4
```

## Measurement protocol

The existing binding benchmark retains `integer-literal`, `integer-int`, and
`integer-text`, and adds `integer-wide-literal` for `2**256 - 1`.
Direct C and raw Mojo now use the integer constructor for the small-literal
control, matching the optimized public path. The wide-literal controls use
the decimal native path. Separate traces enforce equivalent native calls.

Before and after binaries use the same updated benchmark fixture and cached
dependencies. Alternating their execution in randomized pairs limits drift
between campaigns. Timing excludes tracing, allocation instrumentation, and
other test builds. Results must pass checksums and native-library identity
checks before entering summaries. Typed `Int` and decimal-string cases serve
as controls for changes unrelated to literal dispatch.

## Results, 2026-10-07

Cached cvc5 1.4.1 and Mojo 1.1.0, nine shuffled before/after repetitions on
each import route, 500,000 operations after 10,000 warmup operations per
process. Package runs use CPU 0 and source runs CPU 4. All **144 paired
comparison processes** passed. Median times are in microseconds; reductions
are medians of paired observations rather than ratios of independent medians.

| Operation | Package before → after | Source before → after | Interpretation |
|---|---:|---:|---|
| `mkInteger(42)` | 0.778 → 0.390 | 0.757 → 0.366 | 47.9% / 50.2% less time in paired runs |
| `mkInteger(Int(42))` | 0.389 → 0.385 | 0.384 → 0.368 | Unchanged typed-path control; delta intervals cross zero |
| Integer from 256-bit decimal text | 1.270 → 1.204 | 1.199 → 1.160 | Paired-delta intervals cross zero |
| `mkInteger(2**256 - 1)` | 2.341 → 2.460 | 2.368 → 2.459 | Wide fallback remains exact; delta intervals cross zero |

For small literals, descriptive bootstrap intervals for median paired savings
are **0.342–0.496 µs** (package) and **0.334–0.429 µs** (source).
The corresponding wide-literal intervals are −0.119–0.106 µs and
−0.163–0.065 µs: the small shifts in wide-literal medians do not establish
either a speedup or a regression. The report retains every observation,
min/max, median absolute deviation, and interval. These are microbenchmark
results, not whole-solver throughput guarantees.

The separate four-layer after-change campaign passed 112 timings against
bare C, checked C, raw Mojo, and public wrappers. Traces confirm identical
native calls across checked C/raw/public for every workload. The limited
libc probe sees **7 malloc requests / 160 cumulative requested bytes** per
small-literal operation, versus 11 / 232 in the previous decimal-path campaign
with the same production/dependency bytes as this pass's starting point.
This counts native-visible requests, not total Mojo allocations or live heap;
Mojo's TCMalloc allocations remain outside the probe.

Artifacts:

- `.cache/integer-literal-baseline-{source,package}/inputs.json`: before-build
  source/dependency/binary fingerprints, with the updated benchmark fixture.
- `.cache/integer-literal-after-package/report.json`: four-layer timing,
  native calls, and limited allocation diagnostics.
- `.cache/integer-literal-after-source/inputs.json`: source confirmation build.
- `.cache/integer-literal-probe/paired-comparison.json`: paired observations,
  provenance, and summaries; `compare.py` beside it retains the experiment.
- `.cache/integer-literal-contracts/report.json`: all eight boundary/route
  configurations.

Run the current standalone campaign using cached dependencies:

```sh
pixi run --locked binding-benchmark \
  --output .cache/integer-literal-benchmark-<fresh-name> --route package \
  --modes integer-literal,integer-int,integer-text,integer-wide-literal \
  --operations 500000 --repetitions 7 --cpu 0
```

## Integration verification

The cached-dependency verification also passed:

- All 36 O3 contract configurations, including ownership, error recovery,
  formatting faults, failed return-conversion cleanup, and generated
  sequences. Together with the four integer-boundary O0 configurations,
  this covers 40 distinct configurations.
- 34 binding-analysis unit tests and 10 generator unit tests.
- All 346 translated upstream tests in 17 files and 20 examples. Five
  compile-fail blocks and 10 documented failures reproduced their expected
  results, with no unexpected or stale failures. The generated inventory
  remains at 366 called native functions, unchanged by this pass.
- All 16 source/package and O0/O3 documentation-example configurations.
- Deterministic generation from the cached snapshot: all 23 Mojo source
  files remained byte-for-byte identical on a second emission.

Reports are in `.cache/integer-literal-integration/report.json`,
`.cache/integer-literal-upstream/report.json`, and
`.cache/integer-literal-docs/report.json`. Unit-test logs and the regeneration
fingerprints are in `.cache/integer-literal-probe/`. Recorded contract and
benchmark input fingerprints still match the final implementation and cached
dependencies. This pass adds no ownership state and passes the existing
cleanup checks; it does not repeat whole-heap leak profiling or resolve the
native growth findings below.

## Next priority

The [collection-input pass](collection-inputs.md) reserves known buffer sizes
and shares flat/nested conversion. Next review returned collections and
iterators, preserving ownership, error checks, and partial-conversion cleanup.
Native grammar-formatting and repeated-synthesis growth, and whole-heap
allocation attribution, remain separate open findings.
