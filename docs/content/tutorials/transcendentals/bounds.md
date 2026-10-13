# 5. Prove bounds and use approximations soundly

Often an application needs to establish that a value lies within an
interval, rather than obtain its decimal expansion. Exact rational bounds
make that goal explicit and avoid treating a rounded value as a proof.

Prerequisites: [checking properties](../properties.md) and
[trigonometric constraints](trigonometry.md).

## Turn an enclosure into a counterexample query

To establish `L <= f(x) <= U` under domain constraints `D`, ask whether
the following is satisfiable:

```text
D AND (f(x) < L OR f(x) > U)
```

If it is `unsat`, no permitted input violates the enclosure. If it is
`sat`, the returned model describes a counterexample. If it is `unknown`,
the enclosure remains unestablished by that run. A strict target interval
requires non-strict violations instead.

For a constant argument there are no free input choices, but the same
counterexample construction applies. That is how the following example
checks an interval for `sin(1/2)`.

## Derive rational bounds independently

For `0 <= x <= 1`, the terms of the sine power series decrease in magnitude
and alternate in sign:

```math
\sin x = x - \frac{x^3}{3!} + \frac{x^5}{5!} - \frac{x^7}{7!} + \cdots.
```

The alternating-series remainder lies between zero and the next omitted
term with its sign. Thus two successive truncations enclose the value:

```math
\begin{gathered}
x - \frac{x^3}{6} \;\le\; \sin x \;\le\;
x - \frac{x^3}{6} + \frac{x^5}{120}, \\
0 \le x \le 1.
\end{gathered}
```

At `x = 1/2`, the lower expression is `1/2 - 1/48 = 23/48`.
The next term is `1/3840`, making the upper expression `1841/3840`.
This is a mathematical derivation with explicit domain assumptions, not a
comparison of rounded outputs from two numerical libraries.

The program constructs both endpoints as exact rational terms, then asks
whether sine falls below the lower endpoint or above the upper one:

<!-- excerpt: docs/examples/sine_bounds.mojo#enclosure -->

<details markdown="1"><summary>Complete bounds program and expected output</summary>

<!-- example: docs/examples/sine_bounds.mojo -->

</details>

The program keeps every constant rational. It asserts a violation of the
derived bounds against the native sine term and receives `unsat`. The
exact width of the enclosure is `1/3840`. Every point of the interval is
not a possible value of `sin(1/2)`; the interval is an enclosure of one
fixed value.

## A polynomial approximation needs its remainder

Replacing `sin(x)` with `x - x^3/6` as an equality changes the problem.
That polynomial is not sine, even on a small interval. To use it as an
approximation, specify both an applicable domain and a valid error bound
or separate lower and upper bounds.

The inequalities above hold on `[0, 1]` by the alternating-series argument.
They should not be carried to an arbitrary interval without checking the
remainder argument there. A Taylor expansion about another center likewise
needs bounds on the derivatives over its intended interval.

If polynomial coefficients or interval endpoints are computed numerically,
rounding must preserve the enclosure: round a lower bound outward downward
and an upper bound outward upward, or use exact rational arithmetic.
Rounding both to the nearest displayed decimal can destroy the guarantee.

## Understand the direction of an abstraction

Suppose you replace an exact function relation with a fresh variable `v`
and sound bounds `L(x) <= v <= U(x)` over the domain. Every exact solution
is then also a solution of the relaxed problem, but the relaxed problem
may admit additional values of `v`.

| Result on the relaxed problem | Conclusion about the exact problem |
|---|---|
| `unsat` | The exact problem is also unsatisfiable, if the enclosure is valid throughout the domain |
| `sat` | The candidate may be spurious; validate it against the exact relation |
| `unknown` | No satisfiability conclusion follows |

For example, `sin(1/2) > 1/2` is impossible even under the looser interval
above, whose upper endpoint is below one half. An arbitrary rational point
inside that interval, however, is not automatically an exact witness for
an equality to `sin(1/2)`.

## How this relates to cvc5

cvc5's documented transcendental reasoning uses incremental refinement,
including rational bounds for π and bounds derived from Taylor
approximations, tangents, and secants. Those internal approximations support
reasoning about the original real functions; they do not ask the user to
replace the original function by an unchecked polynomial.
[Theory reference](https://cvc5.github.io/docs-ci/docs-main/theories/transcendentals.html),
[pinned proof-rule reference](https://cvc5.github.io/docs/cvc5-1.4.1/api/c/enums/cvc5proofrule.html).

The hand-derived enclosure in this chapter is deliberately small enough
to inspect. It is not a reimplementation of the solver's approximation
engine. Use the native function in a query when that expresses your
specification, and treat any approximation you add yourself as a separate
mathematical obligation.

## Exercise: improve the lower bound

Which additional term gives a tighter lower bound for `sin(1/2)`?

**Worked answer.** Subtract the next term, `(1/2)^7/7! = 1/645120`, from
the current upper bound. The new lower bound is
`1841/3840 - 1/645120 = 309287/645120`. The alternating-series remainder
is now nonnegative, and the enclosure's width drops to `1/645120`.
Keep the fraction exact when modifying the example.

Next: [results and solver limits](results.md).
