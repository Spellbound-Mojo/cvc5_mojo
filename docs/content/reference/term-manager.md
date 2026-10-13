# TermManager

The term manager creates sorts, terms, operators, and datatype
declarations. The objects it creates keep it alive, and several solvers can
share one term manager.

Integer literals stay exact. `mkInteger(42)` automatically uses the direct
64-bit constructor when the literal fits; larger literals retain arbitrary
precision. See [literal construction](../architecture/integer-literals.md).

Fitting APN `Integer` and `Rational` inputs and nonnegative bit-vector values
also use native numeric constructors, with exact text fallbacks for wider
values. See [direct numeric conversions](../architecture/numeric-conversions.md).

The cached C API rejects `mkParamSort()` and `mkParamSort(None)`, although
Python accepts them. Pass an explicit symbol when creating parameter sorts.
An empty string is an empty symbol, not an anonymous sort; see the
[native limitation](../architecture/compound-ffi.md#anonymous-parameter-sorts).

<!-- api: TermManager -->
