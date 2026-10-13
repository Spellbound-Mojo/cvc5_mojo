"""Solve an equation over the reals and over the integers."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var real_solver = Solver(tm)
    real_solver.setLogic("QF_LRA")
    real_solver.setOption("produce-models", "true")
    var x = tm.mkConst(tm.getRealSort(), "x")
    var two = tm.mkInteger(2)
    var one = tm.mkInteger(1)
    var real_one = tm.mkTerm(Kind.TO_REAL, one)
    real_solver.assertFormula(tm.mkTerm(Kind.EQUAL,
        tm.mkTerm(Kind.MULT, two, x), real_one))
    var real_result = real_solver.checkSat()
    assert_true(real_result.isSat())
    var half = real_solver.getValue(x)
    assert_equal(String(half), "(/ 1 2)")
    print("real solution:", half)

    var int_solver = Solver(tm)
    int_solver.setLogic("QF_LIA")
    var n = tm.mkConst(tm.getIntegerSort(), "n")
    int_solver.assertFormula(tm.mkTerm(Kind.EQUAL,
        tm.mkTerm(Kind.MULT, two, n), one))
    var int_result = int_solver.checkSat()
    assert_true(int_result.isUnsat())
    print("integer equation:", int_result)
