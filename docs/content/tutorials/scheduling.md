# 12. Schedule work on a shared machine

Two jobs need the same machine. Job A lasts two time units and job B lasts
three. Both start at or after zero. Determine whether both can finish by a
given deadline without overlapping.

Prerequisites: [Boolean constraints](booleans.md),
[integer constraints](integers.md), and [results and models](models.md).

## Describe feasibility

Use integer start times `a` and `b`. Their end times are `a + 2` and `b + 3`.
The shared-machine constraint is a disjunction:

```text
(a + 2 <= b) OR (b + 3 <= a)
```

Either A finishes before B starts, or B finishes before A starts. The
non-strict comparisons permit back-to-back jobs: finishing at time two
allows the next job to start at time two.

<!-- example: docs/examples/scheduling.mojo -->

The requirements are kept in a list so the program can both assert them
and verify their truth in a returned model. This also gives an application
a natural place to associate labels with requirements for diagnostics.

## Explain both answers

A deadline of four is impossible: one machine must perform five units of
work, and no work may start before zero. A deadline of five is feasible;
for example, A can occupy `[0, 2)` and B `[2, 5)`.

The program does not require this specific ordering. Either job can run
first. The test validates the modeled conditions, so an alternative valid
schedule does not cause a spurious failure.

Checking one deadline is a feasibility query. It is not an optimization
command. If you want the minimum deadline, you can test candidate bounds
and establish that a feasible bound is optimal by ruling out all smaller
allowed bounds. For this integer example, checking four and five plus
monotonicity in the deadline establishes the minimum.

## Extend the model deliberately

A precedence requirement “A must finish before B starts” removes the
choice of ordering. Different machines require non-overlap constraints
only for jobs competing for the same machine. Real-valued start times
would model continuous time, while the current integer sort models a grid
of time slots.

For many jobs, a direct pairwise encoding introduces one non-overlap
condition per competing pair. The small example teaches the model; it is
not evidence of how a large scheduling instance will perform.

## Exercise: add a release time

Suppose neither job may start before time one. What is the earliest common
deadline?

**Worked answer.** Six. Shift either valid five-unit schedule forward by
one. A deadline of five leaves only four usable units after release, which
is insufficient. Change both lower bounds and test adjacent candidate
deadlines in a copy of the example.

Continue with [transcendental functions](transcendentals/index.md) or
[organizing solver code](../guides/modeling.md).
