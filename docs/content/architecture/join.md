# Mapping Python to C

The bindings use the names of cvc5's Python API but call cvc5's C API. Every
Python method must therefore be mapped to the C function, or functions, that
implement it. This page calls that mapping the *join*.

## Why not match names

The two APIs name the same operation differently, and no renaming rule holds
for all of them:

| Python | C |
|---|---|
| `mkBitVectorSort` | `cvc5_mk_bv_sort` |
| `getFloatingPointExponentSize` | `cvc5_sort_fp_get_exp_size` |
| `getUninterpretedSortConstructorArity` | `cvc5_sort_get_uninterpreted_sort_constructor_arity` |

Matching by name would need a table kept by hand, and that table would need
checking again at every release.

## The join through C++

Both APIs are thin wrappers over the same C++ API. Here the C function and
the Python method both call the C++ method `mkBitVectorSort`:

```text
src/api/c/cvc5.cpp
  Cvc5Sort cvc5_mk_bv_sort(Cvc5TermManager* tm, uint32_t size)
    ... tm->export_sort(tm->d_tm.mkBitVectorSort(size)) ...

src/api/python/cvc5.pxi, class TermManager
  def mkBitVectorSort(self, uint32_t size):
      return _sort(self, self.ctm.mkBitVectorSort(size))
```

`bindgen.snapshot` joins a Python method to the C functions that call the
same C++ method. It looks only in the C API section of the method's class:

- `TermManager` ↔ `Cvc5TermManager`;
- `Term` ↔ `Cvc5Term`;
- and so on, as listed under `[classes]` in `bindgen/overrides.toml`.

Several C functions can share a C++ call. Then the join keeps those whose
set of C++ calls equals the Python method's set. For example, this drops
`cvc5_term_get_symbol` from `Term.hasSymbol`: `get_symbol` checks
`hasSymbol` before returning, so its set of calls is larger.

## Binding statuses

A method's *binding status* says how the method is bound. Each Python method
gets exactly one status. The statuses are tried in this order:

| Status | Meaning |
|---|---|
| `override` | The C functions are named explicitly in `overrides.toml` |
| `manual` | Hand-written Mojo in a fragment, `bindgen/manual/<Class>.mojo`. `overrides.toml` names the C functions it uses |
| `skip` | Not mirrored. `overrides.toml` gives the reason |
| `deprecated` | Deprecated in cvc5, and not mirrored |
| `auto` | The join found exactly one C function |
| `overloaded` | The join found several. Each becomes a Mojo overload |
| `rule` | A generic rule, such as `__eq__` → `{prefix}is_equal`, or `isNull` → `{prefix}is_null` or a NULL-handle check |
| `alias` | Delegates to another class, such as `Solver.mkSkolem` → `TermManager.mkSkolem` |
| `unresolved` | None of the above applies. The gate fails |

For cvc5 1.4.1, the join alone (statuses `auto` and `overloaded`) resolves
93.1% of the methods that are neither deprecated nor dunder methods such as
`__eq__`. No method is unresolved. The
[coverage report](../reference/coverage.md) gives the current figures per
class.

## The completeness gate

The completeness gate, `pixi run --locked check-api`, fails when any of these
holds:

- a method is unresolved (the gate prints each one);
- an `overrides.toml` entry is stale: it names a Python method or C function
  that no longer exists;
- the fraction of methods that the join resolves on its own is below
  `policy.min_auto_fraction`, which is 0.75.

Without the last condition, a large drop in that fraction would go
unreported. A drop of that size means that cvc5 changed how its wrappers are
written, and the extractors need attention.

## The exceptions file

`bindgen/overrides.toml`, the exceptions file, is the only hand-maintained
input. The tables that control the join and the gate are:

- **`[policy]`** sets whether deprecated methods are skipped, and the minimum
  automatic fraction.
- **`[classes]`** maps each Python class to its C section and function
  prefix.
- **`[[rules]]`** holds the generic rules.
- **`[methods."Class.method"]`** entries each give one of `c = [...]`,
  `manual = [...]`, `alias = "..."`, or `skip = "reason"`, with an optional
  `note`. An entry with `c = ["cvc5_mk_term"]` can add `kind = "NOT"`: the
  method then builds a term of that kind from the receiver and the method's
  arguments. The gate checks that the kind exists.

The [coverage report](../reference/coverage.md#redundant-overrides) lists
the entries that the extracted data now resolves on its own. Delete them.

Two more tables do not affect the join. `[tests]` and `[examples]` list the
cvc5 tests and examples that are translated but cannot pass in Mojo; see
[leaving out a translated test](../contributing/generator.md#leaving-out-a-translated-test).
