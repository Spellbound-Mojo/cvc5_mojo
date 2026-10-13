# Cleanup after partial return conversion

The next ownership step found and fixed a **failure-path reference leak** in
`SymbolManager.getNamedTerms()`. When a returned name failed UTF-8 decoding,
terms for later dictionary entries were never adopted or released. With three
exported terms and an invalid first name, the previous binding released one
reference and left two outstanding. The fixed binding releases all three.

This was reproduced with a test-only adapter that corrupts a returned string
after the real native function has exported its references. The attempted
malformed parser input was rejected before reaching this conversion, so this
is not evidence that ordinary valid SMT-LIB input triggers the defect. It
demonstrates incorrect ownership when a conversion raises, independently of
RSS or assumptions about the allocator.

## Fix and scope

`bindgen.gen_api` now generates an adoption cursor for each handle array in a
returned dictionary. It adopts the current row's handles into local wrappers
before decoding strings. If conversion raises, Mojo destroys those locals and
the entries already inserted; a `finally` block releases the unadopted tail
of each native array. Release functions come from the existing lifecycle
model. The rule covers both mixed term/string and term/term dictionaries.
No extra staging container or native reference copy is required. The normal
three-entry named-term fixture still makes three exports, zero copies, and
three releases.

Private `_received` helpers now declare their existing non-raising behavior.
They wrap an exported reference and, where needed, retain its owner state;
they perform no native call. Ordinary arrays of handles therefore have no
recoverable element-decoding failure under valid owner invariants. This pass
does not simulate process-aborting allocation failure or malformed raw handle
pointers. Public signatures and successful results are unchanged.

All implementation changes were made in the generator and regenerated from
the cached snapshot. The test adapter and its installation live only under
`tests/`; no production fault-injection mechanism was added.

## Regressions

`test_return_conversion.mojo` uses `return_faults.c`, compiled against the
cached cvc5 headers. The adapter opens the exact native library paths used by
the binding and forwards each call to the real function. Selected function
pointers are replaced only inside the isolated test process. Native buffers
and handles are real; one selected string pointer is replaced with invalid
UTF-8. Borrowed arrays are copied before altering the test response.

The adapter records exported, copied, and released references by address
during each conversion. Unmatched or duplicate releases fail separately from
outstanding-reference counts. Owners remain alive when the counts are checked.
Each injected error must be the expected UTF-8 error and must actually fire;
each is followed by the same valid public operation. A successful control is
also checked for every family.

| Conversion | Injected failure positions on the fixture | Ownership checked |
|---|---|---|
| Named-term dictionary | 0, 1, 2 of three entries | All three term exports, including entries not reached |
| Generated option-name array | 0, 267, 534 of 535 strings | Partial Mojo list cleanup and recovery |
| Statistics iteration to dictionary | 0, 252, 504 of 505 entries | Every exported private statistic reference |
| Statistic histogram | 0, 3, 5 of six keys | Statistic reference retained during partial dictionary conversion |
| String-valued statistic | Its value | Statistic reference released on decoding error |
| Option information | 0, 2, 3 of four mode strings | Partially initialized Mojo object and string list |

Separate buffer tests reject invalid UTF-8 and malformed SMT-LIB escapes
after a valid prefix, then successfully decode valid strings including an
embedded NUL. Test buffers explicitly remain alive across casts to untracked
pointers. Early fixture attempts lacked this lifetime protection and were
corrected before the final matrix; those failures were test defects.

The statistics, option-array, and option-information cases passed against the
previous cached package too. The corrected regression fails against that
package specifically because named-term conversion leaves two references
outstanding. Thus the test demonstrates the fixed defect rather than merely
accepting the new implementation.

## Results on 2026-10-07

All eight configurations passed: source and precompiled imports, O0 and O3,
with assertions enabled and disabled. Each checks six successful conversions
and 16 injected failures, followed by valid recovery calls.

The same eight binaries each completed 500 measured complete test graphs
after ten warmup graphs. These **4,000 measured graphs include 64,000 injected
failures**, with zero outstanding tracked references. RSS growth after warmup
ranged from **680 to 812 KiB**, within the 4 MiB test budget. The address-level
checks establish release of the instrumented native references; the RSS
checks additionally exercise temporary Mojo objects across repeated errors.
They do not prove absence of every heap leak or identify all retained memory.

The broader regression run passed all 24 O3 contract configurations, the API
smoke test, nine generator tests, 12 matched-control analysis tests, and 11
soak-analysis tests. Targeted translated SymbolManager and Solver programs
passed 126 tests; their two existing documented failures were separately
reproduced. All 16 documentation examples and strict documentation/link checks
passed. Generated class files match regeneration from the cached snapshot.
The full translated upstream suite and a heap profiler were not run in this
step.

Local evidence is retained in:

- `.cache/conversion-before/clean-baseline.json`: corrected test against the
  previous package, including its hash and the expected cleanup failure;
- `.cache/conversion-matrix-01/report.json`: eight build configurations,
  per-case counters, source/dependency hashes, and the adapter build;
- `.cache/conversion-matrix-01/soak.json`: repeated cleanup runs using those
  exact binaries;
- `.cache/conversion-contracts` and `.cache/conversion-verification`:
  regression results and the investigation index.
- `.cache/conversion-upstream-symbols`, `.cache/conversion-upstream-solver`,
  and `.cache/conversion-docs`: targeted upstream and documentation runs.

The previous [native synthesis and grammar findings](family-controls.md#repeated-synthesis-queries-fail-the-memory-budget)
remain open. This fix concerns binding cleanup after a conversion error; it
does not change native query or formatting behavior.

## Running the checks

The existing contract runner builds the adapter automatically. CI includes
this fixture in its regular O3 matrix and separately checks O0. These direct
commands reuse cached dependencies without invoking a fetch task:

```sh
pixi run --locked python scripts/run_contract_tests.py --only return_conversion --optimization 0,3 --output .cache/conversion-new --jobs 4
pixi run --locked python scripts/run_contract_tests.py --only return_conversion --optimization 0,3 --conversion-iterations 500 --output .cache/conversion-soak-new --jobs 4
```

## Next step

The [returned-collection pass](returned-collections.md) subsequently shares
counted conversion and adds native iterator-getter failure injection using
this adapter, alongside repeated cleanup checks.

The subsequent [compound FFI pass](compound-ffi.md) covers representative
out-parameter widths, returned-array lengths, nested input arrays, optional
arguments, and error recovery. Next strengthen concurrent initialization,
independent-thread error isolation, and loading failures. Native allocation
attribution beyond RSS and API references remains an explicitly open part of
the broader ownership audit.
