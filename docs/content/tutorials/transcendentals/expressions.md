# 1. Construct transcendental expressions

Construct a transcendental application with `mkTerm`, just as you would
construct addition or a comparison. Its argument is a symbolic real term;
building the expression does not evaluate a machine floating-point function.

Prerequisite: [sorts and symbolic terms](../terms.md).

## Use the existing term interface

<!-- example: docs/examples/transcendental_terms.mojo -->

The program demonstrates exponential, sine, cosine, tangent, and inverse
sine expressions. It constructs symbolic π with `mkTerm(Kind.PI)`;
the generated API also provides the `mkPi()` convenience method.
The pinned upstream test exercises this zero-argument `mkTerm` construction
too. [Upstream term-construction tests](https://github.com/cvc5/cvc5/blob/cvc5-1.4.1/test/unit/api/python/test_term_manager.py)

The sort assertions verify construction. They do not claim that every
equation containing these operators will be decided. In particular, making
an inverse-trigonometric term is different from obtaining a convenient
numeric value for it.

## Operator names

This table is generated from the pinned headers. It lists expression
constructors, not a promise that arbitrary formulas using them are easy
to solve.

<!-- kinds: EXPONENTIAL SINE COSINE TANGENT COSECANT SECANT COTANGENT ARCSINE ARCCOSINE ARCTANGENT ARCCOSECANT ARCSECANT ARCCOTANGENT PI -->

Use the [enum reference](../../reference/enums.md) for the complete inventory.
There is no logarithm kind in this pinned inventory. The next chapter
introduces a logarithm using an exponential relation instead.

## Construct exact constants

The example converts integer terms to real terms and divides them to
represent one half exactly. The printed expression retains those
conversions; construction does not necessarily simplify the expression to
its shortest form.

The helper in [the bounds example](bounds.md) packages this same construction
for several rational constants. All its denominators are nonzero. If a
denominator is symbolic, exclude zero when the intended specification is
ordinary real division.

Symbolic π is also different from a decimal approximation. Replacing it
with `314159/100000` changes the formula. That difference matters at a zero
of sine, at the boundary of a phase interval, or near a tangent pole.
Use a rational approximation only when the approximation and its error are
explicitly part of the model.

## Select the arithmetic extension

The solving examples set the logic to `QF_NRAT` before asserting formulas.
This follows cvc5's
[pinned transcendental example](https://github.com/cvc5/cvc5/blob/cvc5-1.4.1/examples/api/python/transcendentals.py).
Keep real variables for the arguments. Constructing a real term does not
turn a real problem into floating-point arithmetic.

For equalities, ensure both sides have the same sort. A direct equality
between a real expression and an integer term can raise a sort error; use
`Kind.TO_REAL` for the integer numeral, as the executable examples do.

## Exercise: express Euler's number

How would you represent the mathematical constant `e` without using a
rounded decimal?

**Worked answer.** Construct a real one and apply `Kind.EXPONENTIAL` to it.
The term denotes `exp(1)`. Its existence as a symbolic expression does not
imply that a model query will print an exact finite decimal; no such
decimal exists.

Next: [exponentials and logarithms](exponential-logarithms.md).
