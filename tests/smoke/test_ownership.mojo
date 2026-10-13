"""Borrowed owners, value containers, detached handles, and error unwinding.

Scope boundaries deliberately drop the original wrappers before the surviving
values are used. This complements the live-owner matched C controls.
"""
from std.testing import assert_equal, assert_true
from std.sys import argv
from cvc5_mojo import (
    Command, Grammar, InputLanguage, InputParser, Kind, Proof, Result, Solver,
    SymbolManager, SynthResult, Term, TermManager,
)
from cvc5_mojo._c.ffi import trace
from memory_support import resident_kb


def containers[T: ImplicitlyCopyable & Deinitable](first: T, var second: T) raises -> T:
    """Replace distinct values, copy/move, remove, and clear every container."""
    var items = List[T]()
    items.append(first)
    items.append(second)
    items[0] = second
    var removed = items.pop()
    items.clear()
    var slots = Dict[Int, T]()
    slots[0] = first
    slots[1] = removed^
    slots[0] = slots[1]
    var removed_slot = slots.pop(0)
    slots.clear()
    var optional = Optional[T](removed_slot^)
    var copy = optional.value()
    optional = second^
    _ = copy^
    var result = optional.value()
    optional = None
    assert_true(not optional)
    return result^


def detached_parser(external: Bool) raises -> InputParser:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_UF")
    if external:
        var sm = SymbolManager(tm)
        return InputParser(solver, sm)
    return InputParser(solver)


def borrowed_solver(external: Bool) raises -> Solver:
    var parser = detached_parser(external)
    var first = parser.getSolver()
    return containers(first, parser.getSolver())


def borrowed_symbols(external: Bool) raises -> SymbolManager:
    var parser = detached_parser(external)
    parser.setStringInput(InputLanguage.SMT_LIB_2_6, "(declare-fun p () Bool)", "symbols")
    _ = parser.nextCommand().invoke(parser.getSolver(), parser.getSymbolManager())
    return containers(parser.getSymbolManager(), parser.getSymbolManager())


def borrowed_tm() raises -> TermManager:
    # TermManager -> borrowed Solver -> InputParser -> native Solver -> native TM.
    var solver = borrowed_solver(False)
    return containers(solver.getTermManager(), solver.getTermManager())


def borrowed_result() raises -> Result:
    var solver = borrowed_solver(True)
    return solver.checkSat()


def detached_command() raises -> Command:
    var parser = detached_parser(False)
    parser.setStringInput(InputLanguage.SMT_LIB_2_6, "(assert true) (assert false)", "commands")
    var first = parser.nextCommand()
    var second = parser.nextCommand()
    var copy = containers(first, second^)
    assert_true(parser.nextCommand().isNull())
    return copy^


def detached_command_graph() raises -> Tuple[Command, Solver, SymbolManager]:
    var parser = detached_parser(False)
    parser.setStringInput(InputLanguage.SMT_LIB_2_6, "(assert false)", "command graph")
    return (parser.nextCommand(), parser.getSolver(), parser.getSymbolManager())


def check_borrowed() raises:
    for external in [False, True]:
        var solver = borrowed_solver(external)
        assert_equal(solver.getLogic(), "QF_UF")
        assert_true(solver.checkSat().isSat())
        var sm = borrowed_symbols(external)
        assert_equal(sm.getLogic(), "QF_UF")
        assert_equal(sm.getDeclaredTerms()[0].getSymbol(), "p")
    var tm = borrowed_tm()
    assert_equal(tm.mkInteger(19).getIntegerValue(), 19)
    assert_true(borrowed_result().isSat())
    var command = detached_command()
    assert_equal(command.getCommandName(), "assert")
    assert_equal(command.toString(), "(assert false)")
    var graph = detached_command_graph()
    var solver = graph[1]
    assert_equal(graph[0].invoke(solver, graph[2]), "")
    assert_true(solver.checkSat().isUnsat())


def detached_result() raises -> Result:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_UF")
    var sat = solver.checkSat()
    solver.assertFormula(tm.mkFalse())
    return containers(sat, solver.checkSat())


def detached_child() raises -> Proof:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("produce-proofs", "true")
    solver.assertFormula(tm.mkFalse())
    assert_true(solver.checkSat().isUnsat())
    var roots = solver.getProof()
    var children = roots[0].getChildren()
    return containers(roots[0], children.pop())


def detached_grammar() raises -> Grammar:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("sygus", "true")
    var start = tm.mkVar(tm.getBooleanSort(), "start")
    var first = solver.mkGrammar([], [start])
    var second = solver.mkGrammar([], [start])
    second.addRule(start, tm.mkFalse())
    return containers(first, second^)


def detached_synthesis() raises -> SynthResult:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("sygus", "true")
    _ = solver.synthFun("f", [], tm.getBooleanSort())
    solver.addSygusConstraint(tm.mkFalse())
    return containers(solver.checkSynth(), solver.checkSynth())


def check_handles() raises:
    assert_true(detached_result().isUnsat())
    var child = detached_child()
    assert_true(child.getResult().getSort().isBoolean())
    _ = child.getRule()
    var grammar = detached_grammar()
    var text = String()
    grammar.write_to(text)  # one conversion; repeated formatting is a separate finding
    assert_true("false" in text)
    assert_true(detached_synthesis().hasNoSolution())
    var tm = TermManager()
    var term = containers(tm.mkInteger(1), tm.mkInteger(2))
    var sort = containers(tm.getIntegerSort(), tm.getBooleanSort())
    var op = containers(tm.mkOp(Kind.BITVECTOR_EXTRACT, 2, 0), tm.mkOp(Kind.BITVECTOR_EXTRACT, 3, 1))
    var decl = containers(tm.mkDatatypeDecl("old"), tm.mkDatatypeDecl("Pair"))
    var ctor = containers(tm.mkDatatypeConstructorDecl("old"), tm.mkDatatypeConstructorDecl("pair"))
    ctor.addSelector("field", tm.getIntegerSort())
    decl.addConstructor(ctor)
    var datatype = tm.mkDatatypeSort(decl).getDatatype()
    var dt_copy = containers(datatype, datatype)
    var constructor = containers(datatype[0], datatype[0])
    var selector = containers(constructor[0], constructor[0])
    var stats = containers(tm.getStatistics(), tm.getStatistics())
    _ = tm^
    assert_equal(term.getIntegerValue(), 2)
    assert_true(sort.isBoolean())
    assert_equal(op[0].getIntegerValue(), 3)
    assert_equal(decl.getName(), "Pair")
    assert_true("pair" in String(ctor))
    assert_equal(dt_copy.getName(), "Pair")
    assert_equal(constructor.getName(), "pair")
    assert_equal(selector.getName(), "field")
    assert_true(selector.getCodomainSort().isInteger())
    assert_true(len(stats.get(True, True)) > 0)


struct Partial(Movable):
    var result: Result
    var terms: List[Term]
    var name: String

    def __init__(out self, solver: Solver, tm: TermManager) raises:
        self.result = solver.checkSat()
        self.terms = [tm.mkTrue(), tm.mkFalse()]
        # Fail after owned fields have been initialized, before completing self.
        self.name = tm.mkTrue().getSymbol()


def fail_with_live_values(solver: Solver, tm: TermManager, conversion: Bool) raises:
    var results = List[Result]()
    results.append(solver.checkSat())
    var values = Dict[Int, Term]()
    values[0] = tm.mkInteger(7)
    values[1] = tm.mkInteger(8)
    try:
        if conversion:
            _ = tm.mkConst(tm.getBooleanSort(), "bad" + chr(0) + "name")
        else:
            _ = values[0].getBooleanValue()
    finally:
        # Keep containers live across the throwing call, not just lexical scope.
        assert_true(results[0].isSat())
        assert_equal(values[1].getIntegerValue(), 8)


def check_exceptions() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_UF")
    for conversion in [False, True]:
        var caught = False
        try:
            fail_with_live_values(solver, tm, conversion)
        except e:
            caught = True
            assert_true("embedded NUL" in String(e) if conversion else "Boolean" in String(e))
        assert_true(caught)
        assert_true(solver.checkSat().isSat())
    var caught = False
    try:
        _ = Partial(solver, tm)
    except e:
        caught = True
        assert_true("symbol" in String(e))
    assert_true(caught)
    assert_true(solver.checkSat().isSat())
    var parser = InputParser(solver)
    parser.setStringInput(InputLanguage.SMT_LIB_2_6, "(assert", "invalid")
    caught = False
    try:
        _ = parser.nextCommand()
    except e:
        caught = True
        assert_true(String(e).byte_length() > 0)
    assert_true(caught)
    parser.setStringInput(InputLanguage.SMT_LIB_2_6, "(assert true)", "valid")
    assert_equal(parser.nextCommand().getCommandName(), "assert")
    assert_true(solver.checkSat().isSat())


def check_buffers() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_UF")
    var p = tm.mkConst(tm.getBooleanSort(), "p")
    solver.assertFormula(p)
    var assertions = solver.getAssertions()
    solver.assertFormula(p.notTerm())
    var later = solver.getAssertions()
    assert_equal(len(assertions), 1)
    assert_equal(len(later), 2)
    var info = solver.getOptionInfo("arith-prop")
    _ = solver.getOptionInfo("verbosity")
    var name = p.getSymbol()
    _ = tm.mkConst(tm.getBooleanSort(), "other").getSymbol()
    _ = solver^
    _ = tm^
    assert_equal(assertions[0].getSymbol(), "p")
    assert_equal(name, "p")
    assert_equal(info.name, "arith-prop")
    assert_true("both" in info.modes)


def main() raises:
    trace("ownership:borrowed")
    check_borrowed()
    trace("ownership:handles")
    check_handles()
    trace("ownership:exceptions")
    check_exceptions()
    trace("ownership:buffers")
    check_buffers()
    trace("ownership:done")
    var args = argv()
    if len(args) == 2:
        var iterations = Int(args[1])
        assert_true(iterations > 0)
        for _ in range(40):
            check_borrowed()
            check_exceptions()
        var before = resident_kb()
        for _ in range(iterations):
            check_borrowed()
            check_exceptions()
        var growth = resident_kb() - before
        print("borrowed-owner and exception rounds:", iterations, "growth:", growth, "KiB")
        assert_true(growth <= 4096, "discarded owner graphs or exception fields accumulate")
    print("ownership test passed")
