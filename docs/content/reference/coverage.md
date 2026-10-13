# Coverage report

This page shows how completely the bindings cover the pinned cvc5 release.
It is rendered from the snapshot `api/cvc5-api.json` when the site is built.
The binding statuses are explained in
[mapping Python to C](../architecture/join.md#binding-statuses).

<!-- coverage: report -->

## cvc5's unit tests

`bindgen.translate` translates cvc5's Python unit tests and examples to Mojo,
into `tests/cvc5/`, and `pixi run --locked cvc5-tests` runs them. This
section is rendered from `tests/cvc5/translation.json`. See
[verification](../architecture/verification.md#test-layers).

<!-- coverage: tests -->

## C functions the tests reach

This section shows which C functions cvc5's translated unit tests and
examples call. `pixi run --locked cvc5-tests` builds every program with
`-D CVC5_MOJO_TRACE=<file>`, which makes the raw layer write the name of each
C function that it calls. The run saves the result in `tests/cvc5/calls.json`.
Without the define, the recording compiles away.

<!-- coverage: calls -->
