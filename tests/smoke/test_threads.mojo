"""Concurrent first use and deliberately overlapping thread-local errors."""

from std.ffi import external_call
from std.os import abort, getenv
from std.sys import argv
from std.testing import assert_equal, assert_true
from cvc5_mojo import TermManager, Solver, Kind
from cvc5_mojo._c.ffi import c_bytes, null
from cvc5_mojo._c.raw import CApi, CApiPtr, c_api
from memory_support import save_maps

comptime Barrier = Pointer[UInt64, MutUntrackedOrigin]
comptime THREADS = 16


@fieldwise_init
struct Work(Movable):
    var barrier: Barrier
    var slot: Int
    var rounds: Int
    var failure: Bool
    var api: CApiPtr
    var error: String


def rendezvous(barrier: Barrier):
    var result = external_call["pthread_barrier_wait", Int32](barrier)
    if result != 0 and result != -1:
        abort("pthread_barrier_wait failed")


def solve(work: Pointer[Work, MutUntrackedOrigin]) abi("C") -> UInt:
    rendezvous(work[].barrier)
    try:
        if work[].failure:
            for i in range(work[].rounds):
                var caught = False
                try:
                    _ = c_api()
                except e:
                    caught = True
                    if i == 0:
                        work[].error = String(e)
                    else:
                        assert_equal(String(e), work[].error)
                assert_true(caught)
            return 1
        var api = c_api()
        work[].api = api
        var tm = TermManager()
        var solver = Solver(tm)
        solver.setLogic("QF_LIA")
        var x = tm.mkConst(tm.getIntegerSort(), "x")
        for i in range(work[].rounds):
            assert_true(c_api() == api)
            var token = String("missing_option_", work[].slot, "_", i, "_π")
            var name = c_bytes(token)
            var value = c_bytes("true")
            var pending = (work[].slot + i) % 2 == 0
            # Bypass _check only here to leave a native TLS error pending while
            # other threads deliberately hold a clean state.
            if pending:
                api[]._cvc5_set_option(solver._handle().ptr, name.unsafe_ptr(), value.unsafe_ptr())
            rendezvous(work[].barrier)
            assert_equal(api[].cvc5_has_error(), pending)
            var caught = False
            try:
                api[]._check()
            except e:
                caught = True
                assert_true(String(e).startswith("cvc5: ") and token in String(e))
            assert_equal(caught, pending)
            assert_true(not api[].cvc5_has_error())
            rendezvous(work[].barrier)
            # Now every worker exercises normal generated error propagation.
            caught = False
            try:
                solver.setOption(token, "true")
            except e:
                caught = True
                assert_true(String(e).startswith("cvc5: ") and token in String(e))
            assert_true(caught and not api[].cvc5_has_error())
            solver.push()
            solver.assertFormula(tm.mkTerm(Kind.GT, x, tm.mkInteger(i)))
            solver.assertFormula(tm.mkTerm(Kind.LT, x, tm.mkInteger(i + 2)))
            assert_true(solver.checkSat().isSat())
            solver.assertFormula(tm.mkTerm(Kind.LT, x, tm.mkInteger(i)))
            assert_true(solver.checkSat().isUnsat())
            solver.pop()
            _ = (name^, value^)
        return 1
    except e:
        # Aborting avoids stranding other workers at a barrier on an unexpected
        # failure. The process runner classifies crashes as failures.
        abort(String(e))


def main() raises:
    var args = argv()
    var failure = len(args) > 1 and args[1] == "failure"
    var rounds = Int(args[2]) if len(args) > 2 else 50
    assert_true(rounds > 0)
    var storage = List[UInt64](length=8, fill=0)
    var barrier = storage.unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]()
    if external_call["pthread_barrier_init", Int32](barrier, UInt(0), UInt32(THREADS)) != 0:
        raise Error("pthread_barrier_init failed")
    var work = List[Work]()
    for i in range(THREADS):
        work.append(Work(barrier, i, rounds, failure, null[CApi](), String()))
    var threads = List[UInt](length=THREADS, fill=0)
    for i in range(THREADS):
        var ptr = work.unsafe_ptr().unsafe_offset(i).unsafe_origin_cast[MutUntrackedOrigin]()
        if external_call["pthread_create", Int32](Pointer(to=threads[i]), UInt(0), solve, ptr) != 0:
            abort("pthread_create failed")
    var passed = 0
    for i in range(THREADS):
        var result = UInt(0)
        assert_equal(external_call["pthread_join", Int32](threads[i], Pointer(to=result)), Int32(0))
        passed += Int(result)
    assert_equal(external_call["pthread_barrier_destroy", Int32](barrier), Int32(0))
    _ = storage^
    assert_equal(passed, THREADS)
    for i in range(THREADS):
        if failure:
            assert_true(work[i].error and work[i].error == work[0].error)
        else:
            assert_true(work[i].api == work[0].api and work[i].api != null[CApi]())
    var events = getenv("CVC5_MOJO_TEST_EVENTS")
    if events:
        with open(events, "a") as file:
            file.write("checkpoint\n")
    if len(args) > 3:
        save_maps(args[3])
    if failure:
        print("load-error")
        print(work[0].error)
    print("threads passed:", passed, "of", THREADS)
    print("rounds", rounds)
    print("thread test passed")
