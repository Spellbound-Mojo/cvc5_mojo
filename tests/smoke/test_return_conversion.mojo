"""Inject decoding and native iterator errors; check exported references and recovery.

The test-only shared library replaces selected CApi callables in this process.
It counts exports, copies, and releases by pointer, including pending elements.
"""
from std.ffi import OwnedDLHandle, _DLCallable
from std.sys import argv
from std.testing import assert_equal, assert_true
from cvc5_mojo import InputLanguage, InputParser, Kind, Solver, Statistics, SymbolManager, Term, TermManager
from cvc5_mojo._c.raw import c_api
from cvc5_mojo._c.ffi import CChars, Ptr, c_bytes, library_path, to_string, unescape_smt_string
from memory_support import resident_kb


def install(shim: OwnedDLHandle) raises:
    var api = c_api()
    var main_path = c_bytes(library_path("libcvc5"))
    var parser_path = c_bytes(library_path("libcvc5parser"))
    shim.get_function[NoneType]("fault_libraries")(main_path.unsafe_ptr(), parser_path.unsafe_ptr())
    api[]._cvc5_sm_get_named_terms = rebind[_DLCallable[NoneType, MutUntrackedOrigin]](shim.get_function[NoneType]("test_cvc5_sm_get_named_terms"))
    api[]._cvc5_term_copy = rebind[_DLCallable[Ptr, MutUntrackedOrigin]](shim.get_function[Ptr]("test_cvc5_term_copy"))
    api[]._cvc5_term_release = rebind[_DLCallable[NoneType, MutUntrackedOrigin]](shim.get_function[NoneType]("test_cvc5_term_release"))
    api[]._cvc5_term_get_child = rebind[_DLCallable[Ptr, MutUntrackedOrigin]](shim.get_function[Ptr]("test_cvc5_term_get_child"))
    api[]._cvc5_get_option_names = rebind[_DLCallable[Pointer[CChars, MutUntrackedOrigin], MutUntrackedOrigin]](shim.get_function[Pointer[CChars, MutUntrackedOrigin]]("test_cvc5_get_option_names"))
    api[]._cvc5_stats_get = rebind[_DLCallable[Ptr, MutUntrackedOrigin]](shim.get_function[Ptr]("test_cvc5_stats_get"))
    api[]._cvc5_stats_iter_next = rebind[_DLCallable[Ptr, MutUntrackedOrigin]](shim.get_function[Ptr]("test_cvc5_stats_iter_next"))
    api[]._cvc5_stat_copy = rebind[_DLCallable[Ptr, MutUntrackedOrigin]](shim.get_function[Ptr]("test_cvc5_stat_copy"))
    api[]._cvc5_stat_release = rebind[_DLCallable[NoneType, MutUntrackedOrigin]](shim.get_function[NoneType]("test_cvc5_stat_release"))
    api[]._cvc5_stat_get_histogram = rebind[_DLCallable[NoneType, MutUntrackedOrigin]](shim.get_function[NoneType]("test_cvc5_stat_get_histogram"))
    api[]._cvc5_stat_get_string = rebind[_DLCallable[CChars, MutUntrackedOrigin]](shim.get_function[CChars]("test_cvc5_stat_get_string"))
    api[]._cvc5_get_option_info = rebind[_DLCallable[NoneType, MutUntrackedOrigin]](shim.get_function[NoneType]("test_cvc5_get_option_info"))


def convert(mode: Int, sm: SymbolManager, solver: Solver, stats: Statistics, expression: Term) raises:
    if mode == 1:
        var named = sm.getNamedTerms()
        assert_equal(len(named), 3)
        for entry in named.items():
            assert_equal(entry.value, "name_" + entry.key.getSymbol())
    elif mode == 2:
        assert_true("produce-models" in solver.getOptionNames())
    elif mode == 3:
        assert_true(len(stats.get(True, True)) > 0)
    elif mode == 4:
        assert_true(len(stats["resource::steps::resource"].value[Dict[String, UInt64]]) >= 3)
    elif mode == 5:
        assert_true(stats["Normalize::pass_time"].value.isa[String]())
    elif mode == 6:
        var info = solver.getOptionInfo("arith-prop")
        assert_equal(info.name, "arith-prop")
        assert_true("both" in info.modes)
    elif mode == 7:
        var count = 0
        for child in expression:
            assert_equal(child.getSymbol(), ["p", "q", "r"][count])
            count += 1
        assert_equal(count, 3)
    elif mode == 8:
        var count = 0
        for _ in stats:
            count += 1
        assert_true(count > 0)
    elif mode == 9 or mode == 10:
        assert_true(len(stats.get(True, True)) > 0)


def fault_case(shim: OwnedDLHandle, mode: Int, position: Int, sm: SymbolManager, solver: Solver, stats: Statistics, expression: Term, verbose: Bool) raises:
    var begin = shim.get_function[NoneType]("fault_begin")
    var end = shim.get_function[NoneType]("fault_end")
    var metric = shim.get_function[Int32]("fault_metric")
    begin(Int32(mode), Int32(position))
    var caught = False
    try:
        convert(mode, sm, solver, stats, expression)
    except e:
        caught = True
        if mode == 7:
            assert_true(String(e).startswith("cvc5: ") and "index" in String(e))
        else:
            assert_true("invalid UTF-8" in String(e))
    finally:
        end()
    if verbose:
        print("conversion", mode, "position", position, "caught", caught,
              "injected", metric(Int32(0)), "exports", metric(Int32(1)),
              "copies", metric(Int32(2)), "releases", metric(Int32(3)),
              "outstanding", metric(Int32(6)))
    assert_equal(caught, position >= 0)
    assert_equal(metric(Int32(0)), Int32(1 if position >= 0 else 0))
    assert_equal(metric(Int32(5)), Int32(0), "unmatched or duplicate native release")
    assert_equal(metric(Int32(6)), Int32(0), "unreleased native result references")
    if mode == 1:
        assert_equal(metric(Int32(1)), Int32(3))
    elif mode >= 3 and mode <= 5:
        assert_true(metric(Int32(1)) > 0)
    elif mode == 7:
        assert_equal(metric(Int32(1)), Int32(3 if position < 0 else position))
        assert_equal(metric(Int32(2)), Int32(0))
    if mode == 3 or mode == 8:
        if position >= 0:
            assert_equal(metric(Int32(1)), Int32(position + 1))
    if (mode >= 3 and mode <= 5) or mode >= 8:
        assert_true(metric(Int32(1)) > 0)
        assert_equal(metric(Int32(2)), Int32(0))
    assert_equal(metric(Int32(1)) + metric(Int32(2)), metric(Int32(3)))
    # Exercise the same public operation after disabling corruption.
    convert(mode, sm, solver, stats, expression)


def check_buffers() raises:
    var invalid: List[Int8] = [111, 107, -1, 0]
    var caught = False
    try:
        _ = to_string(invalid.unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]())
    except:
        caught = True
    finally:
        _ = invalid^  # The explicit origin cast must not shorten buffer lifetime.
    assert_true(caught)
    var valid: List[Int8] = [111, 107, 0]
    var copied = to_string(valid.unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]())
    _ = valid^
    assert_equal(copied, "ok")
    for malformed in ['"prefix\\u{D800}"', '"prefix\\u{110000}"', '"prefix\\u{12"', '"prefix\\x"', '"prefix"oops"']:
        caught = False
        try:
            _ = unescape_smt_string(malformed)
        except:
            caught = True
        assert_true(caught)
        assert_equal(unescape_smt_string('"good\\u{0}end"'), "good" + chr(0) + "end")


def exercise(shim: OwnedDLHandle, only: Int, verbose: Bool) raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_UF")
    var parser = InputParser(solver)
    parser.setStringInput(InputLanguage.SMT_LIB_2_6,
        "(declare-fun p () Bool)(declare-fun q () Bool)(declare-fun r () Bool)"
        "(assert (! p :named name_p))(assert (! q :named name_q))(assert (! r :named name_r))", "conversions")
    var sm = parser.getSymbolManager()
    while not parser.done():
        var command = parser.nextCommand()
        if command.isNull():
            break
        _ = command.invoke(solver, sm)
    assert_true(solver.checkSat().isSat())
    var stats = solver.getStatistics()
    var expression = tm.mkTerm(Kind.OR, sm.getDeclaredTerms())
    var first_histogram = 0
    var strings = 0
    for _, stat in stats:
        if stat.value.isa[String]():
            strings += 1
        elif stat.value.isa[Dict[String, UInt64]]() and first_histogram == 0:
            first_histogram = len(stat.value[Dict[String, UInt64]])
    assert_true(first_histogram > 0 and strings > 0)
    var sizes = [3, len(solver.getOptionNames()), len(stats.get(True, True)),
                 len(stats["resource::steps::resource"].value[Dict[String, UInt64]]),
                 1, len(solver.getOptionInfo("arith-prop").modes), 3,
                 len(stats.get(True, True)), first_histogram, strings]
    for mode in range(1, 11):
        if only and mode != only:
            continue
        fault_case(shim, mode, -1, sm, solver, stats, expression, verbose)
        var size = sizes[mode - 1]
        var positions: List[Int] = [0]
        if size > 1:
            positions.append(size // 2)
            positions.append(size - 1)
        for position in positions:
            fault_case(shim, mode, position, sm, solver, stats, expression, verbose)
        assert_true(solver.checkSat().isSat())
    check_buffers()


def main() raises:
    var args = argv()
    assert_true(len(args) >= 2)
    var shim = OwnedDLHandle(args[1])
    install(shim)
    var only = Int(args[2]) if len(args) >= 3 else 0
    var rounds = Int(args[3]) if len(args) >= 4 else 0
    try:
        exercise(shim, only, True)
        if rounds:
            for _ in range(10):
                exercise(shim, only, False)
            var before = resident_kb()
            for _ in range(rounds):
                exercise(shim, only, False)
            var growth = resident_kb() - before
            print("conversion cleanup rounds", rounds, "growth", growth, "KiB")
            assert_true(growth <= 4096)
    finally:
        _ = shim^
    print("return conversion test passed")
