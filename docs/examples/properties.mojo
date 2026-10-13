"""Prove a property, then find a counterexample to a stronger claim."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_NRA")
    solver.setOption("incremental", "true")
    solver.setOption("produce-models", "true")
    var x = tm.mkConst(tm.getRealSort(), "x")
    var zero = tm.mkInteger(0)
    var square = tm.mkTerm(Kind.MULT, x, x)
    # Search for a counterexample to: x > 0 implies x*x > 0.
    solver.push()
    solver.assertFormula(tm.mkTerm(Kind.GT, x, zero))
    solver.assertFormula(tm.mkTerm(Kind.LEQ, square, zero))
    var proof = solver.checkSat()
    assert_true(proof.isUnsat())
    print("positive input, nonpositive square:", proof)
    solver.pop()

    # Allowing x = 0 makes that conclusion false.
    solver.assertFormula(tm.mkTerm(Kind.GEQ, x, zero))
    solver.assertFormula(tm.mkTerm(Kind.LEQ, square, zero))
    var counterexample = solver.checkSat()
    assert_true(counterexample.isSat())
    var value = solver.getValue(x)
    assert_equal(String(value), "0.0")
    print("nonnegative input, nonpositive square:", counterexample, "at", value)
