# Tutorial: cvc5's examples in Mojo

Each program on this page is one of cvc5's own Python examples, from
`examples/api/python` in the cvc5 1.4.1 sources, translated to Mojo by
`bindgen.translate`. The programs are generated, not edited by hand.
`pixi run --locked cvc5-tests` builds each one and compares its output with
the official Python bindings. Most examples match exactly. The floating-point
example checks its models and compares the remaining output exactly, since
valid witnesses can differ between builds. Recorded Python output is shown
under each program.

The translation keeps Python's names and structure, so you can read each
program alongside its Python original in cvc5's sources. The differences
come from Mojo:

- a variable is declared with `var`, and a function's parameters have types;
- a list is typed by its first element, or by what is appended to it;
- an f-string or `"...".format(...)` becomes `String(...)`, which writes each
  value as Python's `str` does;
- comments are not carried over, so the explanations are here instead.

## Hello world

A term manager creates sorts and terms, and a solver checks them. A Boolean
constant named `Hello World!` is satisfiable on its own. cvc5 prints the
symbol between bars, because it contains a space.

<!-- translated: helloworld -->

## Quickstart

The quickstart sets options and a logic, builds real and integer constants
and constraints with `mkTerm`, and checks satisfiability. `getValue` returns
a model value as a term. `getRealValue` turns that term into an exact
fraction, apn_mojo's `Rational`, which subtracts and prints as Python's
`Fraction` does. After `resetAssertions`, a set of integer constraints that
cannot hold together gives an unsat core: a `List[Term]` that prints as
Python's list does.

<!-- translated: quickstart -->

## Datatypes

This example declares a list of integers as a datatype: a `DatatypeDecl`
with declarations of its constructors and their selectors. The datatype's
sort gives the `Datatype`, which you can index by constructor name, as in
`consList["cons"]`, and iterate over its constructors and their selectors.
Terms of the datatype apply constructors, selectors, testers, and updaters.
The second half declares a parametric list and instantiates it with
integers.

The Python example's helper function `test` becomes a Mojo function, with
its parameters typed by the arguments it is called with. `main` calls it
twice, the second time on a datatype made with `declareDatatype`.

<!-- translated: datatypes -->

## Parsing SMT-LIB

An `InputParser` reads SMT-LIB text into commands. The loop invokes each
command on the solver until `nextCommand` returns a null command. Each
command prints its response, which is `success` with the `print-success`
option. The solver then holds the parsed assertions.

<!-- translated: parser -->

## Synthesis

This example uses syntax-guided synthesis. It defines a grammar for the
function `max`, leaves `min` unrestricted, and states constraints over
universally quantified variables. `checkSynth` finds both functions. The two
helper functions come from the Python example's `utils` module, and the
translator types their parameters from the call, as `List[Term]`.

<!-- translated: sygus_fun -->

## Floating-point models

The floating-point example demonstrates fused arithmetic, non-associative
addition, NaN and infinity, rounding modes, and the gap between zero and the
smallest positive value. Two correct solver builds can choose different
values for a satisfiable formula. Requiring identical witnesses would reject
valid results.

The translation evaluates every active assertion after each SAT result. It
also checks that each printed value has the term's sort and equals that term
in the model. The comparison keeps the SAT/UNSAT answers, explanatory text,
and output order exact. The Python witness below is one valid output, not a
required choice of floating-point bits.

<!-- translated: floating_point -->

## Catching errors

The legacy exceptions example returns a nonzero status if an expected error
is missing. Its invalid option remains a runtime check. Two other calls have
invalid argument types or arity in Mojo; generated compile-failure fixtures
check those calls separately. Translation stops at the first rejected call,
as Python does when it raises, rather than trying to execute unreachable
legacy names later in the block.

<!-- translated: exceptions -->

## All the examples

22 of cvc5's 23 Python examples run: 21 match Python's output exactly and one
uses the model checks described above. The
[coverage report](../reference/coverage.md#examples) lists them, and says why
the finite-field example does not run. They are in `tests/cvc5/examples/`, and you can run
any of them from the repository root:

```sh
pixi run --locked mojo run -I src tests/cvc5/examples/<name>.mojo
```
