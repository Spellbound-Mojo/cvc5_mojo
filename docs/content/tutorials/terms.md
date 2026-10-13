# 2. Sorts and symbolic terms

A *sort* describes a symbolic expression's domain. An integer symbol has
sort `Int`; an arithmetic comparison has sort `Bool`. A *term* is an
expression tree whose nodes include constants, symbols, and operations.

Prerequisite: [your first query](first-query.md).

## Build before solving

This program constructs `x + x = 6` and inspects it. It needs no solver:
expression construction and satisfiability checking are separate operations.

<!-- example: docs/examples/terms.mojo -->

`tm.mkInteger(6)` turns a Mojo integer into a symbolic integer constant.
`tm.mkConst(integers, "x")` creates a symbol whose value a solver may choose.
Despite the method name, that symbol is not the numeric constant six; its
interpretation remains unconstrained until you add assertions.

`getKind` identifies the expression's outer operation. The kind of
`twice_x` is addition even though an equivalent expression could have been
built as `2*x`. `getSort` reports the domain of the expression's result.
The addition has integer sort, and the equation has Boolean sort.

## Mojo evaluation and symbolic construction

Keep these operations distinct:

| Operation | Meaning |
|---|---|
| Mojo `2 + 3` | Compute a host-language integer immediately |
| `tm.mkTerm(Kind.ADD, a, b)` | Construct a symbolic sum |
| `a == b` for `Term` values | Compare the terms themselves |
| `tm.mkTerm(Kind.EQUAL, a, b)` | Construct a symbolic equality to assert or combine |

Term comparison does not ask whether two expressions have equal values
under your assertions. To ask that question, construct a formula and query
a solver. For example, `x + x` and `2*x` describe the same arithmetic value,
but a program should not use host-language term equality as a proof of an
arithmetic identity.

The same distinction applies to `and`, `or`, and `not`. Mojo's operators
combine Mojo Boolean values. Symbolic conditions use Boolean term kinds,
introduced in [Boolean constraints](booleans.md).

## Types are part of the model

The solver requires Boolean assertions. An integer expression such as
`x + x` must be compared to something before you assert it. Ill-sorted
operations are API errors, not unsatisfiable mathematical problems.
[Ownership and errors](../start/ownership.md) demonstrates catching such
an error and continuing.

## Exercise: inspect the predicate

What are the kind and sort of the equation in the example?

**Worked answer.** Its kind is `Kind.EQUAL` and its sort is Boolean. The
integer domain belongs to its operands. Testing those properties requires
only the term manager; checking whether the equation has a solution requires
a solver and an assertion.

Next: [Boolean constraints](booleans.md).
