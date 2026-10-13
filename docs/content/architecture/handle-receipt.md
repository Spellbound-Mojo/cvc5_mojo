# Handle receipt and anchor generation

The generator now uses one receipt policy for ordinary results, arrays,
iterators, and term convenience methods. It rejects unknown ownership modes
and anchor relationships the receiver cannot supply. **All 23 binding source
files are byte-for-byte unchanged after regeneration.** This pass hardens the
generator without changing public APIs, native reference counts, or runtime
ownership behavior.

## Audit and consolidation

The ownership facts remain extracted by `bindgen.c_impl.handles` into the
snapshot. The [runtime ownership rules](runtime.md#handle-ownership) determine
whether a returned native reference can stand alone or needs a retained owner.
The generator's `Model.received` already applied those rules to ordinary
results, out-parameters, arrays, and dictionaries. Two specialized emitters
assembled `_received(...)` calls themselves: counted iterators and term
convenience methods. They supplied no anchor because their current returned
handle types do not need one. A future ownership change could therefore update
ordinary returns while leaving those paths inconsistent.

Both specialized emitters now call `Model.received`. `receiver_context` supplies
the receiver's API, term manager, and native handle expressions in one place.
`bind_receiver` resolves the receipt template using the actual receiving class,
including methods that delegate to another class. Anchor placeholders name the
required owner category, so emission checks that the receiver either is that
owner or carries that same owner anchor. It rejects an absent or different
anchor instead of emitting a wrong owner type or a nonexistent field.

Model construction also rejects unknown receipt modes and anchor exporters
that are not generated pointer-owned classes. This validates binding policy;
it does not replace the extractor's independent checks of cvc5's allocation,
reference initialization, deregistration, and release protocol.

The audit retained these existing distinctions:

- Receiving a handle adopts its existing native reference; copying an existing
  wrapper acquires another native reference.
- Solver-dependent handles retain an owner anchor and release the native handle
  before that anchor. Null copies/destruction skip native reference operations.
- A borrowed pointer-owned wrapper retains its returning wrapper's state and
  does not delete the borrowed native object. Keeper relationships remain
  derived from C signatures and checked for cycles.
- The manual `_StatReference` holds a native reference only during value
  conversion. It is not another public handle family and remains a separate
  scope-bound cleanup guard.

Manual fragments continue to use the generated receipt factory where they
return public handles. No wrapper cache, new runtime abstraction, constructor
signature change, or anchor-removal optimization is introduced.

## Verification, 2026-10-07

Two cached invocations of `python -m bindgen.gen_api` produced identical output,
matching every pre-pass binding source hash. The API snapshot and dependency
lockfile are unchanged. The generator still emits 18 classes and implements
387 of 388 mirrored methods; the existing unsupported plugin callback method
remains accounted for.

All **13 generator tests** and **37 binding-analysis tests** passed. New mutation
checks cover unknown receipt modes, invalid anchor exporters, missing or
mismatched receiver anchors, anchor propagation through iterators and term
builders, and a delegated method using its actual receiver's anchor.

All **eight ownership configurations** passed: source/package imports, O0/O3,
and assertions on/off. Existing regressions exercise detached handles and proof
children, borrowed parser/solver/term-manager chains, container copies and
replacement, native errors, and partial user-object initialization. Native
traces balance owner creation/deletion and result receipts/copies/releases.
Four O3 return-conversion configurations also passed, including injected native
iterator and decoding failures with zero outstanding tracked references.

The cached C/raw/public controls passed **24 live-owner runs**, totaling
**264,000 measured operations** across result, proof, empty-grammar, and stored
synthesis-result workloads. Each layer also ran one-versus-33 operation traces.
The native work per operation was:

| Workload | Handle exports | Handle copies | Handle releases |
| --- | ---: | ---: | ---: |
| Result query and copy | 1 result | 1 result | 2 results |
| Proof root, child, and copy | 2 proofs | 1 proof | 3 proofs |
| Empty grammar and copy | 1 grammar | 1 grammar | 2 grammars |
| Stored synthesis result | 0 in the measured region | 2 synthesis results | 2 synthesis results |

The public empty-grammar fixture additionally copies/releases one term for its
argument list. Other native calls and reference work match the independent C
control. There is no extra native copy on adoption in these traces. These
counts measure native reference work; they do not measure the CPU cost of Mojo
`ArcPointer` operations. The generated runtime code is unchanged, so this pass
makes no speedup claim and needs no before/after timing attribution.

Maximum post-warmup RSS growth was 28 KiB in C, 348 KiB in raw Mojo, and 344 KiB
in public Mojo. Maximum Mojo excess over paired C was 320 KiB, within the
existing 1 MiB comparison budget. The deliberately retained-reference control
grew by 34,004 KiB and was detected. These runs and balanced references support
correctness for the tested paths; they are not whole-heap leak accounting.
Known native grammar-formatting and repeated-synthesis growth remain open;
these workloads use empty grammars without formatting and stored synthesis
results.

Strict documentation/link checks are included. The full translated upstream
suite and documentation example execution were not repeated because generated
library output is unchanged.

## Reproduce with cached dependencies

Run the generator entry point directly to retain the cached API snapshot;
the full `generate` task has fetch/oracle dependencies.

```sh
pixi run --locked python -m bindgen.gen_api
pixi run --locked python -m unittest discover -s tests/bindgen -v
pixi run --locked python -m unittest discover -s tests/binding
pixi run --locked python scripts/run_contract_tests.py \
  --only ownership --optimization 0,3 --output .cache/handle-ownership-<fresh-name>
pixi run --locked python scripts/run_contract_tests.py \
  --only return_conversion --output .cache/handle-conversion-<fresh-name>
pixi run --locked matched-controls --output .cache/handle-controls-<fresh-name> \
  --modes results,proofs,grammar-empty,synthesis-copy \
  --operations 2000,20000 --repetitions 1
```

Evidence is retained in `.cache/handle-policy-before/`,
`.cache/handle-policy-ownership/`, `.cache/handle-policy-conversion/`, and
`.cache/handle-policy-controls/`. Reports include build commands, source and
library fingerprints, semantic observations, reference accounting, RSS
checkpoints, and the sensitivity control. Matched-control timings are diagnostic
only; they include more than copying and are not isolated anchor benchmarks.

## Next priority

Audit pointer-owned constructors and borrowed-owner state initialization,
including keeper selection and cleanup when construction fails. Consolidate
any duplicated policy while preserving native retention rules. Measure anchor
instruction/allocation costs before proposing a change to their runtime design.
