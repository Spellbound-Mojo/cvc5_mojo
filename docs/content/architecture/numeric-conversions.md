# Direct numeric conversions

The existing public numeric methods now exchange fitting values through the
native C integer and rational APIs. Their signatures, exact APN return types,
and wide-value support are unchanged. This complements the native handle
exchange already used for terms, sorts, and owners; it does not change
`String(value)` or the pinned toolchain.

## Dispatch and compatibility

| Operation | Direct path | Fallback |
|---|---|---|
| `mkInteger(Integer)` | Signed 64-bit input | Decimal text |
| `getIntegerValue()` | Signed 64-bit, then unsigned 64-bit | Exact decimal parsing into `Integer` |
| `mkReal(Rational)` | Normalized numerator and positive denominator both fit signed 64-bit | Decimal text |
| `mkReal(Integer, Integer)` | Both values fit signed 64-bit and denominator is positive | Original decimal path, including error behavior |
| `getRealValue()` | Signed 64-bit numerator and unsigned 64-bit denominator | Exact decimal parsing into `Rational` |
| `mkBitVector(Int, Integer)` | Nonnegative unsigned-64 value fitting a valid width | Original decimal path, including negative values and invalid inputs |

The signed constructor denominator and unsigned getter denominator are
deliberately different: those are the pinned C signatures. For example,
`1/18446744073709551615` uses text on construction but direct numeric
extraction. Reducible wide numerator/denominator pairs remain exact;
an already normalized `Rational` can take the fast path even when the
original unreduced pair could not.

The shared `fits_native_integer` helper compares APN values against native
limits **before** narrowing, without throwing and formatting an error for
normal wide-value fallbacks. Subsequent APN native conversion remains checked.
Real integer literals now reuse the existing `Int` constructor when they fit,
as integer literals already did. The zero-valued bit-vector convenience
overload reuses the exact numeric overload.

Invalid bit-vector widths, values exceeding their width, and nonpositive
rational denominators keep the original text path and diagnostics. Getter
predicates do not broaden the accepted types: integral real terms remain
accepted by the integer getter, while symbolic terms and wrong sorts retain
native rejection. Null errors remain recoverable. Float64 input continues to
mean its shortest decimal fraction; `0.3` is still `3/10`.

Finite-field values and arbitrary-precision values outside these native
ranges retain the exact text interface. Bit-vector **extraction** still
returns `String`, as required by the existing public API.

## Generation and ownership

`overrides.toml` names the additional native getter paths and marks the
fixed-width rational and bit-vector constructors as private generated
helpers. The existing overload emitter handles their C types, range checks,
error checks, and returned-reference adoption. Manual APN overloads select
the helper or existing text overload; they do not duplicate native ownership
logic or expose public overloads that would silently narrow Mojo literals.

Private helpers must use unique `_native_` names and refer to a C function
already in their method's binding. Invalid or colliding mappings fail
generation. Public signatures used by the translator and reference renderer
exclude these helpers. The normal raw layer remains unchanged.

No wrapper field, reference cache, retained native string, or new owner anchor
is added. Numeric getters return independently owned APN values that survive
destruction of the term and all its owners.

## Verification

The numeric fixture compares results against independently parsed APN values
and the existing text constructors. It covers signed and unsigned 64-bit
endpoints and neighboring values, 256-bit integers, normalization, different
constructor/getter denominator limits, negative bit-vectors, null/wrong-sort
errors, borrowed term managers, detached results, and recovery after errors.
Exact diagnostics are compared with the original text/native getter routes.

The contract runner independently chooses expected native calls from Python
integers and fractions, the fixture inventory, and extracted C signatures.
Every case and phase must appear exactly once; missing, duplicated, wrong, or
additional formatting calls fail. Mutation tests exercise the classifier and
the private-helper generation policy. CI includes optimized numeric contracts,
an explicit O0 pass, and semantic runs of all new benchmark workloads.

```sh
pixi run --locked python scripts/run_contract_tests.py \
  --only numeric_conversions,integer_boundaries --optimization 0,3 \
  --output .cache/numeric-contracts-<fresh-name> --jobs 2
```

## Measurement protocol

The existing overhead fixture adds nine numeric workloads, using prebuilt APN
inputs outside the timed loop. Each operation consumes and checks its result.
Native C and raw Mojo controls verify equivalent native call sequences in
separate traced runs. Wide C getter controls validate owned decimal text;
Mojo controls additionally construct APN values. Their total costs are not
interchangeable.

To attribute changes to this pass, preserve old and new package binaries built
from the same fixture and dependency bytes, and alternate their execution in
random order within each repetition. Use unchanged typed-integer and text
construction workloads as controls. Timings exclude tracing, sanitizers,
allocation instrumentation, and concurrent compilation. Wider fallback
workloads are measured too: fast-path probes add native calls when the value
does not fit. There is no universal performance threshold.

## Measurements, 2026-10-08

Cached Mojo 1.1.0 and cvc5 1.4.1; nine randomized paired repetitions, 500,000
operations after 10,000 warmups, package imports, CPU 0. All **198 timed
processes** passed output and loaded-library checks. The before and after
binaries use identical benchmark and dependency bytes. No compiler or test
process ran alongside the paired timings.

Times below are medians in nanoseconds. Changes are median reductions of
paired observations, which need not equal ratios of the separate medians.

| Workload | Before | After | Paired time reduction |
|---|---:|---:|---:|
| `mkInteger(Integer(42))` | 708.5 | 320.1 | 53.2% |
| Integer extraction, `42` | 231.3 | 209.3 | 7.6% |
| Integer extraction, 256-bit | 1,453.9 | 1,580.2 | **−11.4% (slower)** |
| `mkReal(r)`, APN rational `r = 3/7` | 610.6 | 388.5 | 36.2% |
| `mkReal(Integer(3), Integer(7))` | 619.1 | 386.2 | 37.6% |
| Rational extraction, `3/7` | 699.1 | 397.3 | 42.4% |
| Rational extraction, 256-bit numerator | 2,188.5 | 2,281.9 | −6.7%, inconclusive |
| 64-bit bit-vector from APN `2**64 - 1` | 1,080.1 | 338.8 | 68.4% |
| Integer construction, 256-bit APN input | 2,326.9 | 2,333.6 | −1.0%, inconclusive |

Descriptive bootstrap intervals for paired savings exclude zero for the six
improved cases above. The small-integer getter interval is only **10–27 ns**;
its improvement is modest. The wide-integer getter interval is **−368 to
−84 ns**, confirming the fallback cost in this sample. Wide-rational
extraction and wide-APN construction intervals include zero. The unchanged
typed-integer and decimal-input controls also have intervals crossing zero.
Raw observations, variation, and all intervals are retained in the report.

The wide-integer penalty is the explicit cost of checking signed and unsigned
native ranges before the decimal fallback. There is no combined native
get-if-representable API. The cached APN public parser also takes an owned
`String`, so replacing it with an unchecked borrowed buffer is not a supported
way to recover that cost. This implementation provides automatic direct
exchange for fitting values; it does **not** make every numeric workload
faster. A future explicit typed-getter API could avoid probing when a caller
already knows the range, but that is a separate public API decision.

These are conversion microbenchmarks, not solver-throughput or memory-leak
claims. The separate one-repetition C/raw/public campaigns establish fixture
semantics and native-call equivalence, not performance improvements.

Artifacts:

- `.cache/numeric-baseline/report.json`: preserved before binary and inputs.
- `.cache/numeric-after/report.json`: after binary, semantics, and native-call
  equivalence across all nine numeric workloads.
- `.cache/numeric-probe/paired-comparison.json`: alternating observations,
  provenance, and paired summaries; `compare.py` records the experiment using
  the existing benchmark's validation and statistics helpers.
- `.cache/numeric-probe/public-signatures.json`: all 387 supported public
  method signature lists are unchanged.
- `.cache/numeric-generation/report.json`: deterministic cached generation and
  17 generator, 45 binding-analysis, and 11 soak-analysis unit tests.

## Integration results

All checks completed on the final runtime implementation:

- **52 O3 contract configurations** across source/package imports and
  assertion modes, including the 37-case numeric trace inventory, ownership,
  partial conversion failure, strings, formatting faults, collections,
  retention, compound C comparisons, and generated operation sequences.
- **Four fresh O0 numeric configurations**, including real-literal boundaries.
  The initial targeted matrix also passed all eight integer-literal
  configurations at O0/O3.
- **Four O1 ASan/LSan numeric configurations**, after all five sanitizer
  sensitivity checks passed. No new leak was detected in the scoped checks.
  Native library shutdown still reproduces the separately recorded 16-byte
  leak in two allocations without Mojo binding calls; it is not suppressed.
  ASan instruments Mojo; the cached native libraries are not rebuilt with
  instrumentation. The leak checkpoint follows fixture-local cleanup and
  precedes process-global teardown.
- All **346 translated upstream tests in 17 files**, **20 examples**,
  **five compile-fail blocks**, and **10 documented failures**, with no
  unexpected or stale failure. The generated call inventory now records
  **373 native functions** reached by the translated suite.
- Raw/API smoke tests, lifetimes, threads, and the standalone leak fixture.
  The latter measured **512 KiB growth over 200 rounds**, below its 4,096 KiB
  budget. This and the sanitizer results are scoped evidence, not a claim
  of absolute leak freedom.
- All **16 documentation-example configurations** and strict documentation,
  rendered-link, and search-index checks.

The preserved old implementation passes the new fixture's semantic checks
but fails its optimized native-route requirements, as intended. This confirms
the trace regression detects a return to text conversion even when values
remain correct.

Reports are `.cache/numeric-integration-contracts/report.json`,
`.cache/numeric-final-O0/report.json`, `.cache/numeric-sanitizers/report.json`,
`.cache/numeric-upstream/report.json`, and `.cache/numeric-closeout/report.json`.
The before-route evidence is `.cache/numeric-probe/before-route-evidence.json`.
The original targeted matrix is `.cache/numeric-contracts/report.json`.

Only `_c/ffi.mojo`, generated `Term`, and generated `TermManager` change at
runtime. The API snapshot records the new mappings; the translated call
inventory changes through its runner. Other generated sources and translated
tests remain byte-identical, and cached dependencies and pins are unchanged.

Next run hosted CI on the committed revision. Explicit typed getters remain
an optional API follow-up to avoid range probes when the caller knows its
numeric range. The Mojo `String(value)` constructor is still a separate
toolchain limitation; no standard-library change is included here.
