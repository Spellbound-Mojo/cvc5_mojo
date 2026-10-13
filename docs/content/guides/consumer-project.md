# Use the bindings in another project

Build a small application outside this checkout, import a precompiled
`cvc5_mojo` package, and point it at the pinned shared library. The example
keeps application constraints in a separate module and tests both a feasible
and an infeasible worker count.

Complete [installation](../start/installation.md) first. This workflow uses
the checkout’s pinned toolchain and native library; it is the current way
to consume the project before a published package is available. Keep the
checkout for these steps, since the external application refers to its
compiler environment and artifacts. That Pixi environment also supplies the
released apn_mojo package, so it needs no extra import path.

## Separate the application model from its test

Each worker can complete three tasks. For ten tasks, three workers cannot
suffice, while four can. The application's helper constructs that capacity
requirement without owning a solver:

<!-- source: docs/examples/consumer/capacity.mojo -->

The entry point imports the local helper and the binding package. It uses
a temporary scope to test the insufficient count, then checks the feasible
count against the same base requirements:

<!-- example: docs/examples/consumer/main.mojo -->

The displayed quick run works from the repository root. The steps below
copy these exact files into a new directory and build and run there.
The assertions belong to this application: compiling the dependency alone
would not test the worker-capacity model.

## Prepare a separate directory

Start at the binding repository root, using a Bash shell. Save its absolute
path, build the package, and copy the example's two files into a fresh
directory outside the checkout:

```sh
BINDINGS_DIR="$PWD"
pixi run --locked package
CONSUMER_DIR="$(mktemp -d /tmp/cvc5-mojo-consumer.XXXXXX)"
cp docs/examples/consumer/main.mojo "$CONSUMER_DIR/main.mojo"
cp docs/examples/consumer/capacity.mojo "$CONSUMER_DIR/capacity.mojo"
cd "$CONSUMER_DIR"
```

`main.mojo` imports its neighboring `capacity.mojo`. The bindings are a
separate dependency, supplied with an absolute import path. Keeping the
paths absolute prevents a change of working directory from accidentally
selecting a different package or library.

## Build against the precompiled package

Point Pixi at the existing manifest to use the same compiler environment,
then give Mojo the directory containing `cvc5_mojo.mojoc`:

```sh
pixi run --locked --manifest-path "$BINDINGS_DIR/pixi.toml" mojo build \
  --Werror -O3 -I "$BINDINGS_DIR/build" \
  "$CONSUMER_DIR/main.mojo" -o "$CONSUMER_DIR/capacity-test"
```

The absolute source and output paths make the command independent of the
working directory Pixi uses for execution. Rebuild the package after
changing its source or the pinned compiler. A precompiled Mojo package is
a compiler artifact, not a substitute for the cvc5 shared library.

For development against the binding sources, use the same command with
`-I "$BINDINGS_DIR/src"` in place of `-I "$BINDINGS_DIR/build"`. Use one
route at a time so the import target is clear.

## Select the runtime library and run your tests

Run the resulting executable from the consumer directory with an explicit
path to the pinned shared library:

```sh
case "$(uname -s)" in
  Darwin) CVC5_LIBRARY_FILE=libcvc5.dylib ;;
  *) CVC5_LIBRARY_FILE=libcvc5.so ;;
esac
CVC5_MOJO_LIBRARY="$BINDINGS_DIR/third_party/cvc5/lib/$CVC5_LIBRARY_FILE" \
  "$CONSUMER_DIR/capacity-test"
```

It prints:

```text
three workers: unsat
four workers: sat
```

The `-I` compiler argument chooses the Mojo module at build time.
`CVC5_MOJO_LIBRARY` selects the native library when the executable runs.
Setting one does not set the other. Preserve the downloaded release's
library directory and its dependencies rather than copying an arbitrary
solver library from another installation.

The repository-relative fallback under `third_party/cvc5/lib/` is resolved against the process's working directory. It is unavailable in this
new directory, which is why the explicit environment variable matters.
See [library discovery](../start/installation.md#where-the-library-is-found)
for the search order and [troubleshooting](troubleshooting.md) for loader
and linker failures.

## Keep this boundary in your own checks

The documentation runner copies the consumer files to a fresh temporary
directory outside the checkout, builds them with both source and package
imports at O0 and O3, and runs each executable there with the explicit
library setting. It asserts that the repository-relative library fallback
is absent. This catches accidental dependence on running from the binding
repository root.

For your application, keep a known feasible case and a known infeasible
case with the model code. Add cases for domain boundaries and any behavior
that changes when you add requirements. Use assertions on the mathematical
result rather than one arbitrary model ordering; several assignments may
be equally valid. [Organizing solver code](modeling.md) develops this
structure for larger applications.
