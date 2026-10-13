# Oracle functions

An oracle gives an SMT function an implementation in Mojo. When cvc5 needs
to evaluate an application, it calls your `Oracle.evaluate` method with a
list of argument terms. Return a term of the declared result sort, created
with the solver's term manager.

This differs from a [plugin](plugin.md): an oracle computes a function
result, while a plugin supplies constraints or observes search events.
Use an oracle when an external algorithm supplies a deterministic function
that would be awkward to encode directly in SMT. A callback is not a way
to turn an approximate floating-point computation into exact real arithmetic.

## Implement and register a function

Enable `oracles` before declaring functions. Implement the `Oracle` trait,
wrap your instance in an `ArcPointer`, and pass it to
[`Solver.declareOracleFun`](solver.md#Solver.declareOracleFun).

<!-- example: docs/examples/oracles.mojo -->

The callback computes `3 + 1`, so the assertion that its result equals `5`
is unsatisfiable. The domain list fixes argument order and sorts; the
separate result sort fixes the return type. Multiple declarations can use
different callback instances and different sorts.

Oracle functions are an experimental cvc5 API. This method is a Mojo
extension backed by the C API; it is absent from the pinned Python base API
and does not count toward Python-method coverage.

## Keep evaluation deterministic

cvc5 caches oracle evaluations. The same arguments must always describe the
same result for the declaration's lifetime. Counters and diagnostic logging
are fine, but do not depend on an exact number or order of invocations.
Changing a callback field must not change the mathematical function during
a solve. Declare a new function when the intended function changes.

Use typed term getters, perform the computation, and construct the result
through your stored `TermManager`. Returning an argument directly is also
supported. The bridge rejects null results, results from another term
manager, and results whose sort differs from the declaration.

## Lifetimes and memory

Registration retains the callback instance until the solver and handles
that retain it are released. Solver copies and parser-derived solver values
share registrations. There is no removal API: scope the solver when a batch
of declarations is finished.

The bridge receives and releases every native argument reference. You may
copy an argument into your own state if you need it afterward. It retains
only the latest returned term per declaration, plus one internal error
sentinel; repeated evaluations do not append to a Mojo result history.
cvc5's own evaluation cache can still grow with distinct arguments.

Use an oracle function and expressions containing it only with the solver
that registered it. Keep that solver alive while using those expressions;
do not transfer them to another solver. This bridge does not implement
cross-solver oracle ownership. Each thread needs a separate object graph.

Store the original term manager in callback state. Storing the solver, its
parser, or a term-manager wrapper borrowed from that solver creates an
ownership cycle. Break such cycles explicitly before releasing the graph.

## Errors

`evaluate` may raise. The bridge records the first error and prevents it
from unwinding through C. It returns a retained sentinel of a different
sort, causing cvc5's checked oracle evaluator to unwind to the calling API
operation. Mojo then raises the original callback error. The sentinel is
never reported as a successful result or model value.

Discard the solver after a callback error. Later operations raise the stored
error, including calls through copied solvers, parsers, and `Command.invoke`.
Calling back into the registering solver or parser during evaluation is
rejected. Build terms through the original term manager instead.
