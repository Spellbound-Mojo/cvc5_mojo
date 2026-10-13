"""Returned collections remain owned snapshots, including partial iteration."""
from std.testing import assert_equal, assert_true
from cvc5_mojo import DatatypeConstructor, Kind, Solver, Stat, Statistics, Term, TermManager
from cvc5_mojo._c.ffi import CChars, OwnedIterator, c_bytes, to_strings


def detached_children(n: Int) raises -> OwnedIterator[Term]:
    var tm = TermManager()
    var terms = List[Term]()
    for i in range(n):
        terms.append(tm.mkInteger(i + 1))
    var expression = tm.mkInteger(0) if n == 0 else tm.mkTerm(Kind.NEG if n == 1 else Kind.ADD, terms)
    return expression.__iter__()


def detached_constructors(n: Int) raises -> OwnedIterator[DatatypeConstructor]:
    var tm = TermManager()
    var decl = tm.mkDatatypeDecl(String("Choices", n))
    for i in range(n):
        var ctor = tm.mkDatatypeConstructorDecl(String("case", i))
        for j in range(i % 4):
            ctor.addSelector(String("field", j), tm.getIntegerSort())
        decl.addConstructor(ctor)
    return tm.mkDatatypeSort(decl).getDatatype().__iter__()


def fail_with_iterator() raises:
    var items = detached_children(9)
    assert_equal(items.__next__().getIntegerValue(), 1)
    raise Error("stop iteration early")


def exhausted[T: Copyable & Deinitable](mut items: OwnedIterator[T]) raises:
    for _ in range(2):
        var stopped = False
        try:
            _ = items.__next__()
        except StopIteration:
            stopped = True
        assert_true(stopped)


def iterators() raises:
    for n in [0, 1, 2, 4, 5, 8, 9, 32, 33, 257]:
        var items = detached_children(n)
        for i in range(n):
            var child = items.__next__()
            assert_equal(child.getIntegerValue(), i + 1)
        exhausted(items)
    var partial = detached_children(9)
    var first = partial.__next__()
    _ = partial^
    assert_equal(first.getIntegerValue(), 1)
    var caught = False
    try:
        fail_with_iterator()
    except e:
        caught = String(e) == "stop iteration early"
    assert_true(caught)
    for n in [1, 2, 5, 9]:
        var constructors = detached_constructors(n)
        for count in range(n):
            var ctor = constructors.__next__()
            assert_equal(ctor.getName(), String("case", count))
            var fields = ctor.__iter__()
            _ = ctor^
            for index in range(count % 4):
                var field = fields.__next__()
                assert_equal(field.getName(), String("field", index))
                assert_true(field.getCodomainSort().isInteger())
            exhausted(fields)
        exhausted(constructors)


def snapshots() raises:
    var tm = TermManager()
    for n in [0, 1, 4, 5, 8, 9, 32, 33]:
        var solver = Solver(tm)
        for i in range(n):
            solver.assertFormula(tm.mkConst(tm.getBooleanSort(), String("snapshot_", i)))
        var held = solver.getAssertions()
        solver.resetAssertions()
        solver.assertFormula(tm.mkFalse())
        _ = solver.getAssertions()
        _ = solver^
        assert_equal(len(held), n)
        for i in range(n):
            assert_equal(held[i].getSymbol(), String("snapshot_", i))


def string_arrays() raises:
    for n in [0, 1, 4, 5, 8, 9, 32, 33]:
        var storage = List[List[Int8]]()
        var pointers = List[CChars]()
        for i in range(n):
            storage.append(c_bytes("" if i % 3 == 0 else String("name_π😀_", i)))
        for i in range(n):
            pointers.append(storage[i].unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]())
        var copied = to_strings(pointers.unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin](), UInt(n))
        for i in range(n):
            storage[i][0] = 0
        _ = (pointers^, storage^)
        assert_equal(len(copied), n)
        for i in range(n):
            assert_equal(copied[i], "" if i % 3 == 0 else String("name_π😀_", i))


def check_statistics(stats: Statistics) raises:
    var complete = stats.get(True, True)
    # Filtering uses the flags of the unfiltered iterator as an independent
    # selection oracle; indexing checks values independently of bulk traversal.
    for internal in [False, True]:
        for defaulted in [False, True]:
            var filtered = stats.get(internal, defaulted)
            var names = List[String]()
            for name, stat in stats:
                if (internal or not stat.internal) and (defaulted or not stat.default):
                    names.append(name)
                    assert_equal(String(filtered[name]), String(stat))
                    assert_equal(String(filtered[name]), String(stats[name]))
            assert_equal(len(filtered), len(names))
            var index = 0
            for name in filtered.keys():
                assert_equal(name, names[index])
                index += 1
    # A copied Statistics handle shares native iterator state. Public iterators
    # must finish taking their snapshot before later gets reset that state.
    var alias = stats
    var held = stats.__iter__()
    _ = alias.get()
    var count = 0
    for name in complete.keys():
        var entry = held.__next__()
        assert_equal(entry[0], name)
        assert_equal(String(entry[1]), String(complete[name]))
        count += 1
    assert_equal(count, len(complete))
    exhausted(held)


def detached_statistics() raises -> Tuple[Dict[String, Stat], Dict[String, Stat], OwnedIterator[Tuple[String, Stat]]]:
    var tm = TermManager()
    # TermManager statistics include empty filtered results and histograms.
    check_statistics(tm.getStatistics())
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    var x = tm.mkConst(tm.getIntegerSort(), "x")
    solver.assertFormula(tm.mkTerm(Kind.GT, x, tm.mkInteger(0)))
    assert_true(solver.checkSat().isSat())
    var stats = solver.getStatistics()
    check_statistics(stats)
    var first = stats.get(True, True)
    var second = stats.get(True, True)
    var iterator = stats.__iter__()
    return (first^, second^, iterator^)


def statistics_snapshots() raises:
    var snapshots = detached_statistics()
    ref first = snapshots[0]
    ref second = snapshots[1]
    ref iterator = snapshots[2]
    var saw_int = False
    var saw_double = False
    var saw_string = False
    var saw_histogram = False
    for entry in first.items():
        var held = iterator.__next__()
        assert_equal(held[0], entry.key)
        assert_equal(String(held[1]), String(entry.value))
        assert_equal(String(second[entry.key]), String(entry.value))
        ref value = entry.value.value
        if value.isa[Int]():
            saw_int = True
        elif value.isa[Float64]():
            saw_double = True
        elif value.isa[String]():
            saw_string = True
        else:
            saw_histogram = True
    assert_true(saw_int and saw_double and saw_string and saw_histogram)
    exhausted(iterator)
    # Mutations of nested dictionaries and strings cannot affect a separately
    # obtained snapshot, even after all native owners have been destroyed.
    var histogram_name = String("resource::steps::resource")
    var original = String(second[histogram_name])
    first[histogram_name].value[Dict[String, UInt64]]["binding-only"] = 999
    assert_equal(String(second[histogram_name]), original)
    var string_name = String("Normalize::pass_time")
    original = String(second[string_name])
    first[string_name].value[String] = "changed"
    assert_equal(String(second[string_name]), original)


def main() raises:
    iterators()
    snapshots()
    string_arrays()
    statistics_snapshots()
    print("returned collection test passed")
