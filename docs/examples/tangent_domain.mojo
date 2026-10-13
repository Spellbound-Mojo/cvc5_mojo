"""Keep cosine nonzero when expressing tangent as a quotient."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var zero = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(0))
    var two = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(2))
    var angle = tm.mkConst(tm.getRealSort(), "angle")
    var solver = Solver(tm)
    solver.setLogic("QF_NRAT")
    solver.setOption("tlimit-per", "5000")
    solver.setOption("rlimit-per", "100000")
    # docs:begin domain
    var sine = tm.mkTerm(Kind.SINE, angle)
    var cosine = tm.mkTerm(Kind.COSINE, angle)
    solver.assertFormula(tm.mkTerm(Kind.DISTINCT, cosine, zero))
    var tangent = tm.mkTerm(Kind.DIVISION, sine, cosine)
    solver.assertFormula(tm.mkTerm(Kind.EQUAL, angle, zero))
    solver.assertFormula(tm.mkTerm(Kind.DISTINCT, tangent, zero))
    var value_result = solver.checkSat()
    assert_true(value_result.isUnsat())
    print("tan(0) != 0 on its domain:", value_result)
    # docs:end domain

    var pole_solver = Solver(tm)
    pole_solver.setLogic("QF_NRAT")
    pole_solver.setOption("tlimit-per", "5000")
    pole_solver.setOption("rlimit-per", "100000")
    var half_pi = tm.mkTerm(Kind.DIVISION, tm.mkTerm(Kind.PI), two)
    pole_solver.assertFormula(tm.mkTerm(Kind.DISTINCT,
        tm.mkTerm(Kind.COSINE, half_pi), zero))
    var pole_result = pole_solver.checkSat()
    assert_true(pole_result.isUnsat())
    print("pi/2 satisfies the tangent domain:", pole_result)
