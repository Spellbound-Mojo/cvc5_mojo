"""Rule out a square below sine on the negative half of a period."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_NRAT")
    solver.setOption("tlimit-per", "5000")
    var real = tm.getRealSort()
    var angle = tm.mkConst(real, "angle")
    var y = tm.mkConst(real, "y")
    var pi = tm.mkTerm(Kind.PI)
    var two_pi = tm.mkTerm(Kind.MULT, tm.mkInteger(2), pi)
    solver.assertFormula(tm.mkTerm(Kind.GT, angle, pi))
    solver.assertFormula(tm.mkTerm(Kind.LT, angle, two_pi))
    solver.assertFormula(tm.mkTerm(Kind.LT,
        tm.mkTerm(Kind.MULT, y, y), tm.mkTerm(Kind.SINE, angle)))
    var result = solver.checkSat()
    assert_true(result.isUnsat())
    print("pi < angle < 2*pi and y*y < sin(angle):", result)
