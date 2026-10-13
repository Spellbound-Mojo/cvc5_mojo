# Binding overhead

This benchmark measures **cvc5_mojo** with the cached cvc5 1.4.1 and Mojo 1.1.0
toolchain. It concerns binding operations, not solver recycling or CAS
throughput. No binding implementation changes are part of this measurement
pass. The historical results below predate the workload-isolation protocol;
use the [current protocol](#workload-isolation-2026-10-07) for new comparisons.

## Measurement contract

`scripts/benchmark_binding_overhead.py` reuses the existing workload builder,
native fixture compiler, subprocess runner, source fingerprints, loaded-library
identity checks, and trace analysis. Each observation runs in a fresh process
on one selected CPU. Processes run sequentially, with randomized workload and
layer order in each repetition. Every result must include the expected count,
checksum, warmup checksum, and completion marker; crashes, timeouts, incomplete
output, and different loaded cvc5 bytes fail.

The steady-state fixtures use the same inputs, returned-reference lifetimes,
and observable outputs. Four layers separate the costs:

- **Bare C:** the native calls and equivalent transient buffers, without an
  error check after every call. This is a lower bound, not the production
  error-handling contract.
- **Checked C:** the same work with `cvc5_has_error()` after each call.
- **Raw Mojo:** checked raw methods, explicit release of returned references,
  and buffers/conversion helpers where the result requires owned data.
- **Public Mojo:** ordinary wrapper methods and automatic destruction.

The C control allocates and frees transient argument arrays and copies returned
arrays/strings before using them. It checks the digit-only output as valid
ASCII/UTF-8. It is independent of the generator. Different compilers and
allocation implementations remain part of the C/Mojo comparison; a time delta
is not automatically attributable to one wrapper instruction.

Setup, library loading, the single model query, warmup, mapping capture, and
final graph cleanup are outside steady-state timing. Creation and destruction
of the result of **each measured operation** remain inside. Checksums consume
results inside the timed loop. Each workload has a separate compiled loop,
selected before warmup. Reported times include iteration and result consumption
as well as the named operation; workload selection is outside the timing region.
Native function-pointer calls and wrapper error checks remain part of the
operation. Historical reports used runtime workload dispatch inside the loop.

The workloads cover:

| Workload | One measured operation |
| --- | --- |
| `scalar` | Read the number of children of an eight-child term |
| `copy` | Copy that handle, read its child count, release the copy |
| `integer-int` | Construct `42` via a typed `Int`, check its kind, release |
| `integer-literal` | Public `mkInteger(42)`; the historical baseline used decimal C/raw controls, changed to the direct integer path by the [literal optimization](integer-literals.md) |
| `integer-wide-literal` | Public `mkInteger(2**256 - 1)` with decimal C/raw controls; added by the literal optimization |
| `integer-text` | Construct the decimal string for `2**256 - 1`, check its kind, release |
| `term-2`, `term-8` | Construct an ADD from variadic children, read its size, release |
| `term-list-8` | The same eight-child construction from a borrowed list |
| `values-8` | Get eight constant model values, materialize the owned list, inspect and release every value |
| `children-8` | Snapshot eight term children, check their kinds, and release them; added by the [returned-collection pass](returned-collections.md) |
| `assertions-32` | Snapshot 32 assertions, check their symbols, and release them |
| `option-names` | Copy every option name into owned strings and check for `produce-models` |
| `format` | Format the 256-bit integer term into an owned string and sum its bytes |
| `format-once` | Same owned result using the explicit `toString()` method; added in the [formatting optimization](single-pass-formatting.md) after this baseline |
| `decimal-copy` | Copy the native decimal getter's output with `to_string`, then sum its bytes |

`decimal-copy` is deliberately the **same helper-level control** in both Mojo
modes. It does not invoke public `getIntegerValue()`, which also parses an
`apn_mojo.Integer`. The large-number baseline covers decimal marshaling;
arbitrary-precision parsing and Unicode conversion costs remain unmeasured.

Cold initialization is separate: time the first `c_api()` in a new Mojo
process. The independent C loader opens both cached libraries, resolves the
binding's symbol list extracted from generated raw code, and creates/checks/
deletes the same version-query owner graph. It performs six extra lifecycle
symbol lookups and uses `RTLD_NOW | RTLD_LOCAL`; this is an initialization
comparison, not an instruction-identical loader implementation. Manifest input
and process launch are excluded. The OS page cache is warm; no cache flush or
host settings change is performed. The Mojo public and raw layers share this
one process-wide loader.

## Variation and attribution

Counts are calibrated against checked C to target a substantial timed batch,
then held fixed for all four layers in that workload. Reports retain every
observation, min/max, median absolute deviation, paired deltas, paired ratios,
and a deterministic bootstrap interval for the median paired delta. The
interval describes these repetitions; it does not eliminate cloud scheduling,
clock-frequency, allocator, or compiler effects. There is no universal
performance pass threshold and no timing gate in CI. CI runs a short semantic
invocation to keep the fixtures and runner executable.

Native-call traces come from **separate instrumented builds** and one versus
33 operations. Subtraction removes initialization/destruction calls. Raw and
checked C calls must match. Public calls may add balanced copies/releases and
formatter invocations; amplification remains visible. Internal raw error
checks are not themselves trace entries. Timing binaries contain no trace
branch per native call.

The optional Linux/glibc allocation interposer also runs separately. It counts
`malloc`, `calloc`, `realloc`, non-null `free`, and `aligned_alloc` requests
inside the measured loop. A known allocation/reallocation/free sequence must
be observed correctly. Subtracting 1,000 from 2,000 warmed operations gives
per-operation counts and cumulative requested bytes. This is **not live heap
size**: realloc requests count their full requested size, and requests may be
satisfied from existing allocator storage.

The probe is incomplete for Mojo allocations: this toolchain's
`KGEN_CompilerRT_AlignedAlloc` dispatches to its TCMalloc runtime, bypassing the
interposed libc functions. It also does not cover direct mmap, every aligned
allocation API, or other threads. Consequently, the report's C/Mojo allocation
columns must not be interpreted as total allocations or leak accounting.
Native formatter amplification is observable, but Mojo buffer allocation
attribution still needs appropriate runtime instrumentation.

## Historical results, 2026-10-07

Two optimized release campaigns passed: nine repetitions of every workload
and layer through package imports (CPU 0, 150 ms calibration target), then
source imports (CPU 4, 300 ms target, different order seed). Together these
are **828 valid timing processes**, including 36 cold-loader observations.
The environment exposes five CPUs with a four-CPU cgroup quota; affinity
does not reserve a CPU or remove host scheduling noise. These campaigns test
robustness across configurations, not a causal package-versus-source difference.

Package-import medians, **nanoseconds per operation**:

| Workload | Bare C | Checked C | Raw Mojo | Public Mojo |
| --- | ---: | ---: | ---: | ---: |
| `scalar` | 20.6 | 26.4 | 28.4 | 27.6 |
| `copy` | 52.0 | 68.4 | 74.4 | 73.2 |
| `integer-int` | 380.9 | 412.2 | 443.9 | 448.4 |
| `integer-literal` | 732.7 | 723.3 | 929.5 | 985.6 |
| `integer-text` | 1,164.9 | 1,269.2 | 1,646.7 | 1,643.5 |
| `term-2` | 449.3 | 461.9 | 635.1 | 622.5 |
| `term-8` | 726.5 | 704.0 | 957.2 | 937.9 |
| `term-list-8` | 717.5 | 726.1 | 1,040.2 | 1,199.9 |
| `values-8` | 7,353.2 | 7,047.0 | 8,062.4 | 7,760.2 |
| `format` | 1,712.5 | 1,804.3 | 2,189.3 | 4,464.6 |
| `decimal-copy` | 825.9 | 740.1 | 1,187.5 | 1,254.0 |

The source-import confirmation measured formatting at 1.54 µs checked C,
2.16 µs raw Mojo, and 4.49 µs public Mojo. The package campaign measured
1.80 / 2.19 / 4.46 µs respectively. Its public formatting range was
3.85–5.58 µs, with a 0.56 µs median absolute deviation. The median paired
public-minus-checked-C delta interval was 2.10–3.83 µs for package imports
and 2.66–3.70 µs for source imports. This large difference is supported by
the independent call counts, not just a timing ratio.

Other apparent differences deserve caution: the public copy-versus-checked-C
interval crosses zero in both campaigns, and the returned-value interval
crosses zero in the source campaign. Bare C sometimes measures slower than
checked C for allocation-heavy operations. Do not treat a single run or
small percentage difference as proof of a regression or improvement.

Cold loading resolved all **474 extracted symbols**. Package medians were
5.90 ms in the C loader and 5.95 ms in Mojo; source confirmation was
6.67 / 6.46 ms. Both paired delta intervals cross zero. There is no evidence
here to prioritize loader redesign.

### Priorities identified by the baseline

1. **Format once.** `String(term)` invokes `cvc5_term_to_string` twice,
   versus once for raw Mojo and C, repeating native formatting and
   `to_string` conversion. The libc probe sees 36 malloc requests and two
   realloc requests per public operation versus 18 and one in raw Mojo:
   36,864 versus 18,432 cumulative requested bytes. These are observable
   native/standard-library requests, not total Mojo allocations or live
   retained memory. The subsequent [single-pass formatting pass](single-pass-formatting.md)
   added explicit `toString()` methods and measured the improvement.
   Existing `String(value)` calls remain two-pass under Mojo 1.1.
2. **Reduce string conversion work.** The helper-level decimal copy costs
   about 1.1–1.3 µs in Mojo versus 0.7–0.8 µs in checked C. Constructing
   a 256-bit decimal integer also shows a repeatable conversion gap.
   Inspect byte-at-a-time, growing temporary buffers in `c_bytes` and
   `to_string`, retaining embedded-NUL rejection and UTF-8 validation.
3. **Fast-path representable integer literals.** Public `mkInteger(42)`
   costs about 0.99–1.01 µs versus 0.43–0.45 µs for `mkInteger(Int(42))`.
   Traces show that the former calls decimal `cvc5_mk_integer`, while
   the latter calls `cvc5_mk_integer_int64`. This is a native-path and
   conversion difference, not just raw dispatch. Any fast path must
   preserve the exact behavior of literals outside signed 64-bit range.
4. **Then examine collection buffers.** Two/eight-child construction has
   measurable marshaling cost. Native-call traces show no extra term
   copies in these fixtures, so changing copy semantics is not justified.
   The list/variadic relative ordering changes between campaigns; prioritize
   their shared conversion code rather than choosing an overload by one run.
5. **Leave cheap scalar/copy and initialization design alone for now.**
   Scalar public overhead is only a few nanoseconds here. These results
   do not support removing error checks or redesigning handle ownership.

Artifacts are `.cache/overhead-baseline-package/report.json` and
`.cache/overhead-confirm-source/report.json`. The former also contains 66
call-trace runs and 66 allocation diagnostic runs; all eleven workload call
comparisons and integral allocation deltas passed. Timing observations
exclude both instrumentation mechanisms.

Additional validation passed: both import routes with assertions enabled
(92 short semantic observations), all four existing O3 compound-FFI
configurations after generalizing the shared C builder, and 29 binding-analysis
unit tests. Strict documentation/link checks passed. All 23 binding source
files retain their hashes from the previous sequence pass. The full translated
upstream suite, documentation example execution, and whole-heap leak profiling
were not rerun in this measurement-only pass.

## Workload isolation, 2026-10-07

The statistics investigation exposed a weakness in shared, runtime-dispatched
timing loops: a change to one workload can alter compilation of another control.
The general fixture now selects a compile-time-specialized workload before
warmup and timing. Mojo uses `comptime` branches and a non-inlined `execute`
per specialization. C emits non-inlined timing functions from one workload
list and forcibly inlines the existing operation body with a constant mode.
Neither fixture dispatches on the workload inside the measured loop.

The operation implementations, result lifetimes, checksums, and separate cold
loader remain the same. `decimal-copy` already measures the identical conversion
helper in raw and public Mojo; both labels now explicitly use the same compiled
control. There are **31 Mojo timing functions covering 32 layer/workload pairs**
and **16 functions in each C fixture**. Equivalent C bodies may share a code
address without sharing runtime dispatch.

Every timing, tracing, and allocation build now passes a compiled-symbol
inventory check before execution. The runner invokes GNU `nm -S --defined-only`,
checks the expected nonempty timing functions, and saves the command, output,
symbol addresses/sizes, and binary hash in `*-loops.json`. Missing, duplicate,
generic, malformed, or unexpected specializations fail. This checks entry-point
coverage; it is not a disassembly proof or an allocation measurement. Runtime
checksums and native-call comparisons remain required independently.

Reports carry `protocol: isolated-workloads-v1`. Do not pool these measurements
with earlier reports that lack that identifier, or describe differences from
the old fixture as binding speedups. The library and generator are unchanged
in this pass. Future before/after runs must keep this protocol and use matching
operation counts, route, assertions, dependency bytes, and CPU placement.

### Isolation verification

All 16 steady-state workloads and the cold loader passed through source and
package imports, with assertions on and off: **264 short semantic observations**.
For each import route, 96 separate trace processes checked one versus 33
operations in checked C, raw Mojo, and public Mojo. All **48 per-operation call
inventories** per route are identical to the preserved pre-isolation fixture.
The package allocation probe passed sensitivity and observation checks in 96
separate processes. Its allocator coverage limits above still apply.

Every built fixture passed the new compiled-loop gate, including the trace
and allocation variants. The 37 binding-analysis unit tests passed, including
rejection of missing, duplicate, generic, zero-size, and malformed compiled-loop
evidence. The existing short CI benchmark invocation automatically exercises
the new gate; no additional CI compilation is needed.

Artifacts are `.cache/isolation-{package,source}/report.json` and
`.cache/isolation-{package,source}-assertions/report.json`. The old fixture and
call traces are preserved in `.cache/benchmark-isolation-before/` and
`.cache/isolation-before-package/`. These short verification timings are not
performance measurements.

### Fresh baseline under the isolated protocol

A separate package-import campaign passed **330 timing observations**: five
shuffled repetitions of all 16 workloads across four layers, plus the two cold
loader controls. It used O3, assertions disabled, CPU 4, 10,000 warmup operations,
and a 100 ms checked-C calibration target. No compilation or other test campaign
ran concurrently. Per-workload counts were then fixed across layers/repetitions;
the minimum count of 32,768 means expensive workloads exceed the target.

Medians, **nanoseconds per operation**, from
`.cache/isolation-baseline-package/report.json`:

| Workload | Bare C | Checked C | Raw Mojo | Public Mojo |
| --- | ---: | ---: | ---: | ---: |
| `scalar` | 17.6 | 24.9 | 23.2 | 21.7 |
| `copy` | 46.0 | 60.1 | 65.7 | 59.7 |
| `integer-int` | 321.1 | 321.6 | 371.3 | 349.5 |
| `integer-literal` | 345.0 | 380.3 | 359.4 | 361.6 |
| `integer-text` | 938.5 | 1,068.2 | 1,141.1 | 1,118.1 |
| `term-2` | 393.3 | 412.3 | 506.8 | 512.1 |
| `term-8` | 572.9 | 622.0 | 828.7 | 722.8 |
| `term-list-8` | 577.0 | 641.2 | 845.2 | 715.1 |
| `values-8` | 5,851.6 | 5,906.1 | 6,749.0 | 5,983.6 |
| `format` | 1,285.2 | 1,244.5 | 1,414.6 | 2,904.4 |
| `decimal-copy` | 598.1 | 572.3 | 601.8 | 622.4 |
| `format-once` | 1,189.4 | 1,334.6 | 1,387.0 | 1,428.3 |
| `integer-wide-literal` | 988.3 | 926.8 | 1,150.1 | 2,283.4 |
| `children-8` | 885.2 | 894.3 | 1,174.6 | 1,033.2 |
| `assertions-32` | 4,437.1 | 4,789.5 | 5,903.7 | 5,450.6 |
| `option-names` | 50,209.6 | 52,796.2 | 44,583.1 | 40,161.3 |

These are starting values for subsequent experiments, not before/after gains.
The identical raw/public `decimal-copy` control has different observed medians
because it runs in different processes; sharing a compiled loop does not remove
host or allocator variation. Public `format` still makes two native formatter
calls and `format-once` makes one, as established by the independent traces.
Cold medians were 5.42 ms for C and 4.14 ms for Mojo, with the loader differences
described above. The report retains individual observations, dispersion, and
paired-delta intervals; five repetitions on one host do not establish universal
performance bounds.

To reproduce this campaign after diagnostic verification:

```sh
pixi run --locked binding-benchmark \
  --output .cache/isolation-baseline-<fresh-name> --route package \
  --repetitions 5 --target-ms 100 --cpu 4 --skip-traces --skip-allocations
```

Use an allowed CPU on the current host. Library/generator sources and the lockfile
retain their pre-pass hashes. Strict documentation/link checks are part of this
pass; translated upstream tests, documentation example execution, and whole-heap
profiling are not rerun for this benchmark-only change.

## Reproduce with cached dependencies

```sh
pixi run --locked binding-benchmark \
  --output .cache/overhead-<fresh-name> --route package \
  --repetitions 9 --target-ms 150
```

This task has no fetch dependency. Use `--route source` for the other import
route, `--assertions` for assertion-enabled verification, and `--cpu` to choose
an allowed CPU. `--operations 32 --warmup 2 --repetitions 1` is a short semantic
check, not a performance result. `--skip-traces --skip-allocations` supports an
uninstrumented timing replication after diagnostic validation.

Outputs include build commands/results, source/dependency/binary hashes,
actual library mappings, CPU/quota metadata, raw observations, call traces,
allocation diagnostics, compiled-loop inventories, the protocol identifier, and
`report.json`. The Linux benchmark requires GNU `nm` from binutils. Fresh output
directories prevent reuse of stale observations. The benchmark-analysis unit tests reject wrong
checksums, missing/duplicate repetitions, incomplete/crashed runs, and invalid
compiled-loop evidence.

## Next step

The [explicit single-pass formatting](single-pass-formatting.md) and
[shared string-conversion buffer](string-buffers.md) improvements are implemented.
The latter also benefits existing `String(value)` calls.
The [integer-literal optimization](integer-literals.md) then reuses the direct
constructor for representable literals. The [collection-input pass](collection-inputs.md)
reserves known buffer sizes and shares flat/nested conversion. The
[returned-collection pass](returned-collections.md) shares counted-list and
string-array conversion. The [statistics pass](statistics-snapshots.md) measures
its snapshot and value copies and reserves dictionary capacity. The general
benchmark now isolates workloads in their own compiled timing loops. The
[handle-receipt audit](handle-receipt.md) then consolidates receipt/anchor
generation without changing runtime code. Next audit pointer-owned construction
and borrowed-owner state initialization, including failure cleanup.
Native grammar-formatting growth and repeated
synthesis growth documented in earlier passes remain open.
