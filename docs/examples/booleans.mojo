"""Choose a valid feature configuration with a dependency."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_UF")
    solver.setOption("produce-models", "true")
    var storage = tm.mkConst(tm.getBooleanSort(), "storage")
    var encryption = tm.mkConst(tm.getBooleanSort(), "encryption")
    solver.assertFormula(tm.mkTerm(Kind.IMPLIES, encryption, storage))
    solver.assertFormula(encryption)
    var result = solver.checkSat()
    assert_true(result.isSat())
    var chosen = solver.getValue(storage)
    assert_equal(String(chosen), "true")
    print("configuration:", result)
    print("storage required:", chosen)
