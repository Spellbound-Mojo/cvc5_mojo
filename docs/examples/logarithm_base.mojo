"""Check the negative logarithm of a base between zero and one."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_NRAT")
    solver.setOption("tlimit-per", "5000")
    solver.setOption("rlimit-per", "100000")
    var zero = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(0))
    var one = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(1))
    var two = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(2))
    # docs:begin sign
    var base = tm.mkTerm(Kind.DIVISION, one, two)
    var base_log = tm.mkConst(tm.getRealSort(), "base_log")
    solver.assertFormula(tm.mkTerm(Kind.EQUAL,
        tm.mkTerm(Kind.EXPONENTIAL, base_log), base))
    solver.assertFormula(tm.mkTerm(Kind.GEQ, base_log, zero))
    var result = solver.checkSat()
    assert_true(result.isUnsat())
    print("ln(1/2) >= 0:", result)
    # docs:end sign
