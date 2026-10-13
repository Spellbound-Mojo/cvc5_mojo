"""Hand-written overloads of `TermManager` methods: Python's other argument forms.

`bindgen.gen_api` adds the methods of `struct TermManager` below to the
generated ones, with cvc5's docstrings. This file is not compiled on its own.

Python passes an `int` of any size, or a `Fraction`, to cvc5 as decimal text
(`str(x)`). These overloads use direct native values when exactly representable
and otherwise use the generated `String` overloads. Python's `mkReal` formats
a numerator and a denominator alike, so each may be an integer or a string;
a `float` is its shortest text (`0.3` is 3/10), which Mojo's `Float64` writes too.

Mojo converts an integer literal that does not fit an `Int` without a
diagnostic (`2**70` becomes 0), so a method with an `Int` overload also
takes an `IntLiteral`, kept exact. `overrides.toml` gives the unsafe narrowing
overloads private helper names: `mkReal(Int, Int)` and
`mkBitVector(Int, UInt64)` are not public overloads.

Python's `mkFunctionSort` also takes a single domain sort, and its
`mkRecordSort` takes the fields as `(name, sort)` pairs, where the C API
takes two arrays.
"""

from ._c.ffi import escape_smt_string, fits_int_literal, fits_native_integer

struct TermManager:
    def mkString(self, s: String, useEscSequences: Optional[Bool] = None) raises -> Term:
        var text = s if useEscSequences else escape_smt_string(s)
        var text_c = c_bytes(text)
        var escaped = useEscSequences.value() if useEscSequences else True
        var api = self._o[].api
        return Term._received(api, self._o[].tm, api[].cvc5_mk_string(self._handle(), text_c.unsafe_ptr(), escaped))

    def mkInteger(self, val: Integer) raises -> Term:
        if fits_native_integer[DType.int64](val):
            return self.mkInteger(Int(val))
        return self.mkInteger(String(val))

    def mkInteger(self, val: IntLiteral) raises -> Term:
        # Test the exact literal before any narrowing, then reuse the typed path.
        if fits_int_literal(val):
            return self.mkInteger(Int(val))
        return self.mkInteger(Integer(val))

    def mkReal(self, numerator: Rational) raises -> Term:
        return self.mkReal(numerator.numerator(), numerator.denominator())

    def mkReal(self, numerator: IntLiteral) raises -> Term:
        if fits_int_literal(numerator):
            return self.mkReal(Int(numerator))
        return self.mkReal(Rational(numerator))

    def mkReal(self, numerator: Float64) raises -> Term:
        return self.mkReal(String(numerator))  # the shortest text, as Python's `str`

    def mkReal(self, numerator: FloatLiteral) raises -> Term:
        return self.mkReal(Float64(numerator))

    def mkReal(self, numerator: Integer, denominator: Integer) raises -> Term:
        # Keep invalid/nonpositive denominators on the original error path.
        if denominator > 0 and fits_native_integer[DType.int64](numerator) and fits_native_integer[DType.int64](denominator):
            return self._native_mkReal64(Int(numerator), Int(denominator))
        return self.mkReal(String(numerator, "/", denominator))

    def mkReal(self, numerator: String, denominator: String) raises -> Term:
        return self.mkReal(String(numerator, "/", denominator))

    def mkReal(self, numerator: Integer, denominator: String) raises -> Term:
        return self.mkReal(String(numerator, "/", denominator))

    def mkReal(self, numerator: String, denominator: Integer) raises -> Term:
        return self.mkReal(String(numerator, "/", denominator))

    def mkFiniteFieldSort(self, size: Integer) raises -> Sort:
        return self.mkFiniteFieldSort(String(size))

    def mkFiniteFieldElem(self, value: Integer, sort: Sort) raises -> Term:
        return self.mkFiniteFieldElem(String(value), sort)

    def mkBitVector(self, size: Int, val: Integer) raises -> Term:
        # Invalid widths/overflow retain the string constructor's diagnostics.
        if size > 0 and size <= 4294967295 and fits_native_integer[DType.uint64](val) and val.magnitude_bit_length() <= size:
            return self._native_mkBitVector64(size, val.to_native_exact[DType.uint64]())
        return self.mkBitVector(size, String(val), 10)

    def mkBitVector(self, size: Int) raises -> Term:
        return self.mkBitVector(size, Integer(0))

    def mkBitVector(self, size: IntLiteral, val: Integer) raises -> Term:
        return self.mkBitVector(checked_int_literal(size), val)

    def mkBitVector(self, size: IntLiteral) raises -> Term:
        return self.mkBitVector(checked_int_literal(size))

    def mkFunctionSort(self, sorts: Sort, codomain: Sort) raises -> Sort:
        return self.mkFunctionSort([sorts], codomain)

    def mkRecordSort(self, *fields: Tuple[String, Sort]) raises -> Sort:
        var names = List[String](capacity=len(fields))
        var sorts = List[Sort](capacity=len(fields))
        for field in fields:
            names.append(field[0])
            sorts.append(field[1])
        return self.mkRecordSort(names, sorts)
