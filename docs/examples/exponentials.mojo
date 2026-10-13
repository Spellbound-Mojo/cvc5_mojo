"""Prove positivity and growth above one for positive inputs."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_NRAT")
    solver.setOption("tlimit-per", "5000")
    var x = tm.mkConst(tm.getRealSort(), "x")
    var exponential = tm.mkTerm(Kind.EXPONENTIAL, x)
    var zero = tm.mkInteger(0)
    solver.assertFormula(tm.mkTerm(Kind.LEQ, exponential, zero))
    var positivity = solver.checkSat()
    assert_true(positivity.isUnsat())
    print("exp(x) <= 0:", positivity)

    var positive_solver = Solver(tm)
    positive_solver.setLogic("QF_NRAT")
    positive_solver.setOption("tlimit-per", "5000")
    positive_solver.assertFormula(tm.mkTerm(Kind.GT, x, zero))
    var one = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(1))
    positive_solver.assertFormula(tm.mkTerm(Kind.LEQ, exponential, one))
    var lower_bound = positive_solver.checkSat()
    assert_true(lower_bound.isUnsat())
    print("x > 0 and exp(x) <= 1:", lower_bound)
