# Installation and first run

## Supported environment

| Item | Requirement |
|---|---|
| Platform | Linux x86-64 (`linux-64`), Linux ARM64 (`linux-aarch64`), or macOS 15+ Apple Silicon (`osx-arm64`); see [platform validation](../architecture/packaging.md#platform-validation) |
| Compiler | Mojo 1.1.0, pinned through Pixi |
| Exact numbers | apn_mojo 1.0.1, installed by Pixi from the modular-community channel |
| Solver | cvc5 1.4.1, the matching official shared build, downloaded and checked against its sha256 |
| Tools | [Pixi](https://pixi.sh), which installs Mojo, Python, and a C compiler |

## Install the package

Version **1.4.1.0 is being prepared and is not published yet**. Until it is
available, use the [checkout instructions](#work-from-a-checkout).

After publication, create a consumer project with the release platforms and
all three channels, then install the bindings and the tested compiler:

```sh
pixi init solver-project --platform linux-64 --platform linux-aarch64 \
  --platform osx-arm64 -c https://conda.modular.com/max \
  -c https://repo.prefix.dev/modular-community -c conda-forge
cd solver-project
pixi add "mojo==1.1.0" "cvc5_mojo==1.4.1.0"
```

`linux-64` means Intel/AMD x86-64; `linux-aarch64` means 64-bit ARM on
Linux. `osx-arm64` means Apple Silicon Macs running macOS 15 or later,
following [Mojo’s macOS requirements](https://mojolang.org/docs/requirements/).
Intel Macs and 32-bit ARM are not included. Pixi selects the build for the
current machine. For a project targeting only one platform, include only
that platform.

The package includes cvc5's native solver and parser libraries and depends
on apn_mojo 1.0.1. Save the [first-query example](../tutorials/first-query.md)
as `main.mojo`, then run it from the consumer project:

```sh
pixi run --locked mojo run main.mojo
```

Installed-package imports need no `-I src` or `CVC5_MOJO_LIBRARY` override.
Pixi activates the environment used by the library loader. See the
[release notes](../releases.md) for the first release's scope and
[packaging](../architecture/packaging.md) for release preparation.

## Work from a checkout

After installing Pixi, clone the repository and set it up:

```sh
git clone https://github.com/Spellbound-Mojo/cvc5_mojo.git
cd cvc5_mojo
pixi install --locked
pixi run --locked generate   # downloads cvc5 1.4.1 into third_party/ and regenerates
```

Run the commands in this documentation from the repository root. `--locked`
keeps every dependency at the version in `pixi.lock`, as CI does.

`pixi run --locked generate` downloads the pinned cvc5 release and its
source archive and checks both against the sha256 values in
`cvc5-version.toml`. It then regenerates every generated file. These cvc5
downloads go to `third_party/`, which Git ignores. Pixi installs
[apn_mojo](#big-numbers-apn_mojo) as a precompiled package in the environment.

## Import from source

To run a program against the sources, pass `-I src` for the bindings.
Mojo finds the installed apn_mojo package through the Pixi environment:

```sh
pixi run --locked mojo run -I src docs/examples/quickstart.mojo
```

Follow [your first solver query](../tutorials/first-query.md) for an explanation
of the program, then continue through the [learning path](../tutorials/index.md).
For an application outside this checkout, use the
[external consumer guide](../guides/consumer-project.md).

## Import a precompiled package

You can also precompile the bindings once and import the result:

```sh
pixi run --locked package   # writes build/cvc5_mojo.mojoc
pixi run --locked mojo run -I build docs/examples/quickstart.mojo
```

## Big numbers: apn_mojo

Python's cvc5 returns and accepts an `int` of any size and a `Fraction`. In
Mojo, these are `Integer` and `Rational` from apn_mojo, an arbitrary-precision
number library for Mojo. For example, `term.getIntegerValue() == 2**70`
compares exactly. Import the types with `from apn_mojo import Integer,
Rational`.

[apn_mojo 1.0.1](https://prefix.dev/channels/modular-community/packages/apn_mojo)
is available from `https://repo.prefix.dev/modular-community`. The project's
`pixi.toml` includes that channel and pins the package version.
`pixi install --locked` installs the build recorded in `pixi.lock`, including its archive
checksum. The published package supports Mojo 1.1.x; this project continues
to pin Mojo 1.1.0.

After updating an existing checkout, run `pixi install --locked` again.
Remove `-I third_party/apn_mojo` from any local build commands so an old
preview artifact cannot override the installed package. The old source
archive pin and `APN_MOJO_TOKEN` are no longer used. See the
[APN Mojo documentation](https://spellbound-mojo.github.io/apn_mojo/) for
the number types themselves.

## Where the library is found

The bindings load `libcvc5.so` and `libcvc5parser.so` on Linux, or
`libcvc5.dylib` and `libcvc5parser.dylib` on macOS. They select the main
library in this order and require the matching parser beside it:

1. `$CVC5_MOJO_LIBRARY`, the full path of the main library, including its
   platform suffix. The parser is taken from the same directory.
2. `$CONDA_PREFIX/lib/cvc5_mojo/lib/`, where the conda package installs them.
3. `third_party/cvc5/lib/`, relative to the working directory, where a
   checkout keeps them.

A program using checkout libraries outside the repository root needs
`CVC5_MOJO_LIBRARY`; an installed conda package uses the active environment
instead. The libraries are loaded once per process, when the
first `TermManager` is created, so set the variable before then. See
[troubleshooting](../guides/troubleshooting.md) if a library is not found.
Initialization rejects a reported cvc5 version that differs from the pin.

## Documentation site

```sh
pixi run --locked -e docs docs-serve
```

This serves the site locally and reloads it when a page changes. See
[maintaining the docs](../contributing/documentation.md).
