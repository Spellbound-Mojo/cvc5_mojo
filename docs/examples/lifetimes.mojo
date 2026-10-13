"""A result stays valid after its solver is destroyed, as in cvc5's C++ API."""

from std.testing import assert_true

from cvc5_mojo import TermManager, Solver, Result


def check_false(tm: TermManager) raises -> Result:
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.assertFormula(tm.mkFalse())
    # The solver is destroyed when this function returns; the result is not.
    return solver.checkSat()


def main() raises:
    var tm = TermManager()
    var result = check_false(tm)
    assert_true(result.isUnsat())
    print("false is", result)
