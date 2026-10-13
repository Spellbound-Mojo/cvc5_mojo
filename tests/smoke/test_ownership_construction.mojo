"""Native constructor failure at each field; partial objects release their owners."""
from std.ffi import OwnedDLHandle
from std.sys import argv
from std.testing import assert_equal, assert_true
from cvc5_mojo import InputLanguage, InputParser, Solver, SymbolManager, Term, TermManager
from owner_fault_support import install, OWNER_COUNT, TermManager_ID, Solver_ID, SymbolManager_ID, InputParser_ID


struct Graph:
    var tm: TermManager
    var solver: Solver
    var sm: SymbolManager
    var parser: InputParser

    def __init__(out self, external: Bool) raises:
        self.tm = TermManager()
        self.solver = Solver(self.tm)
        self.sm = SymbolManager(self.tm)
        self.parser = InputParser(self.solver, self.sm) if external else InputParser(self.solver)


def construct(external: Bool) raises:
    var graph = Graph(external)
    assert_true(graph.parser.getSolver().checkSat().isSat())
    assert_equal(graph.parser.getSolver().getTermManager().mkInteger(7).getIntegerValue(), 7)


def check(shim: OwnedDLHandle, selected: Int, external: Bool) raises:
    var begin = shim.get_function[NoneType]("probe_begin")
    var metric = shim.get_function[Int32]("probe_metric")
    begin(Int32(selected))
    var caught = False
    try:
        construct(external)
    except e:
        caught = True
        assert_true(String(e).startswith("cvc5: "))
    assert_equal(caught, selected >= 0)
    assert_equal(metric(Int32(-1), Int32(0)), Int32(1 if selected >= 0 else 0))
    assert_equal(metric(Int32(-1), Int32(1)), Int32(0), "null owner deleted")
    var reached = True
    var order = [TermManager_ID, Solver_ID, SymbolManager_ID, InputParser_ID]
    assert_equal(len(order), OWNER_COUNT, "new owner needs construction coverage")
    for owner in order:
        var expected = Int32(1 if reached else 0)
        assert_equal(metric(Int32(owner), Int32(0)), expected, "constructor attempts")
        if owner == selected:
            reached = False
        expected = Int32(1 if reached else 0)
        assert_equal(metric(Int32(owner), Int32(1)), expected, "successful constructors")
        assert_equal(metric(Int32(owner), Int32(2)), expected, "owner deletion after scope or unwind")


def reject_mixed_managers(shim: OwnedDLHandle, solver: Solver, sm: SymbolManager) raises:
    var begin = shim.get_function[NoneType]("probe_begin")
    var metric = shim.get_function[Int32]("probe_metric")
    begin(Int32(-1))
    var caught = False
    try:
        var parser = InputParser(solver, sm)
        _ = parser^
    except e:
        caught = True
        assert_equal(String(e), "cvc5_mojo: InputParser solver and symbol manager must share a term manager")
    assert_true(caught, "mixed term managers accepted")
    assert_equal(metric(Int32(InputParser_ID), Int32(0)), Int32(0), "native parser constructor entered")
    assert_equal(metric(Int32(InputParser_ID), Int32(2)), Int32(0), "rejected parser deleted")
    # A rejected constructor must leave both owners usable and no native error.
    assert_true(solver.checkSat().isSat())
    assert_equal(len(sm.getDeclaredTerms()), 0)
    var recovered = InputParser(solver)
    assert_true(recovered.getSolver().checkSat().isSat())
    _ = recovered^
    assert_equal(metric(Int32(InputParser_ID), Int32(0)), Int32(1))
    assert_equal(metric(Int32(InputParser_ID), Int32(1)), Int32(1))
    assert_equal(metric(Int32(InputParser_ID), Int32(2)), Int32(1))


def mixed_managers(shim: OwnedDLHandle) raises:
    var first = TermManager()
    var second = TermManager()
    var solver = Solver(first)
    var sm = SymbolManager(second)
    reject_mixed_managers(shim, solver, sm)
    var copied_solver = solver
    var copied_sm = sm
    reject_mixed_managers(shim, copied_solver, copied_sm)
    var first_parser = InputParser(solver)
    var second_solver = Solver(second)
    var second_parser = InputParser(second_solver, sm)
    reject_mixed_managers(shim, first_parser.getSolver(), second_parser.getSymbolManager())


def shared_parser(solver: Solver, sm: SymbolManager, mode: Int) raises -> InputParser:
    if mode == 0:
        return InputParser(solver)
    if mode == 1:
        return InputParser(solver, None)
    if mode == 2:
        return InputParser(solver, sm)
    if mode == 3:
        var copied_solver = solver
        var copied_sm = sm
        return InputParser(copied_solver, copied_sm)
    if mode == 4:
        var parent = InputParser(solver, sm)
        return InputParser(parent.getSolver(), parent.getSymbolManager())
    # Different wrapper state, but the same underlying native term manager.
    var borrowed_tm = solver.getTermManager()
    var other_solver = Solver(borrowed_tm)
    var other_sm = SymbolManager(borrowed_tm)
    return InputParser(other_solver, other_sm)


def shared_term(mode: Int) raises -> Term:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_UF")
    var sm = SymbolManager(tm)
    var parser = shared_parser(solver, sm, mode)
    parser.setStringInput(InputLanguage.SMT_LIB_2_6, "(declare-const p Bool)", "shared managers")
    _ = parser.nextCommand().invoke(parser.getSolver(), parser.getSymbolManager())
    return parser.getSymbolManager().getDeclaredTerms()[0]


def main() raises:
    var shim = OwnedDLHandle(argv()[1])
    install(shim)
    try:
        for external in [False, True]:
            for selected in range(OWNER_COUNT):
                check(shim, selected, external)
                check(shim, -1, external)  # The checked call cleared native error state.
        mixed_managers(shim)
        for mode in range(6):
            var term = shared_term(mode)
            assert_equal(term.notTerm().toString(), "(not p)")
    finally:
        _ = shim^
    print("owner construction test passed")
