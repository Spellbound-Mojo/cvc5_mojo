"""Construct transcendental expressions and exact real constants."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Kind


def main() raises:
    var tm = TermManager()
    var real = tm.getRealSort()
    var x = tm.mkConst(real, "x")
    var exponential = tm.mkTerm(Kind.EXPONENTIAL, x)
    var sine = tm.mkTerm(Kind.SINE, x)
    var cosine = tm.mkTerm(Kind.COSINE, x)
    var tangent = tm.mkTerm(Kind.TANGENT, x)
    var inverse_sine = tm.mkTerm(Kind.ARCSINE, x)
    var pi = tm.mkTerm(Kind.PI)
    var one = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(1))
    var two = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(2))
    var half = tm.mkTerm(Kind.DIVISION, one, two)
    assert_true(exponential.getSort() == real)
    assert_true(sine.getSort() == real)
    assert_true(cosine.getSort() == real)
    assert_true(tangent.getSort() == real)
    assert_true(inverse_sine.getSort() == real)
    assert_true(pi.getKind() == Kind.PI)
    assert_true(half.getSort() == real)
    print("exponential:", exponential)
    print("sine:", sine)
    print("cosine:", cosine)
    print("tangent:", tangent)
    print("inverse sine:", inverse_sine)
    print("pi:", pi)
    print("exact half:", half)
