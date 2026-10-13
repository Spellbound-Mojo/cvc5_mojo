# 8. Certifying a damped oscillation

Suppose a sensor signal has uncertain amplitude, damping, frequency, and
phase. You need an envelope that holds for every permitted parameter value
throughout a time window. Sampling a few trajectories cannot establish that
claim. This application builds the symbolic signal, divides the time
window, and combines checked bounds while keeping inconclusive pieces open.

Prerequisites: [exponentials](exponential-logarithms.md),
[trigonometric constraints](trigonometry.md), [proving bounds](bounds.md),
and [solver limits](results.md).

## Define the signal and its units

The signal is:

```math
s(t)=A\exp(-kt)\sin(\omega t+\phi).
```

| Quantity | Meaning | Allowed values |
|---|---|---|
| `A` | Amplitude in volts | `[0,1]` |
| `k` | Damping rate in inverse seconds | `[1,2]` |
| `ω` | Angular frequency in radians per second | `[1,2]` |
| `φ` | Phase in radians | `[-1/4,1/4]` |
| `t` | Time in seconds | `[0,2]` |

The exponent `-kt` is dimensionless, and the sine argument is in radians.
Every decimal-free endpoint becomes an exact real integer or rational term.
The initial target is `|s(t)| <= 1` volt over the whole window; a second
target tightens the bound to one half volt after one second.

## Ask the direct counterexample question

To prove the first target, assert the parameter ranges and ask whether
`s(t) < -1 OR s(t) > 1` can occur. The symbolic constants represent a
candidate violating assignment. An unsatisfiable query would rule out
every such assignment, giving the desired universal claim without an
explicit quantifier.

<!-- excerpt: docs/examples/damped_oscillation.mojo#signal -->

The program deliberately gives this query a resource budget of one unit
and checks for `unknown`. That result supplies neither a violating signal
nor a proof of the envelope. It is an example of how the application handles
an unfinished query, not a claim that the full formula is impossible to
solve with a larger budget.

## Split the time window and the proof

Use two closed intervals, `[0,1]` and `[1,2]`. Their union covers the whole
window, and checking the shared endpoint twice is harmless. Each interval
gets a decay bound, followed by an algebraic bound on the product.

The mathematical reasoning behind the decomposition is:

```math
\begin{aligned}
t\in[a,b],\ k\in[1,2],\ a\ge0 &\quad\Longrightarrow\quad kt\ge a,\\
u\ge a,\ \exp(u)\ge d>0
&\quad\Longrightarrow\quad
0<\exp(-u)=\frac{1}{\exp(u)}\le\frac1d,\\
0\le A\le1,\ |\sin\theta|\le1
&\quad\Longrightarrow\quad |s(t)|\le\frac1d.
\end{aligned}
```

Choose `(a,b,d) = (0,1,1)` for the early interval and `(1,2,2)` for the
late interval. Both exponential lower bounds can also be understood from
`exp(u) >= 1+u` for nonnegative `u`. The program checks the particular
inequalities it needs rather than encoding this general theorem.

### Establish a lower bound on the exponent magnitude

The first subquery uses polynomial real arithmetic. It asks for a permitted
`k,t` with `k*t < a`:

<!-- excerpt: docs/examples/damped_oscillation.mojo#rate -->

An `unsat` result certifies `k*t >= a` on that interval. Keeping this step
separate removes a product of two symbolic quantities from the exponential
subquery. The nonnegative lower endpoint and positive damping range are
essential to this particular lower bound.

### Bound the exponential using one symbolic argument

Introduce an independent `u >= a` and ask whether `exp(u) < d` is possible:

<!-- excerpt: docs/examples/damped_oscillation.mojo#decay -->

If this is unsatisfiable, substitute the already bounded value `u = k*t`.
The ordinary real exponential is positive and obeys
`exp(-u) = 1/exp(u)`, so its decay factor is at most `1/d`. Those identities
are the mathematical bridge between the checked subqueries. The program
does not ask cvc5 to prove the identities themselves or emit a proof object
for their composition.

### Combine independent enclosures

The program also checks the sine range `[-1,1]` for an arbitrary real angle.
That bound covers every allowed `ω*t+φ`, so the product query can replace
the transcendental factors by independent real quantities:

<!-- excerpt: docs/examples/damped_oscillation.mojo#product -->

This replacement allows more combinations than the original signal: a
particular decay value and a particular sine value need not occur at the
same time. Ruling out a violation in this larger set rules it out for the
signal too. Conversely, a satisfying assignment to the relaxed product
query would require checking against the original signal before calling
it a physical counterexample.

The result is a conservative envelope, not the exact maximum amplitude.
Using the specific phase and frequency ranges could tighten it, at the
cost of a harder query.

## Keep an inconclusive interval in the result

The first pass proves the early interval, then gives the late exponential
query the deliberately tiny budget. Its `unknown` result leaves the late
interval uncertified, so the program refuses to announce coverage of the
whole window. It retries that piece with the normal example budget and
combines the successful checks:

<!-- excerpt: docs/examples/damped_oscillation.mojo#coverage -->

Each helper returns `True` only for `unsat`; it returns `False` for
`unknown` and raises on `sat`, because these fixed example bounds are
expected to hold. A general application should retain all three statuses
with each interval. In particular, a satisfiable relaxed subquery can mean
that an enclosure is too loose, while an inconclusive one means that its
bound has not been established.

| Interval | First pass | After retry | Established envelope |
|---|---|---|---|
| `[0,1]` | Certified | Retained | `|s(t)| <= 1` |
| `[1,2]` | Inconclusive | Certified | `|s(t)| <= 1/2` |
| `[0,2]` | Incomplete | Covered by both pieces | `|s(t)| <= 1` |

Subdivision alone does not justify dropping a difficult interval. If you
refine `[a,b]` at an exact midpoint, keep both `[a,m]` and `[m,b]` in the
coverage record. If either remains open, so does the claim for their union.
Do not replace an unresolved piece with a sampled maximum.

## Run the complete application

The complete program includes the term helpers, separate solver instances,
resource settings, and assertions behind the walkthrough. Resource units
control search effort; they are not a precision setting. The documentation
runner also gives the executable a process-level timeout, so a slow solver
check cannot run indefinitely.

<details markdown="1"><summary>Complete application and expected output</summary>

<!-- example: docs/examples/damped_oscillation.mojo -->

</details>

## Adapt the bounds

For an amplitude interval `[0,M]`, the same product argument gives `M/d`.
For signed amplitudes, use an established bound on `|A|`. A different
damping range needs a new bound on `k*t`; allowing negative damping can
produce growth and invalidates the decay interpretation. A tighter phase
interval can help bound sine more sharply, provided you preserve its
dependence on time when needed.

**Exercise.** Extend the time window with `[2,3]`, keeping `k >= 1` and
`A <= 1`. What rational decay bound follows from the same argument?

**Worked answer.** Here `k*t >= 2`, and `exp(u) >= 1+u >= 3` yields
`exp(-k*t) <= 1/3`. Check those new subqueries and the product bound, then
include the third interval in the coverage record. This extension is a
mathematical exercise; it is not part of the tested program's recorded output.

For mistakes in domains, units, or coverage assumptions, continue with
the [model-debugging workshop](../../guides/debugging-models.md).
