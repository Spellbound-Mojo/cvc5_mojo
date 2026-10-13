"""Prove uniqueness for selected symbols by blocking their model tuple."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("produce-models", "true")
    solver.setOption("incremental", "true")
    var x = tm.mkConst(tm.getIntegerSort(), "x")
    var y = tm.mkConst(tm.getIntegerSort(), "y")
    solver.assertFormula(tm.mkTerm(Kind.EQUAL,
        tm.mkTerm(Kind.ADD, x, y), tm.mkInteger(5)))
    solver.assertFormula(tm.mkTerm(Kind.EQUAL,
        tm.mkTerm(Kind.SUB, x, y), tm.mkInteger(1)))
    assert_true(solver.checkSat().isSat())
    var vx = solver.getValue(x)
    var vy = solver.getValue(y)
    assert_equal(String(vx), "3")
    assert_equal(String(vy), "2")
    # docs:begin block
    solver.push()
    var same_pair = tm.mkTerm(Kind.AND,
        tm.mkTerm(Kind.EQUAL, x, vx), tm.mkTerm(Kind.EQUAL, y, vy))
    solver.assertFormula(tm.mkTerm(Kind.NOT, same_pair))
    var alternative = solver.checkSat()
    assert_true(alternative.isUnsat())
    print("another (x, y) pair:", alternative)
    solver.pop()
    # docs:end block
    assert_true(solver.checkSat().isSat())
    print("original problem remains satisfiable")
