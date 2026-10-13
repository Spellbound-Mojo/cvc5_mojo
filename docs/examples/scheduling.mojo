"""Check a deadline for two jobs sharing one machine."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import TermManager, Solver, Term, Kind


def check_deadline(tm: TermManager, deadline: Int) raises:
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("produce-models", "true")
    var a = tm.mkConst(tm.getIntegerSort(), "start_a")
    var b = tm.mkConst(tm.getIntegerSort(), "start_b")
    var end_a = tm.mkTerm(Kind.ADD, a, tm.mkInteger(2))
    var end_b = tm.mkTerm(Kind.ADD, b, tm.mkInteger(3))
    var requirements = List[Term]()
    requirements.append(tm.mkTerm(Kind.GEQ, a, tm.mkInteger(0)))
    requirements.append(tm.mkTerm(Kind.GEQ, b, tm.mkInteger(0)))
    requirements.append(tm.mkTerm(Kind.LEQ, end_a, tm.mkInteger(deadline)))
    requirements.append(tm.mkTerm(Kind.LEQ, end_b, tm.mkInteger(deadline)))
    requirements.append(tm.mkTerm(Kind.OR,
        tm.mkTerm(Kind.LEQ, end_a, b), tm.mkTerm(Kind.LEQ, end_b, a)))
    for requirement in requirements:
        solver.assertFormula(requirement)
    var result = solver.checkSat()
    if deadline == 4:
        assert_true(result.isUnsat())
    else:
        assert_true(result.isSat())
        for requirement in requirements:
            assert_equal(String(solver.getValue(requirement)), "true")
    print("deadline", deadline, ":", result)


def main() raises:
    var tm = TermManager()
    check_deadline(tm, 4)
    check_deadline(tm, 5)
