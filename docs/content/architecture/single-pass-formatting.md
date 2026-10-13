# Single-pass formatting

Use `value.toString()` when an owned textual representation is needed. This
calls the native formatter **once** and immediately copies and validates its
UTF-8 output. The returned `String` survives subsequent native calls and the
destruction of the original wrapper and its owners.

The method is available on `Term`, `Sort`, `Op`, `Result`, `SynthResult`,
`Grammar`, `Datatype`, `DatatypeConstructor`, `DatatypeSelector`,
`DatatypeDecl`, `DatatypeConstructorDecl`, and `Command`. This pass adds the
first eleven methods; `Command.toString()` was already part of the mirrored
Python API. The [overhead baseline](binding-overhead.md) identified the
duplicate formatting cost.

## Why an explicit method

Mojo 1.1 implements `String(value)` for `Writable` values by calling
`write_to` twice: first to count bytes and then to fill the destination.
Implementing `__str__` does not change that constructor's dispatch; the old
`Stringable` trait is unavailable in this toolchain. This is outside the
binding library's implementation scope.

### Constructor investigation, 2026-10-08

Rechecked the installed compiler's constructor overloads and the
[Mojo 1.1 `String` implementation](https://github.com/modular/modular/blob/c6fa49f712fe15c99d0461ad2baaf2a15cbc58ce/Mojo/stdlib/std/collections/string/string.mojo#L464).
The variadic constructor unconditionally sends its arguments to
`_TotalWritableBytes`, then writes them again into a growable destination.
The public
[`Writable` and `Writer` traits](https://github.com/modular/modular/blob/c6fa49f712fe15c99d0461ad2baaf2a15cbc58ce/Mojo/stdlib/std/format/__init__.mojo#L88)
provide no single-pass conversion or byte-count bypass hook. Adding a wrapper
`__str__` cannot redirect this constructor.

A proposed upstream change is a single-argument constructor path that
initializes an empty `String` and writes the argument and `end` once. It would
need standard-library correctness and performance validation, especially for
large output and custom `Writable` implementations. This proposal has **not**
been applied or tested as a toolchain change. The pinned dependencies remain
unchanged.

Do not special-case the private counting writer and report a false length.
That breaks its counting contract and depends on internal implementation
details. Do not keep a pending formatted string in wrappers or global state:
the public writer protocol supplies no paired-pass lifetime, and mutable
declarations, aliasing, and nested formatting make invalidation unreliable.
Shadowing `String` with a library function would also change name resolution
and would not fix existing uses of the standard type.

The current supported call-site solution is `value.toString()` (or
`String(value.toString())` when the outer constructor must remain). It makes
one native formatting call. Fixing **unchanged** `String(value)` calls needs
an explicitly approved expansion beyond the binding repository into Mojo's
standard library, or a future verified toolchain release with that support.

Fresh verification is retained in
`.cache/string-single-pass-contracts/report.json`: all eight O0/O3,
source/package, assertion-mode configurations pass. Each checks all twelve
formatter families and confirms the existing 1 / 1 / 2 native call counts
for `toString()`, direct `write_to`, and `String(value)`, plus null/lifetime
behavior. All 48 deliberately injected native/UTF-8 abort cases are correctly
classified. This is evidence for the current behavior, **not** a constructor
fix or a new performance result.

`toString()` provides a direct conversion without altering that language
behavior. `String(value)`, `print(value)`, and direct `write_to` remain
available. The existing single-pass pattern—create an empty `String`, then
call `value.write_to(text)`—also continues to work. **Existing `String(value)`
call sites do not automatically become single-pass.**

The generator emits the conversion once and makes `write_to` delegate to it.
Native formatter selection and null text still come from the extracted
snapshot and null oracle. There is no stored formatting cache, new wrapper
field, extra native reference, or owner anchor. Mutable declarations and
grammars are formatted afresh on every call.

## Error and null contracts

The eleven new methods follow the existing non-raising `Writable` contract:
native errors and invalid returned UTF-8 abort with the original diagnostic.
Null objects return their existing formatter-specific text without calling
the native API. This is a convenience for the already-supported formatting
operation, not a new recoverable formatting-error contract.

`Command.toString()` retains its **raising** contract and native rejection of
a null command. `String(Command())` and `Command().write_to(...)` retain the
`"null"` marker. The generator recognizes and reuses this existing method
rather than replacing it. It fails generation if an existing `toString`
method does not match the expected no-argument native string formatter.

## Verification

`tests/smoke/test_formatting.mojo` runs through the existing contract runner
at O0/O3, source/package imports, and with/without assertions. All eight
configurations verify:

- Identical text from `toString()`, direct `write_to(String)`, and
  `String(value)` for all twelve native-formatted classes.
- Exactly 1 / 1 / 2 native formatting calls respectively, using separate
  trace sections and function names extracted from the API snapshot.
- Null formatting without native calls for the eleven new methods, plus
  preservation of the existing Command null/error distinction.
- Returned strings surviving later formatting, owner destruction, and
  mutation of a grammar through an aliased handle.
- Native-error and invalid-UTF-8 injection through each formatting route:
  48 deliberately aborting subprocesses. The runner requires Mojo 1.1's
  Linux trap exit and the specific `ABORT:` diagnostic. Other signals,
  missing diagnostics, success, and timeouts fail.

The generator guard and trace/failure classifiers have mutation regressions.
The formatting fixture is part of the normal O3 contract gate and a separate
O0 CI invocation. Run only this fixture with cached dependencies using:

```sh
pixi run --locked python scripts/run_contract_tests.py \
  --only formatting --optimization 0,3 \
  --output .cache/formatting-<fresh-name> --jobs 4
```

The API generator was run directly against the cached snapshot, with a
second emission checked for identical output. No dependency refresh or
generated-file hand edit is needed.

Additional checks passed: eight existing null-formatting configurations,
four string and four ownership configurations, 32 binding-analysis and ten
generator unit tests, and all sixteen documentation example builds/runs.
Strict documentation and link checks passed. Production source fingerprints
match the formatting, null, string, ownership, and performance reports.
The full translated upstream suite and whole-heap leak profiling were not
rerun in this targeted pass.

Correctness artifacts are `.cache/formatting-contract-final/report.json`,
`.cache/formatting-null/report.json`, `.cache/formatting-strings/report.json`,
`.cache/formatting-ownership/report.json`, and
`.cache/formatting-docs/report.json`. The final formatting report preserves
the import-route labels separately from the injected error routes.

## Measured improvement

The finished implementation was measured with cached cvc5 1.4.1 and Mojo
1.1.0. Each route used nine shuffled repetitions of 200,000 operations after
10,000 warmup operations, pinned to a CPU, with no competing test builds.
Both calls produced the same owned representation of the same 256-bit integer
term; every byte contributed to the checked result. Timing excluded tracing
and allocation instrumentation. Direct C and raw Mojo controls used the same
native library bytes. There were 216 passing timing processes across three
workloads, four layers, and both import routes.

| Import route | `String(term)`, median | `term.toString()`, median | Reduction of medians |
|---|---:|---:|---:|
| Package | 4.080 µs | 2.258 µs | 44.7% |
| Source | 4.227 µs | 2.211 µs | 47.7% |

Pairing by repetition gives median savings of 1.994 µs (package) and
2.045 µs (source). Descriptive bootstrap intervals for these savings are
1.777–2.170 µs and 1.822–2.304 µs respectively. This is a formatting workload
improvement when using the explicit API, not a solver-throughput claim or an
automatic speedup for existing `String(value)` calls. Timings cover `Term`;
the call-count and correctness matrix covers all twelve classes.

Separate package diagnostics confirm one native formatter invocation per
`toString()` versus two per `String(term)`. The libc probe observes 18 malloc
and one realloc request versus 36 and two, with cumulative requested bytes
falling from 36,864 to 18,432 per operation. It does **not** observe Mojo's
TCMalloc allocations, measure total heap use, or establish leak freedom.
The unchanged decimal-copy control remains about 1.1–1.2 µs in public Mojo
versus 0.66–0.70 µs in checked C, supporting shared conversion buffers as
the next priority.

Reports retain raw observations, source/dependency/binary hashes, loaded
libraries, and variation:

- `.cache/formatting-benchmark-package/report.json`
- `.cache/formatting-benchmark-source/report.json`
- `.cache/formatting-probe/finished-api-comparison.json` (paired comparison)

Reproduce the package campaign with cached dependencies:

```sh
pixi run --locked binding-benchmark \
  --output .cache/formatting-benchmark-<fresh-name> --route package \
  --modes format,format-once,decimal-copy \
  --operations 200000 --repetitions 9 --cpu 0
```

The source confirmation used `--route source --cpu 4 --order-seed 73
--skip-traces --skip-allocations`. Choose an allowed CPU on the target host.

## Follow-up

The subsequent [shared-buffer optimization](string-buffers.md) removes
unnecessary growth and intermediate copies from `c_bytes` and `to_string`.
It also improves existing `String(value)` calls, while preserving their two
native formatting calls and all validation/ownership contracts. The timings
above record the earlier single-pass API change in isolation.

The subsequent [integer-literal fast path](integer-literals.md) handles
representable literals. Next investigate shared collection-marshaling buffers.
Native grammar-formatting and repeated synthesis growth remain separate,
unresolved native findings; reducing formatter calls does not fix them.

## Direct Mojo and C exchange

Formatting is not the representation used to pass CVC5 objects across the
binding. `Term`, `Sort`, and the other wrappers already hold native handles.
For example, `mkTerm` puts its arguments' `Cvc5Term` handles into an array,
calls C, and receives a handle for the result. No term serialization, text
parsing, or reconstruction of an expression tree occurs. Handle receipt,
copy/release, and owner lifetime rules still apply; direct exchange does not
mean arbitrary C++ objects can be reinterpreted as Mojo objects.

The pinned C interface permits further removal of numeric text conversions:

| Value or operation | Path at the initial audit | Binding-side opportunity |
|---|---|---|
| Handles, Boolean values, scalar API parameters | Native handles/scalars | Already direct |
| `mkInteger(Int)` and fitting integer literals | `cvc5_mk_integer_int64` | Already direct |
| `mkInteger(Integer)` | Decimal text, even for small values | Exact signed-64 range check, then reuse the existing typed overload |
| `getIntegerValue()` | Native decimal text parsed into `Integer` | Native signed/unsigned-64 predicates and getters, constructing `Integer` directly; retain the exact wide fallback |
| `mkReal(Rational)` and numeric numerator/denominator pairs | Decimal text | `cvc5_mk_real_num_den` when both inputs fit its signed-64 parameters |
| `getRealValue()` | Native decimal text parsed into `Rational` | Native real64 predicate/getter, with a signed-64 numerator and unsigned-64 denominator; retain the exact wide fallback |
| Numeric bit-vector construction | Decimal text | Check nonnegative unsigned-64 range before using `cvc5_mk_bv_uint64`; preserve width and error semantics |

These opportunities were subsequently approved and implemented in the
[direct numeric conversion pass](numeric-conversions.md). That report records
the exact range policies and validation. Existing public signatures and
arbitrary-precision results are preserved; private native helpers reuse the
generator's error checking and handle-receipt mechanisms. Wide-value dispatch
does not construct a conversion error to select the fallback.

There are limits to direct exchange through the pinned C ABI:

- Arbitrary-precision integer/rational and finite-field entry points expose
  text, not a limb buffer or an APN-compatible numeric object. Removing that
  serialization completely needs a native API extension or another ABI;
  reinterpreting APN storage as a CVC5 object is not valid.
- `getStringValue()` preserves embedded NUL by decoding the SMT-LIB
  representation. The C UTF-32 getter has no length, so simply scanning to
  the first zero would reintroduce truncation. A counted native string getter
  would be needed to remove this representation safely for all values.
- The Float64 real constructor intentionally uses shortest decimal text,
  matching Python: `0.3` denotes `3/10`. Importing the exact IEEE binary
  fraction instead would change that public behavior.

The direct numeric paths are implemented; see their linked report for the
validation results. The exact `String(value)` request remains a separate
toolchain scope decision.
