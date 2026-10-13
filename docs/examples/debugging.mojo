"""Expose four modeling mistakes with paired failing and corrected queries."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Term, Kind


def check(tm: TermManager, formula: Term, label: String, expect_sat: Bool) raises:
    var solver = Solver(tm)
    solver.setLogic("QF_NRAT")
    solver.setOption("tlimit-per", "1000")
    solver.setOption("rlimit-per", "10000")
    solver.assertFormula(formula)
    var result = solver.checkSat()
    if expect_sat:
        assert_true(result.isSat())
    else:
        assert_true(result.isUnsat())
    print(label, ":", result)


def main() raises:
    var tm = TermManager()
    var zero = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(0))
    var one = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(1))
    var x = tm.mkConst(tm.getRealSort(), "x")
    # docs:begin domain
    # ln(x) < 0 means 0 < x < 1. Try the invalid candidate x = -1.
    var candidate = tm.mkTerm(Kind.EQUAL, x, tm.mkTerm(Kind.NEG, one))
    var incomplete = tm.mkTerm(Kind.AND, candidate, tm.mkTerm(Kind.LT, x, one))
    check(tm, incomplete, "missing logarithm domain", True)
    var corrected = tm.mkTerm(Kind.AND, incomplete, tm.mkTerm(Kind.GT, x, zero))
    check(tm, corrected, "positive logarithm domain", False)
    # docs:end domain

    # docs:begin vacuity
    var impossible = tm.mkTerm(Kind.AND,
        tm.mkTerm(Kind.GT, x, zero), tm.mkTerm(Kind.LT, x, zero))
    # The false universal claim x > 10 would appear to be proved here.
    var violation = tm.mkTerm(Kind.LEQ, x, tm.mkInteger(10))
    check(tm, tm.mkTerm(Kind.AND, impossible, violation), "vacuous property check", False)
    check(tm, impossible, "check the assumptions alone", False)
    var feasible = tm.mkTerm(Kind.GEQ, x, zero)
    check(tm, feasible, "corrected assumptions", True)
    check(tm, tm.mkTerm(Kind.AND, feasible, violation), "actual counterexample exists", True)
    # docs:end vacuity

    # docs:begin angles
    var pi = tm.mkTerm(Kind.PI)
    var two = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(2))
    var quarter_turn = tm.mkTerm(Kind.DIVISION, pi, two)
    var degrees = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(90))
    var half_turn_degrees = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(180))
    # The application permits angles in the closed first quadrant.
    check(tm, tm.mkTerm(Kind.LEQ, degrees, quarter_turn), "90 treated as radians", False)
    var radians = tm.mkTerm(Kind.DIVISION,
        tm.mkTerm(Kind.MULT, degrees, pi), half_turn_degrees)
    check(tm, tm.mkTerm(Kind.LEQ, radians, quarter_turn), "90 degrees converted to radians", True)
    # docs:end angles

    # docs:begin blocking
    var y = tm.mkConst(tm.getRealSort(), "y")
    # Old tuple: (0,0). New valid tuple: (0,1).
    var next_pair = tm.mkTerm(Kind.AND,
        tm.mkTerm(Kind.EQUAL, x, zero), tm.mkTerm(Kind.EQUAL, y, one))
    var changed_x = tm.mkTerm(Kind.DISTINCT, x, zero)
    var changed_y = tm.mkTerm(Kind.DISTINCT, y, zero)
    check(tm, tm.mkTerm(Kind.AND, next_pair,
        tm.mkTerm(Kind.AND, changed_x, changed_y)), "require both coordinates to change", False)
    check(tm, tm.mkTerm(Kind.AND, next_pair,
        tm.mkTerm(Kind.OR, changed_x, changed_y)), "require at least one coordinate to change", True)
    # docs:end blocking
