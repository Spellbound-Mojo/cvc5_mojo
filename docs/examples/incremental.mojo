"""Try two candidates while keeping shared bounds in one solver."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("incremental", "true")
    solver.setOption("produce-models", "true")
    var x = tm.mkConst(tm.getIntegerSort(), "x")
    solver.assertFormula(tm.mkTerm(Kind.GEQ, x, tm.mkInteger(0)))
    solver.assertFormula(tm.mkTerm(Kind.LEQ, x, tm.mkInteger(10)))
    solver.push()
    solver.assertFormula(tm.mkTerm(Kind.GT, x, tm.mkInteger(10)))
    var rejected = solver.checkSat()
    assert_true(rejected.isUnsat())
    print("candidate above 10:", rejected)
    solver.pop()

    solver.push()
    solver.assertFormula(tm.mkTerm(Kind.EQUAL, x, tm.mkInteger(7)))
    var accepted = solver.checkSat()
    assert_true(accepted.isSat())
    var value = solver.getValue(x)
    assert_equal(String(value), "7")
    print("candidate 7:", accepted, "with x =", value)
    solver.pop()
