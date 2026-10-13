"""Color a triangle with a bounded integer assigned to each vertex."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import TermManager, Solver, Term, Kind


def check_triangle(tm: TermManager, colors: Int) raises:
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("produce-models", "true")
    var vertices = List[Term]()
    for i in range(3):
        vertices.append(tm.mkConst(tm.getIntegerSort(), "v" + String(i)))
        solver.assertFormula(tm.mkTerm(Kind.GEQ, vertices[i], tm.mkInteger(0)))
        solver.assertFormula(tm.mkTerm(Kind.LT, vertices[i], tm.mkInteger(colors)))
    var edges = tm.mkTerm(Kind.DISTINCT, vertices[0], vertices[1], vertices[2])
    solver.assertFormula(edges)
    var result = solver.checkSat()
    if colors == 2:
        assert_true(result.isUnsat())
    else:
        assert_true(result.isSat())
        assert_equal(String(solver.getValue(edges)), "true")
        for vertex in vertices:
            var in_range = tm.mkTerm(Kind.AND,
                tm.mkTerm(Kind.GEQ, vertex, tm.mkInteger(0)),
                tm.mkTerm(Kind.LT, vertex, tm.mkInteger(colors)))
            assert_equal(String(solver.getValue(in_range)), "true")
    print(colors, "colors:", result)


def main() raises:
    var tm = TermManager()
    check_triangle(tm, 2)
    check_triangle(tm, 3)
