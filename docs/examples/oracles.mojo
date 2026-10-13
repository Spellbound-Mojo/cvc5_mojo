"""Give an SMT function a deterministic Mojo implementation."""

from std.memory import ArcPointer
from std.testing import assert_true
from cvc5_mojo import Kind, Oracle, Solver, Term, TermManager


struct Increment(Oracle):
    var tm: TermManager

    def __init__(out self, tm: TermManager):
        self.tm = tm

    def evaluate(mut self, arguments: List[Term]) raises -> Term:
        return self.tm.mkInteger(arguments[0].getIntegerValue() + 1)


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("oracles", "true")
    var integers = tm.getIntegerSort()
    var implementation = ArcPointer(Increment(tm))
    var increment = solver.declareOracleFun("increment", [integers], integers, implementation)
    var application = tm.mkTerm(Kind.APPLY_UF, increment, tm.mkInteger(3))
    solver.assertFormula(application.eqTerm(tm.mkInteger(5)))
    var result = solver.checkSat()
    assert_true(result.isUnsat())
    print("increment(3) = 5:", result)
