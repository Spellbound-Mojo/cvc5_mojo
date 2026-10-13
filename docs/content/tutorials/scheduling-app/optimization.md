# 3. Find and certify the minimum deadline

A feasible schedule answers “can we finish by this time?” To find the
minimum deadline, solve a sequence of feasibility problems and retain
certified bounds. This application uses ordinary solver queries rather
than requiring an optimization-specific API.

Prerequisite: the [shared model](model.md) and its deadline helper.

## Use monotonicity

If all jobs can finish by integer deadline `d`, the same schedule meets
any larger deadline. If deadline `d` is impossible, every smaller deadline
is impossible. This follows from the direction of the inequalities
`end_i <= d`; the other requirements do not change during search.

Maintain two bounds: `low` is proved infeasible and `high` is proved
feasible. The program establishes both before entering the loop. A midpoint
query then replaces the corresponding bound, preserving the invariant:

<!-- excerpt: docs/examples/schedule_application.mojo#search -->

When `high - low == 1`, there is no integer deadline between the bounds.
Thus `high` is the smallest feasible integer deadline. The final two
queries explicitly check the claimed optimum and the adjacent smaller
bound, which also makes the conclusion easy to review independently.

## Preserve inconclusive outcomes

Only `sat` moves the upper bound and only `unsat` moves the lower bound.
An `unknown` result leaves both unchanged. This demonstration raises an
error instead of printing an unproved optimum. An interactive application
could report the last certified bracket and let its caller retry with a
larger budget or a different search strategy.

Likewise, the initial feasible upper bound must be established before
search starts. In a larger application, finding that bound may require
expanding the candidate deadline. If the whole model is infeasible, no
amount of deadline expansion repairs it; separate structural conflicts
from an overly tight objective.

## Check the answer independently

The dependency chain A → B → C gives a lower bound of `2 + 3 + 2 = 7`.
The schedule shown in the [first chapter](model.md#establish-a-feasible-upper-bound)
finishes by seven. A lower bound and an attaining schedule establish the
same optimum as the solver queries.

The integer time model matters. Searching adjacent integers proves an
optimum on that grid. For continuous start times or a continuous objective,
one-unit adjacency does not rule out an intermediate improvement. You
would need an exact optimality argument or a stated tolerance and a
certified remaining interval.

## Exercise: use a different search strategy

Would testing deadlines in descending order from ten still establish the
same optimum?

**Worked answer.** Yes, if each required query is decided and the process
stops only after the first infeasible smaller deadline. Binary search uses
fewer feasibility checks when the initial integer bracket is wide, but
neither strategy may treat `unknown` as infeasible.

Continue with the [task cookbook](../../guides/cookbook.md) or return to
the [learning path](../index.md).
