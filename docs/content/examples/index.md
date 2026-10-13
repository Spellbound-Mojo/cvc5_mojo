# Examples

Every program below is a complete, maintained file in `docs/examples/`. Each
one asserts its own results, and the documentation tests build it from source
and from the precompiled package at O0 and O3 with `--Werror`, run it, and
compare its output with the expected output shown on its page. Run any of them
from the repository root:

```sh
pixi run --locked mojo run -I src docs/examples/<name>.mojo
```

## Foundations and applications

Follow the [tutorial learning path](../tutorials/index.md) for prerequisites
and exercises. The early examples assume basic Mojo and introduce SMT from
the beginning; the application examples assume the preceding modeling lessons.

| Program | Task and explanation |
|---|---|
| `quickstart.mojo` | [Rule out a negative real square](../tutorials/first-query.md) |
| `terms.mojo` | [Inspect symbolic sorts and operations](../tutorials/terms.md) |
| `booleans.mojo` | [Configure dependent features](../tutorials/booleans.md) |
| `integers.mojo` | [Recover ticket counts](../tutorials/integers.md) |
| `reals.mojo` | [Compare integer and real solutions](../tutorials/reals.md) |
| `properties.mojo` | [Prove a property and find a counterexample](../tutorials/properties.md) |
| `incremental.mojo` | [Try candidates in assertion scopes](../tutorials/incremental.md) |
| `unsat_core.mojo` | [Identify conflicting bounds](../tutorials/unsat-cores.md) |
| `enumeration.mojo` | [Enumerate a finite solution set](../tutorials/enumeration.md) |
| `coloring.mojo` | [Color a triangle with a fixed budget](../tutorials/coloring.md) |
| `uniqueness.mojo` | [Prove uniqueness of a selected tuple](../guides/cookbook.md#prove-uniqueness) |
| `schedule_application.mojo` | [Build, diagnose, and optimize a four-job application](../tutorials/scheduling-app/model.md) |
| `scheduling.mojo` | [Check deadlines and resource conflicts](../tutorials/scheduling.md) |
| `debugging.mojo` | [Repair domains, assumptions, units, and blocking clauses](../guides/debugging-models.md) |

## Transcendental functions

These examples build on real arithmetic and counterexample queries. Start
with the [transcendental learning path](../tutorials/transcendentals/index.md)
for the mathematical assumptions and solver limitations.

| Program | Task and explanation |
|---|---|
| `transcendental_terms.mojo` | [Construct functions, symbolic π, and exact fractions](../tutorials/transcendentals/expressions.md) |
| `exponentials.mojo` | [Prove exponential positivity and growth](../tutorials/transcendentals/exponential-logarithms.md#prove-exponential-properties) |
| `logarithms.mojo` | [Encode a logarithm and prove an enclosure](../tutorials/transcendentals/exponential-logarithms.md#represent-a-natural-logarithm) |
| `trigonometry.mojo` | [Prove sine and cosine range bounds](../tutorials/transcendentals/trigonometry.md#prove-range-bounds) |
| `sine_phase.mojo` | [Combine a phase restriction and a square](../tutorials/transcendentals/trigonometry.md#restrict-a-phase-interval) |
| `inverse_branches.mojo` | [Select a principal inverse branch](../tutorials/transcendentals/inverse-derived.md#choose-an-inverse-branch) |
| `hyperbolic.mojo` | [Build sinh and cosh from exponentials](../tutorials/transcendentals/inverse-derived.md#build-hyperbolic-functions) |
| `sine_bounds.mojo` | [Check exact rational Taylor bounds](../tutorials/transcendentals/bounds.md) |
| `root_bracket.mojo` | [Certify endpoint signs for a unique root](../tutorials/transcendentals/practical-cases.md#bracket-a-root-on-a-monotonic-interval) |
| `logarithm_base.mojo` | [Check the sign behind a decreasing logarithm](../tutorials/transcendentals/practical-cases.md#work-with-a-logarithm-base-below-one) |
| `tangent_domain.mojo` | [Exclude a tangent pole](../tutorials/transcendentals/practical-cases.md#keep-tangent-away-from-its-poles) |
| `encoding_budgets.mojo` | [Compare equivalent queries at fixed budgets](../tutorials/transcendentals/results.md#compare-equivalent-encodings) |
| `resource_limits.mojo` | [Handle an inconclusive query](../tutorials/transcendentals/results.md) |
| `damped_oscillation.mojo` | [Certify a signal envelope over uncertain parameters and time intervals](../tutorials/transcendentals/application.md) |

## Runtime and combined workflows

| Program | Task and explanation |
|---|---|
| `models.mojo` | [Combine options, scopes, model values, and an unsat core](#models-and-unsat-cores) |
| `errors.mojo` | [Catch a cvc5 error and continue](../start/ownership.md#errors-are-mojo-errors) |
| `lifetimes.mojo` | [Return a result that outlives its solver](../start/ownership.md#values-outlive-what-made-them) |
| `migration.mojo`, `migration.py` | [Compare equivalent Python and Mojo programs](../guides/python-migration.md) |
| `consumer/main.mojo` | [Import the library and a local module outside the checkout](../guides/consumer-project.md) |

cvc5's Python examples are also translated to Mojo in `tests/cvc5/examples/`.
The [upstream tutorial](tutorial.md) explains five of them, and the
[coverage report](../reference/coverage.md#examples) lists them all. The
maintained tutorial programs complement those examples with worked reasoning
and exercises; see [verification](../architecture/verification.md).
The migration pair also runs in the pinned Python oracle environment against
the same output. The consumer example receives an additional working-directory
check: every build route runs from an isolated directory with explicit library
discovery.

## Models and unsat cores

<!-- example: docs/examples/models.mojo -->
