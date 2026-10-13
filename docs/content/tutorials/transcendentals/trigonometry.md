# 3. Trigonometric constraints

Trigonometric models need both a function and a meaningful angular domain.
The same sine value can occur at many angles. A range bound may settle a
question immediately, while an unrestricted equation can leave infinitely
many candidate inputs.

Prerequisite: [constructing expressions](expressions.md).

## Work in radians

Use radians in the mathematical trigonometric functions. If an input is
measured in degrees, convert the symbolic expression by multiplying it by
`π/180`. Keep π symbolic when the conversion is intended to be exact.
An application should track the input unit independently: the real sort
alone does not distinguish degrees, radians, meters, or seconds.

For example, the degree angle 180 corresponds to π radians. Substituting
180 directly into sine asks a different question.

## Prove range bounds

Sine and cosine lie in the closed interval `[-1, 1]`. The program asks for
values outside that interval, using the disjunction of two strict
violations.

<!-- example: docs/examples/trigonometry.mojo -->

Both results are `unsat`. That proves both lower and upper bounds because
either violation was allowed by the query. The endpoints belong to the
range: replacing the strict violations with non-strict comparisons would
ask a different, satisfiable question.

## Restrict a phase interval

For angles strictly between π and 2π, sine is negative. A real square is
nonnegative. Therefore no square can be strictly smaller than sine on that
interval.

<!-- example: docs/examples/sine_phase.mojo -->

This is the mathematical problem used in cvc5's
[upstream transcendental example](https://github.com/cvc5/cvc5/blob/cvc5-1.4.1/examples/api/python/transcendentals.py),
expressed through the current Mojo constructors. Its output is independently
explained by the sign of sine and the sign of a square.

The interval constraints are essential. In the first half of a period,
sine can be positive, allowing small squares below it. Names such as
`angle` or `phase` do not impose an interval on a symbol.

## Periodicity and inverse questions

The mathematical identity `sin(x + 2πk) = sin(x)` holds for integer `k`.
Similarly, cosine has period `2π`, while tangent has period `π` where it is
defined. A phase restriction can select the part of the application you
care about, but it may still leave multiple roots.

For instance, on `[0, π]`, the equation `sin(x) = 1/2` has two solutions.
A smaller monotonic interval is needed if the task demands a unique inverse.
Adding that restriction is a modeling decision: it changes an unrestricted
search into a search within that branch.

Do not assert a bound solely because it makes a difficult problem faster.
Either the bound follows from the application's specification, or you must
report that you have answered a restricted question. A systematic search
over several intervals must cover the full intended domain before it can
support a global conclusion.

## Tangent and reciprocal functions

For ordinary real tangent, exclude angles where cosine is zero. Within
that domain, `tan(x) = sin(x)/cos(x)`. Secant has the same denominator;
cosecant and cotangent require nonzero sine. The reciprocal forms do not
remove the need for these restrictions.

SMT terms must have interpretations even at inputs where the familiar
mathematical function is partial. Do not interpret such cases as a
numerical library's exception, infinity, or NaN. Express the valid domain
explicitly when those ordinary real-function meanings are intended.

## Exercise: include the phase endpoints

If the phase interval becomes `[π, 2π]`, can a square be strictly below
sine there?

**Worked answer.** Still no. Sine is zero at the endpoints and negative
inside, while the square is always nonnegative. But changing the square
comparison to `y*y <= sin(angle)` admits the endpoints with `y = 0`.
Strictness in the comparison and in the interval controls different parts
of the problem.

Next: [inverse and derived functions](inverse-derived.md).
