# Reason about transcendental functions

Use transcendental constraints when a specification involves exponential
growth, logarithmic thresholds, angles, or periodic behavior. The workflow
is the same as for arithmetic: construct expressions, state the domain,
assert a question, and interpret the solver's result. The mathematical
domain and the limits of the solving procedure deserve more attention.

Prerequisites: [real arithmetic](../reals.md),
[results and models](../models.md), and [checking properties](../properties.md).

## A path through the subject

| Chapter | Main question |
|---|---|
| [1. Expressions and constants](expressions.md) | How do I build `exp`, `sin`, `cos`, and symbolic π with the current bindings? |
| [2. Exponentials and logarithms](exponential-logarithms.md) | How do I prove exponential properties and represent a logarithm? |
| [3. Trigonometric constraints](trigonometry.md) | How do ranges, periods, angles, and singularities affect a model? |
| [4. Inverse and derived functions](inverse-derived.md) | How do I choose branches and build hyperbolic functions or real powers? |
| [5. Proving bounds](bounds.md) | How do I obtain a rigorous interval and use an approximation soundly? |
| [6. Results and solver limits](results.md) | What does an answer establish, and what should I do after `unknown`? |
| [7. Practical cases](practical-cases.md) | How do I bracket roots, work with bases below one, and avoid tangent poles? |
| [8. Damped oscillation](application.md) | How do I certify a signal envelope with uncertain parameters and incomplete interval checks? |

These chapters use the current Mojo API. They do not require adding new
runtime bindings. Operator names and descriptions are taken from the
generated snapshot; runnable examples establish which constructions and
queries this course actually exercises.

## Decide which question you need answered

Three tasks involving the same function can be quite different:

- **Evaluate:** obtain a numerical approximation to `sin(0.5)` for display.
- **Find a witness:** find a real input satisfying an equation or inequality.
- **Establish a property:** show that no input violates a bound or other claim.

This course concentrates on the latter two. A numerical approximation can
help explore a model, but a floating-point sample is not a proof over an
interval. Conversely, an `unsat` counterexample query can establish a bound
without returning a decimal expansion of any transcendental value.

The formulas here concern real functions. They do not directly model the
rounding behavior of Mojo's numerical math routines, and they do not model
complex branches. State additional assumptions when the application needs
either of those interpretations.

Start with [expressions and constants](expressions.md).
