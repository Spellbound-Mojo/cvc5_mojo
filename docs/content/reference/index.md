# API reference

This reference covers the base API of cvc5's Python bindings as cvc5 Mojo
mirrors it, for the pinned cvc5 release. Every page is generated from the
snapshot `api/cvc5-api.json`, the record of cvc5's API that the generator
works from:

- class and method descriptions are cvc5's own docstrings, converted from
  reStructuredText;
- each method shows the C API function that implements it.

## Classes

| Class | Page |
|---|---|
| `TermManager` | [TermManager](term-manager.md) |
| `Solver` | [Solver](solver.md) |
| `Term`, `Op` | [Term and Op](terms.md) |
| `Sort` | [Sort](sorts.md) |
| `Result`, `SynthResult` | [Results](results.md) |
| `DatatypeDecl`, `DatatypeConstructorDecl`, `Datatype`, `DatatypeConstructor`, `DatatypeSelector` | [Datatypes](datatypes.md) |
| `Grammar`, `Proof` | [Grammars and proofs](proofs.md) |
| `Statistics` | [Statistics](statistics.md) |
| `SymbolManager`, `InputParser`, `Command` | [Parser](parser.md) |
| `Plugin` | [Plugin](plugin.md) |
| `Kind`, `SortKind`, and the other enums | [Enums](enums.md) |

Import names from the package root, for example
`from cvc5_mojo import TermManager, Solver, Kind`.

## Reading an entry

- **Signature.** A generated method shows its Mojo signatures, one per
  overload, exactly as generated, followed by the labeled upstream Python
  signature. A method that is not generated shows the Python signature and
  explains why it is unavailable.
- **Description.** The text is cvc5's Python documentation, so it speaks of
  Python types. Read `int` as `Int`, `str` as `String`, a list as a `List`,
  and a returned tuple as a Mojo `Tuple`.
- **Mojo column.** The **Mojo** column of each summary table shows ✓ when the
  package has the method. A method without it says why it is not generated;
  the [coverage report](coverage.md#base-api) lists them all.
- **Binding line.** The **Binding** line names the C functions behind a
  method and how the generator found them. The statuses are explained in
  [mapping Python to C](../architecture/join.md#binding-statuses).
- **Not mirrored.** Methods that are not mirrored, because cvc5 deprecates
  them or they have no Mojo counterpart, are listed collapsed at the end of
  each class.

## Common contracts

- **Ownership and errors.** Every value owns one cvc5 reference, and a call
  that cvc5 rejects raises `Error("cvc5: …")`; see
  [ownership and errors](../start/ownership.md).
- **Enum arguments.** A method that takes a kind takes a `Kind` value, such
  as `Kind.ADD`.
- **Integers.** Integer parameters are `Int`, checked against the C type. A
  value that does not fit raises `Error("cvc5_mojo: … is out of range for
  uint32_t")`. `uint64_t` values are `UInt64`.
- **Numbers of any size.** Where Python returns or takes an `int` of any size
  or a `Fraction`, the bindings use apn_mojo's `Integer` and `Rational`:
  `getIntegerValue` returns an `Integer`, and `mkInteger` also takes one. See
  [big numbers](../start/installation.md#big-numbers-apn_mojo).
- **Lists.** Python lists are Mojo `List` values, such as `List[Term]`. A
  method that takes Python's `*args` also takes a `List`, because Mojo cannot
  pass a list as `*args`: `tm.mkTerm(Kind.AND, a, b)` and
  `tm.mkTerm(Kind.AND, terms)` both work.
- **Optional names.** Where Python's default is `None`, the parameter is
  `Optional`: `tm.mkConst(sort)` makes an unnamed constant.
- **Several results** come back as a `Tuple`, as in Python:
  `t.getCardinalityConstraint()[1]`.
- **Copies** are implicit, as Python shares objects. Copying a value of a
  handle class, such as `Term` or `Sort`, takes a cvc5 reference; moving it
  with `^` does not. See [ownership and errors](../start/ownership.md).

## Configure a solver

The [option catalog](options.md) combines defaults from the pinned binary
with descriptions from its source. Start with the
[configuration guide](../guides/solver-options.md) for models, incremental
queries, and resource limits. The [Python migration guide](../guides/python-migration.md)
compares complete programs in both languages.
