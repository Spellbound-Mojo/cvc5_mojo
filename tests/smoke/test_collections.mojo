"""Input buffers preserve order, duplicates, lifetimes and conversion errors."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import Kind, ProofFormat, Solver, Sort, Term, TermManager


def handle_lists(tm: TermManager) raises:
    for n in [0, 1, 2, 3, 4, 5, 7, 8, 9, 16, 17, 32, 33, 257]:
        var inputs = List[Term]()
        for i in range(n):
            inputs.append(tm.mkInteger((i * 37 % 101) - 50))
        var tuple = tm.mkTuple(inputs)
        var values = tuple.getTupleValue()
        assert_equal(len(values), n)
        for i in range(n):
            assert_equal(values[i], inputs[i])
            assert_equal(inputs[i], tm.mkInteger((i * 37 % 101) - 50))
        inputs.clear()
        _ = tuple^
        for i in range(n):
            assert_equal(values[i], tm.mkInteger((i * 37 % 101) - 50))


def variadic_and_scalars(tm: TermManager) raises:
    var integer = tm.getIntegerSort()
    var boolean = tm.getBooleanSort()
    assert_true(tm.mkTupleSort() == tm.mkTupleSort(List[Sort]()))
    assert_true(tm.mkTupleSort(integer) == tm.mkTupleSort([integer]))
    assert_true(tm.mkTupleSort(integer, boolean) == tm.mkTupleSort([integer, boolean]))
    assert_true(tm.mkTupleSort(integer, boolean, integer, boolean, integer, boolean, integer, boolean) ==
                tm.mkTupleSort([integer, boolean, integer, boolean, integer, boolean, integer, boolean]))
    var x = tm.mkConst(integer, "collection_x")
    var y = tm.mkConst(integer, "collection_y")
    assert_equal(tm.mkTerm(Kind.PI), tm.mkTerm(Kind.PI, List[Term]()))
    assert_equal(tm.mkTerm(Kind.NEG, x), tm.mkTerm(Kind.NEG, [x]))
    assert_equal(tm.mkTerm(Kind.SUB, x, y), tm.mkTerm(Kind.SUB, [x, y]))
    assert_equal(tm.mkTerm(Kind.ADD, x, y, x, y, x, y, x, y),
                 tm.mkTerm(Kind.ADD, [x, y, x, y, x, y, x, y]))
    var op = tm.mkOp(Kind.TUPLE_PROJECT, [2, 0, 2, 1])
    assert_equal(op, tm.mkOp(Kind.TUPLE_PROJECT, 2, 0, 2, 1))
    assert_equal(tm.mkOp(Kind.TUPLE_PROJECT), tm.mkOp(Kind.TUPLE_PROJECT, List[Int]()))
    for bad in [-1, 4294967296]:
        var caught = False
        try:
            _ = tm.mkOp(Kind.TUPLE_PROJECT, [2, 0, bad])
        except e:
            caught = "out of range" in String(e)
        assert_true(caught)
        assert_equal(tm.mkOp(Kind.TUPLE_PROJECT, [2, 0, 2, 1]), op)
    var a = tm.mkConst(boolean, "collection_a")
    var b = tm.mkConst(boolean, "collection_b")
    assert_equal(a.notTerm(), tm.mkTerm(Kind.NOT, a))
    assert_equal(a.andTerm(b), tm.mkTerm(Kind.AND, a, b))
    assert_equal(a.iteTerm(x, y), tm.mkTerm(Kind.ITE, a, x, y))


def strings_and_parallel_arrays(tm: TermManager) raises:
    var integer = tm.getIntegerSort()
    var boolean = tm.getBooleanSort()
    for n in [0, 1, 4, 5, 8, 9, 33]:
        var names = List[String]()
        var sorts = List[Sort]()
        for i in range(n):
            names.append(String("field_π_", i))
            sorts.append(integer if i % 2 == 0 else boolean)
        var record = tm.mkRecordSort(names, sorts)
        var constructor = record.getDatatype()[0]
        for i in range(n):
            assert_equal(constructor[i].getName(), names[i])
            assert_true(constructor[i].getCodomainSort() == sorts[i])
        if n > 0:
            # Reject a late element after earlier byte buffers were constructed.
            var previous = names[n - 1]
            names[n - 1] += chr(0)
            var caught = False
            try:
                _ = tm.mkRecordSort(names, sorts)
            except e:
                caught = "NUL" in String(e)
            assert_true(caught)
            names[n - 1] = previous
            assert_true(tm.mkRecordSort(names, sorts) == record)
        names.clear()
        sorts.clear()
        _ = record^
        for i in range(n):
            assert_equal(constructor[i].getName(), String("field_π_", i))
    assert_true(tm.mkRecordSort() == tm.mkRecordSort(List[String](), List[Sort]()))
    assert_true(tm.mkRecordSort(("a", integer), ("b", boolean)) ==
                tm.mkRecordSort(["a", "b"], [integer, boolean]))


def dictionary(tm: TermManager) raises:
    var solver = Solver(tm)
    solver.setOption("produce-proofs", "true")
    var a = tm.mkConst(tm.getBooleanSort(), "named_atom")
    var negative = a.notTerm()
    solver.assertFormula(a)
    solver.assertFormula(negative)
    assert_true(solver.checkSat().isUnsat())
    var proof = solver.getProof()[0]
    var names = Dict[Term, String]()
    names[a] = "named_positive"
    names[negative] = "named_negative"
    var text = solver.proofToString(proof, ProofFormat.ALETHE, names)
    assert_true("named_positive" in text and "named_negative" in text)
    names[negative] += chr(0)
    var caught = False
    try:
        _ = solver.proofToString(proof, ProofFormat.ALETHE, names)
    except e:
        caught = "NUL" in String(e)
    assert_true(caught)
    names[negative] = "named_negative"
    assert_equal(solver.proofToString(proof, ProofFormat.ALETHE, names), text)
    names.clear()
    assert_true(solver.proofToString(proof, ProofFormat.ALETHE, names).byte_length() > 0)


def main() raises:
    var tm = TermManager()
    handle_lists(tm)
    variadic_and_scalars(tm)
    strings_and_parallel_arrays(tm)
    dictionary(tm)
    assert_true(not tm._o[].api[].cvc5_has_error())
    print("collection boundary test passed")
