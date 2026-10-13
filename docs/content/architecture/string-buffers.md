# String conversion buffers

The shared `c_bytes` and `to_string` helpers now avoid growing a temporary
list one byte at a time. These helpers serve the existing public methods,
raw-call consumers, and error decoding. **Existing `String(value)` calls
benefit without changing their syntax**, as do explicit `toString()` calls.

## Implementation and contracts

`c_bytes` checks the input byte span for embedded NUL, reserves enough space
for every byte and the terminator, and extends the owned `List[Int8]` from a
span of the same bytes. Reinterpreting `UInt8` as `Int8` changes signedness,
not UTF-8 bit patterns. The terminator fits the original allocation.
Validation completes before allocating the output; rejected arguments retain
the same error message and never reach cvc5.

`to_string` finds the C terminator and passes a borrowed byte span to the
standard library's **validated** `String(from_utf8=...)` constructor. That
constructor produces the owned copy directly, removing the intermediate list.
The native buffer must remain valid through construction, just as before.
The span does not escape, and no cvc5 call occurs between obtaining the native
buffer and copying it. Invalid UTF-8 still raises the original diagnostic.

The formatter generator and wrapper layouts are unchanged. Mojo 1.1's
`String(value)` constructor still calls `write_to` twice, so it still makes
two native formatting calls. Each conversion now does less work.
`toString()` continues to make one native call. There is no formatting cache,
new owner anchor, or borrowed native buffer retained by a wrapper. This
preserves fresh output from mutable grammars and declarations.

The owned string passed to arbitrary `Writer` implementations is retained:
a writer may itself call cvc5 and invalidate native scratch storage. Passing
that writer a borrowed view would weaken the existing lifetime contract.

## Boundary coverage

The existing string contract fixture adds direct helper checks for:

- Empty strings and lengths around small-string, vector-width, allocation,
  and page boundaries, up to 24,582 UTF-8 bytes.
- Exact ASCII, two-byte, and mixed two/four-byte Unicode output, with one
  trailing NUL and no byte-sign corruption.
- Returned strings surviving mutation and destruction of the source buffer,
  and outgoing buffers surviving source-string replacement.
- Leading, middle, and trailing embedded-NUL rejection.
- Ten malformed UTF-8 patterns at eight offsets, including truncated,
  overlong, surrogate, and out-of-range sequences, plus a valid C prefix
  followed by invalid bytes after its terminator.

The fixture uses the same contract runner at O0/O3, source/package imports,
and with/without assertions. CI runs its O3 cases in the normal contract gate
and adds an explicit O0 invocation. The existing formatting fault checks,
native error recovery, ownership accounting, and return-conversion cleanup
remain separate regressions.

```sh
pixi run --locked python scripts/run_contract_tests.py \
  --only strings --optimization 0,3 \
  --output .cache/string-buffers-<fresh-name> --jobs 4
```

## Measurements, 2026-10-07

The comparison uses cached cvc5 1.4.1 and Mojo 1.1.0. Preserve the old and new
executables and alternate their execution in randomized order within each
repetition. Both consume the same results, use identical operation/warmup
counts, and load the same native library bytes. There are nine repetitions,
200,000 operations and 10,000 warmup operations per process, five workloads,
and two import routes: **180 passing comparison processes**. Package runs use
CPU 0 and source runs CPU 4. No test compilation runs alongside timings.

Median times in microseconds; percentages are median reductions of paired
runs, which need not equal the reduction of the two independent medians:

| Operation | Package before → after | Paired reduction | Source before → after | Paired reduction |
|---|---:|---:|---:|---:|
| `String(term)` | 4.138 → 3.509 | 15.2% | 3.999 → 3.321 | 18.4% |
| `term.toString()` | 2.023 → 1.733 | 16.7% | 2.002 → 1.695 | 13.7% |
| Decimal output copy | 1.094 → 0.776 | 28.4% | 1.048 → 0.777 | 27.0% |
| Integer from 256-bit decimal text | 1.526 → 1.356 | 17.1% | 1.664 → 1.384 | 13.0% |
| Integer literal `42` | 0.929 → 0.938 | 5.5%, inconclusive | 0.971 → 0.873 | 7.7% |

For `String(term)`, descriptive bootstrap intervals for median paired time
savings are **0.187–1.111 µs** (package) and **0.452–1.040 µs** (source).
For `toString()` they are 0.223–0.482 µs and 0.193–0.475 µs. These describe
the sampled runs, not universal speedup guarantees. Raw observations, ranges,
median absolute deviations, and intervals are retained. The package small
literal interval crosses zero (−0.027–0.059 µs), so this pass does not establish
a repeatable small-literal improvement across both routes.

The preceding separate before/after package campaigns each ran 140 timing
processes against bare C, checked C, raw Mojo, and public wrappers. Their
apparent 35% `String(term)` improvement also included host-performance changes:
even unchanged native C controls became faster. Prefer the alternating
comparison above for the effect attributed to this change.

Separate call traces confirm that native operations are unchanged in all
five workloads, including two formatter calls for `String(term)` and one for
`toString()`. The limited libc allocation probe likewise sees unchanged
native allocation requests. It cannot observe Mojo's TCMalloc allocations,
so these diagnostics do not measure the removed temporary allocations or
prove leak freedom. Formatting timings cover one 256-bit integer term;
they are not whole-solver throughput measurements.

Artifacts:

- `.cache/string-buffers-baseline/report.json`: fresh before-change campaign.
- `.cache/string-buffers-after-package/report.json`: after-change campaign,
  native traces, and limited allocation diagnostics.
- `.cache/string-buffers-after-source/inputs.json`: source-build fingerprints.
- `.cache/string-buffers-probe/paired-comparison.json`: the 180 alternating
  observations, binary provenance, and paired summaries.
- `.cache/string-buffers-probe/compare.py`: retained experiment driver,
  reusing the benchmark's output checks, library checks, and statistics.

Reproduce either standalone campaign around the helper change with:

```sh
pixi run --locked binding-benchmark \
  --output .cache/string-buffers-benchmark-<fresh-name> --route package \
  --modes format,format-once,decimal-copy,integer-text,integer-literal \
  --operations 200000 --repetitions 7 --cpu 0
```

Retain both binaries to alternate comparisons; do not infer speedup from two
widely separated campaigns when unchanged controls also move.

## Verification results

All 36 standard O3 contract configurations passed. The expanded string
fixture and formatter fixture also passed their four O0 configurations each:
**44 distinct contract configurations** across import routes and assertion
modes. Formatter checks include 48 expected native-error/invalid-UTF-8 aborts
and the unchanged 1 / 1 / 2 call counts for `toString()`, `write_to`, and
`String(value)` on all twelve wrapper families. Ownership accounting,
partial-return-conversion failure cleanup, numeric boundaries, compound FFI,
retention, and seeded differential sequences passed.

Reports are `.cache/string-buffers-contracts/report.json`,
`.cache/string-buffers-boundaries-final/report.json`, and
`.cache/string-buffers-formatting-O0/report.json`. The latter two contain the
additional debug coverage; the string report also repeats its O3 cases.
The only production file changed in this pass is `_c/ffi.mojo`; all generated
binding files and dependency bytes retain their earlier hashes.

Runtime loading and independent-thread error isolation passed all four O3
import/assertion configurations, **128 processes**, including malformed
version UTF-8 and failure cleanup. See
`.cache/string-buffers-runtime/report.json`.

All sixteen documentation example builds/runs passed
(`.cache/string-buffers-docs/report.json`), along with strict documentation,
link, and search-index checks. No dependencies were refreshed.

The full translated upstream suite and whole-heap leak profiling were not
rerun. Native grammar-formatting and repeated-synthesis growth findings remain
open. The development plan continues to separate those findings from measured
binding conversion costs.

## Next priority

The subsequent [integer-literal fast path](integer-literals.md) reuses the
direct constructor for values that fit signed 64-bit range, preserving
arbitrary-precision behavior for all other values. Next investigate shared
collection-marshaling buffers. Native grammar
formatting and repeated synthesis memory growth remain open; reducing
transient conversion work does not establish whole-heap leak freedom.
