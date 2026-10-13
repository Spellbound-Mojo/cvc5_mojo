"""Exact numeric exchange, including fallback and original error semantics."""
from std.testing import assert_equal, assert_true
from apn_mojo import Integer, Rational
from cvc5_mojo import Kind, Solver, Term, TermManager
from cvc5_mojo._c.ffi import to_string, trace


def check_integer[text: StaticString](tm: TermManager) raises:
    var value = Integer(String(text))
    trace("numeric:integer")
    trace(text)
    trace("numeric:new")
    var term = tm.mkInteger(value)
    trace("numeric:get")
    var result = term.getIntegerValue()
    trace("numeric:end")
    assert_equal(result, value)
    assert_equal(term, tm.mkInteger(String(text)))
    # Integral real terms obey the same integer getter contract.
    assert_equal(tm.mkReal(String(text)).getIntegerValue(), value)
    assert_equal(term.getRealValue(), Rational(value))


def check_real[num: StaticString, den: StaticString](tm: TermManager) raises:
    var numerator = Integer(String(num))
    var denominator = Integer(String(den))
    var value = Rational(numerator, denominator)
    trace("numeric:real")
    trace(num)
    trace(den)
    trace("numeric:pair")
    var paired = tm.mkReal(numerator, denominator)
    trace("numeric:rational")
    var term = tm.mkReal(value)
    trace("numeric:get")
    var result = term.getRealValue()
    trace("numeric:end")
    assert_equal(result, value)
    assert_equal(term, paired)
    assert_equal(term, tm.mkReal(String(num, "/", den)))
    assert_true(term.getSort().isReal())


def check_bv[width: Int, text: StaticString](tm: TermManager) raises:
    var value = Integer(String(text))
    trace("numeric:bv")
    # The value identifies each case; width comes from the fixture inventory.
    trace(text)
    trace("numeric:new")
    var term = tm.mkBitVector(Int(width), value)
    trace("numeric:end")
    assert_equal(term, tm.mkBitVector(Int(width), String(text), 10))
    assert_equal(term.getSort().getBitVectorSize(), width)


def errors(tm: TermManager) raises:
    # Preserve the exact text-path diagnostic for invalid widths/values.
    var widths: List[Int] = [-1, 0, 1, 8, 4294967296]
    var values: List[String] = ["0", "-1", "256", "18446744073709551616"]
    for width in widths:
        for text in values:
            var old_error = String()
            var new_error = String()
            try:
                _ = tm.mkBitVector(width, text, 10)
            except e:
                old_error = String(e)
            try:
                _ = tm.mkBitVector(width, Integer(text))
            except e:
                new_error = String(e)
            assert_equal(new_error, old_error)
    var denominators: List[String] = ["0", "-1", "-9223372036854775808", "-9223372036854775809"]
    for den in denominators:
        var old_error = String()
        var new_error = String()
        try:
            _ = tm.mkReal("3/" + den)
        except e:
            old_error = String(e)
        try:
            _ = tm.mkReal(Integer(3), Integer(den))
        except e:
            new_error = String(e)
        assert_equal(new_error, old_error)
    var terms: List[Term] = [Term(), tm.mkTrue(), tm.mkConst(tm.getIntegerSort(), "x"), tm.mkReal("3/7"), tm.mkPi()]
    var getters: List[Bool] = [False, True]
    for term in terms:
        for real in getters:
            var old_error = String()
            var new_error = String()
            try:
                if real:
                    _ = Rational(to_string(term._api[].cvc5_term_get_real_value(term._h)))
                else:
                    _ = Integer(to_string(term._api[].cvc5_term_get_integer_value(term._h)))
            except e:
                old_error = String(e)
            try:
                if real:
                    _ = term.getRealValue()
                else:
                    _ = term.getIntegerValue()
            except e:
                new_error = String(e)
            assert_equal(new_error, old_error)
    assert_equal(tm.mkInteger(Integer(42)).getIntegerValue(), Integer(42))


def detached_values() raises -> Tuple[Integer, Rational]:
    var tm = TermManager()
    var solver = Solver(tm)
    var borrowed = solver.getTermManager()
    var integer = borrowed.mkInteger(Integer("18446744073709551615"))
    var real = borrowed.mkReal(Rational(Integer(3), Integer(7)))
    return (integer.getIntegerValue(), real.getRealValue())


def check_real_literal[text: StaticString](tm: TermManager, value: IntLiteral) raises:
    assert_equal(tm.mkReal(value), tm.mkReal(String(text)))


def main() raises:
    var tm = TermManager()
    check_integer["0"](tm)
    check_integer["1"](tm)
    check_integer["-1"](tm)
    check_integer["42"](tm)
    check_integer["-42"](tm)
    check_integer["2147483648"](tm)
    check_integer["4294967296"](tm)
    check_integer["-9223372036854775808"](tm)
    check_integer["9223372036854775807"](tm)
    check_integer["-9223372036854775809"](tm)
    check_integer["9223372036854775808"](tm)
    check_integer["18446744073709551615"](tm)
    check_integer["18446744073709551616"](tm)
    check_integer["-1180591620717411303424"](tm)
    check_integer["115792089237316195423570985008687907853269984665640564039457584007913129639935"](tm)
    check_real["0", "7"](tm)
    check_real["3", "7"](tm)
    check_real["-3", "7"](tm)
    check_real["6", "14"](tm)
    check_real["-9223372036854775808", "1"](tm)
    check_real["9223372036854775807", "2"](tm)
    check_real["1", "9223372036854775807"](tm)
    check_real["1", "9223372036854775808"](tm)
    check_real["1", "18446744073709551615"](tm)
    check_real["1", "18446744073709551616"](tm)
    check_real["-9223372036854775809", "7"](tm)
    check_real["9223372036854775808", "7"](tm)
    check_real["18446744073709551616", "36893488147419103232"](tm)
    check_real["115792089237316195423570985008687907853269984665640564039457584007913129639935", "7"](tm)
    check_bv[1, "0"](tm)
    check_bv[1, "1"](tm)
    check_bv[8, "255"](tm)
    check_bv[8, "-1"](tm)
    check_bv[64, "9223372036854775808"](tm)
    check_bv[64, "18446744073709551615"](tm)
    check_bv[65, "18446744073709551616"](tm)
    check_bv[256, "115792089237316195423570985008687907853269984665640564039457584007913129639935"](tm)
    trace("numeric:done")
    errors(tm)
    check_real_literal["-9223372036854775808"](tm, -9223372036854775808)
    check_real_literal["9223372036854775807"](tm, 9223372036854775807)
    check_real_literal["-9223372036854775809"](tm, -9223372036854775809)
    check_real_literal["9223372036854775808"](tm, 9223372036854775808)
    var integer, real = detached_values()
    assert_equal(integer, Integer("18446744073709551615"))
    assert_equal(real, Rational(Integer(3), Integer(7)))
    assert_equal(tm.mkReal(0.3).getRealValue(), Rational(Integer(3), Integer(10)))
    assert_equal(tm.mkReal(42).getRealValue(), Rational(42))
    assert_equal(tm.mkReal(18446744073709551616).getRealValue(), Rational("18446744073709551616"))
    assert_equal(tm.mkBitVector(8), tm.mkBitVector(8, 0))
    print("numeric conversions passed")
