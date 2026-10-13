"""Statistics snapshot timing; native filtering independently checks result counts."""
from std.sys import argv
from std.time import perf_counter_ns
from std.testing import assert_equal, assert_true
from cvc5_mojo import Kind, Solver, Statistics, TermManager
from cvc5_mojo._c.ffi import null
from memory_support import save_maps


def step[mode: Int](stats: Statistics) raises -> Int:
    comptime if mode < 4:
        return len(stats.get(Bool(mode & 1), Bool(mode & 2)))
    else:
        var count = 0
        for _ in stats:
            count += 1
        return count


def native_count(mode: Int, stats: Statistics) raises -> Int:
    var api = stats._api
    api[].cvc5_stats_iter_init(stats._h, mode == 4 or Bool(mode & 1), mode == 4 or Bool(mode & 2))
    var count = 0
    while api[].cvc5_stats_iter_has_next(stats._h):
        var name = null[Int8]()
        var stat = api[].cvc5_stats_iter_next(stats._h, Pointer(to=name))
        api[].cvc5_stat_release(stat)
        count += 1
    return count


@no_inline
def execute[mode: Int](count: Int, warmup: Int, maps: String) raises:
    assert_true(mode >= 0 and mode <= 4 and count > 0 and warmup >= 0)
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    var x = tm.mkConst(tm.getIntegerSort(), "x")
    solver.assertFormula(tm.mkTerm(Kind.GT, x, tm.mkInteger(0)))
    assert_true(solver.checkSat().isSat())
    var stats = solver.getStatistics()
    var expected = native_count(mode, stats)
    assert_true(expected > 0)
    var warmed = 0
    for _ in range(warmup):
        warmed += step[mode](stats)
    var total = 0
    var before = Int(perf_counter_ns())
    for _ in range(count):
        total += step[mode](stats)
    var elapsed = Int(perf_counter_ns()) - before
    assert_equal(total, count * expected)
    assert_equal(warmed, warmup * expected)
    save_maps(maps + ".maps")
    print(mode, count, elapsed, total, warmed)
    print("overhead passed")
    print("expected", expected)


def main() raises:
    var args = argv()
    assert_equal(len(args), 5)
    var mode = Int(args[1])
    var count = Int(args[2])
    var warmup = Int(args[3])
    var maps = String(args[4])
    if mode == 0:
        execute[0](count, warmup, maps)
    elif mode == 1:
        execute[1](count, warmup, maps)
    elif mode == 2:
        execute[2](count, warmup, maps)
    elif mode == 3:
        execute[3](count, warmup, maps)
    elif mode == 4:
        execute[4](count, warmup, maps)
    else:
        raise Error("unknown statistics workload")
