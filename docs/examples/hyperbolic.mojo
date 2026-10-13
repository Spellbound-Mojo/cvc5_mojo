"""Build hyperbolic functions from exponential terms and check zero."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_NRAT")
    solver.setOption("tlimit-per", "5000")
    var x = tm.mkConst(tm.getRealSort(), "x")
    var positive = tm.mkTerm(Kind.EXPONENTIAL, x)
    var negative = tm.mkTerm(Kind.EXPONENTIAL, tm.mkTerm(Kind.NEG, x))
    var two = tm.mkInteger(2)
    var sinh_x = tm.mkTerm(Kind.DIVISION,
        tm.mkTerm(Kind.SUB, positive, negative), two)
    var cosh_x = tm.mkTerm(Kind.DIVISION,
        tm.mkTerm(Kind.ADD, positive, negative), two)
    var zero = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(0))
    var one = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(1))
    solver.assertFormula(tm.mkTerm(Kind.EQUAL, x, zero))
    solver.assertFormula(tm.mkTerm(Kind.OR,
        tm.mkTerm(Kind.DISTINCT, sinh_x, zero),
        tm.mkTerm(Kind.DISTINCT, cosh_x, one)))
    var result = solver.checkSat()
    assert_true(result.isUnsat())
    print("sinh(0) != 0 or cosh(0) != 1:", result)
