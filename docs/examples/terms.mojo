"""Inspect a symbolic expression before asking a solver about it."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Kind


def main() raises:
    var tm = TermManager()
    var integers = tm.getIntegerSort()
    var x = tm.mkConst(integers, "x")
    var twice_x = tm.mkTerm(Kind.ADD, x, x)
    var equation = tm.mkTerm(Kind.EQUAL, twice_x, tm.mkInteger(6))
    assert_true(twice_x.getKind() == Kind.ADD)
    assert_true(twice_x.getSort() == integers)
    assert_true(equation.getSort() == tm.getBooleanSort())
    print("expression:", twice_x)
    print("sort:", twice_x.getSort())
    print("constraint:", equation)
