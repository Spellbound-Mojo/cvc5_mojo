"""The Python counterpart of migration.mojo, checked against the same output."""
from cvc5 import Kind, Solver, TermManager


def main():
    # docs:begin setup
    tm = TermManager()
    solver = Solver(tm)
    solver.setLogic("QF_LRA")
    solver.setOption("produce-models", "true")
    solver.setOption("incremental", "true")
    x = tm.mkConst(tm.getRealSort(), "x")
    one = tm.mkReal(1)
    operands = [x, x]
    doubled = tm.mkTerm(Kind.ADD, *operands)
    solver.assertFormula(tm.mkTerm(Kind.EQUAL, doubled, one))
    # docs:end setup
    assert solver.checkSat().isSat()
    value = solver.getValue(x)
    assert str(value) == "(/ 1 2)"
    print("x:", value)

    # docs:begin shared
    shared = solver
    shared.push()
    shared.assertFormula(tm.mkTerm(Kind.LT, x, tm.mkInteger(0)))
    conflict = solver.checkSat()
    assert conflict.isUnsat()
    print("shared solver with x < 0:", conflict)
    shared.pop()
    restored = solver.checkSat()
    assert restored.isSat()
    print("after pop:", restored)
    # docs:end shared


if __name__ == "__main__":
    main()
