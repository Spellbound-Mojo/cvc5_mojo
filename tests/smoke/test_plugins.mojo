"""Callback contracts beyond the translated upstream tests."""

from std.memory import ArcPointer
from std.testing import assert_true, assert_equal
from cvc5_mojo import Plugin, Solver, TermManager, Term, Kind, InputParser, InputLanguage, Command


struct Reject(Plugin):
    var tm: TermManager
    var calls: Int

    def __init__(out self, tm: TermManager):
        self.tm = tm
        self.calls = 0

    def check(mut self) raises -> List[Term]:
        self.calls += 1
        return [self.tm.mkBoolean(True), self.tm.mkBoolean(False)]

    @staticmethod
    def getName() -> StaticString:
        return "Reject"


struct Tracked(Plugin):
    var tm: TermManager
    var dropped: ArcPointer[Int]

    def __init__(out self, tm: TermManager, dropped: ArcPointer[Int]):
        self.tm = tm
        self.dropped = dropped

    def __deinit__(deinit self):
        self.dropped[] += 1

    def check(mut self) raises -> List[Term]:
        return [self.tm.mkBoolean(False)]


struct Failing(Plugin):
    var tm: TermManager
    var mode: Int
    var solver: Optional[Solver]

    def __init__(out self, tm: TermManager, mode: Int):
        self.tm = tm
        self.mode = mode
        self.solver = None

    def check(mut self) raises -> List[Term]:
        if self.mode == 0:
            raise Error("deliberate failure")
        if self.mode == 1:
            return [self.tm.mkInteger(7)]
        if self.mode == 2:
            return [self.tm.mkBoolean(True)]
        if self.mode == 4:
            return [Term()]
        _ = self.solver.value().checkSat()
        return List[Term]()


struct Listener(Plugin):
    var clauses: List[Term]
    var lemmas: List[Term]
    var fail: Bool

    def __init__(out self, fail: Bool = False):
        self.clauses = List[Term]()
        self.lemmas = List[Term]()
        self.fail = fail

    def notifySatClause(mut self, clause: Term) raises:
        self.clauses.append(clause)
        if self.fail:
            raise Error("notification failure")

    def notifyTheoryLemma(mut self, lemma: Term) raises:
        self.lemmas.append(lemma)
        if self.fail:
            raise Error("notification failure")


def simple_registration() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("sat-solver", "minisat")
    var plugin = ArcPointer(Reject(tm))
    solver.addPlugin(plugin)
    assert_true(solver.checkSat().isUnsat())
    assert_true(plugin[].calls > 0)


def retained_solver(tm: TermManager, dropped: ArcPointer[Int]) raises -> Solver:
    var solver = Solver(tm)
    solver.setOption("sat-solver", "minisat")
    solver.addPlugin(ArcPointer(Tracked(tm, dropped)))
    var parser = InputParser(solver)
    var borrowed = parser.getSolver()
    # Registration through a borrowed handle also survives that handle's scope.
    borrowed.addPlugin(ArcPointer(Tracked(tm, dropped)))
    return solver


def retained_parser(tm: TermManager, dropped: ArcPointer[Int]) raises -> InputParser:
    var solver = Solver(tm)
    solver.setOption("sat-solver", "minisat")
    var parser = InputParser(solver)
    parser.getSolver().addPlugin(ArcPointer(Tracked(tm, dropped)))
    return parser


def retained_command(tm: TermManager, dropped: ArcPointer[Int]) raises -> Command:
    var parser = retained_parser(tm, dropped)
    parser.setStringInput(InputLanguage.SMT_LIB_2_6, "(set-logic ALL)", "retained")
    return parser.nextCommand()


def lifetimes(dropped: ArcPointer[Int]) raises:
    var tm = TermManager()
    var solver = retained_solver(tm, dropped)
    assert_equal(dropped[], 0)
    assert_true(solver.checkSat().isUnsat())
    _ = solver^
    assert_equal(dropped[], 2)
    var parser = retained_parser(tm, dropped)
    assert_true(parser.getSolver().checkSat().isUnsat())
    _ = parser^
    assert_equal(dropped[], 3)
    var command = retained_command(tm, dropped)
    assert_equal(dropped[], 3)
    assert_equal(command.getCommandName(), "set-logic")
    _ = command^
    assert_equal(dropped[], 4)


def callback_errors() raises:
    for mode in range(5):
        var tm = TermManager()
        var other_tm = TermManager()
        var solver = Solver(tm)
        solver.setOption("sat-solver", "minisat")
        var plugin = ArcPointer(Failing(other_tm if mode == 2 else tm, mode))
        if mode == 3:
            plugin[].solver = solver
        solver.addPlugin(plugin)
        var caught = False
        try:
            _ = solver.checkSat()
        except e:
            var message = String(e)
            var expected = "deliberate failure"
            if mode == 1:
                expected = "Boolean terms"
            elif mode == 2:
                expected = "different term manager"
            elif mode == 3:
                expected = "cannot reenter"
            elif mode == 4:
                expected = "non-null Boolean terms"
            assert_true(expected in message, message)
            caught = True
        # Break the deliberate user-created cycle even for the reentry case.
        plugin[].solver = None
        assert_true(caught)
        caught = False
        try:
            _ = solver.checkSat()
        except e:
            assert_true("plugin callback" in String(e))
            caught = True
        assert_true(caught, "a failed callback must not expose a later solver result")


def listen(plugin: ArcPointer[Listener]) raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("sat-solver", "minisat")
    solver.setOption("plugin-notify-sat-clause-in-solve", "false")
    solver.addPlugin(plugin)
    var x = tm.mkConst(tm.getStringSort(), "x")
    var y = tm.mkConst(tm.getStringSort(), "y")
    solver.assertFormula(tm.mkTerm(Kind.OR, tm.mkTerm(Kind.STRING_CONTAINS, x, y), tm.mkTerm(Kind.STRING_CONTAINS, y, x)))
    solver.assertFormula(tm.mkTerm(Kind.GT, tm.mkTerm(Kind.STRING_LENGTH, x), tm.mkTerm(Kind.STRING_LENGTH, y)))
    assert_true(solver.checkSat().isSat())


def notifications() raises:
    var plugin = ArcPointer(Listener())
    listen(plugin)
    assert_true(len(plugin[].clauses) > 0)
    assert_true(len(plugin[].lemmas) > 0)
    # Callback arguments retained by user code survive the original solver/TM.
    for term in plugin[].clauses:
        assert_true(term.getSort().isBoolean())
    for term in plugin[].lemmas:
        assert_true(term.getSort().isBoolean())
    var failing = ArcPointer(Listener(True))
    var caught = False
    try:
        listen(failing)
    except e:
        assert_true("notification failure" in String(e))
        caught = True
    assert_true(caught)


def command_callback_error() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("sat-solver", "minisat")
    solver.setLogic("ALL")
    solver.addPlugin(ArcPointer(Failing(tm, 0)))
    var parser = InputParser(solver)
    parser.setStringInput(InputLanguage.SMT_LIB_2_6, "(check-sat)", "plugin")
    var command = parser.nextCommand()
    var caught = False
    try:
        _ = command.invoke(solver, parser.getSymbolManager())
    except e:
        assert_true("deliberate failure" in String(e))
        caught = True
    assert_true(caught)


def main() raises:
    simple_registration()
    var dropped = ArcPointer(Int(0))
    lifetimes(dropped)
    assert_equal(dropped[], 4)
    callback_errors()
    notifications()
    command_callback_error()
    print("plugin contracts passed")
