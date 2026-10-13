"""The smallest complete program: prove that no real number has a negative square."""

from std.testing import assert_true

from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_NRA")

    # docs:begin terms
    var x = tm.mkConst(tm.getRealSort(), "x")
    var negative_square = tm.mkTerm(Kind.LT, tm.mkTerm(Kind.MULT, x, x), tm.mkInteger(0))
    solver.assertFormula(negative_square)
    # docs:end terms

    var result = solver.checkSat()
    assert_true(result.isUnsat())
    print(negative_square, "is", result)
