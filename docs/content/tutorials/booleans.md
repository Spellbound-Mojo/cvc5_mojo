# 3. Boolean constraints

Suppose a configuration has two features: storage and encryption.
Encryption requires storage. A user selects encryption, and you want to
find a valid configuration.

Prerequisite: [sorts and symbolic terms](terms.md).

## Translate the requirement

Use one Boolean symbol for each feature. The dependency is the implication
`encryption ⇒ storage`. Assert encryption separately to represent the user's
choice. These two conditions force storage to be enabled.

<!-- example: docs/examples/booleans.mojo -->

The program enables model production before the query. After obtaining
`sat`, it asks for the value of `storage` in the returned model. The printed
`true` is justified by both assertions together.

An implication expresses a one-way dependency. It allows storage without
encryption. If the product requires both features to be enabled or disabled
together, use Boolean equality instead. If exactly one feature must be
enabled, use exclusive-or.

## Combine requirements

These operator descriptions come from the pinned release:

<!-- kinds: AND OR NOT IMPLIES XOR EQUAL -->

Separate calls to `assertFormula` accumulate requirements: every assertion
must hold. To allow alternatives, build a single disjunction. Asserting
`a` and then asserting `b` requires both, even if you intended “a or b.”

The example uses `QF_UF`, which accommodates these Boolean constraints.
Once you add arithmetic conditions, choose an arithmetic logic containing
the operations you use; chapter 5 gives examples.

## Do not confuse a witness with a requirement

Remove the assertion selecting encryption. The implication alone allows
several configurations. A model that happens to enable storage does not
prove that storage is required. To test necessity, assert its negation in
addition to the dependency and ask whether a solution remains. Chapter 7
develops this counterexample technique.

## Exercise: introduce a conflict

Keep encryption selected and also require storage to be disabled.

**Worked answer.** Add the symbolic negation of `storage`. The result must
be `unsat`: the dependency forces storage true while the added assertion
forces it false. Change the example's expected result and remove its model
query, because an unsatisfiable problem has no satisfying model to inspect.

Next: [integer constraints](integers.md).
