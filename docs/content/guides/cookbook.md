# Solver task cookbook

Start here when you know the question you want to ask. Each recipe links
to a complete, tested program and explains what its result establishes.
The [tutorial course](../tutorials/index.md) introduces the concepts in order;
the [glossary](glossary.md) collects the terminology.

| I want to… | Recipe |
|---|---|
| Prove that a solution is unique | [Block the selected model tuple](#prove-uniqueness) |
| Get another solution | [Exclude exactly the previous tuple](#find-another-solution) |
| Prove a property | [Search for a counterexample](#prove-a-property) |
| Check a tolerance | [Refute an out-of-range value](#check-an-absolute-tolerance) |
| Explain an impossible request | [Map a core to requirement labels](#explain-unsatisfiability) |
| Find the best deadline | [Maintain feasible and infeasible bounds](#find-a-minimum) |
| Recover from `unknown` | [Preserve the open question](#handle-an-inconclusive-query) |
| Diagnose an unexpected answer | [Debug domains, assumptions, units, and blockers](debugging-models.md) |
| Combine transcendental bounds over a time window | [Certify a damped oscillation](../tutorials/transcendentals/application.md) |
| Choose solver settings | [Configure features and resource limits](solver-options.md) |
| Translate a Python application | [Compare the paired Python and Mojo programs](python-migration.md) |
| Use the bindings from another directory | [Build a consumer project](consumer-project.md) |

## Prove uniqueness

First establish existence with `checkSat()` and read the values of the
symbols whose uniqueness matters. Then block that tuple in a temporary
scope and check again. The example solves `x+y=5` and `x-y=1`, whose
unique integer solution is `(3,2)`:

<!-- excerpt: docs/examples/uniqueness.mojo#block -->

The second query has three possible interpretations:

| Result | Conclusion |
|---|---|
| `unsat` | The previously found tuple is the only one for the selected symbols |
| `sat` | At least one different tuple exists; read it before changing the assertions |
| `unknown` | Uniqueness has not been established |

<details markdown="1"><summary>Complete uniqueness program and expected output</summary>

<!-- example: docs/examples/uniqueness.mojo -->

</details>

Uniqueness is relative to the selected symbols. Blocking just `x` establishes
whether another value of `x` is possible; unrelated or auxiliary symbols
may still vary. The initial satisfiability check matters: an inconsistent
problem has no solutions, rather than one unique solution.

Related API: [`checkSat`](../reference/solver.md#Solver.checkSat),
[`getValue`](../reference/solver.md#Solver.getValue),
[`push`](../reference/solver.md#Solver.push), and
[`pop`](../reference/solver.md#Solver.pop).

## Find another solution

For a previously returned pair `(a,b)`, assert `NOT(x=a AND y=b)`.
Equivalently, require `x != a OR y != b`. Using `AND` between the two
inequalities would wrongly exclude other pairs that share one coordinate
with the original solution.

The [enumeration example](../tutorials/enumeration.md) repeats this operation
until `unsat` establishes exhaustion of the selected tuples. It checks all
three nonnegative integer pairs summing to two, without relying on model
order. For an unbounded or real domain, enumeration need not terminate.
Plan a stopping rule appropriate to the application.

## Prove a property

Assert the domain and the negation of the desired property. An `unsat`
answer establishes the property for every assignment satisfying that
domain. A `sat` answer supplies a counterexample; `unknown` leaves the
claim open. See [checking properties](../tutorials/properties.md) for both
a successful proof and a concrete counterexample.

Check the domain itself when vacuity would matter. If the domain is
inconsistent, every counterexample query is unsatisfiable. For example,
contradictory temperature bounds do not establish that an operating system
can actually run safely anywhere.

## Check an absolute tolerance

For a value `v`, target `c`, and nonnegative exact tolerance `ε`, the
requirement and its counterexample are:

```math
\begin{gathered}
|v-c|\le\varepsilon
\quad\Longleftrightarrow\quad c-\varepsilon\le v\le c+\varepsilon, \\
\varepsilon\ge0.
\end{gathered}
```

Ask whether `v < c-ε OR v > c+ε` can hold under the domain. There is no need
to construct an absolute-value term. For a strict tolerance, the violation
uses non-strict comparisons instead. A zero tolerance expresses equality.

The [sine bounds program](../tutorials/transcendentals/bounds.md) implements
this pattern with the interval `[23/48, 1841/3840]`. Its midpoint is
`3681/7680` and its half-width is `1/7680`, so its result also certifies
that absolute tolerance about that target. Those are exact fractions.
Replacing them with rounded decimal inputs would require checking that
the rounding preserves the claimed enclosure.

An absolute tolerance is measured in the same units as the value. A
relative tolerance uses a reference magnitude; near zero it may need an
additional absolute tolerance. State the chosen rule explicitly before
encoding it. Solver limits are computational budgets and have no relation
to an application's numerical tolerance.

## Explain unsatisfiability

Enable core production before the query, retain the original asserted
terms with their labels, and request a core only after `unsat`. The
[unsat-core lesson](../tutorials/unsat-cores.md) starts with two bounds; the
[scheduling diagnosis](../tutorials/scheduling-app/conflicts.md) maps a
larger core to application requirements.

A core identifies an inconsistent subset. It does not promise a minimum
subset or tell you which requirement should be relaxed. After changing
the requirements, solve again; an old core describes the old problem.

Related API: [`getUnsatCore`](../reference/solver.md#Solver.getUnsatCore).

## Find a minimum

When feasibility is monotonic in an integer bound, maintain a proved
infeasible lower bound and a proved feasible upper bound. Use midpoint
queries to narrow the interval. Adjacent integer bounds certify an optimum.
The [scheduling application](../tutorials/scheduling-app/optimization.md)
implements this process and validates every returned feasible model.

Monotonicity must come from the formulation. It cannot be assumed for an
arbitrary parameter, such as an angle in a periodic constraint.

## Handle an inconclusive query

Retain the formula, logic, domain, and options that produced `unknown`.
Try a justified equivalent encoding or a larger budget; do not reinterpret
`unknown` as `unsat`, and do not present an unverified candidate as a witness.
The [encoding comparison](../tutorials/transcendentals/results.md#compare-equivalent-encodings)
provides a reproducible example of both outcomes on the same mathematical
question.

For interval splitting, retain the unresolved pieces. A global proof needs
every piece covered, including endpoints. For optimization, retain both
certified bounds. In both cases a partial result can be useful if its scope
is stated precisely.
