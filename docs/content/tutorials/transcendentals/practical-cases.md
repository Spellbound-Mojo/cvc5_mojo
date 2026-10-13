# 7. Root brackets, decreasing logarithms, and singularities

This chapter applies the earlier lessons to three situations where the
mathematical domain determines what a solver result means. The examples
use exact real constants and keep the assertion being checked small enough
to inspect independently.

Prerequisites: [logarithmic relations](exponential-logarithms.md),
[inverse branches](inverse-derived.md), and [rational bounds](bounds.md).

## Bracket a root on a monotonic interval

Suppose you need the principal solution of `sin(x) = 1/2`. An exact decimal
is unnecessary if the application needs only a certified interval.
Define `f(x) = sin(x) - 1/2` and choose the endpoints `1/2` and `3/5`.

```math
f\!\left(\frac12\right)<0, \qquad
f\!\left(\frac35\right)>0.
```

The program asks whether either of those strict sign conditions fails.
Its `unsat` result certifies both endpoint inequalities:

<!-- excerpt: docs/examples/root_bracket.mojo#bracket -->

Sine is continuous, so the intermediate value theorem gives a root in the
open interval `(1/2, 3/5)`. Sine is strictly increasing throughout this
interval, which lies inside `(-π/2, π/2)`, so that root is unique there.
Consequently the principal inverse sine of one half lies in the bracket.
The familiar exact value `π/6` is consistent with the result, but was not
used to construct the query.

There are two distinct parts to this reasoning: the solver certifies the
endpoint signs; continuity and strict monotonicity supply the mathematical
existence and uniqueness argument. The program does not ask the solver to
prove these general theorems or return an exact root model.

<details markdown="1"><summary>Complete root bracket program and expected output</summary>

<!-- example: docs/examples/root_bracket.mojo -->

</details>

### Refine the bracket without losing the guarantee

For an increasing continuous function with opposite strict signs at `a`
and `b`, form the exact rational midpoint `m = (a+b)/2`. Prove the sign of
`f(m)` using another counterexample query. If it is negative, replace `a`
with `m`; if positive, replace `b` with `m`. If equality is established,
you have the root. If the sign query is inconclusive, keep the old bracket.
An `unknown` result cannot justify discarding either half.

The same approach needs a different uniqueness argument outside a
monotonic interval. Opposite endpoint signs alone establish existence,
not uniqueness, and equal signs do not rule out roots in between.

## Work with a logarithm base below one

Change of base gives the following formula on its real domain:

```math
\begin{gathered}
\log_b x = \frac{\ln x}{\ln b}, \\
x>0,\quad 0<b<1,\quad \ln b<0.
\end{gathered}
```

Dividing by the negative denominator reverses an inequality. For the
concrete base one half, this yields:

```math
\begin{aligned}
\log_{1/2}x > 1
&\quad\Longleftrightarrow\quad \ln x < \ln(1/2) \\
&\quad\Longleftrightarrow\quad 0<x<\frac12.
\end{aligned}
```

The sign of the denominator is the essential step. This program encodes
`base_log = ln(1/2)` and rules out a nonnegative value:

<!-- excerpt: docs/examples/logarithm_base.mojo#sign -->

<details markdown="1"><summary>Complete decreasing-base program and expected output</summary>

<!-- example: docs/examples/logarithm_base.mojo -->

</details>

For a threshold of two, use the exact endpoint `(1/2)^2 = 1/4`, giving
`log_(1/2)(x) > 2` precisely when `0 < x < 1/4`. The inequality is strict:
`x = 1/4` makes the logarithm equal to two. Omitting positivity would
incorrectly admit zero and negative arguments.

If the base is symbolic and may lie on either side of one, split the cases
`0 < b < 1` and `b > 1`, excluding one in both. A single inequality direction
does not cover both cases. For a fixed threshold, a justified rewrite can
also avoid the product of two symbolic terms in the general logarithm
relation. The [budget comparison](results.md#compare-equivalent-encodings)
shows why that can matter computationally.

## Keep tangent away from its poles

The quotient definition of tangent has an explicit domain:

```math
\tan x = \frac{\sin x}{\cos x}, \qquad \cos x\ne0.
```

For a principal-branch application, `-π/2 < x < π/2` selects one interval
between poles. When an application also needs a numerical margin from a
pole, use justified stricter endpoints or a bound such as `cos(x) >= c`
with a fixed positive `c`. That margin is an additional requirement; it
changes the allowed inputs and should come from the application.

The example includes the nonzero-denominator condition, verifies tangent
at zero, and separately checks that the endpoint `π/2` fails the domain:

<!-- excerpt: docs/examples/tangent_domain.mojo#domain -->

<details markdown="1"><summary>Complete tangent-domain program and expected output</summary>

<!-- example: docs/examples/tangent_domain.mojo -->

</details>

Constructing a division term does not by itself add the classical domain
restriction to your problem. Preserve the restriction explicitly when
replacing a native function with a quotient. Do not interpret a value at an
excluded pole as a value of the ordinary real tangent.

Cross-multiplication also needs care. If `cos(x) > 0`, then
`sin(x)/cos(x) < t` is equivalent to `sin(x) < t*cos(x)`. If `cos(x) < 0`,
reverse the comparison. Merely knowing that the denominator is nonzero
is enough for an equality transformation, but not for choosing the direction
of an inequality.

## Exercise: diagnose two invalid rewrites

A model replaces `log_(1/2)(x) > 0` with `x > 1`, and replaces
`tan(x) < 1` with `sin(x) < cos(x)` for every angle. What is missing?

**Worked answer.** The logarithm is decreasing, so the first condition is
`0 < x < 1`. The tangent rewrite is valid where cosine is positive.
Where cosine is negative the comparison reverses, and cosine zero must be
excluded. A restriction to `(-π/2, π/2)` justifies the positive case.

Continue with the [damped oscillation application](application.md), which
combines exponential and sine bounds into a complete envelope calculation.
