"""Use a precompiled dependency and a local module from another directory."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Kind
from capacity import required_capacity


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("incremental", "true")
    var workers = tm.mkConst(tm.getIntegerSort(), "workers")
    solver.assertFormula(required_capacity(tm, workers, 10))
    solver.push()
    solver.assertFormula(tm.mkTerm(Kind.LEQ, workers, tm.mkInteger(3)))
    var too_small = solver.checkSat()
    assert_true(too_small.isUnsat())
    print("three workers:", too_small)
    solver.pop()
    solver.assertFormula(tm.mkTerm(Kind.EQUAL, workers, tm.mkInteger(4)))
    var enough = solver.checkSat()
    assert_true(enough.isSat())
    print("four workers:", enough)
