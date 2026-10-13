# Glossary and mathematical index

Use this page to translate a mathematical question into the vocabulary of
the tutorials. For a task-first starting point, use the [cookbook](cookbook.md).

## Solver vocabulary

| Term | Meaning and next step |
|---|---|
| Assertion | A Boolean formula added to a solver's current problem. Constructing a term alone does not assert it. See [first query](../tutorials/first-query.md). |
| Branch | A restricted output interval that selects a conventional inverse from a many-valued relation. See [inverse functions](../tutorials/transcendentals/inverse-derived.md). |
| Counterexample | An assignment satisfying the domain and violating a proposed property. See [checking properties](../tutorials/properties.md). |
| Domain | The allowed inputs and side conditions of the mathematical problem, such as positivity for a logarithm. See [practical transcendental cases](../tutorials/transcendentals/practical-cases.md). |
| Enclosure | An interval proved to contain a value. It need not contain only realizable values of an exact function. See [bounds](../tutorials/transcendentals/bounds.md). |
| Exact rational | A fraction of integers represented without floating-point rounding. See [real arithmetic](../tutorials/reals.md). |
| Feasibility | Whether all requirements can hold together. See [scheduling](../tutorials/scheduling.md). |
| Incremental solving | Keeping common assertions while adding and removing temporary scoped constraints. See [push and pop](../tutorials/incremental.md). |
| Logic | The selected collection of supported theories and formula forms, such as `QF_LIA` for quantifier-free linear integer arithmetic. See [choosing a logic](../tutorials/reals.md#choose-a-logic). |
| Model; witness; satisfying assignment | Values interpreting the symbols so every assertion holds, available after `sat` with model production enabled. See [models](../tutorials/models.md). |
| Monotonicity | Consistently increasing or decreasing behavior. It can justify a threshold rewrite, a uniqueness argument, or a bound search. See [practical cases](../tutorials/transcendentals/practical-cases.md) and [optimization](../tutorials/scheduling-app/optimization.md). |
| Nonlinear | Arithmetic involving products of symbolic quantities or other nonlinear functions. A fixed constant times a symbol remains linear. See [integer constraints](../tutorials/integers.md). |
| Principal value | The value selected by a conventional branch restriction. See [inverse branches](../tutorials/transcendentals/inverse-derived.md#choose-an-inverse-branch). |
| Projection | The selected symbols whose model values you inspect, enumerate, or test for uniqueness. See [uniqueness](cookbook.md#prove-uniqueness). |
| Relaxation; overapproximation | A problem that admits every exact solution and possibly more. Its `unsat` result transfers to the exact problem when that inclusion is justified. See [abstraction direction](../tutorials/transcendentals/bounds.md#understand-the-direction-of-an-abstraction). |
| Resource budget | A limit on solver work, distinct from a time limit or a numerical tolerance. See [solver effort](../tutorials/transcendentals/results.md). |
| `sat`; satisfiable | There exists an assignment satisfying all assertions. |
| SMT | Satisfiability modulo theories: checking formulas with interpretations for arithmetic and other supported theories. |
| Sort | The type of a symbolic expression, such as Boolean, integer, or real. See [sorts and terms](../tutorials/terms.md). |
| Term | A symbolic expression, including constants, symbols, and compound operations. It is not automatically a numerical value. See [sorts and terms](../tutorials/terms.md). |
| `unknown`; inconclusive | The solver established neither satisfiability nor unsatisfiability for the query. See [handling unknown](cookbook.md#handle-an-inconclusive-query). |
| `unsat`; unsatisfiable | No assignment satisfies all assertions. It is a logical result, not an exception. |
| Unsat core | An inconsistent subset of the assertions, not necessarily a minimum one. See [conflicting requirements](../tutorials/unsat-cores.md). |
| Vacuous proof | A property holds under inconsistent assumptions because no permitted case exists. See [proving a property](cookbook.md#prove-a-property). |

## Mathematical index

| Notation or search term | Where to learn it |
|---|---|
| `exp(x)`, `e^x`, exponential | [Expressions](../tutorials/transcendentals/expressions.md) and [exponential properties](../tutorials/transcendentals/exponential-logarithms.md#prove-exponential-properties) |
| `ln(x)`, natural logarithm, `log(x)` | [Logarithm as an exponential relation](../tutorials/transcendentals/exponential-logarithms.md#represent-a-natural-logarithm) |
| `log_b(x)`, change of base | [Other bases](../tutorials/transcendentals/exponential-logarithms.md#other-logarithm-bases) and [bases below one](../tutorials/transcendentals/practical-cases.md#work-with-a-logarithm-base-below-one) |
| `sin`, sine; `cos`, cosine | [Ranges, periods, and radians](../tutorials/transcendentals/trigonometry.md) |
| `tan`, tangent; pole; singularity | [Nonzero denominator and tangent domain](../tutorials/transcendentals/practical-cases.md#keep-tangent-away-from-its-poles) |
| `asin`, arcsin; `acos`, arccos; `atan`, arctan | [Principal inverse branches](../tutorials/transcendentals/inverse-derived.md#choose-an-inverse-branch) |
| `sinh`, `cosh`, `tanh`; hyperbolic functions | [Construction from exponentials](../tutorials/transcendentals/inverse-derived.md#build-hyperbolic-functions) |
| `b^r`, positive-base real power | [Real powers and their domain](../tutorials/transcendentals/inverse-derived.md#positive-base-real-powers) |
| `sqrt(x)`, square root | [Algebraic relation and sign selection](../tutorials/transcendentals/inverse-derived.md#positive-base-real-powers) |
| `π`, pi; radians; degrees | [Symbolic constants](../tutorials/transcendentals/expressions.md) and [angle units](../tutorials/transcendentals/trigonometry.md) |
| Taylor series, remainder, approximation error | [Rational sine bounds](../tutorials/transcendentals/bounds.md) |
| Bisection, root isolation, root bracket | [Endpoint certificates on a monotonic interval](../tutorials/transcendentals/practical-cases.md#bracket-a-root-on-a-monotonic-interval) |
| `ε`, epsilon; absolute tolerance | [Tolerance recipe](cookbook.md#check-an-absolute-tolerance) |

The generated [operator table](../tutorials/transcendentals/expressions.md#operator-names)
provides the pinned release's actual `Kind` names. The notation in this
index describes mathematical concepts; it is not a list of callable Mojo
functions.
