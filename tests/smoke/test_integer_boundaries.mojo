"""Integer literals must be range-checked before conversion to native Int."""

from std.testing import assert_equal, assert_true
from apn_mojo import Integer
from cvc5_mojo import Kind, Solver, TermManager
from cvc5_mojo._c.ffi import trace


def check_literal[expected: StaticString](tm: TermManager, value: IntLiteral) raises:
    trace("integer_literal:begin")
    trace(expected)
    var term = tm.mkInteger(value)
    trace("integer_literal:end")
    var text = String(expected)
    assert_true(term.isIntegerValue())
    assert_equal(term.getIntegerValue(), Integer(text))
    assert_equal(term, tm.mkInteger(text))
    var copied = term
    _ = term^
    assert_equal(copied.getIntegerValue(), Integer(text))


def literal_values(tm: TermManager) raises:
    check_literal["0"](tm, 0)
    check_literal["1"](tm, 1)
    check_literal["-1"](tm, -1)
    check_literal["42"](tm, 42)
    check_literal["-42"](tm, -42)
    check_literal["2147483648"](tm, 2**31)
    check_literal["4294967296"](tm, 2**32)
    check_literal["-9223372036854775807"](tm, -9223372036854775807)
    check_literal["-9223372036854775808"](tm, -9223372036854775808)
    check_literal["9223372036854775806"](tm, 9223372036854775806)
    check_literal["9223372036854775807"](tm, 9223372036854775807)
    check_literal["-9223372036854775809"](tm, -9223372036854775809)
    check_literal["9223372036854775808"](tm, 9223372036854775808)
    check_literal["18446744073709551615"](tm, 2**64 - 1)
    check_literal["18446744073709551616"](tm, 2**64)
    check_literal["18446744073709551624"](tm, 18446744073709551624)
    check_literal["-1180591620717411303424"](tm, -(2**70))
    check_literal["115792089237316195423570985008687907853269984665640564039457584007913129639935"](tm, 2**256 - 1)
    trace("integer_literal:done")

    # Construction through a borrowed manager keeps the same value semantics.
    var solver = Solver(tm)
    var borrowed = solver.getTermManager()
    assert_equal(borrowed.mkInteger(-9223372036854775808), tm.mkInteger("-9223372036854775808"))
    assert_equal(borrowed.mkInteger(9223372036854775808), tm.mkInteger("9223372036854775808"))
    # The explicitly arbitrary-precision overload remains exact too.
    assert_equal(tm.mkInteger(Integer("42")), tm.mkInteger(Int(42)))
    var caught = False
    try:
        _ = tm.mkInteger("not-an-integer")
    except e:
        caught = String(e).startswith("cvc5: ")
    assert_true(caught)
    assert_equal(tm.mkInteger(42).getIntegerValue(), Integer("42"))


def main() raises:
    var tm = TermManager()
    literal_values(tm)
    var caught = 0
    try:
        _ = tm.mkBitVectorSort(18446744073709551624)
    except e:
        assert_true("out of range" in String(e))
        caught += 1
    try:
        _ = tm.mkBitVector(18446744073709551624, 1)
    except e:
        assert_true("out of range" in String(e))
        caught += 1
    try:
        _ = tm.mkBitVector(18446744073709551624)
    except e:
        assert_true("out of range" in String(e))
        caught += 1
    var n = Int(8)
    try:
        _ = tm.mkFloatingPointSort(18446744073709551624, n)
    except e:
        assert_true("out of range" in String(e))
        caught += 1
    try:
        _ = tm.mkFloatingPointSort(n, 18446744073709551624)
    except e:
        assert_true("out of range" in String(e))
        caught += 1
    try:
        _ = tm.mkOp(Kind.BITVECTOR_EXTRACT, n, 18446744073709551624)
    except e:
        assert_true("out of range" in String(e))
        caught += 1
    try:
        _ = tm.mkBitVectorSort(-18446744073709551608)
    except e:
        assert_true("out of range" in String(e))
        caught += 1
    try:
        _ = tm.mkBitVectorSort(4294967296)
    except e:
        assert_true("out of range" in String(e))
        caught += 1
    assert_equal(caught, 8)
    assert_equal(String(tm.mkBitVectorSort(8)), "(_ BitVec 8)")
    assert_equal(String(tm.mkBitVector(n, 1)), "#b00000001")
    assert_equal(String(tm.mkOp(Kind.BITVECTOR_EXTRACT, n, 0)), "(_ extract 8 0)")
    # Numeric *values* still use the exact arbitrary-precision overloads.
    assert_equal(String(tm.mkInteger(18446744073709551624)), "18446744073709551624")
    print("integer boundary test passed")
