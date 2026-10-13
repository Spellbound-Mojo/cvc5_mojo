# Repeated-workload memory investigation

The targeted follow-up on **2026-10-13** reproduced grammar-formatting and
repeated-synthesis growth in direct C, raw Mojo, and public Mojo, all using
the pinned cvc5 1.4.1 library. Complete graph cleanup stayed within the
memory budgets. Native allocation profiles now identify SyGuS datatype
construction on the formatting path. The long-lived workloads still fail
the memory gate; no native fix or automatic recycling was introduced.

## Matched measurements

These runs reuse the [matched-control runner](binding-controls.md), with
precompiled Mojo imports, O3, assertions enabled, 100 warmup iterations,
and one repetition. The budgets remain 4 MiB growth after warmup and 1 MiB
of Mojo growth above the paired C control. Every process has a 60-second
timeout and the runner's existing 512 MiB memory cap.

| Workload and lifetime | Measured iterations | C growth, KiB | Raw Mojo growth, KiB | Public Mojo growth, KiB |
|---|---:|---:|---:|---:|
| Format the same grammar, live graph | 3,000 | 12,948 | 12,904 | 26,108 |
| Construct grammars and rules without formatting, live graph | 3,000 | 64 | 404 | 4 |
| Repeat synthesis, live graph | 3,000 | 21,132 | 20,964 | 20,960 |
| Format a grammar, complete graph per iteration | 1,000 | 64 | 20 | 4 |
| Synthesis, complete graph per iteration | 1,000 | 108 | 44 | 24 |

The live formatting and synthesis rows fail in all three layers. The
unformatted grammar row and all six complete-graph runs pass. Every run
completed, loaded the expected library bytes, and produced the matching
checksum. Native-call accounting and both retained-reference sensitivity
controls passed.

One formatting iteration prints both the grammar and its copy: two native
calls in C/raw Mojo, four in the public `String(grammar)` path. The measured
doubling agrees with Mojo's two-pass String construction. The existing
[`toString()` helper](single-pass-formatting.md) performs one native call;
it reduces the amplification but does not remove growth per native call.

Repeated synthesis shows no additional Mojo growth above C on this run.
That narrows the cause to the native workload; it does not make the workload
memory-safe for an indefinitely live graph.

## Allocation profiles

Two direct-C Massif profiles ran 1,000 measured iterations after 100 warmup
iterations. The grammar profile's retained allocations include
`NodeManager::mkMutualDatatypeTypesInternal`, `DType::addSygusConstructor`,
and skolem construction beneath `SygusGrammar::resolve` and
`SygusGrammar::toString`.

The checksum-verified source archive explains this path: the pinned
`SygusGrammar::toString()` copies the grammar and calls `resolve()` on the
copy before printing. Repeatedly printing an unchanged grammar therefore
repeats datatype construction. This is native allocation work, even when
the public grammar handle and its rule list have not changed.

The synthesis profile also contains SyGuS datatype construction beneath
default-grammar generation. Its peak additionally includes substantial
temporary solver initialization. A peak allocation tree alone does not
attribute every byte retained between queries; that needs a more detailed
comparison of the live allocations at query boundaries.

Separate Memcheck runs used 300 measured iterations after 30 warmup
iterations, then destroyed the complete graph. Both reported **zero errors
and zero definitely, indirectly, or possibly lost bytes**. Process-exit
reachable allocations were 40 bytes for formatting and 3,695 bytes for
synthesis. These observations support lifetime-dependent retention on
these fixtures, rather than a demonstrated unreachable leak. They do not
prove all workloads leak-free, or promise that the allocator returns freed
pages to the operating system immediately. RSS remained elevated after
cleanup in the live runs, even though repeated complete-graph runs stayed
bounded.

## Practical steps and next work

- Format a grammar only when its text is needed. If it is unchanged, keep
  the owned String from `grammar.toString()` and reuse that text. Refresh
  it after changing rules. This avoids repeated native resolution.
- For independent synthesis jobs, scope the term manager, solver, and
  their handles together. Return detached strings or exact numbers when
  a caller does not need live terms. See [ownership](../start/ownership.md)
  and the [earlier synthesis controls](family-controls.md).
- Do not treat `pop()` or dropping one solver variable as a memory budget.
  Copies, results, proofs, grammars, parsers, commands, and callback state
  can keep owners alive. User-created callback ownership cycles need
  explicit cleanup.

The next binding-level design to evaluate is shared grammar-text caching
with correct invalidation across aliases and mutations. It could bound
repeated formatting of an unchanged grammar, but it cannot fix allocation
growth from genuinely new grammars or repeated native synthesis. Before
adding such a cache, test its ownership, invalidation, and memory cost
against these same C controls. No hidden cache has been added here.

Changing-expression arithmetic workloads were not rerun in this follow-up;
their earlier results remain in the [soak report](soaks.md). Oracle callbacks
received targeted lifetime and error contracts, but this memory matrix does
not measure native oracle-cache growth with distinct arguments.

## Reproduce the bounded controls

Use fresh output directories:

```sh
pixi run --locked python scripts/run_matched_controls.py --output build/memory-live-new --modes grammar-reuse,grammar-rules,synthesis --operations 3000 --warmup 100 --repetitions 1 --timeout 60
pixi run --locked python scripts/run_matched_controls.py --output build/memory-round-new --modes grammar-reuse,synthesis --operations 1000 --warmup 100 --repetitions 1 --lifetime round --timeout 60
```

The first command currently exits nonzero because the native growth exceeds
the budget. Keep that failure visible. The second command passes on the
recorded fixture.

Local evidence is in `build/memory-live-20261013/report.json`,
`build/memory-round-20261013/report.json`, and
`build/memory-profiles-20261013/`. The matched reports contain commands,
hashes, mapped-library checks, checkpoints, checksums, and reference traces.
The profile directory contains the exact bounded commands and exit results,
Massif snapshots, extracted allocation summaries, Memcheck logs, and the
relevant source passages from the verified archive. No full test suite or
long-duration soak was run.
