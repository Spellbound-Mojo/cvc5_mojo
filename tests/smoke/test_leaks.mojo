"""Leak test: everything a round creates is freed when the round ends.

The lifetime test checks that wrappers take enough cvc5 references; this test
checks that they take no more than they release. Each round creates a term
manager and a solver, calls every method that receives a cvc5 handle, and
drops everything.

Objects made by a term manager keep it alive (see
docs/content/architecture/c-api.md), so one reference that is taken and never
released keeps the whole term manager of its round alive. Its node pool then
keeps the round's released ballast terms, whose long names make each pinned
round cost several hundred kB. After a warm-up, the resident set must stop
growing.

An extra reference on a solver object that keeps nothing else alive, such as
a `Result`, costs too little memory to detect this way.

Run it as a built program (`pixi run leaks`). Under `mojo run`, cvc5 reuses
memory the JIT compiler has freed, which hides the growth. Reads
/proc/self/status, so it runs on Linux.
"""

from cvc5_mojo import TermManager, Solver, Kind
from memory_support import resident_kb

comptime WARMUP_ROUNDS = 30
comptime ROUNDS = 200
comptime BALLAST_TERMS = 200
comptime BALLAST_NAME_BYTES = 1024
# With cvc5 1.4.1 a pinned round retains about 370 kB, and a leak-free run
# grows by under 0.5 MB.
comptime BUDGET_KB = 4096


def round(ballast_name: String) raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("incremental", "true")
    solver.setOption("produce-models", "true")
    solver.setOption("produce-unsat-cores", "true")
    solver.setOption("produce-difficulty", "true")

    # Sorts.
    var integer = tm.getIntegerSort()
    var integer_copy = integer.copy()
    if not (integer == integer_copy) or String(integer) != "Int":
        raise Error("unexpected integer sort")
    _ = tm.getBooleanSort()
    _ = tm.getRealSort()

    # Ballast: released here, but kept by a term manager that a leak pins.
    var total = tm.mkInteger(0)
    for i in range(BALLAST_TERMS):
        var b = tm.mkConst(integer, ballast_name + String(i))
        total = tm.mkTerm(Kind.ADD, total, b)

    # Terms.
    var x = tm.mkConst(integer, "x")
    var x_copy = x.copy()
    if not (x == x_copy) or x.getKind() != Kind.CONSTANT or not (x.getSort() == integer):
        raise Error("unexpected constant")
    _ = tm.mkTrue()
    _ = tm.mkFalse()
    var positive = tm.mkTerm(Kind.GT, x, tm.mkInteger(0))
    var children = 0
    for child in positive:
        children += 1 if child.getKind() == Kind.CONSTANT or child.getKind() == Kind.CONST_INTEGER else 0
    if children != 2:
        raise Error("expected the two children of x > 0")

    # A model inside a scope: results and values.
    solver.push()
    solver.assertFormula(tm.mkTerm(Kind.LT, x, tm.mkInteger(2)))
    solver.assertFormula(positive)
    var sat = solver.checkSat()
    var sat_copy = sat.copy()
    if not sat_copy.isSat() or String(solver.getValue(x)) != "1":
        raise Error("expected x = 1")
    solver.pop()

    # An unsat core: an array of handles.
    solver.assertFormula(positive)
    solver.assertFormula(tm.mkTerm(Kind.LT, x, tm.mkInteger(0)))
    if not solver.checkSat().isUnsat() or len(solver.getUnsatCore()) != 2:
        raise Error("expected an unsat core of two assertions")
    # A dictionary of handles; assertions it leaves out have no difficulty.
    if len(solver.getDifficulty()) == 0:
        raise Error("expected a difficulty")

    # Statistics: each is read from a handle that must be released.
    var stats = solver.getStatistics()
    var listed = 0
    for _ in stats:
        listed += 1
    if listed != len(stats.get(True, True)) or stats["global::totalTime"].internal:
        raise Error("unexpected statistics")

    # A failed call wraps nothing.
    var raised = False
    try:
        _ = tm.mkTerm(Kind.ADD, x, tm.mkTrue())
    except e:
        raised = String(e).startswith("cvc5: ")
    if not raised:
        raise Error("expected a cvc5 error for an ill-sorted term")


def main() raises:
    var ballast_name = String("b") * BALLAST_NAME_BYTES
    for _ in range(WARMUP_ROUNDS):
        round(ballast_name)
    var before = resident_kb()
    for _ in range(ROUNDS):
        round(ballast_name)
    var growth = resident_kb() - before
    print("resident set growth over", ROUNDS, "rounds:", growth, "kB (budget", BUDGET_KB, "kB)")
    if growth > BUDGET_KB:
        raise Error("cvc5 objects leak: a wrapper takes a reference it never releases")
    print("leak test passed")
