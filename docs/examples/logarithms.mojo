"""Represent a logarithm by its exponential relation and prove bounds."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_NRAT")
    solver.setOption("tlimit-per", "5000")
    var y = tm.mkConst(tm.getRealSort(), "log_value")
    var exponential = tm.mkTerm(Kind.EXPONENTIAL, y)
    var one = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(1))
    var two = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(2))
    # docs:begin relation
    # y = ln(2). Search for a value outside the open interval (0, 1).
    solver.assertFormula(tm.mkTerm(Kind.EQUAL, exponential, two))
    solver.assertFormula(tm.mkTerm(Kind.OR,
        tm.mkTerm(Kind.LEQ, y, tm.mkInteger(0)), tm.mkTerm(Kind.GEQ, y, one)))
    var bounds = solver.checkSat()
    assert_true(bounds.isUnsat())
    print("ln(2) outside (0, 1):", bounds)
    # docs:end relation

    var unit_solver = Solver(tm)
    unit_solver.setLogic("QF_NRAT")
    unit_solver.setOption("produce-models", "true")
    unit_solver.setOption("tlimit-per", "5000")
    unit_solver.assertFormula(tm.mkTerm(Kind.EQUAL, exponential, one))
    var result = unit_solver.checkSat()
    assert_true(result.isSat())
    var value = unit_solver.getValue(y)
    assert_equal(String(value), "0.0")
    print("ln(1):", value)
