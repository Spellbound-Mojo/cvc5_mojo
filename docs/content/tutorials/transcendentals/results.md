# 6. Interpret results and control solver effort

A correct transcendental encoding does not guarantee a quick answer.
An equation can have a familiar mathematical solution while a particular
solver query returns `unknown` or exceeds its resource budget. Your program
must preserve that distinction.

Prerequisites: [results and models](../models.md) and
[exponentials and logarithms](exponential-logarithms.md).

## What each result establishes

For the exact assertions in these examples, `sat` establishes existence and
`unsat` establishes nonexistence. If you asserted a property's negation,
`unsat` establishes that property under the other assertions. `unknown`
establishes neither answer.

If you instead supplied a polynomial approximation, the result concerns
that approximate model. Transferring the conclusion to the original
function requires an argument such as the
[enclosure reasoning](bounds.md#understand-the-direction-of-an-abstraction)
from the previous chapter.

## Exercise the inconclusive branch

The mathematical equation `exp(x) = 2` has the solution `ln(2)`. This
example deliberately gives the solver a resource budget too small to
establish that result.

<!-- example: docs/examples/resource_limits.mojo -->

The test expects the `unknown` branch for this pinned example. It does not
pretend that the equation is unsatisfiable, and it does not request a model
and present it as a verified witness after an inconclusive result.

The transcendental examples also set `tlimit-per` to `5000`, a per-query
time limit in milliseconds. This example uses `rlimit-per`, which counts
solver resources rather than elapsed seconds. A resource unit is not a
portable amount of CPU time. Both options are documented in the
[pinned option reference](https://cvc5.github.io/docs/cvc5-1.4.1/options.html).

A finite limit is useful for an interactive application, but reaching it
says something about the run, not the mathematics. Likewise, success on a
small tutorial does not guarantee the same cost for a larger formula.

## Choose a useful query

Ask for the property the application actually needs. To establish that a
logarithmic value lies within a safe interval, try refuting a violation of
the interval. You may not need an exact witness for the unconstrained
logarithm equation. The [logarithm example](exponential-logarithms.md)
uses precisely that approach for `ln(2)`.

Tighter domain constraints can help when they are justified by the
application. Splitting an interval can also help, but a conclusion covering
the original interval requires covering every piece, including the
endpoints. Do not report a global proof after solving only a convenient
subset of the domain.

Independent queries can use fresh solvers. In checks for this course,
reusing a solver after an unsatisfiable transcendental query made some
subsequent queries reach their time limit, while fresh solvers completed
them. The exponential and logarithm examples therefore use independent
solvers for independent questions. This is an observed formulation choice,
not a general claim that incremental solving is incorrect or always slower.

## Compare equivalent encodings

On the domain `0 < x < 1`, the property `ln(x) < 0` can be checked by
refuting either `exp(y) = x AND y >= 0`, or the equivalent condition
`x >= 1`. Both contradict the same domain. The latter removes the
transcendental relation using strict monotonicity of the exponential.

<!-- excerpt: docs/examples/encoding_budgets.mojo#formulations -->

Run each formulation in a fresh solver with the same resource budget. This
program tests both a deliberately tiny budget and a larger fixed one;
it reports all three statuses without asking for a model after `unknown`.

<!-- example: docs/examples/encoding_budgets.mojo -->

For this pinned release, the algebraic contradiction is resolved even with
the tiny resource budget. The relational version is inconclusive at that
budget and succeeds with the larger one. The output records statuses,
not a wall-clock benchmark. Resource accounting and preprocessing can
change across releases; these observations do not promise a speedup or a
particular threshold for other formulas.

The comparison is meaningful because the formulas were first shown to be
equivalent on the same domain. Replacing a difficult function with an
unchecked approximation would compare different problems.

## Inspect values without inventing precision

An exact real term may print as a rational or as a symbolic expression.
Do not assume that `String(value)` is a decimal suitable for conversion to
`Float64`, or that a displayed decimal proves an exact transcendental
equality. For inequalities near a boundary, use a justified enclosure.

After `result.isUnknown()` succeeds, use
[`result.getUnknownExplanation()`](../../reference/results.md#Result.getUnknownExplanation)
to inspect the diagnostic enum. Keep the original formula and solver
settings with that result; a diagnostic identifies why the query was
inconclusive, rather than answering the pending mathematical question.

## A practical recovery procedure

After an inconclusive query, retain the exact formula, domain restrictions,
logic selection, and resource options. Check the encoding for accidental
nonlinearity or missing domains. Then choose whether a larger budget, an
equivalent formulation, or a sound interval decomposition answers the
application's question. Report an inconclusive result if none succeeds.

Do not add the desired inequality as an assumption merely to obtain a
decided result. An auxiliary lemma needs an independent justification;
otherwise it changes the claim being checked.

## Exercise: partial success

A domain is split into three intervals. Two counterexample queries return
`unsat` and the third returns `unknown`. Has the property been proved on
the whole domain?

**Worked answer.** No. It has been established on the first two intervals,
assuming the encodings and endpoint coverage are correct. The third remains
open. Increasing its budget or splitting it further can be useful, but the
reported global status must remain inconclusive until every part is covered.

Continue with [root brackets and domain pitfalls](practical-cases.md),
or [organizing solver code](../../guides/modeling.md) or browse
the [example gallery](../../examples/index.md).
