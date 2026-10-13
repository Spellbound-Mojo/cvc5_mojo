# Runtime

This page describes what the Mojo package does at run time, and why. The
summary for users is [ownership and errors](../start/ownership.md).

## Loading the library

The [raw layer](layers.md#raw-layer) is the generated, internal binding of
cvc5's C API. Its `CApi` loads `libcvc5` and `libcvc5parser` with
`OwnedDLHandle`, using `.so` on Linux and `.dylib` on macOS. It then resolves every bound C function from the library that
exports it. To find the main library, `library_path` in
`src/cvc5_mojo/_c/ffi.mojo` looks in these places, in order:

1. `$CVC5_MOJO_LIBRARY`, the path of the main solver library. The other libraries are
   taken from the same directory.
2. `$CONDA_PREFIX/lib/cvc5_mojo/lib/`, the installed package.
3. `third_party/cvc5/lib/`, the development checkout.

The process loads one `CApi`, on first use, and the generated function
`c_api()` returns it. A failure to load is kept and raised again on every
use. `CVC5_MOJO_LIBRARY` must therefore be set before the first `TermManager`
is created. The `CApi` is unloaded when the process exits.

The parser library must be beside the selected main library; discovery does
not combine libraries from different directories. An explicit path must
include a directory. Initialization creates a temporary term manager and
solver, calls the version getter, and deletes both. A version other than the
snapshot's pin raises an error naming the expected and actual versions and
the library path. Constructor and destructor names are extracted from the
snapshot. This checks the reported version and required symbols; it does not
certify the ABI of arbitrary custom builds that report the same version.

## Handle ownership

A wrapper is a Mojo object of a handle class, such as `Term` or `Result`.
Every wrapper owns exactly one cvc5 reference:

- copying calls `cvc5_*_copy`;
- destroying calls `cvc5_*_release`;
- moving is free.

How the *first* reference is acquired depends on which C structure exported
the handle. `bindgen.c_impl.handles()` reads this from cvc5's
`cvc5_c_structs.cpp` and `cvc5_parser.cpp`, for every release. The result is
each handle type's ownership mode, `own` or `anchor`, in the last column:

| Exported by | Handle types | The returned reference | Receive |
|---|---|---|---|
| term manager (`Cvc5TermManager::export_*`) | Sort, Term, Op, Datatype, DatatypeConstructor, DatatypeSelector, DatatypeDecl, DatatypeConstructorDecl, Stat, and Statistics | belongs to the caller, and the object keeps the term manager alive | `own`: wrap it |
| input parser (`Cvc5InputParser::export_cmd`) | Command | belongs to the caller, and the command keeps the parser alive | `own` |
| solver (`Cvc5::export_*`) | Result, SynthResult, Proof, and Grammar | initially registered with the solver; final release deregisters it | `anchor`: adopt the reference and retain the solver |

The extracted table for the pinned release:

<!-- coverage: handles -->

### Why the solver stays alive

Mojo destroys a value right after its last use. In
`print(solver.checkSat())`, the solver's last use is `checkSat`, so the
solver wrapper can disappear before the result is printed. The returned
handle therefore retains the solver's state. The native reference is released
before that state can be destroyed. A copied handle takes a native reference
and shares the same state anchor; proof children inherit it too.

Earlier bindings copied every solver export. Dropping a Mojo result then left
the original reference registered with the live solver, so discarded results
accumulated until solver destruction. Adopting the initial reference lets its
final release deregister it immediately. The extractor requires the pinned
source's allocation, reference-count initialization, deregistration, and
deletion protocol; a structural change stops generation for review.

A result outlives its original solver wrapper, as in the C++ API.
`docs/examples/lifetimes.mojo` and `tests/smoke/test_lifetimes.mojo` guard
this behavior.

The [matched C/raw/public controls](binding-controls.md) verify live-owner
result, proof, and grammar reference balance against the same native build.
Unformatted ownership fixtures stayed stable. Grammar formatting grows in
direct C too, and Mojo's two-pass `String(value)` conversion doubles its
native formatting calls. The one-pass Writer diagnostic removes that
amplification but does not resolve native growth.

The [ownership audit](ownership-audit.md) additionally exercises borrowed
owner chains, copies and moves through containers, and cleanup after errors.
Its trace gate balances owner deletion and query-result references after
each completed test section; this is separate from native heap accounting.

### Arrays and leaks

A handle inside a returned array is received exactly like a single returned
handle. The array is temporary storage, valid until the next call. Each
element, however, is a reference: an `own` element is wrapped, and an `anchor`
element is wrapped with the solver's state.

For dictionaries combining exported handles with decoded strings, conversion
can fail before all references are adopted. Generated code tracks each
array's adopted prefix and releases the remaining references in `finally`;
ordinary wrapper destruction releases the prefix. The
[return-conversion regressions](return-conversion.md) exercise this with real
native exports and injected decoding failures, checking references by address.

Taking one reference too many is as wrong as taking one too few, only
quieter. The extra reference is never released. If it belongs to an object
that a term manager made, that object is never released either, and it keeps
its whole term manager alive. The first seed copied every element of
`getUnsatCore`, so each unsat core kept its term manager alive after the
program had dropped it.

`tests/smoke/test_leaks.mojo` guards this direction, which the lifetime test
cannot see. It runs the core API in a loop of term managers and solvers, and
requires the resident set to stop growing. `test_retention.mojo` separately
keeps solvers alive while discarding 200,000 query results and 30,000 proof
and grammar exports. Memory budgets detect the old retention behavior.

Synthesis has an additional upstream boundary: repeated synthesis queries
grow memory with a shared term manager in both the official Python bindings
and Mojo, including when solvers are recreated. Bounding both solver and term
manager lifetimes kept memory stable in the regression workload. A retained
result, proof, or grammar also retains its solver and its associated state;
applications must release these values to end that lifetime.

The [matched family controls](family-controls.md) reproduce fixed-input
synthesis-query growth against the same cached C library. Stored-result
copy/release and complete-graph cleanup controls stay within their budgets.
Result export/copy/release counts match C; allocation-level attribution of
the native query growth remains open.

The [production-like soaks](soaks.md) also found native growth when a live
arithmetic solver processes continually new constants. Bounded vocabularies
stayed stable, but dropping per-query values and popping assertions did not
bound this case. Recycling the solver every eight requests did, even with its
term manager retained. A subsequent [batch-size comparison](soaks.md#batch-size-screen-on-2026-10-07)
selected 512 as a measured starting interval, with sustained peak RSS below
36 MiB under a provisional 128 MiB budget. This is separate from the corrected
exported-handle retention, and differs from synthesis's need to bound
term-manager lifetimes. The interval still needs validation on actual queries
and longer service runs.

### What a wrapper holds

A wrapper holds:

- its typed handle;
- a pointer to the process's `CApi`, which outlives every wrapper;
- the pointer of its term manager, which outlives the wrapper's object,
  because objects keep their term manager alive inside cvc5.

Solver-exported handles additionally hold an optional `ArcPointer` to the
solver state; null handles have no anchor.

Like Python's wrappers, a wrapper remembers its term manager because
`Term.notTerm` and its siblings build terms with it, and the terms these
methods return must remember it too. Copying a `Term` costs one `cvc5_term_copy` and no
reference counting in Mojo.

The [pointer-owned classes](layers.md#classes) work differently. Copies of a
`TermManager`, `Solver`, `SymbolManager`, or `InputParser` share their cvc5
object through an `ArcPointer` to a state. The state holds the object's
pointer and the pointer of its term manager, and it deletes the object with
the last copy.

An object of these classes that another one returns, such as
`Solver.getTermManager()`, is borrowed. Its state does not delete it, and it
keeps the state of the object that returned it alive. Each class has its own
state type, because Mojo rejects a struct that refers to itself, even through
an `ArcPointer`. The generator therefore refuses a cycle of such relations.

## Strings and arrays

Strings and arrays returned by cvc5 are valid only until the next C API call
on that object or thread. They are therefore copied immediately into
`String`, `List`, and `Dict` values. Handles in an array are not copied this
way. Each is received by its [ownership mode](#arrays-and-leaks).

A statistic (`Cvc5Stat`) has no wrapper class, as Python has none. It is read
into a `Stat` value, and its reference is released at once.

Ordinary C string arguments reject embedded NUL before calling cvc5, because
the C API accepts no length. Returned byte strings are copied as unsigned
bytes and validated as UTF-8. A malformed diagnostic produces a fallback
message and still clears the native error state.

The shared helpers reserve outgoing byte buffers including the terminator and
construct returned strings directly from a validated byte span. This removes
temporary buffer growth for existing `String(value)` calls as well as
`toString()`; native call counts and ownership are unchanged. See
[string conversion buffers](string-buffers.md).

SMT string values need a different path. `mkString(s)` preserves Unicode,
control characters, backslashes, and embedded NUL by encoding ASCII SMT-LIB
escapes. Explicit `True` or `False` flags keep the upstream escaped-string
behavior, including its input restrictions. `getStringValue()` validates the
term with the C getter, then decodes its quoted SMT-LIB representation. The
C UTF-32 getter is zero-terminated and cannot convey embedded NUL. This
lossless fallback costs serialization and parsing; non-Unicode code points
that Mojo `String` cannot represent raise an error.

Widths and indices have literal overloads that check the exact value before
conversion to `Int`, then check the target C range. `mkInteger` reuses that
range predicate to choose the direct constructor for signed 64-bit literals,
preserving arbitrary precision outside the range; see [integer literals](integer-literals.md).
Variadic operator indices
use exact `Integer` values. A value already narrowed by the caller to `Int`
or `List[Int]` cannot be recovered by the binding.

## Errors

After every call, the generated raw layer checks `cvc5_has_error()`. On
failure, it reads `cvc5_get_error_message()`, calls `cvc5_reset_error()`, and
raises `Error("cvc5: " + message)`. Only the three error-state functions
themselves are not checked.

Releasing, copying, comparing, and printing cannot fail on valid handles. In
Mojo, however, destructors, copy constructors, `__eq__`, and `write_to` cannot
raise. These places call the raising raw methods, and abort with cvc5's
message if one ever fails. Null formatting bypasses C: it uses the text
recorded by the pinned Python oracle, or `Class(null)` when Python itself
raises or crashes while formatting that class. A symbol missing from the library raises when the
`CApi` is created, never later.

## Threads

cvc5's error state is thread-local. Each worker should create its own term
manager and solver and keep their entire object graph on that worker.
Atomic Mojo state references do not make cvc5 objects safe to share.

All threads share the process's `CApi`. Mojo 1.1 has no global variables, so
`c_api()` keeps the `CApi` with the runtime's named globals
(`std.ffi._get_global`). These globals do not serialize initialization. When
several threads use the bindings for the first time at once, each may load a
`CApi`. One is kept for all of them, and the others are unloaded. Threads
must finish before `main` returns, because the `CApi` is unloaded at exit.

`tests/smoke/test_threads.mojo` starts 16 POSIX threads at a barrier, each
with its own term manager and solver. It checks the shared API pointer,
deliberately overlaps pending errors with clean workers, verifies unique
Unicode diagnostics and recovery, and checks results after every error.
Loading failures also run concurrently with stable cached diagnostics.
The [initialization report](runtime-validation.md) describes the matrix,
native bootstrap and DSO cleanup evidence, and its limits.

Initialization failures are cached for the process too. Correct library
selection before startup; subsequent calls do not retry a failed load.
