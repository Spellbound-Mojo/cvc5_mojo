# Matched binding controls

The first binding-only development pass compares direct C, the internal raw
Mojo API, and the public Mojo API against the same cached cvc5 library.
Results, proofs, and unformatted grammars stayed within the ownership budgets.
**Grammar formatting failed the memory gate in all three layers.** This page
records both outcomes; the passing ownership subset is not a claim that the
whole library is leak-free.

## Protocol

`tests/binding/controls.c` is an independent implementation against the public
C header. `tests/binding/controls.mojo` implements raw and public operations.
`scripts/run_matched_controls.py` reuses the existing build, watchdog,
checkpoint, provenance, and coverage helpers. It does not fetch dependencies.

Each process creates one term manager and solver, warms up, and keeps that
owner graph alive through the last measured checkpoint. Each iteration drops
its exported handles. A final checkpoint follows graph cleanup. Fixtures use
fixed inputs so changes in native problem size cannot conceal binding
retention. The C control checks native errors after each call, just as the
raw binding does.

The runner records source, header, dependency, binary, and loaded-library
SHA-256 hashes, compiler commands and versions, stdout/stderr, checksums,
RSS checkpoints, and the extracted API inventory. Actual mappings come from
`/proc/self/maps`. The cached release contains byte-identical `libcvc5.so` and
`libcvc5.so.1` files; equivalent names are accepted, duplicate mappings or
different library bytes are rejected. The parser library is also checked
when loaded.

Cases run sequentially in a reproducibly shuffled order (seed 17). The
default budgets are 4 MiB of peak RSS growth after warmup and 1 MiB of Mojo
growth above its paired C control. The C control must satisfy the absolute
budget too. A 512 MiB process watchdog and a 180-second timeout stop runaway
cases. Missing checkpoints, abnormal exits, semantic mismatches, or library
mismatches fail the comparison.

Short traced runs of 1 and 33 iterations subtract setup and teardown calls.
C and raw Mojo must make the same native calls per iteration. The public
layer must preserve the tested export counts and copy/release balance; extra
balanced copies from value semantics are reported. This counts API calls,
not individual live pointers or native heap allocations.

The sensitivity control deliberately retains one extra result reference per
iteration. The runner requires it to exceed the memory budget. These
references remain reachable through the live solver until deletion, matching
the previously corrected export-retention defect.

## Results on 2026-10-07

Measurements used the cached cvc5 1.4.1 release, Mojo 1.1.0, and GCC 15.3.0
on Linux x86-64. The main native library SHA-256 was
`61206e6d5f36585cfe682a1ec97ad2c1c548e1fa772925d5205fcad4ae7a7a24`.
The working tree includes the earlier hardening fixes; per-run source hashes
identify it more precisely than the unchanged Git HEAD.

### Ownership with live owners

Each fixture ran at 200,000 and 1,000,000 measured iterations, with 2,000
warmup iterations and two repetitions per layer. Mojo used precompiled
imports, O3, and assertions enabled. All **48 ownership runs passed**, totaling
**28.8 million measured fixture iterations** across the three layers.

| Fixture | What each iteration checks | Maximum C growth, KiB | Maximum raw Mojo growth, KiB | Maximum public Mojo growth, KiB |
|---|---|---:|---:|---:|
| Results | Query, copy, inspect both results, release both | 28 | 4 | 4 |
| Proofs | Export roots, copy, compare, inspect conclusion sort and child rules, release all handles | 28 | 8 | 344 |
| Empty grammars | Create, copy, release | 28 | 340 | 344 |
| Grammars with rules | Create, add a rule, copy, release | 28 | 340 | 344 |

Maximum paired Mojo growth above C was 316 KiB. Copy/release traces agreed
with the ownership contract. Creating public grammar argument lists adds one
balanced native term copy/release pair per iteration. The deliberately
retained result control grew by 34,000 KiB over 200,000 iterations and was
detected. These results support the earlier exported-reference fix for the
tested paths.

### Grammar formatting remains an open finding

The fixture creates a Boolean grammar with nonterminal `Γ` and rule `true`,
copies it, converts both handles to text, and checks the text. At 20,000
measured iterations after 2,000 warmup iterations, the following are maximum
growth across two repetitions:

| Conversion | Native formatter calls per iteration | C growth, KiB | Raw Mojo growth, KiB | Public Mojo growth, KiB |
|---|---|---:|---:|---:|
| Public `String(grammar)` and `String(copy)` | C/raw: 2; public: 4 | 84,036 | 84,148 | 168,556 |
| Public `write_to` into two existing `String` buffers | All layers: 2 | 84,036 | 84,484 | 84,484 |

All 12 of these runs completed, and all failed the 4 MiB absolute growth
gate. The one-pass public conversion stayed within 448 KiB of its paired C
control, but C itself still grew by about 82 MiB. Output checksums agreed.

Two separate effects are established:

- **Native formatting grows memory on this fixture.** Direct C reproduces
  it with balanced grammar references. Formatting one unchanged grammar
  repeatedly also grows, while creating grammars and adding rules without
  formatting stays stable. This isolates the growth to the formatting path,
  rather than discarded grammar exports.
- **Mojo's `String(value)` conversion amplifies that growth.** On the pinned
  compiler it calls `write_to` twice per conversion, causing two native
  formatting calls. Explicitly calling the existing `write_to` method once
  with a `String` buffer removes this duplication. This is a diagnostic use
  of the existing API; no public binding implementation changed in this pass.

The initial longer formatting matrix hit the 512 MiB watchdog in all 12
cases. Representative 200,000-iteration runs reached their last checkpoint
at about 120,000 iterations in C/raw Mojo and 60,000 in public Mojo. They are
incomplete failures, not completed long runs. Their partial checkpoints and
termination reasons remain in the artifacts.

The cached C entry point assigns the C++ formatter's result to a
thread-local string. That fact does not identify which underlying allocations
grow. The cached source omits the C++ implementation, and Valgrind/heaptrack
were unavailable. No allocator trace, sanitizer result, or classification as
an unreachable native leak is claimed. The measured wrapper reference
balance also does not prove every allocation is released.

## Contract coverage and remaining gaps

The runner saves `api-coverage.json` using the canonical `bindgen.report`
summary. The [generated coverage report](../reference/coverage.md) is the
method/function inventory, and the [extracted ownership table](runtime.md#handle-ownership)
is the native receipt contract. Reaching a function is distinct from checking
all of its lifetimes, conversions, or failure paths.

| Family | Evidence available | Remaining binding work |
|---|---|---|
| Solver-anchored results, proofs, grammars | Matched live-owner controls, copies, proof arrays/children, final graph cleanup; existing result/proof/grammar lifetime regressions | Assignment, moves, container removal, owner-dropped variants for each path, conversion failures and partial results |
| Synthesis results | Existing semantic and bounded-lifetime tests; native-growth diagnostics | Matched fixed-input C ownership controls and explicit anchor audit |
| Term-manager-owned terms and sorts | Temporary proof conclusions and sorts in the matched fixture; existing lifetime and retention tests | Broader construction/copy/container matrix and changing-input controls |
| Operators, datatype declarations/constructors/selectors, statistics | Existing raw/API smoke and translated tests | Matched ownership controls for every extracted handle family, including returned collections |
| Parser commands and borrowed owners | Existing parser, borrowed-term-manager, and lifetime examples | Borrowed solver/parser/symbol-manager lifetime chains, command retention, exception cleanup, cycles |
| Scalars, enums, ABI widths and layouts | Extracted compiler checks, raw smoke tests, literal-boundary regressions | Broader signedness/boundary combinations and deterministic generated inputs |
| Strings and large numbers | Unicode/NUL/escape contracts, existing exact-number tests; matched grammar text conversion | Temporary-buffer invalidation, conversion exceptions, allocation/call overhead across other formatters |
| Arrays, nested arrays, dictionaries, tuples, option/statistic structs | Existing marshaling smoke tests; matched proof roots and children | Partial conversion failure, empty/nested containers, stored values surviving subsequent native calls |
| Nulls, defaults, errors, loading, threads | Null-format, string/default, loading and error regressions; existing independent-thread smoke | Full negative-boundary matrix, error recovery after each failure, initialization stress |
| Unsupported and intentionally different behavior | [Support boundaries](../guides/status.md), generated omissions, and `overrides.toml` | Keep exclusions explicit and checked; callbacks, other platforms, and packaging are outside this pass |

The existing targeted baseline was rerun with cached dependencies: 16
boundary/retention configurations, 8 generator regressions, 4 loading cases,
and the lifetime documentation example in 4 source/package O0/O3 builds.
The initial CI ownership command passed 12 cases at 20,000 iterations. Small
33-iteration matrices passed at source O0 with assertions and source O3
without `ASSERT=all`; these are compilation/semantic checks, not long memory
runs. Seven matched-analysis and eleven existing soak-analysis unit tests
also passed. The full translated upstream suite was not rerun in this pass.
Final documentation validation passed all 16 example builds/runs and the
strict site, link, anchor, and search-index checks.

Timing fields are diagnostic. They do not isolate wrapper overhead, startup,
allocator effects, or compiler differences sufficiently for speedup claims.

## Reproducing and retaining evidence

Use a fresh output directory for each run. The cached-only core ownership
command is:

```sh
pixi run --locked matched-controls --output .cache/matched-new --modes results,proofs,grammar-empty,grammar-rules,commands --operations 20000 --repetitions 1
```

For the larger ownership matrix, use `--operations 200000,1000000
--repetitions 2`. The formatting diagnostic is:

```sh
pixi run --locked matched-controls --output .cache/format-new --modes grammars,grammar-write --operations 20000 --repetitions 2
```

The latter returns failure on the measured cached release. The runner's
default modes also include formatted grammars, so a default full run is not
green. CI explicitly runs the stable ownership subset; the native formatting
finding is not reclassified as a pass. `pixi run --locked binding-check` tests
the runner's failure classification and loaded-library identity checks.

Local artifacts are under `.cache/matched-ownership`,
`.cache/matched-grammar-ownership`, `.cache/matched-grammar-isolation`,
`.cache/matched-formatting`, `.cache/matched-ci`, `.cache/matched-debug`, and
`.cache/matched-release`. Each contains JSON reports, commands, TSV samples,
mapped-library records, and short native-call traces. `.cache/matched-report`
indexes the results, including reanalysis of incomplete-run checkpoints.
`.cache/matched-docs` contains the final documentation example matrix.
Cache directories are local evidence, not tracked source files.

## Next priority

The follow-up [ownership audit](ownership-audit.md) adds borrowed-owner,
container, assignment, and exception-cleanup coverage and matched command
controls. [Family controls](family-controls.md) add datatypes, statistics,
synthesis results, and complete graph cleanup. The next priority is failures
during partial native-return conversion. Keep
the formatting reproduction as an open finding. Review how to offer a single
native string conversion before changing the public API.
