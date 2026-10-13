# Organize and validate solver code

Keep the mathematical model visible in the program. Give symbols and
requirements application names, separate construction from query handling,
and validate returned values against the requirements you intended to encode.

Start with the [tutorial course](../tutorials/index.md) if you have not built
a model before.

## Separate three responsibilities

Model construction creates symbols, derives useful expressions, and asserts
requirements. Query handling checks satisfiability and distinguishes all
three result states. Result presentation translates model values or core
members back into the application's vocabulary.

The [scheduling example](../tutorials/scheduling.md) keeps requirements in a
list and uses the list for both assertion and model validation. The
[core example](../tutorials/unsat-cores.md) retains the original terms so it
can identify returned requirements. These patterns scale more clearly than
scattering unnamed assertions throughout unrelated application code.

Keep helper functions local to an example or application when they express
its domain. A helper that constructs a mathematical formula is not a new
library primitive and should not hide essential assumptions such as a
positive logarithm argument or a nonzero denominator.

## Keep related terms together

Use one term manager for the terms in a problem and construct the solver
from that manager. Separate solvers can share expressions made by that
manager, as the [exponential examples](../tutorials/transcendentals/exponential-logarithms.md)
demonstrate. Create a new solver when you need independent assertion state;
copying the current wrapper shares its underlying state.

Values retain the ownership needed for their lifetimes. You do not add
manual release calls when returning a term or a result from a helper.
See [ownership and errors](../start/ownership.md) for the complete contract
and a tested function-return example.

## Check the translation into mathematics

Before querying, write down what each symbol means, its domain, and its
unit. A count usually needs an integer and a nonnegative bound. An angle
needs a unit and sometimes an interval. A logarithm needs a positive
argument. A fixed-width machine calculation needs an appropriate machine
arithmetic model rather than an unqualified real expression.

Check the Boolean structure too. Several assertions mean all conditions
must hold. An alternative requires a disjunction. A property check needs
the negated conclusion. These errors can produce perfectly valid solver
answers to the wrong problem.

## Validate outcomes at the right level

For a unique small answer, independently derive it and assert the expected
value, as in the ticket tutorial. For multiple possible models, check
validity conditions rather than choosing one arbitrary output ordering.
For enumeration, check uniqueness and completeness separately. For a proof,
inspect whether the assumptions themselves are satisfiable.

Distinguish an API error from `unsat`, and distinguish `unknown` from both.
Catch API errors where the application can report a useful invalid-input
message or recover its construction state. Give inconclusive solver results
an explicit path through the application instead of presenting them as a
missing solution.

## Reproduce an unexpected result

Reduce the problem to a complete program with its original sorts, assertions,
options, and status handling. Prefer that program to a screenshot of a
printed formula. For a nonlinear or transcendental issue, include resource
limits and whether the query used a fresh solver or an incremental stack.

The [troubleshooting guide](troubleshooting.md) covers environment and
runtime failures. The [documentation workflow](../contributing/documentation.md)
explains how to turn a small program into a maintained example with tested
output.
