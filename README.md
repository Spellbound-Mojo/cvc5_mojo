# CVC5 Mojo

CVC5 Mojo lets Mojo programs use the [cvc5](https://cvc5.github.io) SMT
solver. Its API follows cvc5's Python bindings, with the same classes,
methods, and enum names, so cvc5's Python documentation and examples carry
over. The bindings are generated from the cvc5 release they bind.

![Mojo 1.1.0](https://img.shields.io/badge/Mojo-1.1.0-orange)
![cvc5 1.4.1](https://img.shields.io/badge/cvc5-1.4.1-blue)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20Apple%20Silicon-blue)
![License](https://img.shields.io/badge/license-Apache%202.0%20with%20LLVM%20exceptions-green)

This program asks cvc5 whether the square of a real number can be negative:

```mojo
from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Kind

def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_NRA")
    var x = tm.mkConst(tm.getRealSort(), "x")
    var negative_square = tm.mkTerm(Kind.LT, tm.mkTerm(Kind.MULT, x, x), tm.mkInteger(0))
    solver.assertFormula(negative_square)
    var result = solver.checkSat()
    assert_true(result.isUnsat())
    print(negative_square, "is", result)   # (< (* x x) 0) is unsat
```

## Install

Version **1.4.1.0** is published in the
[modular-community channel](https://prefix.dev/channels/modular-community/packages/cvc5_mojo)
for Linux x86-64 (`linux-64`), Linux ARM64 (`linux-aarch64`), and macOS 15+
Apple Silicon (`osx-arm64`). Install [Pixi](https://pixi.sh/), then create a
project with the three channels and add Mojo and the bindings:

```sh
pixi init solver-project --platform linux-64 --platform linux-aarch64 \
  --platform osx-arm64 -c https://conda.modular.com/max \
  -c https://repo.prefix.dev/modular-community -c conda-forge
cd solver-project
pixi add "mojo==1.1.0" "cvc5_mojo==1.4.1.0"
```

Save the program above as `main.mojo` and run it with
`pixi run --locked mojo run main.mojo`. The package includes cvc5's native
solver and parser libraries, and installs apn_mojo 1.0.1 for exact integers
and fractions; no `-I` flag or library path is needed. See
[installation](docs/content/start/installation.md) and the
[release notes](docs/content/releases.md).

## Work from a checkout

To change the bindings or the generator, get the source and its
dependencies:

```sh
git clone https://github.com/Spellbound-Mojo/cvc5_mojo.git
cd cvc5_mojo
pixi install --locked
pixi run --locked generate   # downloads and checks cvc5 1.4.1, then regenerates
pixi run --locked mojo run -I src docs/examples/quickstart.mojo
```

Run the commands from the repository root. `--locked` keeps every dependency
at the version in `pixi.lock`, including the build and checksum of
[apn_mojo](https://prefix.dev/channels/modular-community/packages/apn_mojo).
Each platform has its own native archive; see
[platform validation](docs/content/architecture/packaging.md#platform-validation).

## What the bindings cover

- **Python's base API.** 392 of the 458 methods of cvc5's Python API are
  generated, across all 19 base API types. The others are the 65 deprecated
  methods and `Term.toPythonObj`.
- **Plugin callbacks.** Implement the `Plugin` trait to supply lemmas or
  observe learned clauses and theory lemmas during solving. See the
  [plugin tutorial](docs/content/reference/plugin.md).
- **Oracle callbacks.** Implement a deterministic function with the `Oracle`
  trait and register it through `Solver.declareOracleFun`. See the
  [oracle tutorial](docs/content/reference/oracles.md).
- **Numbers of any size.** Integers and fractions are apn_mojo's `Integer`
  and `Rational`.
- **cvc5's own tests.** 366 of cvc5's 377 Python unit tests are translated to
  Mojo and pass. 22 of its 23 Python examples run: 21 reproduce the official
  Python output exactly; the floating-point example validates its models
  and matches the solver results and explanatory text. Nine generated
  compile-failure fixtures check arguments that Mojo rejects before execution.

## How the bindings are made

The generator extracts cvc5's API declarations, enum values, documentation,
and ownership information from a pinned release, then produces the Mojo
bindings and reference pages. Fixes go into the generator so they survive
an upstream upgrade.

See the [architecture overview](docs/content/architecture/overview.md) for
the three layers and the [contributor guide](docs/content/contributing/generator.md)
for implementation details. Maintainers can follow the
[upgrade procedure](docs/content/architecture/upgrades.md) when cvc5 changes.

## Documentation

The [tutorial course](docs/content/tutorials/index.md) teaches constraint
solving through twelve lessons, with worked examples and exercises. The
[transcendental-functions course](docs/content/tutorials/transcendentals/index.md)
covers exponentials, logarithm encodings, trigonometry, inverse branches,
exact bounds, and solver limits. Continue with a complete scheduling
application or the guides for Python migration and external consumers.

The documentation is a site built from [`docs/content`](docs/content/index.md).
It will be published when the repository becomes public. To browse it
locally:

```sh
pixi run --locked -e docs docs-serve
```

| Start with | For |
|---|---|
| [Installation](docs/content/start/installation.md) | Setting up a checkout and running programs |
| [Tutorial course](docs/content/tutorials/index.md) | Constraint solving from the first query through applications |
| [Transcendental functions](docs/content/tutorials/transcendentals/index.md) | Exponentials, logarithms, trigonometry, bounds, and solver limits |
| [Upstream examples](docs/content/examples/tutorial.md) | cvc5's own Python examples, translated to Mojo |
| [Ownership and errors](docs/content/start/ownership.md) | Lifetimes, failures, and threads |
| [Examples](docs/content/examples/index.md) | Every example program, with its output |
| [API reference](docs/content/reference/index.md) | Every mirrored class and method, generated from the snapshot |
| [Architecture](docs/content/architecture/overview.md) | A short overview of the bindings and runtime |
| [Support and limitations](docs/content/guides/status.md) | What works today, and what does not |
| [Roadmap](docs/content/contributing/roadmap.md) | Milestones and open questions |

## Development

```sh
pixi run --locked generate                                 # regenerate; then git shows no diff
pixi run --locked test                                     # the gate and every test suite
pixi run --locked docs-test --output .cache/docs-001       # every documentation example
pixi run --locked -e docs docs-check                       # the site, in strict mode
```

See the [development guide](docs/content/contributing/development.md) for
the full set of checks, the repository layout, and the working rules.

## License

Apache License 2.0 with LLVM Exceptions; see [LICENSE](LICENSE). Built
packages include cvc5, which has its own licenses; see [NOTICE](NOTICE).
