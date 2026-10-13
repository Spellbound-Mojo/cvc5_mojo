# Generated operation sequences

This pass extends the existing C/raw/public comparisons with replayable
stateful sequences and an independent Python exact-arithmetic model. The
32-seed matrix passes in all eight build configurations. No binding defect
was reproduced, and the binding source files are unchanged from the
[runtime validation pass](runtime-validation.md).

## Protocol

`scripts/binding_sequences.py` owns input generation, the expected-value
model, failure classification, and bounded sequence reduction.
`tests/binding/sequences.c` executes the inputs through the cached C API.
`tests/smoke/test_sequences.mojo` executes the same file through raw or public
Mojo calls. The existing contract runner builds and runs all three layers,
checks loaded-library identity, and records source/dependency/input hashes.

Python's arbitrary-precision integers and `fractions.Fraction` compute the
expected values without calling cvc5, apn_mojo, or the binding generator.
Every layer must match that model, and Mojo must also match the corresponding
C output. Agreement between C and Mojo alone cannot certify an incorrect
value. Model tests include hand-written expected observations; a simulated
narrowing defect checks that matching wrong C/Mojo output still fails and
produces a smaller replay file.

Each process begins with eight integer slots initialized to zero and an
empty saved collection. Operations are whitespace-separated records:

| Operation | Behavior checked |
|---|---|
| `I` | Replace a slot with an exact integer through String, arbitrary-precision Integer, or in-range runtime Int input |
| `C` | Copy between slots, including self-copy and replacement; public mode reuses the existing List/Dict/Optional copy/move fixture |
| `A` | Add or subtract two slots, simplify the constant expression, and replace a destination that may alias an input |
| `Q` | Construct and retrieve a rational using six public input forms: combined text, two strings, two Integers, both mixed forms, or Rational |
| `B` | Construct signed/unsigned bit-vector boundary values in decimal, binary, or hexadecimal; check the unsigned decimal result |
| `V` | Get a model-value array with empty, repeated, or reordered slot references; adopt it before another call overwrites the native output buffer |
| `G` | Inspect the saved collection after intervening mutations, errors, and solver destruction |
| `R` | Replace the test solver while retaining the term manager, slots, and saved returned terms |
| `E` | Reject malformed integer text, zero-denominator rational text, bit-vector overflow, a wrong-type getter, a non-Boolean assertion, or mixed-sort arithmetic; unwind local copies and perform a valid read |
| `P` | Check value equality, ordering consistency, and equal-value hashing; public mode also checks dictionary insertion/lookup with term keys |

Solver replacement here is a test of returned-term lifetime. It is not a
binding policy or application lifecycle recommendation. The test never mixes
native object graphs from different term managers. Raw mode uses public
wrappers for fixture ownership and calls the generated raw API at the
crossing under test; C remains an independent implementation.

The mandatory 249-operation prefix includes signed values around 31-, 32-,
63-, 64-, 127-, and 256-bit boundaries; bit-vector widths 1, 2, 7, 8, 31, 32,
63, 64, 65, 127, 128, 256, and 257; every rational form and rejection family;
empty arrays; and saved values inspected after errors and solver destruction.
Seeded operations then vary values, forms, slot aliasing, array order and
length, and operation order. Runtime integer inputs are tested here; the
separate integer-boundary fixture tests compile-time literal narrowing.

Rational observations use normalized `numerator/denominator` form. Native C
prints `0/1` where the public Rational's Python-style formatter prints `0`.
The fixture adds `/1` to the public representation in that case. This is
value normalization in the test protocol, not a library formatting change.
Term ordering is checked for consistency, not mistaken for numeric ordering.

## Reproduction and reduction

Every generated input and its complete expected output are saved before
execution. Reports retain the seed settings, exact input hashes, command,
output, return code, and loaded libraries. Failed C controls stop the matrix
before they can be used to certify Mojo results.

On a completed-run output discrepancy or unexpected process exit, the runner
tries at most 80 chunk deletions. Slots always start initialized, so deleting
operations does not create dangling input dependencies. Each candidate gets
a freshly computed mathematical expectation. The reducer preserves the
failure category and, for output discrepancies, the first mismatching
opcode. Original inputs remain intact; the reduced input, expected output,
replay command, and confirmation result are saved separately.

This is a bounded reduction, not a guarantee of a globally minimal test or
minimal numeric values. It preserves an exit category rather than proving
that two crashes have the same root cause; reduced failures still require
investigation. Timeouts fail the check but are not automatically reduced.
Crashes, incomplete output, missing completion markers, and mismatched
libraries can never pass as expected rejection cases.

## Results on 2026-10-07

| Measure | Result |
|---|---|
| Seeds | 0 through 31 |
| Operations per input | 761: 249 mandatory plus 512 generated |
| Input operations across the corpus | 24,352; the mandatory prefix repeats in each stream |
| Build configurations | 8: source/package × O0/O3 × assertions enabled/disabled |
| C executions | 64: one per seed at each optimization level |
| Mojo executions | 512: raw/public for every seed and configuration |
| Checked operation observations | 438,336 across all layers |
| Rejected-operation recovery | 1,144 operations in the corpus, replayed 18 times for 20,592 checks |

All cases matched the independent model and direct C, with byte-identical
cached native libraries. No minimized binding discrepancy was produced.
The initial pilot diagnosed the rational-format distinction above and two
unused test-variable initializations rejected by `--Werror`; neither was a
binding defect.

This pass checks observable values and handle validity, not allocation
balance for every operation. The earlier ownership and return-conversion
checks remain the evidence for their instrumented reference lifecycles.
The corpus is deliberately bounded to these ten operation families; it is
not an exhaustive search of the supported API. Native growth and C API
limitations from previous reports remain open.

Broader validation passed all 32 O3 contract configurations, 44 generator
and runner analysis tests, all 16 documentation-example configurations, and
strict documentation/link checks. The full translated upstream suite and
heap profiling were not rerun in this pass.

Local evidence:

- `.cache/sequences-matrix-01/report.json`: the complete matrix, hashes,
  native controls, and per-case results;
- `.cache/sequences-matrix-01/sequence-inputs/`: exact input and expected
  files for each seed;
- `.cache/sequences-verification/summary.json`: investigation index and
  broader regression results;
- `.cache/sequences-pilot-01` and `.cache/sequences-pilot-02`: initial
  diagnostics and the passing O3 pilot.

## Running the checks

The regular contract suite now includes a short three-seed corpus at O3.
CI and the cvc5 update workflow also run it at O0. Use the runner directly
to avoid fetch task dependencies:

```sh
pixi run --locked python scripts/run_contract_tests.py --only sequences --optimization 0,3 --sequence-seeds 0,1,42 --sequence-steps 512 --output .cache/sequences-new --jobs 4
```

To replay a saved input or a reduced failure, pass
`--sequence-input path/to/case.txt` instead of seed selection. The report
records the copied input, its expectation, and the selected build matrix.

## Next step

The [binding-overhead baseline](binding-overhead.md) now covers cold loading,
inexpensive scalar calls, handle copies/destruction, collection marshaling,
and decimal/string conversion against the same cached C build. Next reduce
the measured formatting and conversion costs. These correctness and ownership
checks remain regression gates for those optimizations.
