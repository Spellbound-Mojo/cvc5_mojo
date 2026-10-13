# Configure a solver for your task

Choose the logic and options when you create a solver, before asserting
the model or asking a query. Keep those choices in one setup function so a
retry or a second solver uses the intended configuration. Start with the
features your application needs, then measure any performance changes on
its actual formulas.

The table below is generated from the pinned release. The values in its
default column are fresh-solver defaults, not settings prescribed by this
guide.

<!-- options: produce-models incremental produce-unsat-cores tlimit-per rlimit-per -->

The [complete option reference](../reference/options.md) includes modes,
reported numeric bounds, aliases, categories, and source links. Keeping
that catalog generated makes a version change reviewable without copying
hundreds of option descriptions into prose.

## Select a configuration by the result you need

| Task | Configuration used by the tutorials | Tested workflow |
|---|---|---|
| Read a satisfying assignment | Set `produce-models` to `true`; read values after `sat` | [Results and models](../tutorials/models.md) |
| Try temporary constraints | Set `incremental` to `true`; balance `push` and `pop` | [Incremental solving](../tutorials/incremental.md) |
| Explain conflicting assertions | Set `produce-unsat-cores` to `true`; read the core after `unsat` | [Conflicting requirements](../tutorials/unsat-cores.md) |
| Bound work per query | Choose `rlimit-per` and/or `tlimit-per`; retain an inconclusive result | [Results and solver limits](../tutorials/transcendentals/results.md) |

Explicitly enabling an application requirement keeps the setup readable
even when the current default happens to agree. Option values are strings,
as the runnable examples show. The result status still controls what the
application can conclude: enabling models does not turn `unknown` into
`sat`, and enabling cores does not make a satisfiable model contradictory.

The migration example puts its chosen logic and two required features
together:

<!-- excerpt: docs/examples/migration.mojo#setup -->

Here the model is linear real arithmetic. Select the logic to match the
terms you construct; changing resource limits does not permit terms outside
that logic. The transcendental application uses `QF_NRAT` for exponential
and sine checks and `QF_NRA` for its polynomial subqueries.

## Use resource limits as application policy

The damped oscillation example uses a shared setup helper. Its budget is a
parameter because the tutorial deliberately compares an inconclusive query
with a more generous retry:

<!-- excerpt: docs/examples/damped_oscillation.mojo#configuration -->

Time and resource limits answer different operational needs. Use elapsed
time to constrain responsiveness and resource units to bound solver work;
neither is a decimal accuracy or error-tolerance setting. The example's
values demonstrate its workflow and are not a general performance
recommendation.

For a service or batch worker that must stop by an external deadline, run
the solver in a process with its own timeout as well. The documentation
test runner enforces a hard timeout on the example's process group.
A forced termination produces a failed run, not a solver result.

On `unknown`, retain the pending question and its settings. You can retry
with a larger budget, simplify the encoding, or split the domain into
pieces whose union still covers it. The
[damped oscillation application](../tutorials/transcendentals/application.md)
shows how to preserve coverage across that retry.

## Keep configuration experiments comparable

Record the pinned library version, logic, nondefault options, input formula,
and result when comparing configurations. Use a fresh solver for independent
experiments; [copying a solver](../start/ownership.md) retains the same
underlying instance and assertion stack. A faster run on one formula does
not establish a better setting for another theory or workload.

If an option is rejected, first check its exact name, value kind, and modes
in the generated reference, then check when the program sets it. Do not
silently continue with a missing required feature. The binding raises an
error for a failing call; see [error handling](../start/ownership.md).
