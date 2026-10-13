# 1. Your first solver query

Ask whether there is a real number `x` for which `x*x < 0`. You already
know the mathematical answer: every real square is nonnegative. That makes
this a useful first query because you can check the solver's answer
independently.

Prerequisite: [installation and first run](../start/installation.md).

## Describe a counterexample

The program creates a symbolic real number and asserts that its square is
negative. The word *symbolic* matters: `x` is an expression representing an
unknown number. Constructing it does not assign a numeric value.

<!-- excerpt: docs/examples/quickstart.mojo#terms -->

`TermManager` constructs expressions. `Solver` stores the conditions you
assert and checks whether they can all hold. The two objects have different
jobs: creating `negative_square` builds a formula; `assertFormula` adds it
to this solver's problem.

`QF_NRA` selects quantifier-free nonlinear real arithmetic. The product of
two symbolic occurrences of `x` makes the expression nonlinear. You will
learn how the arithmetic fragments differ in
[real arithmetic](reals.md#choose-a-logic).

The nested `mkTerm` calls build the multiplication first and the comparison
second. The printed form `(< (* x x) 0)` uses prefix notation: the operator
comes before its arguments. It describes the same expression as `x*x < 0`.

## Run the complete program

The complete source includes imports, solver setup, and an assertion on the
expected answer. Download it or run it from the checkout:

<!-- example: docs/examples/quickstart.mojo -->

## Read the answer

`unsat` means no assignment satisfies the asserted conditions. Here that
rules out every real counterexample, establishing that a real square cannot
be negative. It does not mean the solver encountered an error. The
`assert_true` call checks that the example received the expected result.

The other possible statuses are `sat`, meaning a satisfying assignment
exists, and `unknown`, meaning the solver did not establish either answer.
Always preserve that third possibility in application code; see
[results and models](models.md).

## Exercise: change the claim

Replace the strict comparison with a non-strict one: ask whether
`x*x <= 0`. Predict the answer before running it.

**Worked answer.** The answer is `sat`, because `x = 0` satisfies it. In a
copy of the program, replace `Kind.LT` with `Kind.LEQ` and change the
assertion to `result.isSat()`. To see the zero value, enable model production
before checking and query `x` afterward, as shown in chapter 6.

Next: [sorts and symbolic terms](terms.md).
