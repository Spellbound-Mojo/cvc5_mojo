# 1. Build a scheduling application

The [two-job tutorial](../scheduling.md) introduced machine conflicts.
This three-part application adds dependencies, explains an impossible
request, and searches for the minimum integer deadline. All three parts
use one model and one maintained program.

Prerequisites: [incremental solving](../incremental.md),
[unsat cores](../unsat-cores.md), and [scheduling](../scheduling.md).

## Describe the jobs

A small workshop has two machines and four jobs:

| Job | Index in the program | Duration | Machine | Required predecessor |
|---|---:|---:|---:|---|
| A: prepare | 0 | 2 | 0 | None |
| B: cut | 1 | 3 | 1 | A |
| C: finish | 2 | 2 | 0 | B |
| D: inspect | 3 | 2 | 1 | A |

Time starts at zero and advances in integer slots. Each job runs without
interruption on its assigned machine. Finishing at a time allows another
job to start then, so job occupancy uses half-open intervals `[start, end)`.
The model covers these requirements; it does not include setup times,
optional jobs, alternate machines, or preemption.

Keep each job's start as a symbol and its end as an expression. The
requirements list owns copies of its terms, and the parallel labels list
holds explanations for people:

<!-- excerpt: docs/examples/schedule_application.mojo#jobs -->

`Term` supports implicit copies and `.copy()`. The example writes `.copy()`
explicitly when storing a term it also needs afterward. Either form retains
a reference to the same symbolic expression; it does not create another
decision variable.
See [ownership](../../start/ownership.md) for the runtime contract.

## Add dependencies and machine capacity

Precedence is an inequality between one end and another start. For jobs
sharing a machine, use a disjunction allowing either order. Here A precedes
C through B, so their machine conflict is already implied by the chain.
Keeping that condition makes the resource model explicit, but it need not
appear in an unsat core.

<!-- excerpt: docs/examples/schedule_application.mojo#dependencies -->

The helper `add_requirement` appends a formula and its label together.
Only after the model is assembled does the program assert those formulas.
This keeps the same requirements available for model validation and for
mapping a returned core back to the application.

## Establish a feasible upper bound

The `check_deadline` helper pushes a scope, constrains every end to be at
most the candidate deadline, and checks the result. For `sat`, it evaluates
both the shared requirements and the temporary deadline constraints in the
model before popping. It returns the result after removing the temporary
constraints, ready for another query.

A deadline of ten is feasible. One schedule is A at `[0,2)`, B at `[2,5)`,
C at `[5,7)`, and D at `[5,7)`. C and D overlap in time on different machines,
which the model permits. The tests validate requirements rather than
requiring the solver to choose this particular schedule.

## Run the complete application

The later chapters explain the conflict and optimization sections of the
same file. The full source and its expected output are available here:

<details markdown="1"><summary>Complete scheduling application and expected output</summary>

<!-- example: docs/examples/schedule_application.mojo -->

</details>

## Exercise: add a dependency

Suppose inspection D must finish before C starts. What happens to the
minimum deadline?

**Worked answer.** It becomes nine. After A takes two units, B and D need
five units on machine 1. C then takes two more units on machine 0. Either
ordering of B and D gives this lower bound, and a schedule attains it.
Add the new inequality to the requirements list, then update the expected
optimal deadline in a copy of the program.

Next: [explain an impossible request](conflicts.md).
