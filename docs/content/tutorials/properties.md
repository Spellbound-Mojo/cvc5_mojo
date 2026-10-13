# 7. Check a property through counterexamples

To establish that a property holds under some assumptions, ask whether the
assumptions and the property's negation can hold together. An `unsat`
answer proves that no counterexample exists within the modeled domain.

Prerequisite: [results and models](models.md). This example also uses
assertion scopes, explained fully in [incremental solving](incremental.md).

## Negate the conclusion

For real `x`, consider “if `x > 0`, then `x*x > 0`.” The counterexample
conditions are `x > 0` and `x*x <= 0`. Notice that negating a strict
inequality makes it non-strict. Looking only for `x*x < 0` would miss a
possible zero-valued counterexample.

<!-- example: docs/examples/properties.mojo -->

The first query is unsatisfiable. The second changes the assumption to
`x >= 0`, which admits the counterexample `x = 0`. The program reads that
value only after checking the satisfiable status.

## Check the assumptions too

An implication holds vacuously when its assumptions cannot be satisfied.
For example, from `x > 1` and `x < 0`, any conclusion follows because there
is no permitted `x`. When assumptions come from a larger model, check their
satisfiability separately if you need to know the property is useful for
some real input.

The solver proves what you encoded. A missing precondition, an unintended
integer sort, or an overly restrictive interval can change the claim. A
counterexample is especially useful here: translate it back into the
application's vocabulary and verify it independently.

## Equality of expressions

To check an identity between arithmetic terms, assert their disequality
together with the intended domain conditions. This asks for an input where
the expressions differ. It avoids confusing Mojo term equality with a
mathematical equivalence test.

This technique extends to transcendental bounds, but termination is no
longer something to expect from every formulation. See
[exponential properties](transcendentals/exponential-logarithms.md) for
examples and [inconclusive results](transcendentals/results.md) for handling
the limits honestly.

## Exercise: a precondition for reciprocal reasoning

What assumption is needed before interpreting `x*(1/x) = 1` as the usual
real-number identity?

**Worked answer.** Require `x != 0`. The ordinary reciprocal is undefined
at zero, so excluding zero is part of the mathematical specification.
Do not use a solver's treatment of out-of-domain operations to silently
choose the application's behavior there.

Next: [incremental solving](incremental.md).
