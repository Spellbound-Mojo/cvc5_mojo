"""Check global sine and cosine bounds with counterexample queries."""

from std.testing import assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_NRAT")
    solver.setOption("incremental", "true")
    solver.setOption("tlimit-per", "5000")
    var x = tm.mkConst(tm.getRealSort(), "angle")
    var sine = tm.mkTerm(Kind.SINE, x)
    var cosine = tm.mkTerm(Kind.COSINE, x)
    var lower = tm.mkInteger(-1)
    var upper = tm.mkInteger(1)
    solver.push()
    solver.assertFormula(tm.mkTerm(Kind.OR,
        tm.mkTerm(Kind.LT, sine, lower), tm.mkTerm(Kind.GT, sine, upper)))
    var sine_result = solver.checkSat()
    assert_true(sine_result.isUnsat())
    print("sin(x) outside [-1, 1]:", sine_result)
    solver.pop()

    solver.assertFormula(tm.mkTerm(Kind.OR,
        tm.mkTerm(Kind.LT, cosine, lower), tm.mkTerm(Kind.GT, cosine, upper)))
    var cosine_result = solver.checkSat()
    assert_true(cosine_result.isUnsat())
    print("cos(x) outside [-1, 1]:", cosine_result)
