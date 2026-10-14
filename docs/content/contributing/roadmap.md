# Roadmap

This page lists the project's milestones, C0 to C4, and the open design
questions. Items marked done are finished. Decided questions link to the
relevant implementation or usage documentation.

The latest approved API work adds silent sort inequality, null-object query
compatibility, and oracle callbacks. Memory is the next priority. The
[2026-10-13 follow-up](../architecture/memory-followup.md) records targeted
controls and native allocation profiles; shared formatting-cache design and
synthesis retention remain open.

## Production hardening

The active development plan below is limited to **cvc5_mojo as a binding
library**: its generated API, native-call boundary, ownership, generator,
tests, and documentation. It supersedes the earlier proposed work on CAS
workers and solver recycling. Application lifecycle policies, native cvc5
changes, new API extensions, and distribution packaging are outside this
plan. Continue using the cached, pinned dependencies.

The first hardening pass already implemented fixes for C-string truncation,
default Unicode semantics, null formatting, discarded solver-handle retention,
integer-literal narrowing, and runtime version checks. Generator and
negative-test gates now reject unexpected omissions and failures. Preserve
these fixes and their regressions; validate the current working tree before
extending it. See [production validation](../architecture/production-validation.md).

The [soak and batch measurements](../architecture/soaks.md) remain diagnostic
evidence. They do not establish binding overhead or identify every source of
retained memory. In particular, different Python and C release builds are not
a matched memory/performance baseline, and replacing owners can conceal
binding retention while those owners remain alive.

## Binding development plan

*Approved sequence, 2026-10-07.* Correct confirmed defects as they are found,
with a regression demonstrating the defect before the fix. Do not postpone
correctness fixes until a later refactoring phase.

The [production validation report](../architecture/production-validation.md)
closes the constructor audit, behavioral-category inventory, sanitizer/tooling
evaluation, remaining generator review, and extended verification automation.
It separates tested binding behavior from the documented native findings and
instrumentation limits. The final cached matrix completed on 2026-10-08,
including corrected reruns for the investigated harness failures. The subsequent
approved [parser guard](../architecture/production-validation.md#mixed-parser-term-managers-early-rejection)
rejects different solver and symbol-manager term managers before entering native
cvc5. Review of the accumulated changes also fixed timeout cleanup in the shared
verification runner. All 25 [local CI-equivalent gates](../architecture/production-validation.md#clean-source-local-ci-2026-10-08)
then passed in a fresh source/build export with cached dependencies and no
source or dependency drift. Next run hosted CI on a committed revision before
release. Packaging and native engine fixes remain outside this plan.

The subsequent request to remove duplicate `String(value)` formatting led to
a [pinned-toolchain investigation](../architecture/single-pass-formatting.md#constructor-investigation-2026-10-08):
the exact constructor fix requires a Mojo standard-library change beyond the
binding scope. The subsequently approved
[direct numeric exchange](../architecture/numeric-conversions.md) implements
integer, rational, and bit-vector fast paths with exact wide fallbacks and
unchanged public signatures. Its report records separate verification and
paired timings, including the measured overhead on wide integer extraction.
This follow-up is not included in the earlier hardening results above.

### Pass 1: establish the contract and matched controls

**Completed for the initial result/proof/grammar baseline.** The
[matched-control report](../architecture/binding-controls.md) records 48
passing large ownership runs, the existing regression baseline, and a
coverage-gap inventory. Grammar formatting fails the memory gate in direct
C as well as Mojo; public `String(grammar)` doubles native formatting calls.
That finding remains open. The subsequent ownership and boundary passes
below build on this baseline.

Record the current source state, dependency and loaded-library hashes,
compiler settings, and existing regression results. Account for every
supported API/marshaling/ownership family using the existing extracted
snapshot and coverage reporter. Distinguish functions reached by tests from
behaviors actually checked; list intentional differences from Python and
unsupported features explicitly.

Add minimal direct-C controls against the **same cached headers and shared
libraries** used by Mojo. Use the same inputs, options, native-call sequences,
and ownership lifetimes. Keep C implementations independent of the generator's
conversion logic so both sides cannot pass by sharing the same mistake.
Reuse existing build, execution, and report infrastructure.

Compare direct C, the internal raw Mojo binding, and the public Mojo API.
For public conveniences such as lossless strings, give the C control an
equivalent semantic operation rather than silently testing truncated data.
Keep Python as a semantic oracle where appropriate, not as the matched-build
performance or allocation control. Compare semantic invariants when valid
models, proofs, or output order are nondeterministic.

**Acceptance:** reproducible controls for result lifetime, representative
handle/array operations, and conversions; a documented coverage-gap list;
the existing binding regression baseline passes or has explicit investigated
failures. An unexpected crash or timeout cannot count as an expected failure.

### Pass 2: audit ownership and attribute memory growth

**Audited by ownership category; native findings remain explicit.** The [initial ownership audit](../architecture/ownership-audit.md)
adds borrowed-owner, container, exception-unwinding, partial-initialization,
and returned-buffer regressions, plus matched command controls. The subsequent
[family controls](../architecture/family-controls.md) add datatype/statistics
and synthesis-result fixtures, with both live owners and complete graph
cleanup. Repeated synthesis queries grow in direct C too. The
[partial return-conversion pass](../architecture/return-conversion.md) fixes
unreleased pending terms after a failed name conversion, with address-level
reference accounting and repeated failure/recovery checks. The
[compound FFI pass](../architecture/compound-ffi.md) adds representative
out-parameter, array, struct, nested-input, and optional-argument controls.
The [runtime pass](../architecture/runtime-validation.md) checks concurrent
initialization, thread error isolation, and cleanup after loading failures.
The [generated-sequence pass](../architecture/generated-sequences.md) adds
stateful value, collection, and error/lifetime checks in Pass 3. The
[statistics snapshot pass](../architecture/statistics-snapshots.md) follows
the explicit single-pass formatting, string-buffer, integer-literal,
collection-input, and returned-collection improvements in Pass 4. The
[general benchmark](../architecture/binding-overhead.md#workload-isolation-2026-10-07)
now isolates compiled timing loops and verifies their coverage. The
[handle-receipt audit](../architecture/handle-receipt.md) centralizes receipt and
receiver policy, validates anchor categories, and preserves generated runtime
output. The [constructor and sanitizer audit](../architecture/production-validation.md)
adds failure cleanup for all pointer owners, qualified ASan/LSan checks, and a
direct-C reproduction of a native library-unload leak. Every ownership category
has lifetime/cleanup coverage; complete native memory-access instrumentation
and proof of absolute leak freedom remain outside the evidence.

Audit every ownership category, including terms and sorts, results, proofs
and proof children, grammars, synthesis results, datatypes, statistics,
parser commands, and borrowed solver/term-manager/parser/symbol-manager
objects. Trace construction, receipt, copy, move, assignment, container
storage/removal, and destruction. Check owner anchors for premature deletion,
unnecessary retention, and cycles.

Exercise both lifetime directions: keep owners alive while discarding many
returned handles, and keep returned handles alive after their original owner
wrappers disappear. Finally release all references and check cleanup. Cover
exceptions during conversion, partially constructed results, returned arrays,
and temporary native buffers invalidated by subsequent calls. Include debug
and optimized builds because Mojo's last-use destruction is part of the risk.

Run fixed-input tests to isolate binding retention, then changing-input tests
with matched C controls to distinguish native growth. Use allocation traces
and reference accounting where observable, in addition to RSS and growth
slopes. Evaluate available profiler/sanitizer support rather than assuming
it instruments both Mojo and the cached native binary. Record instrumentation
limits. Classify findings as lost references, reachable retained objects,
native state, allocator retention, or unresolved; an RSS increase alone is
not proof of a leak.

**Acceptance:** every ownership category has lifetime and cleanup coverage;
no reproduced use-after-free, double release, or unexplained binding-specific
growth remains in the tested paths. Each investigated growth pattern has an
attribution or an explicit open issue. Solver replacement is not a fix for a
binding leak.

### Pass 3: close correctness and FFI boundary gaps

**Behavioral-category inventory and representative rejection paths completed.** The
[compound FFI report](../architecture/compound-ffi.md)
records the C/raw/public boundary matrix and two native C limitations:
anonymous parameter-sort creation and unsolicited sort-inequality output.
The [runtime report](../architecture/runtime-validation.md) adds concurrent
first initialization, independent-thread error isolation, and loading failure
cleanup. The [generated-sequence report](../architecture/generated-sequences.md)
adds deterministic differential operations for numeric boundaries, returned
collections, and handle lifetimes after rejected operations, with an
independent mathematical model. These verification passes required no
binding implementation change. The [overhead baseline](../architecture/binding-overhead.md)
now ranks formatting and conversion work for Pass 4;
the [completed category inventory](../architecture/production-validation.md#behavioral-coverage-inventory)
maps positive, rejection, and recovery evidence, including null dictionary-key
semantics. Exhaustive combinations of methods and engine states are not claimed.

Extend the existing contract tests and Python/C differential checks by
behavioral category:

- ABI widths, signedness, Boolean representation, enum values, struct layouts,
  out-parameters, array lengths, and nested arrays.
- Exact integers/rationals, literal and runtime boundaries, empty values,
  Unicode, embedded NUL, escape processing, omitted arguments, and explicit
  Boolean/optional flags.
- Returned strings and arrays surviving later calls; null formatting,
  equality, hashing, and ordering according to the supported contract.
- Invalid inputs and non-ASCII diagnostics producing recoverable errors,
  with the native error state cleared and subsequent valid calls succeeding.
- Library selection, missing symbols, version rejection, concurrent first
  initialization, and error isolation between threads that each own their
  cvc5 object graph. Do not introduce support for sharing native objects.

Use deterministic generated inputs and short operation sequences to explore
combinations beyond hand-picked examples. Save the seed and minimized failing
case for each discrepancy. Keep tests about observable contracts rather than
mirroring emitted implementation text. Fix the stale documentation that still
describes already-corrected null behavior as part of this contract audit.

**Acceptance:** each boundary category has positive and negative tests;
documented behavior agrees across source and precompiled imports, optimized
and debug builds where relevant, and assertions enabled/disabled. Unsupported
operations and intentional upstream differences are explicit, not silent
test omissions.

### Pass 4: measure and reduce binding overhead

**Representative baseline, formatting, string buffers, integer literals, and collection inputs/returns completed.** The
[overhead report](../architecture/binding-overhead.md) separates bare C,
checked C, raw Mojo, and public wrappers, with repeated isolated timings,
independent call traces, and limited libc allocation diagnostics. The approved
[`toString()` helper](../architecture/single-pass-formatting.md) now formats
each native-formatted wrapper once; existing `String(term)` remains two-pass
under Mojo 1.1. The [shared-buffer improvement](../architecture/string-buffers.md)
also benefits existing `String(value)` calls. The [integer-literal fast path](../architecture/integer-literals.md)
reuses the typed constructor when exact values fit. The
[collection-input pass](../architecture/collection-inputs.md) reserves known
buffer sizes and reuses flat conversion for nested rows. The
[returned-collection pass](../architecture/returned-collections.md) shares counted
list generation and string-array decoding while preserving snapshots and
partial-conversion cleanup. The [statistics pass](../architecture/statistics-snapshots.md)
reserves `Statistics.get` dictionary capacity while retaining the existing
shared traversal and independent value copies. The general benchmark now uses
separate compiled timing loops, verified inventories, and a versioned protocol.
Pass 5 begins with the [handle-receipt audit](../architecture/handle-receipt.md),
which consolidates generation policy without changing runtime output.
Mojo's separate allocator remains a
limitation of the libc allocation probe; these measurements are not a leak audit.

Benchmark direct C, raw Mojo calls, and the public wrappers on the same
native build. Distinguish the bare C-call lower bound from a C control that
performs equivalent error checking and ownership work. Separate cold library
initialization from steady-state calls.

Start with inexpensive native operations, term construction, handle copying
and destruction, scalar and collection arguments, returned arrays, and
string/large-number conversions. Record time per operation, allocation count
and bytes where measurable, and native calls per public operation. Validate
results to prevent dead-code elimination. Use repeated isolated runs with
reported variation; expensive solving must not hide wrapper costs.

Optimize the largest measured binding costs: redundant native copies,
temporary lists/buffers, repeated marshaling, or generator-emitted duplication.
Preserve required ownership and error checks. Do not use a workload's solver
replacement speedup as evidence that the bindings became faster.

**Acceptance:** an attributable overhead baseline and ranked hotspots; each
retained optimization has a reproducible improvement beyond measurement
variation, unchanged observable semantics, and passing correctness/lifetime
regressions. Set regression tolerances from measured noise, not a speculative
universal overhead percentage.

### Pass 5: simplify the generator and runtime architecture

**Receipt, anchor and owner construction policy consolidated; remaining review completed.** The
[receipt audit](../architecture/handle-receipt.md) routes specialized iterators
and term builders through the canonical receipt policy and rejects missing or
mismatched anchors. Cached regeneration preserves every binding source byte;
ownership and native-reference controls pass. Review of pointer-owned
constructors and borrowed-owner state initialization was completed in the
[production audit](../architecture/production-validation.md#constructors-and-borrowed-state),
including failure cleanup and a byte-identical regeneration check. The
remaining overload/error/manual-fragment review found no further abstraction
justified by duplicated policy.

Retain the existing separation of extracted facts, generation, raw C calls,
and public wrappers. Review whether each conversion, receipt/release rule,
error-handling path, and overload-emission rule has one canonical owner.
Prioritize duplicated list/variadic implementations and manual fragments
identified by the preceding correctness and performance work.

Refactor incrementally around those shared mechanisms. Extract cvc5 facts
into the snapshot; keep unavoidable exceptions in `overrides.toml`. Change
generator/manual sources and regenerate outputs instead of editing generated
files. Keep structural refactors separately reviewable from semantic fixes.
Measure implicit-copy and owner-anchor costs before changing their design.
Any public API redesign requires a separate discussion.

**Acceptance:** reduced duplication and clearer invariants, deterministic
regeneration, unchanged public behavior, and no material correctness, memory,
or performance regression. Do not add a new abstraction merely to reduce
line count.

### Pass 6: make verification repeatable and enforceable

**Core/extended cached runners, sanitizer sensitivity, scheduled/manual CI and
stored timing comparisons implemented.** See the
[verification commands](../architecture/production-validation.md#repeatable-commands-and-artifacts)
and final matrix results. Remote CI execution and publication require their
ordinary subsequent workflow; this local pass does not claim either occurred.

Build on the current CI and expected-failure machinery. Add the new binding
checks to appropriate tiers: deterministic contract/lifetime/ABI checks on
changes; longer paired memory runs and supported independent-thread stress
on a scheduled or explicit job; isolated performance comparisons with stored
baselines and noise-aware thresholds. Run the broader matrix before a binding
version is considered ready for the supported toolchain/platform.

Use locked environments and a clearly separated cached-dependency execution
path. Generation must fail on unrecognized signatures, ownership changes,
defaults, layouts, or new/stale omissions. Compile-fail tests must fail at the
intended operation; crashes, timeouts, and unrelated errors always fail.
Store source/library hashes, commands, seeds, outputs, timings, and profiles
with each investigation. Test the runners' failure classification too.

**Acceptance:** a documented verification command set, reproducible artifacts,
and CI gates that catch the demonstrated defects. Report tested scope and
tooling limitations; neither method counts nor RSS-only checks justify a
blanket claim that the binding is leak-free.

### Completion criteria and reporting

For the supported pinned toolchain and platform, the target is an API with
verified boundary behavior, correct lifetimes, no known unaddressed
binding-specific leaks or memory-safety failures, measured overhead, and a
generator/CI process that prevents demonstrated regressions. Native engine
findings are documented with minimal reproductions; they are not fixed by
silently changing binding semantics.

After each pass, report the findings, changes, evidence, unresolved questions,
and **the next priority**. The first implementation pass established matched
C/Mojo controls and reassessed live-owner result/proof/grammar retention.
Publishing changes and public API redesign still require separate agreement.

## Milestones

### C0: extraction and snapshot (done)

- Fetch with sha256 pins.
- Header extraction, checked by the compiler.
- Enum generation.
- Extraction of the C implementation, the Python API, and handle ownership.
- The [join](../architecture/join.md), the
  [snapshot](../architecture/inputs.md#the-snapshot), and the
  [completeness gate](../architecture/join.md#the-completeness-gate): 0
  methods unresolved, and 93.1% resolved automatically.
- The API diff, the bump tool, CI, and the upgrade workflow.
- Hand-written seed bindings passing the smoke and lifetime tests.
- This site.

### C1: generators (done)

1. **Choose where the library handle lives (done).** The process has one
   `CApi`, and every wrapper caches its pointer. See the
   [runtime design](../architecture/runtime.md#what-a-wrapper-holds).
2. **Generate the raw layer (done).** `bindgen/gen_raw.py` writes
   `src/cvc5_mojo/_c/raw.mojo` from `c_functions` and `c_types` in the
   snapshot. The file has a struct per handle and owner type, and a typed
   method per function. The generated code resolves every function once,
   from the library that exports it. See the [raw layer](../architecture/layers.md#raw-layer).
   The [coverage report](../reference/coverage.md#raw-layer) lists the
   functions it does not bind.
3. **Generate the base API (done).** `bindgen/gen_api.py` writes every
   mirrored class from `python` in the snapshot. It applies the
   [marshaling rules](../architecture/layers.md#marshaling-rules) and the
   [ownership modes](../architecture/runtime.md#handle-ownership). See the
   [base API](../architecture/layers.md#base-api).
4. **Port the tests and drop the seed (done).** The smoke, lifetime, leak,
   and thread tests and the documentation examples run unchanged on the
   generated API. `tests/smoke/test_api.mojo` covers each marshaling rule
   and class. The seed is deleted.
5. **Extend CI (done).** CI regenerates everything. It fails on any change,
   new file, or deleted file under `api/` and `src/`, and, since C2, under
   `tests/cvc5/`.
6. **Finish the base API (done).** This step added:

    - dictionaries, for C++ maps;
    - the hand-written `Statistics` and `getOptionInfo` methods, in
      [`bindgen/manual/`](generator.md#writing-a-manual-method) fragments;
    - iteration;
    - lists of lists, for `defineFunsRec`;
    - struct layouts measured by the C compiler;
    - enums that print as Python's;
    - Python's big numbers, as apn_mojo's `Integer` and `Rational`.

    `addPlugin` and the `Plugin` trait are now supported; see C4 below.

Acceptance: every resolved method is generated or listed with a reason. The
tests and examples pass on generated code, and CI regenerates and checks it.

### C2: tests from cvc5 (done)

- A translator from cvc5's Python unit tests and examples to Mojo (done).
  `bindgen/translate.py` writes `tests/cvc5/`, and
  `pixi run --locked cvc5-tests` runs the result. See the
  [test layers and exclusion checks](../architecture/verification.md#test-layers).
- A differential runner against the `oracle` environment (done). The
  translated examples match `bindgen.oracle` output, with explicit model
  validation for non-unique floating-point witnesses. See the
  [example tutorial](../examples/tutorial.md).
- A report of which C functions the tests cover (done). See the
  [coverage report](../reference/coverage.md#c-functions-the-tests-reach).
- A tutorial on this site, built from the translated examples (done). See
  the [tutorial](../examples/tutorial.md).

Acceptance: each runnable example satisfies its recorded comparison policy,
and the translated unit tests pass. Anything else is listed with a reason.

The [coverage expansion](../reference/coverage.md#cvc5s-unit-tests)
adds collection and metadata translation, restores the APN real-value test,
and checks static argument rejection separately. The remaining unit-test
gaps are ten uses of `toPythonObj` and a deprecated constructor. Null-object
query compatibility now covers the four previously excluded tests. The finite-field
example also uses `toPythonObj`; its Python oracle lacks CoCoA. Closing
these gaps requires explicit compatibility or API decisions, rather than
further Python syntax translation.

### C3: distribution

- Depend on the published apn_mojo package (done): version 1.0.1 from
  modular-community, pinned in `pixi.toml` and resolved in `pixi.lock`.
- Configure Linux x86-64, Linux ARM64, and macOS Apple Silicon sources,
  inventories, loading, and locked dependencies (done). Native macOS
  execution is validated, and the `Linux ARM64` workflow builds and tests
  the package on an ARM runner.
- Stage the extracted native dependency closure with deduplicated libraries
  and the upstream license notices (done).
- Version the package as cvc5's version and a revision (done: `1.4.1.0`).
  The recipe builds from `v1.4.1.0` of `Spellbound-Mojo/cvc5_mojo` (done).
- Tighten the Mojo runtime pin and review external native runtime
  requirements (done): Mojo 1.1.x, and `libstdcxx >=11` on Linux, checked
  against the snapshot; no minimum macOS beyond Mojo's own.
- Build the recipe with `rattler-build` and verify installation in a fresh
  project (done on Linux x86-64 and macOS; see
  [platform validation](../architecture/packaging.md#platform-validation)).
- From the first bump that deprecates a method, keep the methods a later
  cvc5 deprecates, marked with `@deprecated`.
- Submit to modular-community (done: 1.4.1.0 through
  [#399](https://github.com/modular/modular-community/pull/399), merged 2026-10-14).
- Enable the twice-yearly upgrade workflow and its PR permission; report
  regeneration failures without losing the upgrade review output.
- Publish this site (done: <https://spellbound-mojo.github.io/cvc5_mojo/>).

### C4: extensions

- Plugin callbacks (done): the `Plugin` trait, retained callback storage,
  error containment, and both upstream plugin tests. See the
  [plugin tutorial](../reference/plugin.md) and
  [callback implementation](../architecture/layers.md#callbacks).
- Oracle function callbacks (done): `Oracle.evaluate`, `Solver.declareOracleFun`,
  shared callback ownership, and checked error handoff. See the
  [oracle tutorial](../reference/oracles.md).
- Selected C-only functions in the base API.
- Linux ARM64 and macOS release preparation is covered by C3.

## Open questions

1. **The library handle (decided).** The process has one `CApi`, and every
   wrapper caches its pointer. See the
   [runtime design](../architecture/runtime.md#what-a-wrapper-holds).
2. **Integers beyond 64 bits (decided).** They are apn_mojo's `Integer` and
   `Rational`. See the
   [exact-number types](../start/installation.md#big-numbers-apn_mojo).
3. **Dictionaries and statistics (decided).** A Python dict is a `Dict`. A
   statistic is a `Stat`, with Python's keys as fields. See the
   [statistics reference](../reference/statistics.md).
4. **The package version scheme (decided).** The version is cvc5's version
   and a package revision, as in `1.4.1.0`. See the
   [release version scheme](../releases.md).
5. **Deprecations after 1.4.1 (decided).** Methods that later releases
   deprecate stay mirrored, marked with `@deprecated`, until cvc5 removes
   them.
6. **Test translation (decided).** The translator supports fixtures,
   `pytest.raises`, helper functions, and the Python the tests use most. The
   translated tests are generated and run. The tests that cannot pass in
   Mojo are listed in `overrides.toml`. See the
   [test layers and exclusion checks](../architecture/verification.md#test-layers).
7. **`Term.notTerm` and its siblings (decided).** They are mirrored as Python
   has them. For this, every wrapper remembers its term manager. See the
   [wrapper state](../architecture/runtime.md#what-a-wrapper-holds).
8. **Implicit copies of handle classes (decided).** Copies are implicit, as
   Python shares objects. Borrowing and `^` avoid the cost. See
   [ownership and copies](../start/ownership.md#every-value-owns-one-cvc5-reference).

## Tutorial and documentation coverage

The site includes a twelve-lesson course, a transcendental-functions course,
a scheduling application, a task cookbook, and guides for debugging, Python
migration, and external consumers. The maintained examples run alongside the
translated upstream examples. Operator and option references come from the
pinned release, and browser checks cover bundled math, search, and navigation.
