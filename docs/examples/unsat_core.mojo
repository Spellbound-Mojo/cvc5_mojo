"""Identify conflicting requirements without depending on core order."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("produce-unsat-cores", "true")
    var x = tm.mkConst(tm.getIntegerSort(), "x")
    var lower = tm.mkTerm(Kind.GEQ, x, tm.mkInteger(5))
    var upper = tm.mkTerm(Kind.LEQ, x, tm.mkInteger(3))
    solver.assertFormula(lower)
    solver.assertFormula(upper)
    var result = solver.checkSat()
    assert_true(result.isUnsat())
    var core = solver.getUnsatCore()
    assert_equal(len(core), 2)
    var has_lower = False
    var has_upper = False
    for formula in core:
        has_lower = has_lower or formula == lower
        has_upper = has_upper or formula == upper
    assert_true(has_lower and has_upper)
    print("requirements:", result)
    print("core contains both conflicting bounds")
