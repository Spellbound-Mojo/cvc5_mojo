"""Smoke test: load cvc5, build terms, solve, and recover from an API error."""

from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_NRA")
    solver.setOption("produce-unsat-cores", "true")

    var real = tm.getRealSort()
    var x = tm.mkConst(real, "x")
    var zero = tm.mkInteger(0)
    var x_squared = tm.mkTerm(Kind.MULT, x, x)
    var negative = tm.mkTerm(Kind.LT, x_squared, zero)
    print("formula:", String(negative))

    solver.assertFormula(negative)
    var result = solver.checkSat()
    print("result:", String(result))
    if not result.isUnsat():
        raise Error("expected unsat")

    var core = solver.getUnsatCore()
    print("unsat core size:", len(core))

    # An ill-sorted term must raise a Mojo error, not terminate the process.
    var b = tm.mkConst(tm.getBooleanSort(), "b")
    var raised = False
    try:
        _ = tm.mkTerm(Kind.ADD, x, b)
    except e:
        raised = True
        print("caught:", String(e))
    if not raised:
        raise Error("expected an error for an ill-sorted term")

    # The term manager is still usable after the error.
    var y = tm.mkConst(real, "y")
    print("after error:", String(tm.mkTerm(Kind.ADD, x, y)))
    print("smoke test passed")
