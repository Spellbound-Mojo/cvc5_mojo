"""Incremental solving: a model inside a scope, then an unsat core after it."""

from std.testing import assert_equal, assert_true

from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("incremental", "true")
    solver.setOption("produce-models", "true")
    solver.setOption("produce-unsat-cores", "true")

    var x = tm.mkConst(tm.getIntegerSort(), "x")
    var positive = tm.mkTerm(Kind.GT, x, tm.mkInteger(0))
    solver.assertFormula(positive)

    # Inside a scope, x < 2 leaves exactly one model.
    solver.push()
    solver.assertFormula(tm.mkTerm(Kind.LT, x, tm.mkInteger(2)))
    var first = solver.checkSat()
    assert_true(first.isSat())
    var value = solver.getValue(x)
    assert_equal(String(value), "1")
    print("x > 0 and x < 2:", first, "with x =", value)
    solver.pop()

    # After the scope, x < 0 contradicts x > 0; the core names both.
    var negative = tm.mkTerm(Kind.LT, x, tm.mkInteger(0))
    solver.assertFormula(negative)
    var second = solver.checkSat()
    assert_true(second.isUnsat())
    var core = solver.getUnsatCore()
    assert_equal(len(core), 2)
    print("x > 0 and x < 0:", second)
    for formula in core:
        print("  core:", formula)
