"""Mirror the paired Python example using the currently available Mojo API."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    # docs:begin setup
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_LRA")
    solver.setOption("produce-models", "true")
    solver.setOption("incremental", "true")
    var x = tm.mkConst(tm.getRealSort(), "x")
    var one = tm.mkReal(1)
    var doubled = tm.mkTerm(Kind.ADD, x, x)
    solver.assertFormula(tm.mkTerm(Kind.EQUAL, doubled, one))
    # docs:end setup
    assert_true(solver.checkSat().isSat())
    var value = solver.getValue(x)
    assert_equal(String(value), "(/ 1 2)")
    print("x:", value)

    # docs:begin shared
    # Copying retains the same solver; it does not clone the assertion stack.
    var shared = solver.copy()
    shared.push()
    shared.assertFormula(tm.mkTerm(Kind.LT, x, tm.mkInteger(0)))
    var conflict = solver.checkSat()
    assert_true(conflict.isUnsat())
    print("shared solver with x < 0:", conflict)
    shared.pop()
    var restored = solver.checkSat()
    assert_true(restored.isSat())
    print("after pop:", restored)
    # docs:end shared
