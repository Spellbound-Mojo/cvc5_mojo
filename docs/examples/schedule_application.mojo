"""Build, diagnose, and optimize a four-job schedule with one shared model."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import TermManager, Solver, Term, Result, Kind


def add_requirement(mut requirements: List[Term], mut labels: List[String], term: Term, label: String):
    requirements.append(term.copy())
    labels.append(label)


def check_deadline(
    solver: Solver, tm: TermManager, ends: List[Term],
    requirements: List[Term], deadline: Int,
) raises -> Result:
    solver.push()
    var bounds = List[Term]()
    for end in ends:
        var bound = tm.mkTerm(Kind.LEQ, end, tm.mkInteger(deadline))
        bounds.append(bound.copy())
        solver.assertFormula(bound)
    var result = solver.checkSat()
    if result.isSat():
        for requirement in requirements:
            assert_equal(String(solver.getValue(requirement)), "true")
        for bound in bounds:
            assert_equal(String(solver.getValue(bound)), "true")
    solver.pop()
    return result^


def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("produce-models", "true")
    solver.setOption("produce-unsat-cores", "true")
    solver.setOption("incremental", "true")
    solver.setOption("tlimit-per", "5000")
    var requirements = List[Term]()
    var labels = List[String]()
    # docs:begin jobs
    var durations: List[Int] = [2, 3, 2, 2]
    var starts = List[Term]()
    var ends = List[Term]()
    for i in range(len(durations)):
        var start = tm.mkConst(tm.getIntegerSort(), "start_" + String(i))
        starts.append(start.copy())
        ends.append(tm.mkTerm(Kind.ADD, start, tm.mkInteger(durations[i])))
        add_requirement(requirements, labels,
            tm.mkTerm(Kind.GEQ, start, tm.mkInteger(0)),
            "job " + String(i) + " starts at or after zero")
    # docs:end jobs
    # docs:begin dependencies
    # Jobs A=0, B=1, C=2, D=3. The chain A -> B -> C takes seven units.
    add_requirement(requirements, labels,
        tm.mkTerm(Kind.LEQ, ends[0], starts[1]), "A before B")
    add_requirement(requirements, labels,
        tm.mkTerm(Kind.LEQ, ends[1], starts[2]), "B before C")
    add_requirement(requirements, labels,
        tm.mkTerm(Kind.LEQ, ends[0], starts[3]), "A before D")
    # A and C use machine 0; B and D use machine 1.
    add_requirement(requirements, labels, tm.mkTerm(Kind.OR,
        tm.mkTerm(Kind.LEQ, ends[0], starts[2]),
        tm.mkTerm(Kind.LEQ, ends[2], starts[0])), "machine 0 does not overlap")
    add_requirement(requirements, labels, tm.mkTerm(Kind.OR,
        tm.mkTerm(Kind.LEQ, ends[1], starts[3]),
        tm.mkTerm(Kind.LEQ, ends[3], starts[1])), "machine 1 does not overlap")
    for requirement in requirements:
        solver.assertFormula(requirement)
    # docs:end dependencies
    var initial = check_deadline(solver, tm, ends, requirements, 10)
    assert_true(initial.isSat())
    print("deadline 10:", initial)

    # docs:begin conflict
    solver.push()
    var rush = tm.mkTerm(Kind.LEQ, ends[2], tm.mkInteger(6))
    solver.assertFormula(rush)
    var conflict = solver.checkSat()
    assert_true(conflict.isUnsat())
    var core = solver.getUnsatCore()
    var core_labels = List[String]()
    var includes_rush = False
    for term in core:
        if term == rush:
            core_labels.append("C must finish by 6")
            includes_rush = True
        else:
            var matched = False
            for i in range(len(requirements)):
                if term == requirements[i]:
                    core_labels.append(labels[i])
                    matched = True
                    break
            assert_true(matched)
    assert_true(includes_rush)
    assert_equal(len(core_labels), len(core))
    print("rush deadline:", conflict)
    print("core labels recognized:", len(core_labels) == len(core))
    solver.pop()
    # docs:end conflict

    # docs:begin search
    # Maintain: low is infeasible and high is feasible.
    var low = 0
    var high = 10
    assert_true(check_deadline(solver, tm, ends, requirements, low).isUnsat())
    assert_true(check_deadline(solver, tm, ends, requirements, high).isSat())
    while high - low > 1:
        var middle = low + (high - low) // 2
        var candidate = check_deadline(solver, tm, ends, requirements, middle)
        if candidate.isSat():
            high = middle
        elif candidate.isUnsat():
            low = middle
        else:
            raise Error("deadline search inconclusive; keep the last certified bounds")
    assert_equal(high, 7)
    assert_true(check_deadline(solver, tm, ends, requirements, high).isSat())
    assert_true(check_deadline(solver, tm, ends, requirements, high - 1).isUnsat())
    print("minimum integer deadline:", high)
    print("adjacent smaller deadline: unsat")
    # docs:end search
