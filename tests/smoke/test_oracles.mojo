"""Oracle semantics, callback errors, retained arguments and owner lifetimes."""

from std.memory import ArcPointer
from std.testing import assert_equal, assert_true
from cvc5_mojo import Command, InputLanguage, InputParser, Kind, Oracle, Plugin, Solver, Sort, Term, TermManager


struct Increment(Oracle):
    var tm: TermManager
    var calls: Int
    var last: Term
    var dropped: ArcPointer[Int]

    def __init__(out self, tm: TermManager, dropped: ArcPointer[Int]) raises:
        self.tm = tm
        self.calls = 0
        self.last = Term()
        self.dropped = dropped

    def __deinit__(deinit self):
        self.dropped[] += 1

    def evaluate(mut self, arguments: List[Term]) raises -> Term:
        self.calls += 1
        assert_equal(len(arguments), 1)
        self.last = arguments[0]
        return self.tm.mkInteger(arguments[0].getIntegerValue() + 1)


struct Identity(Oracle):
    def __init__(out self):
        pass

    def evaluate(mut self, arguments: List[Term]) raises -> Term:
        return arguments[0]


struct Sum(Oracle):
    var tm: TermManager

    def __init__(out self, tm: TermManager):
        self.tm = tm

    def evaluate(mut self, arguments: List[Term]) raises -> Term:
        assert_equal(len(arguments), 2)
        return self.tm.mkInteger(arguments[0].getIntegerValue() + arguments[1].getIntegerValue())


struct FailingOracle(Oracle):
    var tm: TermManager
    var mode: Int
    var solver: Optional[Solver]

    def __init__(out self, tm: TermManager, mode: Int):
        self.tm = tm
        self.mode = mode
        self.solver = None

    def evaluate(mut self, arguments: List[Term]) raises -> Term:
        if self.mode == 0:
            raise Error("deliberate oracle error")
        if self.mode == 1:
            return Term()
        if self.mode == 2:
            return self.tm.mkTrue()
        if self.mode == 3:
            return self.tm.mkInteger(9)
        _ = self.solver.value().checkSat()
        return self.tm.mkInteger(0)


struct EmptyPlugin(Plugin):
    def __init__(out self):
        pass


def values_and_repeated_calls() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("oracles", "true")
    solver.setOption("produce-models", "true")
    solver.setOption("incremental", "true")
    solver.addPlugin(ArcPointer(EmptyPlugin()))
    var dropped = ArcPointer(Int(0))
    var callback = ArcPointer(Increment(tm, dropped))
    var sort = tm.getIntegerSort()
    var f = solver.declareOracleFun("increment", [sort], sort, callback)
    for i in range(64):
        solver.push()
        var application = tm.mkTerm(Kind.APPLY_UF, f, tm.mkInteger(i))
        solver.assertFormula(application.eqTerm(tm.mkInteger(i + 1)))
        assert_true(solver.checkSat().isSat())
        assert_equal(solver.getValue(application).getIntegerValue(), i + 1)
        solver.pop()
    assert_true(callback[].calls >= 64)
    assert_true(not callback[].last.isNull())
    assert_true(callback[].last.getSort() == sort)
    solver.assertFormula(tm.mkTerm(Kind.APPLY_UF, f, tm.mkInteger(3)).eqTerm(tm.mkInteger(5)))
    assert_true(solver.checkSat().isUnsat())
    assert_equal(dropped[], 0)
    _ = solver.getVersion()


def multiple_sorts_and_arguments() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("oracles", "true")
    var int_sort = tm.getIntegerSort()
    var sum = solver.declareOracleFun("sum", [int_sort, int_sort], int_sort, ArcPointer(Sum(tm)))
    solver.assertFormula(tm.mkTerm(Kind.APPLY_UF, sum, tm.mkInteger(-4), tm.mkInteger(7)).eqTerm(tm.mkInteger(3)))
    var bool_sort = tm.getBooleanSort()
    var identity = solver.declareOracleFun("bool_identity", [bool_sort], bool_sort, ArcPointer(Identity()))
    solver.assertFormula(tm.mkTerm(Kind.APPLY_UF, identity, tm.mkTrue()))
    var bv_sort = tm.mkBitVectorSort(8)
    var bv_identity = solver.declareOracleFun("bv_identity", [bv_sort], bv_sort, ArcPointer(Identity()))
    var bv = tm.mkBitVector(8, 42)
    solver.assertFormula(tm.mkTerm(Kind.APPLY_UF, bv_identity, bv).eqTerm(bv))
    assert_true(solver.checkSat().isSat())


def failure(mode: Int, message: String, boolean_result: Bool = False) raises:
    var tm = TermManager()
    var foreign = TermManager()
    var solver = Solver(tm)
    solver.setOption("oracles", "true")
    var callback = ArcPointer(FailingOracle(foreign if mode == 3 else tm, mode))
    if mode == 4:
        callback[].solver = solver
    var int_sort = tm.getIntegerSort()
    var result_sort = tm.getBooleanSort() if boolean_result else int_sort
    var f = solver.declareOracleFun("bad", [int_sort], result_sort, callback)
    var app = tm.mkTerm(Kind.APPLY_UF, f, tm.mkInteger(3))
    solver.assertFormula(app if boolean_result else app.eqTerm(tm.mkInteger(4)))
    var rejected = False
    try:
        _ = solver.checkSat()
    except e:
        rejected = "oracle callback" in String(e) and message in String(e)
    # Explicitly break the cycle this reentry test deliberately constructs.
    callback[].solver = None
    assert_true(rejected)
    rejected = False
    try:
        _ = solver.checkSat()
    except e:
        rejected = message in String(e)
    assert_true(rejected)


def registration_errors() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    var sort = tm.getIntegerSort()
    var callback = ArcPointer(Identity())
    var rejected = False
    try:
        _ = solver.declareOracleFun("disabled", [sort], sort, callback)
    except e:
        rejected = "oracles" in String(e)
    assert_true(rejected)
    solver.setOption("oracles", "true")
    var foreign = TermManager()
    for mode in range(4):
        rejected = False
        var domain = Sort() if mode == 0 else foreign.getIntegerSort() if mode == 1 else sort
        var codomain = Sort() if mode == 2 else foreign.getIntegerSort() if mode == 3 else sort
        try:
            _ = solver.declareOracleFun("invalid", [domain], codomain, callback)
        except e:
            rejected = "term manager" in String(e)
        assert_true(rejected)
    assert_true(solver.checkSat().isSat())


def command_error() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("ALL")
    solver.setOption("oracles", "true")
    var sort = tm.getIntegerSort()
    var f = solver.declareOracleFun("command_error", [sort], sort, ArcPointer(FailingOracle(tm, 0)))
    solver.assertFormula(tm.mkTerm(Kind.APPLY_UF, f, tm.mkInteger(1)).eqTerm(tm.mkInteger(2)))
    var parser = InputParser(solver)
    parser.setStringInput(InputLanguage.SMT_LIB_2_6, "(check-sat)", "oracle error")
    var command = parser.nextCommand()
    var rejected = False
    try:
        _ = command.invoke(solver, parser.getSymbolManager())
    except e:
        rejected = "deliberate oracle error" in String(e)
    assert_true(rejected)


def command_with_oracle(tm: TermManager, dropped: ArcPointer[Int]) raises -> Command:
    var solver = Solver(tm)
    solver.setLogic("ALL")
    solver.setOption("oracles", "true")
    var parser = InputParser(solver)
    var borrowed = parser.getSolver()
    var sort = tm.getIntegerSort()
    var f = borrowed.declareOracleFun("retained", [sort], sort, ArcPointer(Increment(tm, dropped)))
    borrowed.assertFormula(tm.mkTerm(Kind.APPLY_UF, f, tm.mkInteger(3)).eqTerm(tm.mkInteger(5)))
    assert_true(solver.checkSat().isUnsat())
    parser.setStringInput(InputLanguage.SMT_LIB_2_6, "(check-sat)", "oracle lifetime")
    return parser.nextCommand()


def hold_command(tm: TermManager, dropped: ArcPointer[Int]) raises:
    var command = command_with_oracle(tm, dropped)
    assert_equal(dropped[], 0)
    assert_true(not command.isNull())


def main() raises:
    values_and_repeated_calls()
    multiple_sorts_and_arguments()
    failure(0, "deliberate oracle error")
    failure(0, "deliberate oracle error", True)
    failure(1, "non-null")
    failure(2, "declared oracle sort")
    failure(3, "different term manager")
    failure(4, "cannot reenter")
    registration_errors()
    command_error()
    var tm = TermManager()
    var dropped = ArcPointer(Int(0))
    hold_command(tm, dropped)
    assert_equal(dropped[], 1)
    print("oracle contracts passed")
