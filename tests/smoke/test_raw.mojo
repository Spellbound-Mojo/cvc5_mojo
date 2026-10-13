"""Raw-layer test: every way a value crosses the C API arrives intact.

Calls generated `CApi` methods directly, at least once per crossing and
direction: opaque owners, handles, enums, `bool`, integers of each width,
C strings, string arrays, handle arrays, out-parameters, 32-bit strings,
`void`, a struct filled through a pointer and an error. The C compiler
checks the sizes behind the generated types; this test checks that values
survive the call.
"""

from std.testing import assert_equal, assert_false, assert_true

from cvc5_mojo import Kind, OptionCategory, SortKind
from cvc5_mojo._c.ffi import CChars, c_bytes, is_null, null, to_c_int32, to_c_uint32, to_string
from cvc5_mojo._c.raw import CApi, Cvc5, Cvc5OptionInfo, Cvc5OptionInfoKind, Cvc5Sort, Cvc5Statistics, Cvc5Term


def text(api: CApi, term: Cvc5Term) raises -> String:
    return to_string(api.cvc5_term_to_string(term))


def count_stats(api: CApi, stats: Cvc5Statistics, internal: Bool, defaulted: Bool) raises -> Int:
    """Iterate statistics: two bool arguments and a C string out-parameter."""
    api.cvc5_stats_iter_init(stats, internal, defaulted)
    var placeholder = c_bytes("")
    var name = placeholder.unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]()
    var count = 0
    while api.cvc5_stats_iter_has_next(stats):
        var stat = api.cvc5_stats_iter_next(stats, Pointer(to=name))
        if to_string(name).byte_length() == 0:
            raise Error("a statistic without a name")
        # Values read through the raw layer agree with cvc5's own printing.
        var shown = to_string(api.cvc5_stat_to_string(stat))
        if api.cvc5_stat_is_int(stat):
            assert_equal(String(api.cvc5_stat_get_int(stat)), shown)
        if api.cvc5_stat_is_double(stat):
            # Averages without samples are NaN, which cvc5 prints as nan.
            var value = api.cvc5_stat_get_double(stat)
            assert_equal(value != value, "nan" in shown)
        api.cvc5_stat_release(stat)
        count += 1
    _ = placeholder^
    return count


def option_info(api: CApi, solver: Cvc5, name: String, mut info: Cvc5OptionInfo) raises:
    """Fill a struct whose layout callers see, through a pointer."""
    var name_c = c_bytes(name)
    api.cvc5_get_option_info(solver, name_c.unsafe_ptr(), Pointer(to=info))
    assert_equal(to_string(info.name()), name)


def out_of_range(value: Int, signed: Bool) -> Bool:
    """Whether the range-checked conversion rejects `value`."""
    try:
        _ = to_c_int32(value) if signed else Int32(to_c_uint32(value))
        return False
    except:
        return True


def main() raises:
    # Range checks at both ends of int32_t and uint32_t.
    for v in [-2147483648, 0, 1, 2147483647]:
        assert_false(out_of_range(v, True))
    for v in [-2147483649, 2147483648]:
        assert_true(out_of_range(v, True))
    for v in [0, 1, 4294967295]:
        assert_false(out_of_range(v, False))
    for v in [-1, 4294967296]:
        assert_true(out_of_range(v, False))
    var one = 1  # a variable, not a literal: Int(UInt32.MAX) once folded wrongly here
    assert_false(out_of_range(one, False))

    # NULL reaches C: a constant made without a symbol has none.
    assert_true(is_null(null[Int8]()))

    var api = CApi()
    var tm = api.cvc5_term_manager_new()  # an opaque result
    var solver = api.cvc5_new(tm)  # an opaque argument

    # bool, in and out.
    assert_true(api.cvc5_term_get_boolean_value(api.cvc5_mk_boolean(tm, True)))
    assert_false(api.cvc5_term_get_boolean_value(api.cvc5_mk_boolean(tm, False)))
    assert_equal(text(api, api.cvc5_mk_boolean(tm, False)), "false")

    # Integers of each width, in and out.
    var minus = api.cvc5_mk_integer_int64(tm, -1234567890123)
    assert_equal(api.cvc5_term_get_int64_value(minus), Int64(-1234567890123))
    assert_equal(api.cvc5_term_get_int32_value(api.cvc5_mk_integer_int64(tm, -7)), Int32(-7))
    assert_equal(api.cvc5_sort_bv_get_size(api.cvc5_mk_bv_sort(tm, 8)), UInt32(8))
    var all_ones = api.cvc5_mk_bv_uint64(tm, 64, UInt64.MAX)
    assert_equal(text(api, all_ones), "#b" + String("1") * 64)
    var digits = c_bytes(String(UInt64.MAX))
    var largest = api.cvc5_mk_integer(tm, digits.unsafe_ptr())
    assert_equal(api.cvc5_term_get_uint64_value(largest), UInt64.MAX)

    # Integer out-parameters.
    var numerator = Int32(0)
    var denominator = UInt32(0)
    var fraction = api.cvc5_mk_real_num_den(tm, -3, 4)
    api.cvc5_term_get_real32_value(fraction, Pointer(to=numerator), Pointer(to=denominator))
    assert_equal(numerator, Int32(-3))
    assert_equal(denominator, UInt32(4))

    # Enums out and in, a C string in, a handle array in, a C string out.
    var integer = api.cvc5_get_integer_sort(tm)
    assert_equal(api.cvc5_sort_get_kind(integer).value, SortKind.INTEGER_SORT.value)
    var anonymous = api.cvc5_mk_const(tm, api.cvc5_get_integer_sort(tm), null[Int8]())
    assert_false(api.cvc5_term_has_symbol(anonymous))
    var x_name = c_bytes("x")
    var x = api.cvc5_mk_const(tm, integer, x_name.unsafe_ptr())
    var children = List[Cvc5Term]()
    children.append(x)
    children.append(minus)
    var total = api.cvc5_mk_term(tm, Kind.ADD, UInt(len(children)), children.unsafe_ptr())
    assert_true(api.cvc5_term_get_kind(total) == Kind.ADD)
    assert_equal(text(api, total), "(+ x (- 1234567890123))")

    # A C string array and a handle array in. The arrays hold untracked
    # pointers into `a` and `b`, which must outlive the call.
    var a = c_bytes("a")
    var b = c_bytes("b")
    var names = List[CChars]()
    names.append(a.unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]())
    names.append(b.unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]())
    var sorts = List[Cvc5Sort]()
    sorts.append(integer)
    sorts.append(api.cvc5_get_boolean_sort(tm))
    var record = api.cvc5_mk_record_sort(tm, UInt(len(names)), names.unsafe_ptr(), sorts.unsafe_ptr())
    assert_true(api.cvc5_sort_is_record(record))
    var fields = api.cvc5_dt_get_constructor(api.cvc5_sort_get_datatype(record), 0)
    assert_equal(api.cvc5_dt_cons_get_num_selectors(fields), UInt(2))
    for i in range(2):
        var selector = api.cvc5_dt_cons_get_selector(fields, UInt(i))
        assert_equal(to_string(api.cvc5_dt_sel_get_name(selector)), String(to_string(names[i])))
        assert_true(api.cvc5_sort_is_equal(api.cvc5_dt_sel_get_codomain_sort(selector), sorts[i]))
    _ = a^
    _ = b^

    # void calls, a size_t out-parameter and a handle array out.
    var logic = c_bytes("QF_LIA")
    api.cvc5_set_logic(solver, logic.unsafe_ptr())
    var option = c_bytes("produce-unsat-cores")
    var value = c_bytes("true")
    api.cvc5_set_option(solver, option.unsafe_ptr(), value.unsafe_ptr())
    var zero = api.cvc5_mk_integer_int64(tm, 0)
    var gt = List[Cvc5Term]()
    gt.append(x)
    gt.append(zero)
    var lt = List[Cvc5Term]()
    lt.append(x)
    lt.append(zero)
    api.cvc5_assert_formula(solver, api.cvc5_mk_term(tm, Kind.GT, 2, gt.unsafe_ptr()))
    api.cvc5_assert_formula(solver, api.cvc5_mk_term(tm, Kind.LT, 2, lt.unsafe_ptr()))
    var result = api.cvc5_check_sat(solver)
    assert_true(api.cvc5_result_is_unsat(result))
    var size = UInt(0)
    var core = api.cvc5_get_unsat_core(solver, Pointer(to=size))
    assert_equal(size, UInt(2))
    var shown = text(api, core[unsafe_offset=0]) + " " + text(api, core[unsafe_offset=1])
    assert_true(shown == "(> x 0) (< x 0)" or shown == "(< x 0) (> x 0)")

    # A 32-bit string in and out.
    var code_points = List[UInt32]()
    for c in [UInt32(104), UInt32(233), UInt32(955), UInt32(0)]:
        code_points.append(c)
    var string = api.cvc5_mk_string_from_char32(tm, code_points.unsafe_ptr())
    var back = api.cvc5_term_get_u32string_value(string)
    for i in range(4):
        assert_equal(back[unsafe_offset=i], code_points[i])

    # bool arguments again: all statistics outnumber the public ones.
    var stats = api.cvc5_get_statistics(solver)
    var everything = count_stats(api, stats, True, True)
    var public = count_stats(api, stats, False, False)
    assert_true(everything > public)

    # Struct fields at their measured offsets, one option of each kind, with
    # the values the official Python bindings give.
    var info = Cvc5OptionInfo()
    option_info(api, solver, "produce-unsat-cores", info)
    assert_true(info.kind() == Cvc5OptionInfoKind.BOOL and info.category() == OptionCategory.COMMON)
    assert_true(info.is_set_by_user() and info.info_bool_cur() and not info.info_bool_dflt())
    assert_true("produce-unsat-cores" in to_string(api.cvc5_option_info_to_string(Pointer(to=info))))
    option_info(api, solver, "filename", info)
    assert_true(info.kind() == Cvc5OptionInfoKind.STR and info.category() == OptionCategory.UNDOCUMENTED)
    assert_equal(to_string(info.info_str_cur()), "")
    option_info(api, solver, "approx-branch-depth", info)
    assert_true(info.kind() == Cvc5OptionInfoKind.INT64 and not info.is_set_by_user())
    assert_true(info.info_int_has_min() and info.info_int_has_max())
    assert_equal(info.info_int_cur(), 200)
    assert_equal(info.info_int_min(), 0)
    assert_equal(info.info_int_max(), 2147483647)
    option_info(api, solver, "bv-abstraction-size", info)
    assert_true(info.kind() == Cvc5OptionInfoKind.UINT64)
    assert_equal(info.info_uint_dflt(), 33)
    assert_equal(info.info_uint_min(), 3)
    assert_equal(info.info_uint_max(), UInt64.MAX)
    option_info(api, solver, "deep-restart-factor", info)
    assert_true(info.kind() == Cvc5OptionInfoKind.DOUBLE and info.info_double_has_max())
    assert_equal(info.info_double_cur(), 3.0)
    assert_equal(info.info_double_max(), 1000.0)
    option_info(api, solver, "arith-prop", info)
    assert_true(info.kind() == Cvc5OptionInfoKind.MODES)
    assert_equal(to_string(info.info_mode_cur()), "both")
    assert_equal(Int(info.info_mode_num_modes()), 4)
    assert_equal(to_string(info.info_mode_modes()[unsafe_offset=3]), "unate")
    option_info(api, solver, "err", info)
    assert_true(info.kind() == Cvc5OptionInfoKind.VOID)
    assert_equal(Int(info.num_aliases()), 1)
    assert_equal(to_string(info.aliases()[unsafe_offset=0]), "diagnostic-output-channel")

    # A failed call raises and leaves the state clear.
    var mixed = List[Cvc5Term]()
    mixed.append(x)
    mixed.append(api.cvc5_mk_boolean(tm, True))
    var raised = False
    try:
        _ = api.cvc5_mk_term(tm, Kind.ADD, 2, mixed.unsafe_ptr())
    except e:
        raised = String(e).startswith("cvc5: ")
    assert_true(raised)
    assert_false(api.cvc5_has_error())

    api.cvc5_stats_release(stats)
    api.cvc5_delete(solver)
    api.cvc5_term_manager_release(tm)
    api.cvc5_term_manager_delete(tm)
    print("statistics:", everything, "in all,", public, "public")
    print("raw layer test passed")
