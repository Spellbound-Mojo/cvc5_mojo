"""Recover ticket counts from a head count and a total price."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("produce-models", "true")
    var adult = tm.mkConst(tm.getIntegerSort(), "adult")
    var child = tm.mkConst(tm.getIntegerSort(), "child")
    var zero = tm.mkInteger(0)
    solver.assertFormula(tm.mkTerm(Kind.GEQ, adult, zero))
    solver.assertFormula(tm.mkTerm(Kind.GEQ, child, zero))
    solver.assertFormula(tm.mkTerm(Kind.EQUAL,
        tm.mkTerm(Kind.ADD, adult, child), tm.mkInteger(7)))
    var price = tm.mkTerm(Kind.ADD,
        tm.mkTerm(Kind.MULT, tm.mkInteger(8), adult),
        tm.mkTerm(Kind.MULT, tm.mkInteger(5), child))
    solver.assertFormula(tm.mkTerm(Kind.EQUAL, price, tm.mkInteger(47)))
    var result = solver.checkSat()
    assert_true(result.isSat())
    var a = solver.getValue(adult)
    var c = solver.getValue(child)
    assert_equal(String(a), "4")
    assert_equal(String(c), "3")
    print("tickets:", result)
    print("adults:", a, "children:", c)
