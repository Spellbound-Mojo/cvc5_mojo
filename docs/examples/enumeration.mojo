"""Enumerate all nonnegative integer pairs whose sum is two."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import TermManager, Solver, Kind


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("incremental", "true")
    solver.setOption("produce-models", "true")
    var x = tm.mkConst(tm.getIntegerSort(), "x")
    var y = tm.mkConst(tm.getIntegerSort(), "y")
    var zero = tm.mkInteger(0)
    solver.assertFormula(tm.mkTerm(Kind.GEQ, x, zero))
    solver.assertFormula(tm.mkTerm(Kind.GEQ, y, zero))
    solver.assertFormula(tm.mkTerm(Kind.EQUAL,
        tm.mkTerm(Kind.ADD, x, y), tm.mkInteger(2)))
    var seen = List[String]()
    while True:
        var result = solver.checkSat()
        if result.isUnsat():
            break
        if result.isUnknown():
            raise Error("Enumeration stopped before completeness was established")
        var vx = solver.getValue(x)
        var vy = solver.getValue(y)
        var pair = String(vx) + "," + String(vy)
        assert_true(pair == "0,2" or pair == "1,1" or pair == "2,0")
        for previous in seen:
            assert_true(pair != previous)
        seen.append(pair^)
        # Exclude the entire pair, not each coordinate separately.
        var same_pair = tm.mkTerm(Kind.AND,
            tm.mkTerm(Kind.EQUAL, x, vx), tm.mkTerm(Kind.EQUAL, y, vy))
        solver.assertFormula(tm.mkTerm(Kind.NOT, same_pair))
    assert_equal(len(seen), 3)
    print("distinct pairs:", len(seen))
    print("all solutions found")
