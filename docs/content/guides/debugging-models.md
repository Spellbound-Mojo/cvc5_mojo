# Debugging a solver model

A solver answers the formula you submitted. If that formula omits a domain,
uses the wrong units, or rules out every input, a correct solver result can
still answer the wrong application question. This workshop diagnoses four
such mistakes with small, executable examples.

Read [checking properties](../tutorials/properties.md) and
[enumerating solutions](../tutorials/enumeration.md) first. Each case below
compares an incorrect encoding with a corrected one; the complete program
asserts every expected result.

## Recover the domain after rewriting a logarithm

Suppose your application accepts real inputs satisfying `ln(x) < 0`.
Monotonicity gives an algebraic condition that avoids constructing a
logarithm, but positivity is part of that condition:

```math
\ln x<0 \quad\Longleftrightarrow\quad 0<x<1.
```

Replacing the original requirement with only `x < 1` admits `x = -1`,
where the ordinary real logarithm is undefined. The first query fixes the
input to that negative value and demonstrates the mistake. The second adds
the missing lower bound:

<!-- excerpt: docs/examples/debugging.mojo#domain -->

The outputs are `sat` and `unsat`, respectively. Neither query evaluates
the logarithm at a negative input: they test whether the proposed rewrite
admits an invalid input. This distinction helps isolate a modeling error
from the cost of a transcendental query.

When removing a function from an encoding, carry its domain into the new
formula. The same check applies to a denominator that must be nonzero and
to the branch interval of an inverse trigonometric function. See
[logarithmic relations](../tutorials/transcendentals/exponential-logarithms.md)
and [inverse branches](../tutorials/transcendentals/inverse-derived.md).

## Check whether a successful proof is vacuous

To prove a property `P` under assumptions `A`, you ask whether `A AND NOT P`
is satisfiable. If `A` is contradictory, that query is unsatisfiable for
every property, including properties that fail on all intended inputs.

The workshop accidentally assumes both `x > 0` and `x < 0`. It then tries
to prove `x > 10` by searching for `x <= 10`:

<!-- excerpt: docs/examples/debugging.mojo#vacuity -->

The property query returns `unsat`, and so does the separate check of the
assumptions. The latter result exposes the empty domain. With the intended
assumption `x >= 0`, the domain is satisfiable and a counterexample to
`x > 10` exists; zero is one mathematical witness.

Use two checks when establishing a property over a domain that should be
nonempty:

| Check | Useful outcome | What it establishes |
|---|---|---|
| `A` | `sat` | At least one allowed input exists |
| `A AND NOT P` | `unsat` | No allowed input violates the property |

An `unknown` result in either check leaves that part of the argument open.
For larger contradictory assumption sets, attach application labels and
inspect an [unsat core](../tutorials/unsat-cores.md). A small core identifies
a conflict; it does not decide which requirement the application should
change.

## Convert degrees at the input boundary

An application permits angles in the closed first quadrant and receives
the number `90` from a user interface measured in degrees. Comparing that
number directly with `π/2` treats it as ninety radians and rejects it.
Convert the input before using it in trigonometric expressions:

```math
\theta_{\mathrm{rad}}=\theta_{\mathrm{deg}}\,\frac{\pi}{180}.
```

<!-- excerpt: docs/examples/debugging.mojo#angles -->

The test uses a fixed nonnegative input, so only the upper quadrant bound
is needed to distinguish the two encodings. For a symbolic input, include
both bounds. The corrected ninety-degree input lands exactly on the
allowed endpoint; there is no decimal approximation to π.

Name quantities by their units when constructing a larger model. A
dimensionless real sort cannot tell degrees from radians, seconds from
milliseconds, or ordinary frequency from angular frequency. For example,
converting cycles per second into a sine argument introduces a factor
of `2π`; [the damped signal application](../tutorials/transcendentals/application.md)
instead takes angular frequency directly in radians per second.

## Exclude one tuple without excluding its neighbors

After finding `(x,y) = (0,0)`, you want another pair. Requiring both
`x != 0` and `y != 0` throws away pairs such as `(0,1)`, even though they
are different solutions. Negating equality of the whole tuple gives:

```math
\neg(x=0\land y=0) \quad\Longleftrightarrow\quad x\ne0\lor y\ne0.
```

<!-- excerpt: docs/examples/debugging.mojo#blocking -->

The example fixes the candidate to `(0,1)`. The incorrect conjunction
rejects it; the disjunction preserves it. Select the tuple according to
what counts as a different application result. Blocking auxiliary variables
as well can enumerate multiple internal representations of the same result.

## A debugging routine you can reuse

First write down one input that should be accepted and one that should be
rejected. Fix the corresponding symbols to those values and check each
case independently. Then check the assumptions without the property or
objective, inspect the printed terms for wrong sorts and units, and add
requirements back in groups until the result changes. Use temporary scopes
when experimenting so a diagnostic constraint cannot leak into the next
query.

An inconclusive query needs a separate diagnosis: keep `unknown` distinct
from `unsat`, record the logic and resource settings, and reduce the
formula. [Solver options](solver-options.md) and
[transcendental solver limits](../tutorials/transcendentals/results.md)
explain those controls.

<details markdown="1"><summary>Complete workshop program and expected output</summary>

<!-- example: docs/examples/debugging.mojo -->

</details>

## Exercise: repair a uniqueness check

A program finds `(a,b,c) = (1,2,3)` and searches for another solution by
asserting `a != 1 AND b != 2 AND c != 3`. It gets `unsat` and announces
uniqueness. What should change?

**Worked answer.** Join the three inequalities with `OR`, preserving the
original constraints. The corrected query excludes exactly the known
tuple. `unsat` then proves uniqueness of those three selected values;
`sat` supplies another tuple, and `unknown` leaves uniqueness undecided.
