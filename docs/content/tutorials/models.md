# 6. Results and models

A satisfiability result answers whether all current assertions can hold.
A model supplies one satisfying assignment when the answer is `sat`.
Read those as two steps: establish the status, then request values that
make sense for that status.

Prerequisite: [real arithmetic](reals.md).

## Keep three outcomes

| Status | What you may conclude | Typical next action |
|---|---|---|
| `sat` | At least one satisfying assignment exists | Inspect model values |
| `unsat` | No satisfying assignment exists | Review requirements or conclude a counterexample is impossible |
| `unknown` | Neither conclusion was established | Report the limitation or retry with a justified change |

Do not write an application that treats every non-`sat` result as `unsat`.
An exhausted resource budget and a mathematical contradiction require
different responses. The [resource-limits example](transcendentals/results.md)
executes the inconclusive branch deliberately.

## Request a value at the right time

The [ticket program](integers.md) demonstrates the complete sequence:
enable model production, assert requirements, call `checkSat`, verify
`isSat`, then call `getValue`. The
[combined model and core example](../examples/index.md#models-and-unsat-cores)
shows how the sequence interacts with assertion scopes.

`getValue` returns a `Term`. The examples print it through `Writable` and
compare its text where the mathematical value is uniquely determined.
That is enough for these demonstrations; it is not a general numeric
conversion interface. In particular, exact rational or symbolic results
need not print as decimal numbers.

Read the values needed for a witness before changing the assertions or
popping its scope. They describe the model of that query. They must not
be presented as the answer to a later, different query.

## One model is not all models

The constraints `0 < x < 2` have exactly one integer solution, namely one.
The weaker constraint `x > 0` has infinitely many. A model for the weaker
problem may still choose one; that does not establish an upper bound.

To test uniqueness, keep the original assertions and exclude the returned
assignment. A second `sat` result supplies a different witness. `unsat`
establishes uniqueness for the symbols you excluded. `unknown` leaves the
question open. [Enumeration](enumeration.md) builds this into a loop.

When many models are valid, tests should check the requirements instead of
expecting one arbitrary assignment. The [scheduling example](scheduling.md)
queries each requirement in the returned model and verifies it is true.

## Exercise: values of expressions

In the ticket problem, what should a model return for the total-price
expression, and why?

**Worked answer.** It must return 47 because that equality is asserted.
Reading the price expression checks the consequence directly; querying
only the ticket symbols is not the only useful way to inspect a model.

Next: [checking properties](properties.md).
