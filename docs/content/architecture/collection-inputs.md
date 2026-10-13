# Collection input buffers

The generator now reserves the known size of temporary native input arrays
before converting their elements. Nested handle rows reuse the same converter
as flat lists and variadic packs. Public signatures and value semantics are
unchanged.

## Scope and ownership

`Model._array_input` remains the owner of flat conversion policy. It reserves
space for handle and scalar arrays, string-byte storage, and the pointers into
that storage. Dictionary views receive the dictionary's length explicitly;
list and variadic inputs provide their own length.

`Model._nested_input` derives each row's flat array type from the extracted
native parameter and delegates conversion to `_array_input`. It also reserves
the outer row storage, size array, and pointer array. Fixed-arity term helpers
and the manual record-sort convenience overload reserve their known argument
counts too. Generated changes affect five wrapper modules.

Only capacity changes: initialized length still starts at zero and each element
is appended after conversion succeeds. Range checks, NUL rejection, parallel
length guards, native error checking, pointer construction order, and backing
buffer lifetime anchors are preserved. There are no new owners, caches, native
reference copies, unchecked element writes, or runtime conversion traits.
Returned collections and iterators retain their existing conversion paths.

## Boundary coverage

The `collections` fixture checks:

- Handle lists with zero through 257 elements, including allocation-size
  boundaries, preserving order and duplicate values after input containers
  and original terms are destroyed.
- Empty, one-, two-, and eight-element variadic inputs against list overloads;
  fixed-arity term helpers against ordinary term construction.
- Scalar index order and duplicates, rejecting a late negative or overflowing
  index and succeeding again afterward.
- UTF-8 field names in parallel string/sort arrays, empty inputs, a late
  embedded-NUL error after earlier conversions, and recovery.
- Dictionary keys paired with their string values in named proof output,
  including empty dictionaries and recovery after a NUL-containing value.

The existing compound fixture independently compares C, raw Mojo, and public
bindings for nested inputs with empty and unequal-sized rows, outer-length
rejection, native errors, and recovered calls. It also covers returned values
after native buffers are reused. CI includes the new fixture in its normal O3
matrix and an additional O0 invocation.

## Measurement protocol

The maintained benchmark's `term-2`, `term-8`, `term-list-8`, and `values-8`
workloads exercise two/eight-element variadic construction, list construction,
and model values. The C/raw controls and benchmark fixture remain unchanged.
Native-call and limited libc-allocation diagnostics run separately from timing.
The probe cannot see Mojo's TCMalloc allocations, so it cannot establish the
total allocation savings or leak freedom from this change.

Before/after binaries use the same cached native libraries, toolchain, and
fixture. Randomized paired runs check checksums and loaded-library identity;
source/dependency/binary fingerprints identify the measured versions. Timing
runs exclude concurrent test compilation.

## Results, 2026-10-07

Cached Mojo 1.1.0 and cvc5 1.4.1, with 250,000 operations and 10,000 warmup
operations per process. Seven repetitions of all four layers passed both
before and after: **224 timing observations** in the standalone campaigns.
Separate native-call traces were identical before/after for all four workloads
and matched checked C/raw/public. Native-visible allocation counts were also
unchanged, consistent with the probe's inability to observe Mojo buffers.

Nine randomized before/after pairs per workload and import route added
**180 passing comparison processes**, including an unchanged scalar control.
Package runs used CPU 0 and source runs CPU 4. Affinity does not reserve a CPU;
these are two confirmation configurations, not a causal comparison of imports.

Median elapsed times below are in microseconds. Percentage reductions are the
medians of paired observations, rather than ratios of the separate medians.

| Operation | Package before → after | Source before → after | Paired interpretation |
|---|---:|---:|---|
| Two variadic children | 0.560 → 0.560 | 0.531 → 0.500 | Savings intervals cross zero in both routes |
| Eight variadic children | 0.955 → 0.816 | 0.888 → 0.825 | 8.5% / 5.0% less time; positive savings intervals in both routes |
| Eight children from a list | 0.945 → 0.858 | 0.886 → 0.751 | 10.5% / 14.6% less time; only the source interval excludes zero |
| Eight model values | 7.640 → 7.597 | 7.052 → 7.003 | Savings intervals cross zero in both routes |
| Unchanged scalar control | 0.028 → 0.031 | 0.031 → 0.027 | Savings intervals cross zero in both routes |

The descriptive bootstrap intervals for median paired savings on eight
variadic children are **0.014–0.230 µs** (package) and **0.013–0.182 µs**
(source). For list input they are **−0.046–0.151 µs** and
**0.047–0.175 µs**, respectively. The data support a modest improvement in
eight-argument variadic construction; the package list result remains
inconclusive. They do not establish an improvement for two-argument calls,
model-value retrieval, or whole-solver throughput. String, dictionary, and
nested input changes have semantic coverage here, not dedicated timing data.

Artifacts retain raw observations, variation, bootstrap intervals, native
traces, limited allocation diagnostics, and provenance:

- `.cache/collection-baseline-package/report.json` and
  `.cache/collection-after-package/report.json`: four-layer campaigns.
- `.cache/collection-{baseline,after}-source/inputs.json`: source builds.
- `.cache/collection-probe/paired-comparison.json`: paired results;
  `compare.py` beside it retains the experiment and reuses the maintained
  benchmark's measurement, statistics, and library-identity helpers.
- `.cache/collection-input-contracts/report.json` and
  `.cache/collection-compound-contracts/report.json`: all eight configurations
  of each targeted fixture passed.

## Integration verification

The full O3 contract run passed all 40 configurations, including ownership
accounting, formatting faults, failed return-conversion cleanup, and seeded
operation sequences. Together with the collection and compound O0 runs, this
covers **48 distinct contract configurations**. All 34 binding-analysis and
10 generator unit tests passed.

The translated upstream run passed **346 tests in 17 files and 20 examples**.
Five compile-fail blocks and 10 documented failures reproduced their expected
outcomes; there were no unexpected or stale failures. The generated inventory
of 366 called native functions remained unchanged. All 16 source/package and
O0/O3 documentation-example configurations passed as well.

A second generator emission left all 23 Mojo source files byte-for-byte
identical. Contract and benchmark input fingerprints match the final source
and cached dependencies. Broader reports are
`.cache/collection-integration/report.json`,
`.cache/collection-upstream/report.json`, and
`.cache/collection-docs/report.json`; unit logs and regeneration fingerprints
are in `.cache/collection-probe/`.

These checks found no new ownership or error-handling failure in the exercised
paths. Whole-heap leak profiling, long soaks, and runtime-loading/concurrency
campaigns were not repeated in this pass. The separate native memory-growth
findings remain open.

## Reproduce with cached dependencies

These direct runner commands do not invoke the dependency-fetch task:

```sh
pixi run --locked python scripts/run_contract_tests.py \
  --only collections --optimization 0,3 \
  --output .cache/collections-<fresh-name> --jobs 4
pixi run --locked python scripts/run_contract_tests.py \
  --only compound --optimization 0,3 \
  --output .cache/collection-compound-<fresh-name> --jobs 4
pixi run --locked binding-benchmark \
  --modes term-2,term-8,term-list-8,values-8 \
  --output .cache/collection-benchmark-<fresh-name> --route package \
  --operations 250000 --repetitions 7 --cpu 0
```

## Next priority

The [returned-collection pass](returned-collections.md) shares counted-list
generation and string-array decoding while preserving pending-reference
cleanup, owner anchoring, and protection against native buffer reuse. Next
measure the intermediate snapshot and copies in `Statistics.get`.
Native grammar-formatting and repeated-synthesis
growth, and whole-heap allocation attribution, remain separate open findings.
