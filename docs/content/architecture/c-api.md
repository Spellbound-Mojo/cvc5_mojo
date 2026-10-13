# The cvc5 C API

This page lists the facts about cvc5's C API that the design depends on, and
how each one was established.

## Errors

**cvc5 1.4.1 records errors per thread.** A failing call returns a default
value (`NULL`, `false`, or `0`). The error is then visible through three
functions:

- `cvc5_has_error()` reports whether the last call on this thread failed;
- `cvc5_get_error_message()` returns the message;
- `cvc5_reset_error()` clears the state.

The state is reset at the start of each call that is not itself an error
query.

**cvc5 1.3.2 terminated the process instead.** This program builds the same
ill-sorted term on both releases:

```c
Cvc5Sort real = cvc5_get_real_sort(tm), boolean = cvc5_get_boolean_sort(tm);
Cvc5Term args[2] = {cvc5_mk_const(tm, real, "x"), cvc5_mk_const(tm, boolean, "b")};
Cvc5Term bad = cvc5_mk_term(tm, CVC5_KIND_ADD, 2, args);
printf("returned=%p has_error=%d msg=\"%s\"\n", (void*)bad, cvc5_has_error(), cvc5_get_error_message());
cvc5_reset_error();
printf("after reset has_error=%d\n", cvc5_has_error());
```

- On 1.3.2, the `cvc5_mk_term` call printed
  `cvc5: error: expecting an arithmetic subterm` and exited with status 1.
- On 1.4.1, it prints the following, and the process continues:

```text
returned=(nil) has_error=1 msg="expecting an arithmetic subterm"
after reset has_error=0
```

Bindings cannot turn a process exit into an exception. This makes 1.4.1 the
oldest supported release.

## Object lifetimes

The documentation of `cvc5_term_manager_delete` and `cvc5_delete` in
`cvc5.h` gives these rules, and the implementation confirms them:

- **Term-manager objects.** Objects created through a term manager (sorts,
  terms, operators, datatypes, and statistics) keep it alive. They stay valid
  until released, even after `cvc5_term_manager_delete`.
  `cvc5_term_manager_release` releases all of them at once.
- **Solver objects.** Results, synthesis results, proofs, and grammars are
  managed by the solver. Deleting the solver drops one reference to each,
  which frees those that nobody copied. A copied object outlives the solver.
  Proofs also keep the term manager alive.
- **Input parsers** keep their solver alive.
- **Returned data.** Strings and arrays are valid only until the next call.

Every object starts with one reference (`d_refs = 1`). For objects that a
solver makes, that reference belongs to the solver. This is the source of the
[ownership rule](runtime.md#handle-ownership).

## Releases and builds

**Use the libstdc++ build.** The binding uses
`cvc5-Linux-x86_64-shared.zip`, the libstdc++ build, which runs on stock
Linux. The libc++ builds need `libc++.so.1`, `libc++abi.so.1`, and
`libunwind.so.1`, which most systems lack.

**Contents of the zip.** The archive holds:

- `include/`, with the C headers in `include/cvc5/c/`;
- `lib/`, with `libcvc5`, `libcvc5parser`, GMP, MPFR, and LibPoly;
- the licenses.

Each shared library is stored as three full copies, not as symlinks:
`.so`, `.so.1`, and `.so.1.4.1`. For libcvc5, each copy is about 34 MB.

**RUNPATH.** `libcvc5.so` has RUNPATH `$ORIGIN/../lib`.

**Python package.** PyPI's `cvc5` is at the same version, 1.4.1. It provides
the oracle environment for
[differential tests](verification.md#test-layers).

## Size of the API

For cvc5 1.4.1:

| Part | Size |
|---|---|
| C API | 476 functions in 22 sections, including 19 declared in the enum headers |
| Python base API | 458 public methods in 19 classes |
| Enums | 14, with 1,158 values |

The [coverage report](../reference/coverage.md) has the current breakdown.
