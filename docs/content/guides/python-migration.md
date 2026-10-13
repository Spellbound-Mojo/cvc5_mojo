# Move a Python cvc5 model to Mojo

Port the mathematical model first, then adapt construction, ownership,
and error handling to the available Mojo API. The bindings preserve cvc5's
Python base API names; the generated API covers the supported methods. The
[reference](../reference/index.md) shows actual Mojo declarations alongside
the upstream Python signatures and marks unavailable methods.

This guide solves the same problem in both languages: find the real `x`
such that `2*x = 1`, read its value, temporarily require `x < 0`, and
restore the original assertions. Both programs assert their results and
are checked against the same expected output using the pinned release.

## Construct the same formula

<div class="language-comparison" markdown="1">
<section markdown="1">

### Python

<!-- excerpt: docs/examples/migration.py#setup -->

</section>
<section markdown="1">

### Mojo

<!-- excerpt: docs/examples/migration.mojo#setup -->

</section>
</div>

The declarations express the same real equation. Both use `mkReal(1)`
to keep the constant exact. For rational values, `mkReal` also accepts
exact strings and apn_mojo's `Rational`; see the
[constructor reference](../reference/term-manager.md#TermManager.mkReal).

Python's `*operands` expands a list into positional arguments. The current
Mojo `mkTerm` declarations accept variadic `Term` arguments or a `List[Term]`;
the example passes `x, x` directly. For a dynamic collection, pass the list
as one argument, as in `tm.mkTerm(Kind.ADD, operands)`. Read the Mojo
declaration for each construction you port instead of assuming that Python's
list-unpacking syntax applies unchanged.

## Preserve the meaning of a copy

Python assignment gives another reference to the same solver. Mojo assignment
also shares the underlying instance; an explicit `solver.copy()` does too.
Neither creates
an independent assertion stack. Both programs demonstrate that behavior
by pushing through the second reference and checking through the first:

<div class="language-comparison" markdown="1">
<section markdown="1">

### Python shared reference

<!-- excerpt: docs/examples/migration.py#shared -->

</section>
<section markdown="1">

### Mojo shared reference

<!-- excerpt: docs/examples/migration.mojo#shared -->

</section>
</div>

With `x = 1/2`, the temporary negative constraint is contradictory. After
`pop()`, the original problem is satisfiable again. If two experiments need
independent state, construct two solvers and apply the model to each.
Keep terms associated with their intended term manager.

Mojo wrappers own references and release them automatically. Move a value
when transferring ownership; implicit or explicit copies retain another
reference. Do not add manual C-level release calls. The
[ownership guide](../start/ownership.md) explains why returned results and
terms can remain valid after the local wrapper that produced them is gone.

## Translate the surrounding application code

| Python pattern in this example | Mojo counterpart | Why it matters |
|---|---|---|
| Import from `cvc5` | Import from `cvc5_mojo` | Select the binding package |
| Local assignment | `var` declarations | Follow Mojo's value and ownership rules |
| `str(value)` | `String(value)` or `print(value)` | Use the wrapper's `Writable` implementation |
| `assert condition` | `assert_true(condition)` from `std.testing` | Keep executable checks in the tutorial program |
| Exceptions propagate through `main` | `def main() raises` | A failed binding call raises a Mojo error |
| `shared = solver` | `var shared = solver` or `solver.copy()` | Both references share the solver state |

The printed value `(/ 1 2)` is a symbolic exact rational, not a host
floating-point number. Construct further symbolic constraints from terms;
do not make application logic depend on parsing printed expression text.
The example compares text only because this equation has a known, unique
small result and its output is part of the documentation contract.

A solver status is also different from an exception. Handle `sat`, `unsat`,
and `unknown` explicitly. Catch a Mojo error when a binding operation fails,
for example because the term construction has incompatible sorts; see
[error handling](../start/ownership.md#errors-are-mojo-errors).

## Run both complete programs

After [setting up the checkout](../start/installation.md), the Python
counterpart runs in the repository's `oracle` environment. That environment
pins the official Python package to the same cvc5 release. The Mojo program
runs in the default environment.

<details markdown="1"><summary>Complete Python program and expected output</summary>

<!-- python-example: docs/examples/migration.mojo -->

</details>

<details markdown="1"><summary>Complete Mojo program and expected output</summary>

<!-- example: docs/examples/migration.mojo -->

</details>

Run the paired checks from the repository root, choosing fresh report
directories:

```sh
pixi run --locked docs-test --only migration --output .cache/migration-mojo-001
pixi run --locked -e oracle docs-oracle-test --only migration --output .cache/migration-python-001
```

The Mojo check uses source and precompiled imports at O0 and O3. Both
language checks compare their program's output with one manifest entry.
This pair establishes the behavior shown here. The
[upstream tutorial](../examples/tutorial.md) also uses automatically translated
cvc5 examples whose outputs are checked against the Python originals.

## Port a larger model in small steps

Inventory the source program's constructors and solver methods against the
reference before translating it. Start with terms and one satisfiability
query, then add model reads, scopes, and conflict explanations. Keep small
accepted and rejected instances in your application's own tests. If a
required method is unavailable, use a documented construction only when
it preserves the mathematics, or treat it as a binding gap; matching names
alone cannot establish equivalent behavior.

Continue with [using the bindings in another project](consumer-project.md)
to move the translated model out of this checkout.
