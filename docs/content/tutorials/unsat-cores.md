# 9. Diagnose conflicting requirements

An unsat core is a subset of asserted formulas that is already
unsatisfiable. It helps explain a contradiction in the language of the
requirements you supplied.

Prerequisite: [results and models](models.md).

## Keep requirements recognizable

This model requires an integer to be at least five and at most three.
Neither condition is impossible alone, but they cannot hold together.

<!-- example: docs/examples/unsat_core.mojo -->

Enable core production before the query and request the core only after
an `unsat` result. The program retains handles to both assertions so that
it can identify returned formulas by term equality. This is a use of term
identity, not an attempt to prove arithmetic equivalence through `==`.

The test verifies membership without depending on the order of the returned
formulas. A UI can use the same idea to attach application descriptions,
such as “minimum staffing” or “available budget,” to the formulas it asserts.

## A core is an explanation, not an automatic repair

Do not assume a returned core is the smallest possible core or the only
one. Even a subset-minimal core, from which no member can be removed, need
not have minimum cardinality among all cores. Those are different goals.

The core in this example needs both formulas: removing either makes the
remaining requirement satisfiable. That conclusion follows directly from
the example's mathematics; it is not a general guarantee about every core
the API returns.

Deleting one member of one core does not guarantee that a large problem
becomes satisfiable. Another independent conflict may remain. Recheck the
whole model after a proposed repair. Choosing which requirement to relax
is an application decision, such as preferring an optional feature over a
mandatory safety condition.

## Assertion granularity matters

If you assert every requirement as a separate formula, the core can refer
to those individual requirements. If you put the whole model into one
large conjunction and assert it once, the explanation may identify only
that conjunction. Keep the boundaries useful to the people diagnosing the
problem.

## Exercise: conflicting intervals

Replace the upper bound with `x <= 5`. What must change in the program?

**Worked answer.** The result becomes `sat`, with the unique value five.
The code must stop requesting an unsat core. Enable model production if
you want to display the witness instead.

Next: [enumerating solutions](enumeration.md).
