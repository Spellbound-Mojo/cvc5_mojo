"""Show why an inverse sine relation needs a principal interval."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_NRAT")
    solver.setOption("incremental", "true")
    solver.setOption("tlimit-per", "5000")
    var angle = tm.mkConst(tm.getRealSort(), "angle")
    var pi = tm.mkTerm(Kind.PI)
    var half_pi = tm.mkTerm(Kind.DIVISION, pi, tm.mkInteger(2))
    var zero = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(0))
    solver.assertFormula(tm.mkTerm(Kind.EQUAL,
        tm.mkTerm(Kind.SINE, angle), zero))
    solver.assertFormula(tm.mkTerm(Kind.EQUAL, angle, pi))
    var unrestricted = solver.checkSat()
    assert_true(unrestricted.isSat())
    print("sin(angle) = 0 with angle = pi:", unrestricted)

    solver.push()
    solver.assertFormula(tm.mkTerm(Kind.GEQ, angle, tm.mkTerm(Kind.NEG, half_pi)))
    solver.assertFormula(tm.mkTerm(Kind.LEQ, angle, half_pi))
    var principal = solver.checkSat()
    assert_true(principal.isUnsat())
    print("the same angle in [-pi/2, pi/2]:", principal)
    solver.pop()
