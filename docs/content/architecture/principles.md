# Design principles

These rules decide what is generated and what is written by hand. Every
change must keep them.

## Bindings are build output

The generator, `bindgen`, writes the Mojo bindings from the cvc5 release
pinned in `cvc5-version.toml`. No generated file is edited by hand. When
generated code is wrong, the fix goes into the generator, and
`pixi run --locked generate` writes the code again. CI regenerates every
generated file and fails when the result differs from the committed file.
The [repository layout](../contributing/development.md#repository-layout) lists which
files are generated.

## Extracted, not typed

A fact about cvc5 is never written by hand when it can be extracted from the
release. This covers names, signatures, enum values, docstrings,
deprecations, which C function implements each Python method, and how each
handle is owned. The extracted facts are stored in the *snapshot*,
`api/cvc5-api.json` ([the snapshot](inputs.md#the-snapshot)).

A fact typed by hand goes stale without notice when a new release changes
it. An extracted fact changes with the release.

## Verified by machine

Each kind of extracted fact is checked by a mechanism other than the
extractor that produced it:

| Fact | Check |
|---|---|
| C signatures | The C compiler, against the release's headers |
| How each C type crosses into Mojo | Static assertions compiled against the headers, and the [raw-layer](layers.md#raw-layer) test |
| Which library exports a function | The dynamic linker |
| Enum values | A compiled C program prints them |
| Python-to-C mapping | The [completeness gate](join.md#the-completeness-gate) |
| Handle ownership | The lifetime and leak tests |
| Behavior | cvc5's Python unit tests, translated to Mojo, and its Python examples, which must print in Mojo what they print under the official Python bindings ([verification](verification.md#test-layers)) |

## Complete by construction

The generator gives every public Python method exactly one
[binding status](join.md#binding-statuses). The status records how the
method maps to the C API, or why it is not mirrored. A method that fits no
other status is `unresolved`, and the completeness gate fails while any
method is. A method therefore cannot drop out of the mapping unnoticed, and
a method that a new cvc5 release adds is either bound automatically or
reported by the gate. Whether a mapped method's Mojo code is generated yet
is listed separately, in the
[coverage report](../reference/coverage.md#base-api).

## A small, listed hand-written surface

Hand-written code is limited to:

- `bindgen/overrides.toml`, the exceptions file
  ([the exceptions file](join.md#the-exceptions-file));
- the [marshaling rules](layers.md#marshaling-rules) inside the generator;
- the runtime support module `src/cvc5_mojo/_c/ffi.mojo`;
- methods with status `manual`, written in Mojo in *fragments*,
  `bindgen/manual/<Class>.mojo`. The generator adds cvc5's docstrings to
  them and checks that `overrides.toml` lists the C functions they call.

Each of these can be reviewed in one place. Entries of the exceptions file
that are no longer needed are reported:

- The [coverage report](../reference/coverage.md#redundant-overrides) lists
  method entries that the extracted data now resolves on its own, so they
  can be deleted.
- The `[tests]` and `[examples]` tables list cvc5 tests and examples that
  cannot pass in Mojo, each with its reason. `pixi run --locked cvc5-tests`
  still builds and runs each listed one and fails once one of them passes,
  so its entry must then be removed.

## Python names, Mojo values

The Mojo API mirrors the base API of cvc5's Python bindings. Classes,
methods, and enums keep their Python names, so cvc5's Python documentation
and examples apply almost unchanged. Values follow Mojo's rules: ownership
is explicit, overloads are resolved at compile time, and failures raise
`Error`.

## Scope

In scope:

- the Python base API, without the deprecated methods;
- plugin callbacks, through Mojo trait implementations;
- oracle functions, through the `Oracle` trait and `Solver.declareOracleFun`;
- every C API function, in the raw layer;
- a modular-community package with libcvc5 bundled
  ([packaging](packaging.md)).

Planned, and out of scope until then (see the
[roadmap](../contributing/roadmap.md)):

- platforms other than Linux x86-64.

Out of scope:

- the z3-style "pythonic" layer.

## Pins

`cvc5-version.toml` pins the cvc5 release: its version, the commit of its
tag, and the sha256 of both archives. It changes only through
`pixi run --locked bump` and a reviewed pull request. `pixi.toml` pins Mojo,
and that pin changes through a reviewed edit of `pixi.toml`.
