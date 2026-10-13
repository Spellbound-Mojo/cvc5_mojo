# Mojo bindings for the cvc5 SMT solver

<div class="hero" markdown="1">

cvc5 Mojo lets Mojo programs use the [cvc5](https://cvc5.github.io) SMT
solver. Its API follows cvc5's Python bindings, with the same classes,
methods, and enum names, so cvc5's Python documentation and examples carry
over. You build terms with a `TermManager`, assert them on a `Solver`, and
ask for a satisfiability result, a model, an unsat core, a proof, or a
synthesized function.

The bindings are generated from the cvc5 release they bind, currently cvc5
1.4.1. The release targets Mojo 1.1.0 on Linux x86-64, Linux ARM64, and macOS Apple Silicon; see
[platform validation](architecture/packaging.md#platform-validation).
Work from a source checkout for now; a conda package is planned.

<div class="hero-actions" markdown="1">
[Get started](start/installation.md){ .button .primary }
[Tutorials](tutorials/index.md){ .button }
[API reference](reference/index.md){ .button }
</div>

</div>

<div class="cards" markdown="1">
<div class="card" markdown="1">
[Python's API in Mojo](reference/index.md)

`tm.mkConst`, `solver.checkSat`, and `Kind.ADD` work as in Python. The
reference shows each Mojo signature.
</div>
<div class="card" markdown="1">
[cvc5's examples](examples/tutorial.md)

cvc5's own Python examples, translated to Mojo. Output comparisons and model
checks verify their results against the Python originals.
</div>
<div class="card" markdown="1">
[Ownership and errors](start/ownership.md)

Values release their cvc5 objects when Mojo destroys them. A call that cvc5
rejects raises an error that you can catch.
</div>
<div class="card" markdown="1">
[Numbers of any size](start/installation.md#big-numbers-apn_mojo)

Integers and fractions come back exactly, as apn_mojo's `Integer` and
`Rational`.
</div>
<div class="card" markdown="1">
[Tested against cvc5](architecture/verification.md)

366 of cvc5's Python unit tests run in Mojo and pass, alongside the
project's own tests.
</div>
<div class="card" markdown="1">
[How the bindings are made](architecture/overview.md)

Names, signatures, and enum values are extracted from the pinned cvc5
release, and the Mojo code is generated from them.
</div>
</div>

## First program

After [setting up a checkout](start/installation.md), run this program from
the repository root. It asks cvc5 whether the square of a real number can be
negative.

<!-- example: docs/examples/quickstart.mojo -->

A `TermManager` creates sorts and terms, and a `Solver` holds assertions and
checks them. Each value holds a reference to its cvc5 object and releases it
when Mojo destroys the value; see [ownership and errors](start/ownership.md).

## What the bindings cover

| Area | Coverage |
|---|---|
| Python's base API | 392 of its 458 methods, in all 19 of its classes. The [coverage report](reference/coverage.md#base-api) lists the others. |
| Plugin callbacks | Supply lemmas and observe learned clauses through the [`Plugin` trait](reference/plugin.md) and `Solver.addPlugin`. |
| Left out | The 65 deprecated methods, each replaced by a `TermManager` method, and `Term.toPythonObj`, which returns Python objects. |
| Enums | All 14, with Python's member names and values. They print as Python's enums do. |
| Numbers | Integers of any size are apn_mojo's `Integer`, and fractions are its `Rational`. |
| Errors | A call that cvc5 rejects raises an `Error` whose message starts with `cvc5: `. |
| Platforms | Linux x86-64, Linux ARM64, and macOS Apple Silicon with Mojo 1.1.0 and cvc5 1.4.1; [validation status](architecture/packaging.md#platform-validation). Native ARM and macOS execution checks are pending. |

See [support and limitations](guides/status.md) for the details.

## Learn through worked problems

Start with the [twelve-lesson course](tutorials/index.md), then build a
[scheduling application](tutorials/scheduling-app/model.md) that diagnoses
conflicts and certifies an optimum. The
[transcendental course](tutorials/transcendentals/index.md) develops exact
queries involving exponentials, logarithms, trigonometry, and rigorous bounds.
Each course includes complete programs, explanations, and exercises.

Use the [task cookbook](guides/cookbook.md) to choose a solving pattern,
[compare Python and Mojo](guides/python-migration.md), or
[build an external consumer](guides/consumer-project.md).

## Find your starting point

| I want to... | Read |
|---|---|
| Set up a checkout and run a program | [Installation](start/installation.md) |
| Learn constraint solving step by step | [Tutorial course](tutorials/index.md) |
| Model transcendental functions | [Transcendental course](tutorials/transcendentals/index.md) |
| Learn from cvc5's own examples | [Tutorial](examples/tutorial.md) |
| Understand lifetimes and errors | [Ownership and errors](start/ownership.md) |
| Look up a class or method | [API reference](reference/index.md) |
| Check what is supported | [Support and limitations](guides/status.md) |
| Fix a failing build or run | [Troubleshooting](guides/troubleshooting.md) |
| Browse every runnable example | [Examples](examples/index.md) |
| Understand how the bindings are generated | [Architecture](architecture/overview.md) |
| Contribute | [Development](contributing/development.md) |
