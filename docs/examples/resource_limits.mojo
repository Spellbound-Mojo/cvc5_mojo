"""Handle an inconclusive transcendental query without claiming a solution."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_NRAT")
    # Deliberately too little work: an example of the unknown branch.
    solver.setOption("rlimit-per", "1")
    var x = tm.mkConst(tm.getRealSort(), "x")
    var two = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(2))
    solver.assertFormula(tm.mkTerm(Kind.EQUAL,
        tm.mkTerm(Kind.EXPONENTIAL, x), two))
    var result = solver.checkSat()
    assert_true(result.isUnknown())
    if result.isSat():
        print("a solution exists")
    elif result.isUnsat():
        print("no solution exists")
    else:
        print("unknown: no conclusion within the resource budget")
