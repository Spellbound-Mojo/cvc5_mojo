# 5. Real arithmetic

The equation `2*x = 1` has the real solution one half and has no integer
solution. Choosing a sort changes the mathematical question, even when the
printed equation looks the same.

Prerequisite: [integer constraints](integers.md).

<!-- example: docs/examples/reals.mojo -->

The first solver operates on a real symbol. Its answer prints as `(/ 1 2)`,
an exact rational value. The second solver operates on an integer symbol
and reports `unsat`. Each solver has its own assertions, even though both
use terms made by the same term manager.

## Exact reals and machine floats

A symbolic real variable is not a Mojo `Float64`. These real-arithmetic
constraints do not introduce floating-point rounding or overflow.
Consequently, a proof about them does not automatically prove the same
property for an implementation that uses machine floats.

Use exact input values when the specification is exact. `mkReal` accepts
exact strings and apn_mojo's `Rational`. You can also construct a rational
expression by converting integer terms with `Kind.TO_REAL` and combining
them with `Kind.DIVISION`. The
[transcendental expressions example](transcendentals/expressions.md)
demonstrates this explicit term construction; the
[Python migration example](../guides/python-migration.md) uses `mkReal`.

The multiplication in the example accepts an integer coefficient alongside
the real symbol. Equality needs matching operand sorts, so the program
explicitly converts its right-hand side to a real term. Construct real
numerals consistently when building a larger real-arithmetic model; do not
assume that every operation will insert conversions. Real division and
integer division also model different operations.

## Choose a logic

The examples use these logic selections:

| Selection | Example problem |
|---|---|
| `QF_LIA` | Linear constraints on integer ticket counts |
| `QF_LRA` | A real variable multiplied by a fixed coefficient |
| `QF_NRA` | Products of symbolic real variables, such as `x*x` |
| `QF_NRAT` | Real arithmetic with transcendental functions |

`QF` means quantifier-free. Creating free symbols and asking for an
assignment does not require adding an explicit existential quantifier.
The logic declaration describes the allowed mathematical language; it is
not a request to approximate expressions that fall outside that language.

For transcendentals, the extra `T` follows the
[pinned upstream example](https://github.com/cvc5/cvc5/blob/cvc5-1.4.1/examples/api/python/transcendentals.py).

## Exercise: change the domain again

What happens for `2*x = 2`?

**Worked answer.** Both domains admit `x = 1`. That one successful instance
does not make the domains equivalent: `2*x = 1` distinguishes them. Choose
the domain from the application's meaning, not from whether a particular
test happens to pass.

Next: [results and models](models.md).
