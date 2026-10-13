"""Supply an application rule while cvc5 searches."""

from std.memory import ArcPointer
from std.testing import assert_true
from cvc5_mojo import Kind, Plugin, Solver, Term, TermManager


struct Nonnegative(Plugin):
    var tm: TermManager
    var x: Term

    def __init__(out self, tm: TermManager, x: Term):
        self.tm = tm
        self.x = x

    def check(mut self) raises -> List[Term]:
        # This rule is part of the application's intended problem.
        return [self.tm.mkTerm(Kind.GEQ, self.x, self.tm.mkInteger(0))]

    @staticmethod
    def getName() -> StaticString:
        return "Nonnegative"


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("sat-solver", "minisat")
    var x = tm.mkConst(tm.getIntegerSort(), "x")
    var plugin = ArcPointer(Nonnegative(tm, x))
    solver.addPlugin(plugin)
    solver.assertFormula(tm.mkTerm(Kind.LT, x, tm.mkInteger(0)))
    var result = solver.checkSat()
    assert_true(result.isUnsat())
    print("x < 0 with the nonnegative plugin:", result)
