"""Certify opposite signs at the endpoints of a sine root bracket."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_NRAT")
    solver.setOption("tlimit-per", "5000")
    solver.setOption("rlimit-per", "100000")
    var one = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(1))
    var two = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(2))
    var three = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(3))
    var five = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(5))
    # docs:begin bracket
    var half = tm.mkTerm(Kind.DIVISION, one, two)
    var upper = tm.mkTerm(Kind.DIVISION, three, five)
    var left_sine = tm.mkTerm(Kind.SINE, half)
    var right_sine = tm.mkTerm(Kind.SINE, upper)
    solver.assertFormula(tm.mkTerm(Kind.OR,
        tm.mkTerm(Kind.GEQ, left_sine, half),
        tm.mkTerm(Kind.LEQ, right_sine, half)))
    var result = solver.checkSat()
    assert_true(result.isUnsat())
    print("opposite endpoint signs certified:", result)
    # docs:end bracket
