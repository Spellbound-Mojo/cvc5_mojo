# Learn constraint solving with Mojo

A constraint solver searches for values that satisfy the conditions you
write. You describe a valid configuration, schedule, or counterexample;
the solver determines whether one exists. These tutorials take you from
your first query to complete models and reasoning about transcendental
functions.

You need basic Mojo: variables, functions, loops, and `raises`. No previous
SMT experience is assumed. SMT means *satisfiability modulo theories*: the
solver understands both Boolean combinations of conditions and the
mathematical domains, such as integers, used inside them.

First complete [installation](../start/installation.md). Run every program
from the repository root. Each included example has a download link, a run
command, and tested output. The examples use the currently importable
bindings; a method's appearance in the full upstream reference does not
by itself mean the Mojo package implements it.

## The main course

| Chapter | What you will do |
|---|---|
| [1. Your first query](first-query.md) | Ask whether a real number can have a negative square |
| [2. Sorts and symbolic terms](terms.md) | Separate a Mojo value, an expression, and a Boolean constraint |
| [3. Boolean constraints](booleans.md) | Model a feature dependency |
| [4. Integer constraints](integers.md) | Recover ticket counts from a total |
| [5. Real arithmetic](reals.md) | See how the choice of domain changes the answer |
| [6. Results and models](models.md) | Read a witness and interpret all three result states |
| [7. Checking properties](properties.md) | Prove a claim by ruling out counterexamples |
| [8. Incremental solving](incremental.md) | Try alternatives while retaining shared constraints |
| [9. Conflicting requirements](unsat-cores.md) | Identify a subset that cannot hold together |
| [10. Enumerating solutions](enumeration.md) | Block previous assignments and establish completeness |
| [11. Graph coloring](coloring.md) | Build a finite combinatorial model |
| [12. Scheduling](scheduling.md) | Encode durations, deadlines, and a shared resource |

Read the first six in order. The later chapters build on those concepts,
and each identifies any additional prerequisite. Exercises include worked
answers so you can check the reasoning before changing and running a
program yourself. Expected output belongs to the original program; an
exercise can deliberately change that output or invalidate its assertions.

## Transcendental functions

After real arithmetic and property checking, continue to
[transcendental functions](transcendentals/index.md). This six-chapter part
covers expressions involving `exp`, natural and other logarithms, `sin`,
`cos`, `tan`, inverse functions, and derived hyperbolic functions. It also
develops rational bounds and explains how to handle inconclusive queries.

## Use the course in your own program

The [example gallery](../examples/index.md) is a task-oriented index.
[Organizing solver code](../guides/modeling.md) explains model construction,
result handling, and validation. Use the [API reference](../reference/index.md)
to look up an operation once you understand the workflow.

The examples assert mathematical properties and check their output on both
import routes and at both optimization levels. Those checks establish the
examples' behavior with the pinned release. They do not establish a
performance guarantee for a larger instance of the same problem.

## Build a larger application

The [scheduling application](scheduling-app/model.md) carries one model
through dependencies, conflict diagnosis, and deadline optimization. For
specific tasks, use the [cookbook](../guides/cookbook.md); for terminology
and function names, use the [glossary and mathematical index](../guides/glossary.md).
