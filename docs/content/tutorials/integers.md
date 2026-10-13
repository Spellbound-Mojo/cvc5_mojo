# 4. Integer constraints

Seven people buy tickets. An adult ticket costs 8 units and a child ticket
costs 5 units. The total is 47 units. Find the number of each kind of ticket.

Prerequisite: [Boolean constraints](booleans.md).

## Write the mathematical model

Let `adult` and `child` be integer counts. Their constraints are:

```text
adult >= 0
child >= 0
adult + child = 7
8*adult + 5*child = 47
```

Nonnegativity is part of the problem, not something inferred from a symbol's
name. Sort `Int` includes negative integers. The equations happen to have
a nonnegative solution here, but the bounds remain necessary in a model
that will be reused with different totals.

<!-- example: docs/examples/integers.mojo -->

Each assertion is one requirement. The price expression contains
multiplication, but only by fixed coefficients. It is linear arithmetic,
so the example uses `QF_LIA`.

## Verify the answer independently

Subtract five times the head-count equation from the price equation:
`3*adult = 12`. Therefore `adult = 4` and `child = 3`. Substitution gives
`4 + 3 = 7` and `8*4 + 5*3 = 47`, so the returned counts meet both totals.

This reasoning also shows that the model is unique. In general, a solver
returns one satisfying assignment; uniqueness requires a separate argument
or another query.

The input coefficients in this example are small Mojo `Int` values passed
to `mkInteger`. Do not infer from that constructor's input type that
symbolic integer arithmetic wraps like machine arithmetic. These constraints
describe mathematical integers. If the application is about fixed-width
overflow, it needs a bit-vector model and bindings that support that model.

## Exercise: an impossible total

Could the same seven tickets cost 48 units?

**Worked answer.** Subtracting the head-count equation now gives
`3*adult = 13`, which has no integer solution. Change 47 to 48 and expect
`unsat`. Remove the model reads in that variation. Over the reals the
equations would have a solution, but fractional people would not answer
the original question.

Next: [real arithmetic](reals.md).
