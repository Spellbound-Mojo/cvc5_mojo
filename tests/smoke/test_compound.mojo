"""Compound conversions against compound.c's independent native observations.

Raw mode calls CApi at the crossing under test, with public wrappers used to
construct/own fixtures. Public mode exercises the generated marshaling.
"""
from std.sys import argv
from std.testing import assert_equal, assert_true
from cvc5_mojo import DatatypeDecl, Kind, Solver, Sort, Term, TermManager
from cvc5_mojo._c.ffi import c_bytes, null, to_string
from cvc5_mojo._c.raw import Cvc5DatatypeDecl, Cvc5OptionInfo, Cvc5Result, Cvc5Sort, Cvc5Term
from memory_support import save_maps


def scalar_outputs(tm: TermManager, raw: Bool) raises:
    var api = tm._o[].api
    var r32 = tm.mkReal("-2147483648/4294967295")
    var r64 = tm.mkReal("-9223372036854775808/18446744073709551615")
    if raw:
        var n32: List[Int32] = [12345, 0, 12345]
        var d32: List[UInt32] = [12345, 0, 12345]
        var n64: List[Int64] = [12345, 0, 12345]
        var d64: List[UInt64] = [12345, 0, 12345]
        api[].cvc5_term_get_real32_value(r32._h, n32.unsafe_ptr().unsafe_offset(1), d32.unsafe_ptr().unsafe_offset(1))
        api[].cvc5_term_get_real64_value(r64._h, n64.unsafe_ptr().unsafe_offset(1), d64.unsafe_ptr().unsafe_offset(1))
        assert_true(n32[0] == 12345 and n32[2] == 12345 and d32[0] == 12345 and d32[2] == 12345)
        assert_true(n64[0] == 12345 and n64[2] == 12345 and d64[0] == 12345 and d64[2] == 12345)
        assert_true(n32[1] == Int32.MIN and d32[1] == UInt32.MAX)
        assert_true(n64[1] == Int64.MIN and d64[1] == UInt64.MAX)
        print("real32", String(n32[1], "/", d32[1]))
        print("real64", String(n64[1], "/", d64[1]))
    else:
        assert_equal(String(r32.getRealValue()), "-2147483648/4294967295")
        assert_equal(String(r64.getRealValue()), "-9223372036854775808/18446744073709551615")
        print("real32", r32.getRealValue())
        print("real64", r64.getRealValue())
    var bits = tm.mkBitVector(16, 0xbeef)
    var fp = tm.mkFloatingPoint(5, 11, bits)
    if raw:
        var ew: List[UInt32] = [12345, 0, 12345]
        var sw: List[UInt32] = [12345, 0, 12345]
        var value: List[Cvc5Term] = [bits._h, Cvc5Term(null[NoneType]()), bits._h]
        api[].cvc5_term_get_fp_value(fp._h, ew.unsafe_ptr().unsafe_offset(1), sw.unsafe_ptr().unsafe_offset(1), value.unsafe_ptr().unsafe_offset(1))
        assert_true(ew[0] == 12345 and ew[2] == 12345 and sw[0] == 12345 and sw[2] == 12345)
        assert_true(value[0].ptr == bits._h.ptr and value[2].ptr == bits._h.ptr)
        assert_true(ew[1] == 5 and sw[1] == 11 and api[].cvc5_term_is_equal(value[1], bits._h))
        print("fp", ew[1], sw[1], to_string(api[].cvc5_term_get_bv_value(value[1], 16)))
        api[].cvc5_term_release(value[1])
        var caught = False
        try:
            api[].cvc5_term_get_fp_value(r32._h, ew.unsafe_ptr().unsafe_offset(1), sw.unsafe_ptr().unsafe_offset(1), value.unsafe_ptr().unsafe_offset(1))
        except e:
            caught = String(e).startswith("cvc5: ")
        assert_true(caught)
        api[].cvc5_term_get_fp_value(fp._h, ew.unsafe_ptr().unsafe_offset(1), sw.unsafe_ptr().unsafe_offset(1), value.unsafe_ptr().unsafe_offset(1))
        api[].cvc5_term_release(value[1])
    else:
        var value = fp.getFloatingPointValue()
        assert_true(value[0] == 5 and value[1] == 11 and value[2] == bits)
        print("fp", value[0], value[1], value[2].getBitVectorValue(16))
        var caught = False
        try:
            _ = r32.getFloatingPointValue()
        except e:
            caught = String(e).startswith("cvc5: ")
        assert_true(caught)
        assert_equal(fp.getFloatingPointValue()[2], bits)
    assert_true(not api[].cvc5_has_error())
    print("fp-error recovered")
    var sort = tm.mkUninterpretedSort("U")
    var constraint = tm.mkCardinalityConstraint(sort, 4294967295)
    if raw:
        var out: List[Cvc5Sort] = [sort._h, Cvc5Sort(null[NoneType]()), sort._h]
        var upper: List[UInt32] = [12345, 0, 12345]
        api[].cvc5_term_get_cardinality_constraint(constraint._h, out.unsafe_ptr().unsafe_offset(1), upper.unsafe_ptr().unsafe_offset(1))
        assert_true(out[0].ptr == sort._h.ptr and out[2].ptr == sort._h.ptr)
        assert_true(upper[0] == 12345 and upper[2] == 12345)
        assert_true(api[].cvc5_sort_is_equal(out[1], sort._h) and upper[1] == UInt32.MAX)
        print("cardinality", upper[1])
        api[].cvc5_sort_release(out[1])
    else:
        var value = constraint.getCardinalityConstraint()
        assert_true(value[0] == sort)
        assert_equal(value[1], 4294967295)
        print("cardinality", value[1])
    # Raw handles do not carry the lifetime of the wrapper they came from.
    _ = (r32^, r64^, bits^, fp^, sort^, constraint^)


def arrays(tm: TermManager, raw: Bool) raises:
    var api = tm._o[].api
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("produce-models", "true")
    var size: List[UInt] = [12345, 999, 12345]
    if raw:
        _ = api[].cvc5_get_assertions(solver._handle(), size.unsafe_ptr().unsafe_offset(1))
        assert_equal(size[1], UInt(0))
    else:
        assert_equal(len(solver.getAssertions()), 0)
    print("assertions 0")
    assert_true(solver.checkSat().isSat())
    for n in [0, 1, 2, 7, 31, 257]:
        var inputs = List[Term]()
        for i in range(n):
            inputs.append(tm.mkInteger((i * 37 % 101) - 50))
        var checksum = 0
        if raw:
            var handles = List[Cvc5Term]()
            for term in inputs:
                handles.append(term._h)
            var native = api[].cvc5_get_values(solver._handle(), UInt(n), handles.unsafe_ptr(), size.unsafe_ptr().unsafe_offset(1))
            assert_equal(size[1], UInt(n))
            var held = List[Cvc5Term]()
            for i in range(n):
                held.append(native[unsafe_offset=i])
            var later = tm.mkInteger(999)
            var replaced = api[].cvc5_get_values(solver._handle(), 1, Pointer(to=later._h), size.unsafe_ptr().unsafe_offset(1))
            api[].cvc5_term_release(replaced[])
            _ = later^
            for i in range(n):
                var value = Int(api[].cvc5_term_get_int64_value(held[i]))
                assert_equal(value, (i * 37 % 101) - 50)
                checksum += (i + 1) * value
                api[].cvc5_term_release(held[i])
            _ = inputs^
        else:
            var held = solver.getValue(inputs)
            assert_equal(len(held), n)
            _ = solver.getValue([tm.mkInteger(999)])
            for i in range(n):
                var value = Int(held[i].getIntegerValue())
                assert_equal(value, (i * 37 % 101) - 50)
                checksum += (i + 1) * value
        assert_true(size[0] == 12345 and size[2] == 12345)
        print("values", n, checksum)
    _ = solver^
    var core_solver = Solver(tm)
    core_solver.setOption("produce-unsat-cores", "true")
    var ff = tm.mkFalse()
    core_solver.assertFormula(ff)
    if raw:
        var result = Cvc5Result(null[NoneType]())
        var core = api[].cvc5_get_timeout_core(core_solver._handle(), Pointer(to=result), size.unsafe_ptr().unsafe_offset(1))
        assert_true(api[].cvc5_result_is_unsat(result) and size[1] == 1 and api[].cvc5_term_is_equal(core[], ff._h))
        api[].cvc5_term_release(core[])
        api[].cvc5_result_release(result)
    else:
        var core = core_solver.getTimeoutCore()
        assert_true(core[0].isUnsat() and len(core[1]) == 1 and core[1][0] == ff)
    print("timeout-core unsat 1")
    _ = (core_solver^, ff^)


def symbol(tm: TermManager, kind: Int, mode: Int, raw: Bool) raises -> Tuple[Bool, String]:
    var name: Optional[String] = None
    if mode >= 2:
        name = "" if mode == 2 else "sigma_π"
    var api = tm._o[].api
    var integer = tm.getIntegerSort()
    if kind < 2:
        var term = Term()
        if raw:
            var bytes = c_bytes(name.value()) if name else List[Int8]()
            var p = bytes.unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]() if name else null[Int8]()
            var h = api[].cvc5_mk_const(tm._handle(), integer._h, p) if kind == 0 else api[].cvc5_mk_var(tm._handle(), integer._h, p)
            _ = bytes^
            term = Term(api, tm._handle(), h)
        elif kind == 0:
            term = tm.mkConst(integer) if mode == 0 else tm.mkConst(integer, name)
        else:
            term = tm.mkVar(integer) if mode == 0 else tm.mkVar(integer, name)
        _ = integer^
        return (term.hasSymbol(), term.getSymbol() if term.hasSymbol() else "-")
    var sort = Sort()
    if raw:
        var bytes = c_bytes(name.value()) if name else List[Int8]()
        var p = bytes.unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]() if name else null[Int8]()
        var h: Cvc5Sort
        try:
            if kind == 2:
                h = api[].cvc5_mk_param_sort(tm._handle(), p)
            elif kind == 3:
                h = api[].cvc5_mk_uninterpreted_sort(tm._handle(), p)
            else:
                h = api[].cvc5_mk_uninterpreted_sort_constructor_sort(tm._handle(), 2, p)
        finally:
            _ = bytes^
        sort = Sort(api, tm._handle(), h)
    elif kind == 2:
        sort = tm.mkParamSort() if mode == 0 else tm.mkParamSort(name)
    elif kind == 3:
        sort = tm.mkUninterpretedSort() if mode == 0 else tm.mkUninterpretedSort(name)
    else:
        sort = tm.mkUninterpretedSortConstructorSort(2) if mode == 0 else tm.mkUninterpretedSortConstructorSort(2, name)
    return (sort.hasSymbol(), sort.getSymbol() if sort.hasSymbol() else "-")


def symbols(tm: TermManager, raw: Bool) raises:
    for kind in range(5):
        for mode in range(4):
            if kind == 2 and mode < 2:
                # The cached native C implementation rejects NULL despite its
                # header's nullable claim. Do not silently substitute an empty name.
                var caught = False
                try:
                    _ = symbol(tm, kind, mode, raw)
                except e:
                    caught = "unexpected NULL" in String(e)
                assert_true(caught)
                assert_true(not tm._o[].api[].cvc5_has_error())
                print("symbol", kind, mode, "rejected")
            else:
                var value = symbol(tm, kind, mode, raw)
                print("symbol", kind, mode, Int(value[0]), value[1])


def define(solver: Solver, funs: List[Term], rows: List[List[Term]], bodies: List[Term], mode: Int, raw: Bool) raises:
    if not raw:
        if mode == 0:
            solver.defineFunsRec(funs, rows, bodies)
        else:
            solver.defineFunsRec(funs, rows, bodies, mode == 2)
        return
    var fs = List[Cvc5Term]()
    var bs = List[Cvc5Term]()
    var sizes = List[UInt]()
    var storage = List[List[Cvc5Term]]()
    for i in range(len(funs)):
        fs.append(funs[i]._h)
        bs.append(bodies[i]._h)
        var row = List[Cvc5Term]()
        for term in rows[i]:
            row.append(term._h)
        sizes.append(UInt(len(row)))
        storage.append(row^)
    var pointers = List[Pointer[Cvc5Term, MutUntrackedOrigin]]()
    for i in range(len(storage)):
        pointers.append(storage[i].unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]())
    try:
        solver._o[].api[].cvc5_define_funs_rec(solver._handle(), UInt(len(fs)), fs.unsafe_ptr(), sizes.unsafe_ptr(), pointers.unsafe_ptr(), bs.unsafe_ptr(), mode == 2)
    finally:
        _ = storage^


def nested(tm: TermManager, mode: Int, raw: Bool) raises:
    var solver = Solver(tm)
    solver.setLogic("ALL")
    var integer = tm.getIntegerSort()
    var funs: List[Term] = [tm.mkConst(integer, "f0"), tm.mkConst(tm.mkFunctionSort([integer], integer), "f1"), tm.mkConst(tm.mkFunctionSort([integer, integer], integer), "f2")]
    var x = tm.mkVar(integer, "x")
    var y = tm.mkVar(integer, "y")
    var z = tm.mkVar(integer, "z")
    var rows: List[List[Term]] = [[], [x], [y, z]]
    var bodies: List[Term] = [tm.mkInteger(7), tm.mkTerm(Kind.ADD, x, tm.mkInteger(1)), tm.mkTerm(Kind.SUB, y, z)]
    var caught = False
    try:
        define(solver, funs, [[], [tm.mkInteger(1)], [y, z]], bodies, 1, raw)
    except e:
        caught = String(e).startswith("cvc5: ")
    assert_true(caught)
    if not raw:
        # These shapes have no safe equivalent C call: C cannot see the lengths
        # of each outer buffer. Each guard must reject before the native call.
        for part in range(3):
            caught = False
            try:
                if part == 0:
                    solver.defineFunsRec(funs, [[], [x]], bodies)
                elif part == 1:
                    solver.defineFunsRec(funs, rows, [bodies[0]])
                else:
                    _ = tm.mkRecordSort(["a", "b"], [integer])
            except e:
                caught = "must have the same length" in String(e)
            assert_true(caught)
    solver.push()
    define(solver, funs, rows, bodies, mode, raw)
    var calls: List[Term] = [funs[0], tm.mkTerm(Kind.APPLY_UF, funs[1], tm.mkInteger(7)), tm.mkTerm(Kind.APPLY_UF, funs[2], tm.mkInteger(7), tm.mkInteger(1))]
    var expected = [7, 8, 6]
    for i in range(3):
        solver.push()
        solver.assertFormula(tm.mkTerm(Kind.DISTINCT, calls[i], tm.mkInteger(expected[i])))
        assert_true(solver.checkSat().isUnsat())
        solver.pop()
    solver.pop()
    solver.assertFormula(tm.mkTerm(Kind.EQUAL, funs[0], tm.mkInteger(1)))
    var result = solver.checkSat()
    assert_true(result.isUnsat() if mode == 2 else result.isSat())
    print("nested", mode, "unsat" if mode == 2 else "sat")


def declaration(tm: TermManager, name: String) raises -> DatatypeDecl:
    var decl = tm.mkDatatypeDecl(name)
    decl.addConstructor(tm.mkDatatypeConstructorDecl("make_" + name))
    return decl^


def bulk_sorts(tm: TermManager, raw: Bool) raises:
    var api = tm._o[].api
    for n in [1, 7]:
        var decls = List[DatatypeDecl]()
        for i in range(n):
            decls.append(declaration(tm, String("D", n, "_", i)))
        var saved = List[Sort]()
        if raw:
            var inputs = List[Cvc5DatatypeDecl]()
            for decl in decls:
                inputs.append(decl._h)
            var sorts = api[].cvc5_mk_dt_sorts(tm._handle(), UInt(n), inputs.unsafe_ptr())
            # C supplies no output length here: one export per input declaration.
            for i in range(n):
                saved.append(Sort(api, tm._handle(), sorts[unsafe_offset=i]))
            _ = decls^
        else:
            saved = tm.mkDatatypeSorts(decls)
        _ = tm.mkDatatypeSorts([declaration(tm, String("Spare", n))])
        assert_equal(len(saved), n)
        for i in range(n):
            assert_equal(saved[i].getDatatype().getName(), String("D", n, "_", i))
        print("datatype-array", n)


struct GuardedInfo(Movable):
    var before: UInt64
    var info: Cvc5OptionInfo
    var after: UInt64

    def __init__(out self):
        self.before = 12345
        self.info = Cvc5OptionInfo()
        self.after = 12345


def options(tm: TermManager, raw: Bool) raises:
    var solver = Solver(tm)
    var names = ["bv-abstraction-size", "enum-inst-limit", "deep-restart-factor", "produce-models"]
    var values = ["18446744073709551615", "-17", "3.5", "true"]
    for i in range(4):
        solver.setOption(names[i], values[i])
        if raw:
            var box = GuardedInfo()
            var name = c_bytes(names[i])
            tm._o[].api[].cvc5_get_option_info(solver._handle(), name.unsafe_ptr(), Pointer(to=box.info))
            assert_true(box.before == 12345 and box.after == 12345)
            assert_true(box.info.is_set_by_user())
            if i == 0:
                assert_equal(box.info.info_uint_cur(), UInt64.MAX)
                assert_equal(box.info.info_uint_max(), UInt64.MAX)
                print("option", i, box.info.info_uint_cur())
            elif i == 1:
                assert_equal(box.info.info_int_cur(), Int64(-17))
                print("option", i, box.info.info_int_cur())
            elif i == 2:
                assert_equal(box.info.info_double_cur(), Float64(3.5))
                print("option", i, box.info.info_double_cur())
            else:
                assert_true(box.info.info_bool_cur())
                print("option", i, Int(box.info.info_bool_cur()))
        else:
            var info = solver.getOptionInfo(names[i])
            assert_true(info.setByUser)
            if i == 0:
                assert_equal(info.current.value()[UInt64], UInt64.MAX)
                assert_equal(info.maximum.value()[UInt64], UInt64.MAX)
                print("option", i, info.current.value()[UInt64])
            elif i == 1:
                assert_equal(info.current.value()[Int], -17)
                print("option", i, info.current.value()[Int])
            elif i == 2:
                assert_equal(info.current.value()[Float64], Float64(3.5))
                print("option", i, info.current.value()[Float64])
            else:
                assert_true(info.current.value()[Bool])
                print("option", i, Int(info.current.value()[Bool]))
    _ = solver^


def main() raises:
    var args = argv()
    assert_equal(len(args), 3)
    assert_true(args[1] == "raw" or args[1] == "public")
    var raw = args[1] == "raw"
    var tm = TermManager()
    scalar_outputs(tm, raw)
    arrays(tm, raw)
    symbols(tm, raw)
    for mode in range(3):
        nested(tm, mode, raw)
    bulk_sorts(tm, raw)
    options(tm, raw)
    save_maps(args[2] + ".maps")
    print("compound FFI passed")
