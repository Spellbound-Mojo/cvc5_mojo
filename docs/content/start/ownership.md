# Ownership and errors

## Every value owns one cvc5 reference

cvc5 counts references to its objects. Each Mojo value of a handle class,
such as `Term`, `Sort`, or `Result`, owns exactly one of those references:

- Copying a value takes another reference (`cvc5_*_copy`).
- Destroying a value releases its reference (`cvc5_*_release`).
- Moving a value costs nothing.

You never release anything by hand. Copies are implicit, as Python shares
objects: after `var t2 = t` or `terms.append(t)`, both refer to the same term.

A copy and its later release cost about 45 ns. You can avoid them in two
ways: pass the value as an argument, which borrows it, or move it with `^`,
as in `terms.append(t^)`.

`TermManager`, `Solver`, `SymbolManager`, and `InputParser` work differently.
Their copies share one cvc5 object, which is deleted when the last copy is
destroyed. An object that another one returns, such as
`solver.getTermManager()`, keeps the object that returned it alive.

Create a parser's solver and explicit symbol manager from the same
`TermManager`. `InputParser(solver, sm)` raises a recoverable error before native
construction if their managers differ. Copied and borrowed wrappers of the same
native manager are accepted, as are omitted symbol managers and explicit `None`.
The guard prevents a native inconsistency in which parser terms are exported
through the wrong manager. See the
[mixed-manager finding](../architecture/production-validation.md#mixed-parser-term-managers-early-rejection).

## Values outlive what made them

Mojo destroys a value right after its last use, not at the end of its scope.
So a program can lose the solver or term manager that created a value while
it still uses the value. That is safe, because each handle type is received
according to the rule that cvc5 applies to it:

<!-- coverage: handles -->

- **`own`.** The returned reference already belongs to the caller. Objects
  made by the term manager keep it alive themselves, so a term stays valid
  after every `TermManager` value is gone.
- **`anchor`.** Solver results, synthesis results, proofs, and grammars adopt
  the returned reference and keep the solver alive. Their final release
  deregisters the native handle. Discarded results therefore do not accumulate
  in a live solver. Retaining one of these values also retains the solver's
  associated state until the value is released.

The rule for each type is read from cvc5's sources for every release; see
[runtime](../architecture/runtime.md#handle-ownership).

Plugin registrations also own Mojo state that native reference counts cannot
see. Solvers and parsers share that storage, and parsed commands retain their
parser's Mojo state. This keeps callbacks alive when the native solver
outlives its original wrapper. See [plugin ownership](../reference/plugin.md#ownership-and-errors).

<!-- example: docs/examples/lifetimes.mojo -->

## Errors are Mojo errors

When cvc5 rejects a call, the call raises a Mojo `Error`. Its message starts
with `cvc5: `, followed by cvc5's own message when it is valid UTF-8. The
binding clears cvc5's error state before raising. Argument validation errors
can be caught and followed by a valid call, as below. This is not a general
rollback guarantee: consult the failing operation before reusing mutated
solver or parser state. Errors detected by the binding start with
`cvc5_mojo: `.

Non-raising traits such as comparison and formatting abort on a native
error. For a single-pass owned string, use `value.toString()` on the handle
types that support native formatting. The new helpers preserve that
non-raising formatting contract; the existing `Command.toString()` remains
raising. See [formatting contracts](../architecture/single-pass-formatting.md).

<!-- example: docs/examples/errors.mojo -->

cvc5 1.4.1 records errors per thread instead of terminating the process. That
is why it is the oldest supported release; see
[the cvc5 C API](../architecture/c-api.md#errors).

## Threads

Use a separate term manager, solver, and associated values per worker. Keep
each object graph on its worker. cvc5 keeps its error state per thread, so an error
on one thread never surfaces on another. The libraries are loaded once per
process, on first use, and all threads share them. Let your threads finish
before `main` returns.
