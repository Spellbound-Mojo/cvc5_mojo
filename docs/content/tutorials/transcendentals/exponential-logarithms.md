# 2. Exponentials and logarithms

The real exponential is positive everywhere and increases strictly with
its argument. These facts support useful checks without requiring a
numerical approximation to the exponential value.

Prerequisites: [constructing expressions](expressions.md) and
[checking properties](../properties.md).

## Prove exponential properties

The first query looks for a nonpositive exponential value. The second looks
for a positive input whose exponential is at most one. Both are
counterexample queries, and both are unsatisfiable.

<!-- example: docs/examples/exponentials.mojo -->

The independent queries use independent solvers and share terms through
one term manager. The first `unsat` establishes `exp(x) > 0` for every real
`x`. The second establishes `x > 0 ⇒ exp(x) > 1`.

These are exact real inequalities. Their proof does not depend on testing
a selection of positive inputs or on deciding whether a computed float is
close enough to one. cvc5 documents corresponding positivity and sign
reasoning in its
[transcendental proof rules](https://cvc5.github.io/docs/cvc5-1.4.1/api/c/enums/cvc5proofrule.html).

## Represent a natural logarithm

For a positive real `x`, introduce a real symbol `y` with this relation:

```math
x > 0, \qquad e^y = x \quad\Longleftrightarrow\quad y = \ln x.
```

Mathematically, the unique such `y` is `ln(x)`. Exponential positivity and
strict monotonicity give the domain and uniqueness. When `x` is symbolic,
keep the positivity condition explicit so the application's domain is
visible, even though the exponential equality already implies it.

This is a relational encoding. It adds a symbol and a constraint; it does
not add a new `log` method to the package or evaluate a Mojo logarithm.
If the logarithm appears in a larger expression, use `y` in that expression
and retain the defining relation.

The key step is to assert the defining relation and then a violation of the
interval. The query asks for a counterexample to the bound:

<!-- excerpt: docs/examples/logarithms.mojo#relation -->

<details markdown="1"><summary>Complete logarithm program and expected output</summary>

<!-- example: docs/examples/logarithms.mojo -->

</details>

The first query encodes `y = ln(2)` and asks whether `y <= 0` or `y >= 1`.
Its `unsat` result establishes the strict enclosure `0 < ln(2) < 1`.
The argument two is already positive. The second query uses a fresh solver
to show a case with an exact model value: `ln(1) = 0`.

The first query does not print `ln(2)`. Proving an enclosure and producing
an exact model representation are distinct tasks. Asking only
`exp(y) = 2` can be harder for a solver than refuting the out-of-bounds
counterexample. Always handle `unknown` in both formulations.

## Choose a simpler equivalent threshold

Suppose a requirement is `ln(x) < a`, where `a` is real. With `x > 0`, it
is equivalent to `x < exp(a)`. If `a` is fixed, this formulation can avoid
introducing an extra logarithm symbol. Likewise,
`ln(x) <= ln(z)` is equivalent to `x <= z` when both arguments are positive.

The domain conditions make those transformations valid. Dropping them
would admit inputs for which the original real logarithm was undefined.
Use equivalences you can justify; algebraic-looking rewrites involving
real powers or inverse trigonometric functions often need further
conditions.

## Other logarithm bases

For `log_b(x)`, require `x > 0`, `b > 0`, and `b != 1`. One encoding is:

```text
exp(base_log) = b
exp(result * base_log) = x
```

Then `result = log_b(x)`. For base ten, `b` is an exact real ten. For a
symbolic base, keep its domain conditions in the model. The product of
two symbolic terms introduces additional nonlinearity.

For `b > 1`, the logarithm is increasing. For `0 < b < 1`, it is decreasing,
so inequality directions reverse when transforming logarithmic thresholds.
Base one is excluded because its exponential powers cannot distinguish
the desired logarithm value.

## Exercise: a logarithmic threshold

Rewrite `ln(x) >= 0` without a logarithm symbol and explain its domain.

**Worked answer.** On `x > 0`, monotonicity and `exp(0) = 1` make it
equivalent to `x >= 1`. In this particular result the new inequality
already implies positivity. For `ln(x) < 0`, the correct equivalent
condition is `0 < x < 1`; keeping only `x < 1` would admit invalid inputs.

Next: [trigonometric constraints](trigonometry.md).
