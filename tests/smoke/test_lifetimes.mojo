"""Lifetime test: objects must stay valid after the object that made them dies.

Results retain their solver while adopting its exported reference
(`receive = "anchor"`; see docs/content/architecture/runtime.md).
Terms are managed by the term
manager and keep it alive. Mojo destroys values right after their last use,
so these orderings occur in ordinary code, for example
`print(solver.checkSat())` as a solver's last use.
"""

from cvc5_mojo import TermManager, Solver, Result, Term, Kind


def solve_unsat(tm: TermManager) raises -> Result:
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.assertFormula(tm.mkFalse())
    return solver.checkSat()  # the returned result retains the native solver


def make_term() raises -> Term:
    var tm = TermManager()
    return tm.mkInteger(42)  # the TermManager value is destroyed on return


def main() raises:
    var tm = TermManager()

    var detached = solve_unsat(tm)
    print("result after its solver is gone:", detached)
    if not detached.isUnsat():
        raise Error("expected unsat")

    # The solver's last use is inside the print argument.
    var solver = Solver(tm)
    solver.setLogic("QF_NRA")
    var x = tm.mkConst(tm.getRealSort(), "x")
    solver.assertFormula(tm.mkTerm(Kind.LT, tm.mkTerm(Kind.MULT, x, x), tm.mkInteger(0)))
    print("temporary result:", solver.checkSat())

    var t = make_term()
    print("term after its term manager value is gone:", t)
    print("lifetime test passed")
