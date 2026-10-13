"""Verify rational Taylor bounds around sine of one half."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Term, Kind


def rational(tm: TermManager, numerator: Int, denominator: Int) raises -> Term:
    var n = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(numerator))
    var d = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(denominator))
    return tm.mkTerm(Kind.DIVISION, n, d)


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_NRAT")
    solver.setOption("tlimit-per", "5000")
    # docs:begin enclosure
    var half = rational(tm, 1, 2)
    var sine = tm.mkTerm(Kind.SINE, half)
    var lower = rational(tm, 23, 48)
    var upper = rational(tm, 1841, 3840)
    solver.assertFormula(tm.mkTerm(Kind.OR,
        tm.mkTerm(Kind.LT, sine, lower), tm.mkTerm(Kind.GT, sine, upper)))
    var result = solver.checkSat()
    assert_true(result.isUnsat())
    print("sin(1/2) outside [23/48, 1841/3840]:", result)
    # docs:end enclosure
