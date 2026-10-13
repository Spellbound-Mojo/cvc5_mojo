"""Compare a logarithmic threshold and its equivalent algebraic query."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Kind


def check_encoding(tm: TermManager, relational: Bool, budget: Int) raises:
    var solver = Solver(tm)
    solver.setLogic("QF_NRAT")
    solver.setOption("tlimit-per", "5000")
    solver.setOption("rlimit-per", String(budget))
    var x = tm.mkConst(tm.getRealSort(), "x")
    var zero = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(0))
    var one = tm.mkTerm(Kind.TO_REAL, tm.mkInteger(1))
    solver.assertFormula(tm.mkTerm(Kind.GT, x, zero))
    solver.assertFormula(tm.mkTerm(Kind.LT, x, one))
    # docs:begin formulations
    if relational:
        var y = tm.mkConst(tm.getRealSort(), "log_x")
        solver.assertFormula(tm.mkTerm(Kind.EQUAL,
            tm.mkTerm(Kind.EXPONENTIAL, y), x))
        solver.assertFormula(tm.mkTerm(Kind.GEQ, y, zero))
    else:
        solver.assertFormula(tm.mkTerm(Kind.GEQ, x, one))
    # docs:end formulations
    var result = solver.checkSat()
    # Expected observations for this release, not a rule about all encodings.
    if relational and budget == 1:
        assert_true(result.isUnknown())
    else:
        assert_true(result.isUnsat())
    var label = "algebraic"
    if relational:
        label = "relational"
    if result.isSat():
        print(label, "budget", budget, ": sat")
    elif result.isUnsat():
        print(label, "budget", budget, ": unsat")
    else:
        print(label, "budget", budget, ": unknown")


def main() raises:
    var tm = TermManager()
    check_encoding(tm, True, 1)
    check_encoding(tm, False, 1)
    check_encoding(tm, True, 100000)
    check_encoding(tm, False, 100000)
