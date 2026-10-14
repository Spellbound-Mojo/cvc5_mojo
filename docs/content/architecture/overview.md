# Architecture overview

CVC5 Mojo calls the native cvc5 solver through its C API. The Mojo classes
follow cvc5's Python base API, so you can build terms, assert constraints,
and inspect results using familiar solver operations.

## Three layers

| Layer | What it does |
|---|---|
| Public Mojo API | Classes such as `TermManager`, `Solver`, `Term`, and `Sort` convert Mojo values and retain the native objects they depend on. |
| C bindings and runtime | Resolve C functions, load the matching native libraries, copy returned data, and turn cvc5 errors into Mojo errors. |
| Native cvc5 | Performs simplification, solving, model construction, and synthesis. |

The public wrappers retain their owners. A term can outlive the local
variable that created its `TermManager`, but terms from different managers
cannot be mixed. Read [ownership and errors](../start/ownership.md) for the
rules that affect application code.

The runtime loads the main solver and parser libraries from one release.
The package keeps them in a private directory beside their bundled
dependencies. See [installation](../start/installation.md#where-the-library-is-found)
for discovery paths and overrides.

## Generated from a pinned release

`cvc5-version.toml` selects the upstream release. The generator extracts its
API declarations, enum values, documentation, exported symbols, and
ownership information into a committed snapshot. That snapshot produces
the Mojo bindings and this site's API reference. Explicit exceptions live
in `bindgen/overrides.toml`.

Tests compare the bindings with cvc5's own Python tests and examples, and
check Mojo-specific behavior such as object lifetimes and callbacks. The
[coverage report](../reference/coverage.md) records what is covered and
what remains excluded; [support and limitations](../guides/status.md)
explains the practical boundaries.

## Changing the bindings

Application authors can continue with the [tutorials](../tutorials/index.md)
and [API reference](../reference/index.md). Contributors should start with
[development](../contributing/development.md) and
[working on the generator](../contributing/generator.md).

Detailed implementation notes and validation reports are grouped under
**Contributing**. The [upgrade procedure](upgrades.md) and
[packaging guide](packaging.md) cover maintenance and release work.
