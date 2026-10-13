# Development

For binding hardening with dependencies already installed, use
`pixi run --locked verify-binding --tier core --output .cache/verify-core`.
The `extended` tier adds sanitizer sensitivity, longer lifetime/error/thread
checks, matched memory controls, and stored timing baselines. Neither tier
fetches dependencies. See [production validation](../architecture/production-validation.md)
for prerequisites, gate selection, scope, and known native findings.

This page is for you if you change the bindings or the generator. Read the
[design principles](../architecture/principles.md) first, because they
decide what is generated and what may be written by hand.

## Environment

Set up a checkout as described in [installation](../start/installation.md).
The project defines these pixi environments:

| Environment | Contents | Used for |
|---|---|---|
| `default` | Mojo 1.1.0, apn_mojo 1.0.1, Python, LLVM tools, and a C compiler (glibc ≥ 2.34 sysroot on Linux) | The generator, tests, and packaging |
| `docs` | Python, MkDocs 1.6.1, and Pygments 2.19.2 | Building and checking this site |
| `oracle` | Python with PyPI `cvc5==1.4.1` | Differential tests against the official bindings |

The generator, `bindgen`, uses the Python standard library, the C compiler,
and LLVM’s `llvm-readelf`, `llvm-objdump`, and `llvm-nm` for native library
inventories and exported symbols. The locked `llvm-tools` dependency can
inspect ELF and Mach-O archives on either operating system.

Detailed implementation notes, validation reports, and release procedures
are grouped under **Contributing** in the navigation. The
[architecture overview](../architecture/overview.md) covers the essentials
for application authors.

The compiler and native solver checks run on the current host. **The full
`test` gate runs on Linux.** On macOS, `check-api`, `generator-tests`,
`soak-check`, `binding-check`, `cvc5-tests`, and the smoke tests other than
`tests/smoke/test_threads.mojo` run. `leaks`, `contracts`, `runtime-test`,
and the thread test use Linux-only facilities: `/proc/self`, POSIX
barriers, and ELF library names. Valgrind and the ELF loader fault
fixtures are Linux checks too. On macOS, `generate` also rewrites
`tests/cvc5/examples/floating_point.out` and `sygus_fun.out`, because
cvc5 finds different valid models there. Commit generated files from
Linux, as CI checks them.

## Repository layout

| Path | Contents |
|---|---|
| `cvc5-version.toml` | The pinned cvc5 release. Only `pixi run --locked bump` changes it. |
| `pixi.toml`, `pixi.lock` | The environment requirements and resolved builds, including apn_mojo from modular-community. Install them with `pixi install --locked`. |
| `bindgen/` | The generator: fetch, extract, join, report, render, diff, and bump |
| `bindgen/overrides.toml` | The only hand-maintained generator input, also called the [exceptions file](../architecture/join.md#the-exceptions-file) |
| `api/cvc5-api.json` | The [snapshot](../architecture/inputs.md#the-snapshot), which holds the extracted facts and the join. It is generated and committed. |
| `src/cvc5_mojo/` | The Mojo package: the enums, the [raw layer](../architecture/layers.md#raw-layer) `_c/raw.mojo`, one module per class, and `__init__.mojo`. Everything in it is generated except the [runtime](../architecture/runtime.md) module `_c/ffi.mojo`. |
| `tests/smoke/` | Raw-layer, API, smoke, lifetime, thread, and leak tests |
| `tests/cvc5/` | cvc5's Python unit tests and, in `examples/`, its examples, translated to Mojo by `bindgen.translate`. Each translated example comes with what the Python example prints, recorded by `bindgen.oracle`. `translation.json` says why the remaining tests and examples do not run. `calls.json`, written by `pixi run --locked cvc5-tests`, records which C functions they call. |
| `docs/content/` | This site's pages. The navigation is in `mkdocs.yml`. |
| `docs/examples/`, `docs/examples.json` | The runnable examples and their expected output |
| `docs/theme/`, `docs/hooks.py` | The site theme and the MkDocs hooks |
| `scripts/` | The documentation tooling (the audit, the site check, and the example runner) and the runner of the translated cvc5 tests |
| `recipes/cvc5_mojo/` | The conda recipe for modular-community; its tests run programs from `tests/smoke/` and `docs/examples/` |
| `third_party/` | The downloaded cvc5 release and source archive. Git ignores this directory. |

## Verification gates

Run these commands from the repository root. The `--locked` flag keeps every
dependency at the version in `pixi.lock`, as CI does.

| Command | Checks |
|---|---|
| `pixi run --locked generate` | Regenerates everything. Afterwards, `git status` must show no unintended changes under `api/`, `src/`, or `tests/cvc5/`. |
| `pixi run --locked test` | Completeness, generator, boundary-contract, runtime-loading, smoke, lifetime, thread, leak, and translated-upstream gates |
| `pixi run --locked cvc5-tests --test test_term.test_get_real` | One upstream unit test and its compile-failure fixtures; repeat `--test` for a focused group |
| `pixi run --locked cvc5-tests --only floating_point` | The floating-point example, including model validation and output comparison |
| `pixi run --locked contracts` | String, null, single-pass formatting, integer, collection-input, returned-collection, retention, ownership, return-conversion, compound FFI, and generated-sequence regressions across both import routes and assertion modes |
| `pixi run --locked contracts --only formatting --optimization 0,3 --output .cache/formatting-<n>` | Text, call counts, nulls, returned-string lifetime, and injected formatting errors; [single-pass formatting](../architecture/single-pass-formatting.md) |
| `pixi run --locked contracts --only strings --optimization 0,3 --output .cache/strings-<n>` | UTF-8 and NUL handling, buffer-size boundaries, and owned copies; [shared conversion buffers](../architecture/string-buffers.md) |
| `pixi run --locked contracts --only integer_boundaries --optimization 0,3 --output .cache/integer-<n>` | Exact integer values, range rejections, and native constructor selection; [literal fast path](../architecture/integer-literals.md) |
| `pixi run --locked contracts --only collections --optimization 0,3 --output .cache/collections-<n>` | Input and returned collection fixtures (substring filter): order, duplicates, empty arrays, conversion, and recovery; [collection buffers](../architecture/collection-inputs.md) |
| `pixi run --locked contracts --only returned_collections --optimization 0,3 --output .cache/returned-<n>` | Detached and partial iterators, returned array/string snapshots, statistics filters/order and independent values; [return conversion](../architecture/returned-collections.md) |
| `pixi run --locked contracts --only ownership --optimization 0,3 --output .cache/ownership-<n>` | Borrowed owners, handle containers, exception cleanup, returned buffers, and owner/result reference accounting; [cached-only commands](../architecture/ownership-audit.md#running-the-checks) |
| `pixi run --locked contracts --only return_conversion --optimization 0,3 --output .cache/conversion-<n>` | Partial return conversion, pending-reference cleanup, and recovery; [fault protocol and cached-only commands](../architecture/return-conversion.md) |
| `pixi run --locked contracts --only compound --optimization 0,3 --output .cache/compound-<n>` | Independent C/raw/public comparisons for numeric outputs, returned arrays, nested inputs, structs, and optional arguments; [scope and cached-only commands](../architecture/compound-ffi.md) |
| `pixi run --locked contracts --only sequences --optimization 0,3 --output .cache/sequences-<n>` | Seeded C/raw/public operation streams checked against an independent exact-arithmetic model; [replay and reduction](../architecture/generated-sequences.md) |
| `pixi run --locked generator-tests` | Fail-closed extraction and expected-failure classification regressions |
| `pixi run --locked runtime-test` | Library selection, missing symbols, version rejection, native initialization cleanup, and concurrent error isolation across both import routes and assertion modes; [protocol and cached-only command](../architecture/runtime-validation.md) |
| `pixi run --locked binding-check` | Matched-control memory, reference accounting, and loaded-library identity analysis |
| `pixi run --locked matched-controls --output .cache/matched-<n> --modes results,proofs,grammar-empty,grammar-rules,commands --operations 20000 --repetitions 1` | Cached-only C/raw/public ownership subset; see [protocol and formatting failure](../architecture/binding-controls.md) |
| `pixi run --locked matched-controls --output .cache/families-<n> --modes datatype-declarations,datatypes,statistics,statistics-iter,synthesis,synthesis-copy --lifetime round --operations 100 --warmup 40 --repetitions 1` | Complete graph cleanup against C; [extended family commands and synthesis-growth finding](../architecture/family-controls.md) |
| `pixi run --locked binding-benchmark --output .cache/overhead-<n>` | Cached-only C/raw/public timing baseline, compiled-loop inventory (GNU `nm`), separate call traces and limited allocation diagnostics; [protocol and findings](../architecture/binding-overhead.md) |
| `pixi run --locked python scripts/benchmark_statistics.py --output .cache/statistics-<n>` | Statistics snapshot timings for every filter combination, with optional paired comparison against a saved baseline; [protocol](../architecture/statistics-snapshots.md) |
| `pixi run --locked soak --output .cache/soak-<n>` | [CAS-style workloads](../architecture/soaks.md), using cached dependencies without fetching |
| `pixi run --locked batch-benchmark --output .cache/batch-<n>` | Sequential solver recycling comparisons using cached dependencies |
| `pixi run --locked soak-check` | Memory-trend, histogram, partial-checkpoint, and batch-selection analysis |
| `pixi run --locked docs-test --output .cache/docs-<n>` | Every documentation example, built from source and from the precompiled package, at O0 and O3 with `--Werror` |
| `pixi run --locked -e oracle docs-oracle-test --output .cache/docs-oracle-<n>` | Paired Python examples against the shared expected output |
| `pixi run --locked -e docs docs-check` | The documentation audit, a strict build, and the rendered links, anchors, and search index |
| `pixi run --locked package` | Precompiles `build/cvc5_mojo.mojoc` |
| `pixi run --locked python -m bindgen.package_native --release third_party/cvc5 --prefix build/native-package-check` | Stages native libraries and license notices in a fresh prefix; [packaging](../architecture/packaging.md) explains the inventory and remaining conda checks |

For a plugin-only change, use
`pixi run --locked cvc5-tests --test test_solver.test_plugin_unsat --test test_solver.test_plugin_listen`,
`pixi run --locked contracts --only plugins --output build/plugin-contracts`,
and `pixi run --locked docs-test --only plugins --output build/plugin-docs`.
The output directory for documentation tests must be fresh.

For oracle callbacks and null-object compatibility, use
`pixi run --locked contracts --only oracles,null_printing,plugins --optimization 0,3 --output build/api-compat-contracts`
and `pixi run --locked docs-test --only oracles --output build/oracle-docs`.
The result, synthesis-result, proof, and sort upstream tests can be selected
individually with repeated `--test` arguments. A targeted `--update-calls`
preserves earlier observations except native functions that have no public
call site left in the generated bindings.

CI runs `generate` and requires that it leaves no diff. It then runs
all the `test` gates, the complete-graph controls, `docs-test`, and
`package`. The overhead fixtures also run a short semantic check without
a timing threshold. String, integer-boundary, collection-input/return, formatting, ownership, return-conversion, compound, sequence, and runtime fixtures also run at O0.
After `cvc5-tests`, it also requires `tests/cvc5/calls.json` to be
unchanged.
The documentation workflow runs `docs-check`. The `Linux ARM64` workflow
builds the conda recipe and runs its tests on an ARM runner, with the
channel's `rattler-build`: from the checkout on each push, and from the
recipe's release tag when started manually with `source: tag`.

## Rules

1. **Never edit generated files.** Change the generator and run
   `pixi run --locked generate`.
2. **Never type a fact about cvc5 by hand** when it can be extracted. Add the
   extraction to `bindgen/` and put the fact in the snapshot.
3. **Exceptions go in `bindgen/overrides.toml`.** Give an entry a `note` when
   its reason is not obvious.
4. **The cvc5 version lives in `cvc5-version.toml`.** Only
   `pixi run --locked bump` changes it. The bump also moves the PyPI pin of
   the `oracle` environment and the conda recipe.
5. **Document in the same change.** Design decisions go on this site, not in
   notes elsewhere. See [maintaining the docs](documentation.md).

## Working with Mojo 1.1 FFI

The generated code and its tests verify these patterns. You can find working
code in `src/cvc5_mojo/`, which `bindgen/gen_raw.py` and
`bindgen/gen_api.py` generate, in `src/cvc5_mojo/_c/ffi.mojo`, and in
`tests/smoke/`.

- **Loading.** `OwnedDLHandle(path)` loads a library.
  `lib.get_function[R](name)` returns a callable whose **argument types are
  inferred at each call site**. `R` defaults to `NoneType`. The lookup can
  raise.
- **Dynamic function loading.** `get_function` takes the native result
  type, not a complete function signature. To resolve a function
  once, keep the `_DLCallable[R, origin_of(lib)]` that `get_function`
  returns, which is a private type. Rebind it to `MutUntrackedOrigin` with
  `rebind`, store it next to its `OwnedDLHandle`, and call it only from a
  method with typed parameters.
- **Callbacks.** Declare the function with `abi("C")` and its stored pointer
  type with `thin abi("C")`. Ordinary `def(...) -> T` denotes a callable
  trait and cannot be stored as a concrete field. Never unwind a Mojo error
  across C. The plugin bridge catches errors and retains both the callback
  table and its state until native deletion; see the
  [callback implementation](../architecture/layers.md#callbacks).
- **`bool` arguments.** Mojo passes a `Bool` to C as an LLVM `i1` without
  zero extension, as `mojo build --emit llvm` shows. Pass a C `bool` as a
  `UInt8` that is 0 or 1, and read a `bool` result as a `UInt8`.
- **Pointers.** Opaque handles are `Pointer[NoneType, MutUntrackedOrigin]`,
  and C strings are `Pointer[Int8, MutUntrackedOrigin]`.
    - `UnsafePointer` is deprecated.
    - `MutExternalOrigin`, `ImmutExternalOrigin`, and `ImmutUntrackedOrigin`
      do not exist.
- **Indexing.** `p[i]` is deprecated. Use `p[unsafe_offset=i]`.
- **Strings in.** Build a nul-terminated `List[Int8]` with `c_bytes`, and
  pass its `.unsafe_ptr()`. This helper raises on embedded NUL. SMT string
  values use the manual escaped-string path to preserve NUL as data.
  There is no `String.unsafe_cstr_ptr`.
- **Strings out.** `to_string` copies into unsigned bytes and validates
  UTF-8 with `String(from_utf8=...)`; it raises on invalid UTF-8. The
  zero-terminated UTF-32 getter has no length, so `getStringValue` decodes
  the lossless printed term after native type validation.
- **Arrays in.** Pass `List[T].unsafe_ptr()`, with the length as a `UInt`.
  The pointer is a `Pointer[T, origin_of(list)]`, so a parameter declared
  `Pointer[T, _]` keeps the list alive until the call returns. A pointer cast
  to `MutUntrackedOrigin`, such as a string stored in an array of strings,
  does not keep its buffer alive. Keep that buffer alive yourself, for
  example with `_ = buffer^` after the call.
- **Out-parameters.** Pass `Pointer(to=x)` for a `Pointer[mut=True, T, _]`
  parameter. A read-only pointer does not compile there.
- **Arrays of arrays in.** C takes the inner lengths and an array of
  pointers to the inner arrays. Build every inner `List` first, then take
  their pointers. Keep the inner lists alive until the call returns.
- **Iterators.** `for x in v` calls `v.__iter__()`, which may raise. It then
  calls `__next__(mut self) raises StopIteration -> Self.Element` on the
  result. A generic struct that holds a `List[T]` needs
  `T: Copyable & Deinitable`.
- **Structs by pointer.** Pass `Pointer(to=s)`, where `s` is a Mojo struct
  with the C struct's size and alignment. An `Array[UInt64, n]` field gives
  alignment 8. Read a field with
  `Pointer(to=storage).unsafe_bitcast[T]()[unsafe_offset=offset // size_of[T]()]`.
  `comptime assert size_of[Self]() == n` checks the size where the struct is
  built.
- **Arrays out.** A returned array is valid only until the next call, so copy
  it into a `List` at once. Its handles are references, received by their
  ownership mode. Never `cvc5_*_copy` an `own` element. See
  [runtime](../architecture/runtime.md#arrays-and-leaks).
- **Global state.** Mojo rejects a module-level `var` with "global variables
  are not supported". `std.ffi._get_global[name, init, destroy]()`, a private
  function, keeps a runtime global keyed by name:
    - `init` must not raise, and it returns an opaque pointer. Box the value
      with `OwnedPointer(value)` and pass
      `.unsafe_take_allocation().unsafe_leak()`, rebound to the opaque
      pointer type.
    - `destroy` receives that pointer back.
      `OwnedPointer[T](unsafe_from_opaque_pointer=p)` re-adopts and frees it.
    - Initialization is not serialized. Concurrent first calls may each run
      `init`. One result is kept for every caller, and the others go to
      `destroy`.
    - A lookup costs about 10 ns.
- **POSIX threads.** A `def f(arg: T) abi("C") -> U` is a C function
  pointer. `external_call["pthread_create", Int32](Pointer(to=tid), UInt(0), f, arg)`
  starts it, where `UInt(0)` stands for a null attribute pointer. A
  `pthread_barrier_t` fits in 32 bytes. `std.algorithm` has no `parallelize`
  in 1.1.
- **NULL pointers.** A `Pointer` cannot be constructed null. An empty
  `Optional[Pointer[T, ...]]` is NULL in memory, so `ffi.null[T]()` reads one
  through `unsafe_bitcast`. `tests/smoke/test_raw.mojo` checks that cvc5
  receives NULL. Compare with `==`, as `ffi.is_null` does.
- **Checking generated code.** `mojo precompile` does not instantiate every
  type. For example, a struct that refers to itself through
  `Optional[ArcPointer[...]]` precompiles, then fails with "struct has
  recursive reference to itself" when a program creates one. Prove generated
  code by running it.
- **Integer bounds.** In one context, `Int(UInt32.MAX)` evaluated wrongly: it
  rejected `1` as out of range when it was a variable. Write bounds as
  integer literals.
- **Copies.** A type with a custom copy constructor may still be
  `ImplicitlyCopyable`. Passing a value as an `Optional[T]` parameter needs an
  implicit copy.
- **Docstrings under `--Werror`.** A summary starts with a capital letter and
  ends with punctuation. `Args:` documents every parameter, in order, or is
  left out. Every section body ends with punctuation.
- **Measuring memory.** Build a program that measures its own memory with
  `mojo build`. Under `mojo run`, allocations reuse memory the JIT compiler
  freed, and growth does not show.
- **Lifecycle.** The destructor is `def __deinit__(deinit self)`, and
  `__del__` is deprecated. The copy constructor is
  `def __init__(out self, *, copy: Self)`. Neither can raise, so wrap a
  raising lookup in `try`, and `abort` in the `except`.
- **Destruction timing.** Values are destroyed right after their last use.
  A C object that depends on another must hold its own reference. See
  [runtime](../architecture/runtime.md#handle-ownership).
- **Printing.** `print(x)` and `String(x)` need `Writable`, so implement
  `def write_to(self, mut writer: Some[Writer])`. There is no
  `Representable`. `repr(x)` calls `write_repr_to`, which `Writable`
  provides and a type may override. `String`'s own `repr` differs from
  Python's: it gives `'it\'s'` for `"it's"`. `ffi.write_python_repr`
  therefore quotes as Python does.
- **Constant tables.** A `comptime` `Array` cannot be indexed at run time
  unless it is `ImplicitlyCopyable`. A `comptime` `StaticString` can, so the
  enums keep their member names in one space-separated string. Slice a
  string by bytes with `s[byte=start:end]`. `InlineArray` is called `Array`.
- **Big integer literals.** A literal that does not fit an `Int` is
  converted to one without a diagnostic. A parameter `n: Int` receives 0 for
  `2**70`, and `String(2**100)` is `"0"`. An `n: IntLiteral` overload is
  preferred for literals and keeps them exact, as `Integer(n)` does in
  apn_mojo. Generated width/index overloads call `checked_int_literal` before
  conversion. Variadic operator indices accept `Integer` so mixed dynamic
  values and large literals remain exact until range checking.
- **Small gotchas.** `fn` is reserved and cannot name a parameter. A
  docstring summary that breaks the rules above makes `mojo precompile` warn,
  so `--Werror` fails.
- **Packaging.** `mojo precompile <pkg> -o <file>.mojoc` builds a package.
  Mojo 1.1 has no `mojo package`.
- **Stack traces.** `mojo build -debug-level=line-tables` gives symbolized
  traces. See [troubleshooting](../guides/troubleshooting.md#a-crash-without-a-stack-trace).

## Documentation tooling checks

The documentation workflow also runs renderer unit tests, verifies the local
math bundle, and checks Chromium at desktop and mobile sizes. Dependencies
are pinned under `docs/qa/`; [documentation maintenance](documentation.md#browser-checks-and-math-bundle)
lists the commands and the behavior they verify.
