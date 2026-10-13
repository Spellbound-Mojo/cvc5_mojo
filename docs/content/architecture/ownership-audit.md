# Ownership audit

This is the first ownership-audit step of the binding-only development plan,
following the [matched baseline](binding-controls.md). It covers borrowed
owners, container replacement/removal, exception unwinding, partial object
initialization, and retained return values. No new binding defect was
reproduced, and no public API or generated implementation changed in this step.
The allocation audit of the remaining handle families is still open.

The follow-up [family controls](family-controls.md) add matched datatype,
statistics, and synthesis-result fixtures, including complete graph cleanup.

## Ownership paths reviewed

The native receipt rules remain the [extracted ownership table](runtime.md#handle-ownership).
The review followed those rules through the generator, emitted wrappers,
manual statistics conversions, and cached C implementation.

| Path | What keeps the value valid | Cleanup responsibility |
|---|---|---|
| Solver returned by a parser | A non-owning solver state retains the parser's Mojo state; the native parser retains its native solver | The borrowed state does not call solver deletion |
| Symbol manager returned by a parser | A non-owning symbol-manager state retains the parser's Mojo state; cvc5 retains the supplied or internally created symbol manager | The borrowed state does not call symbol-manager deletion |
| Term manager returned by a solver | A non-owning term-manager state retains the solver's Mojo state, including when that solver was itself borrowed | The borrowed state does not call term-manager deletion |
| Commands surviving a parser wrapper | Each native command retains its native parser, which retains the solver and symbol manager | Each owned command reference is released; no additional Mojo parser anchor is needed |
| Results, synthesis results, proofs, grammars | The exported reference is adopted and the Mojo solver state is retained | Release the native handle before releasing the solver anchor |
| Terms, sorts, operators, datatype handles, statistics | cvc5 retains the native term manager behind each exported handle | Release the exported reference; copies acquire another reference |
| Converted statistics and option information | Native temporary values are copied into Mojo strings, variants, and containers | `_StatReference` releases its native handle when conversion returns or raises |

`gen_api.Model._keepers` derives the borrowed-state relationships from C
signatures and rejects cycles. The current Mojo graph is acyclic: term-manager
state can retain solver state, and solver/symbol-manager state can retain
parser state. Native parser dependencies point to native objects, not back
to Mojo states. A new mutation regression checks that a reverse relationship
is rejected.

The C implementation's `delete` entry points can decrement reference counts
without immediately freeing native objects that other handles retain.
Balancing calls to these entry points is necessary evidence, not proof that
the entire native heap was freed.

## New regression coverage

`tests/smoke/test_ownership.mojo` uses one generic container exercise for
implicit copies, explicit moves, list assignment/pop/clear, dictionary
replacement/pop/clear, and optional replacement/reset. This avoids separate
implementations of the same operation sequence for each handle type.

| Fixture section | Checks |
|---|---|
| Borrowed owners | Internal and external symbol managers; solver and symbol-manager values surviving their original parser wrapper; a borrowed term manager surviving a borrowed solver; results retaining a borrowed solver; commands surviving the parser wrapper; command invocation through the retained original graph |
| Handles in containers | Results, proof children, grammars, synthesis results, terms, sorts, operators, datatype declarations and constructor declarations, datatypes, constructors, selectors, and statistics; distinct replacement values where supported; values used after their original owner wrappers disappear |
| Exceptions | A native type error and a rejected embedded-NUL argument while result/term containers remain live; a constructor failing after Result and List[Term] fields initialize; parser failure followed by valid input; valid native calls after every caught error |
| Returned buffers | Assertion arrays surviving a later array export; copied symbol text surviving another getter; option information surviving another option query and solver destruction |

The partially initialized object is a test fixture containing binding values.
This tests Mojo unwinding of those fields; it does not simulate arbitrary
failures halfway through every generated native-array conversion.

The contract runner supports O0 and O3 and both assertion modes on source and
precompiled imports. For ordinary ownership runs it enables the existing
native-call tracer. Markers delimit the four fixture sections. After each
section it checks that owner-construction and deletion counts match and that
successful query-result receipts plus copies equal releases. Missing or empty
sections, corrupt calls, duplicate completion, extra deletion, and missing
releases fail the gate. Expected errors occur outside the constructors and result-producing
calls used for this accounting.

This accounting derives lifecycle names from the canonical generator model.
It counts calls rather than addresses and does not claim per-pointer balance
for every other handle or array element. The other families have semantic
lifetime/container coverage in this step.

An optional untraced mode repeats the borrowed-owner and exception sections
after 40 warmup rounds. Its final RSS growth budget is 4 MiB. Separately, the
matched `commands` fixture repeatedly parses a fixed command, copies it,
checks both names, and releases both references while the parser remains
alive. Direct C, raw Mojo, and public Mojo use the same cached main and parser
library bytes and equivalent native operations. It never invokes the command
or accumulates assertions.

## Results on 2026-10-07

All runs used the cached Mojo 1.1.0 and cvc5 1.4.1 dependencies on Linux
x86-64. The eight ownership configurations passed: source and package imports,
O0 and O3, with and without `ASSERT=all`. Counts balanced in all four fixture
sections. The full O3 contract suite passed all 20 configurations, including
the pre-existing string, null, integer, and retention regressions.

Four additional O3 configurations each completed 1,000 measured borrowed-owner
and exception rounds after warmup. Final RSS growth was 356–372 KiB, below
the 4 MiB budget. This checks repeated graph cleanup; it is not a matched C
allocation profile and does not classify individual retained allocations.

The matched command matrix completed 12 runs at 200,000 and 1,000,000
iterations, twice per layer: **7.2 million measured iterations** in total.
All runs passed. Maximum growth was 40 KiB in C and 344 KiB in either Mojo
layer; maximum paired excess over C was 304 KiB. Each iteration made one
command export, one copy, two releases, two name queries, and one input reset
in all three layers. The existing deliberately retained result control still
detected the known extra-reference pattern.

The updated CI command passed all 15 short matched cases. Ten binding-analysis,
nine generator, and eleven existing soak-analysis unit tests passed, as did
all 16 documentation example builds/runs and the strict documentation checks.
The strengthened trace validator also accepted all eight saved ownership
traces. The full translated upstream suite was not rerun in this step.

Evidence is retained in `.cache/ownership-contracts`, `.cache/ownership-debug`,
`.cache/ownership-stress`, and `.cache/ownership-commands`. The first two
include native-call traces; the matched report includes actual library hashes,
commands, checkpoints, and dependency/source hashes. The aggregate index is
`.cache/ownership-report/summary.json`. These are local artifacts, not tracked
source files.

## Running the checks

All commands below use the cached dependencies directly. The ordinary
`contracts` task also includes this fixture, but its task dependencies may
fetch; invoke the script directly when fetching is not wanted.

```sh
pixi run --locked python scripts/run_contract_tests.py --only ownership --optimization 0,3 --output .cache/ownership-new
pixi run --locked python scripts/run_contract_tests.py --only ownership --ownership-iterations 1000 --output .cache/ownership-stress-new
pixi run --locked matched-controls --modes commands --operations 200000,1000000 --repetitions 2 --output .cache/commands-new
```

Use separate output directories to retain evidence. Ordinary contracts run
the traced O3 matrix, and CI additionally runs the O0 ownership matrix. The
CI matched-control subset includes commands at 20,000 iterations per layer.
Longer command and repeated-graph runs remain explicit checks.

## Remaining work and next step

The follow-up [family controls](family-controls.md) completed the initial
matched datatype, statistics, and synthesis-result fixtures. Repeated synthesis
queries grow in direct C too, while stored-result copies and complete graph
cleanup pass. Next exercise failures during returned-array/dictionary conversion and
temporary-buffer decoding. The current error tests cover argument conversion,
native errors, and user-object partial initialization, not every partially
converted native return. Allocation tracing or suitable instrumentation is
still needed to attribute retained native memory beyond RSS and API counts.

The [grammar-formatting finding](binding-controls.md#grammar-formatting-remains-an-open-finding)
remains unresolved. The current work adds no solver recycling, hidden caches,
new string-conversion API, or packaging changes.
