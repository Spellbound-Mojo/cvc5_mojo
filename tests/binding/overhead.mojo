"""Steady-state raw/public comparisons with equivalent ownership and outputs."""
from std.sys import argv, is_defined, get_defined_string
from std.ffi import OwnedDLHandle
from std.time import perf_counter_ns
from std.testing import assert_equal, assert_true
from apn_mojo import Integer, Rational
from cvc5_mojo import Kind, Solver, Term, TermManager
from cvc5_mojo._c.ffi import c_bytes, to_string
from cvc5_mojo._c.raw import Cvc5Term, c_api
from memory_support import save_maps


struct AllocationProbe(Movable):
    var library: Optional[OwnedDLHandle]

    def __init__(out self) raises:
        self.library = None
        comptime if is_defined["CVC5_OVERHEAD_PROBE"]():
            self.library = OwnedDLHandle(get_defined_string["CVC5_OVERHEAD_PROBE"]())
            assert_equal(self.library.value().get_function[Int32]("overhead_sensitivity")(), Int32(1))

    def begin(self) raises:
        comptime if is_defined["CVC5_OVERHEAD_PROBE"]():
            self.library.value().get_function[NoneType]("overhead_begin")()

    def end(self) raises:
        comptime if is_defined["CVC5_OVERHEAD_PROBE"]():
            self.library.value().get_function[NoneType]("overhead_end")()

    def report(self) raises:
        comptime if is_defined["CVC5_OVERHEAD_PROBE"]():
            var metric = self.library.value().get_function[UInt64]("overhead_metric")
            print("allocations", metric(Int32(0)), metric(Int32(1)), metric(Int32(2)),
                  metric(Int32(3)), metric(Int32(4)), metric(Int32(5)))


def checksum(text: String) raises -> Int:
    var total = 0
    for b in text.as_bytes():
        assert_true(b >= 48 and b <= 57)
        total += Int(b)
    return total


def step[raw: Bool, mode: Int](tm: TermManager, solver: Solver, inputs: List[Term],
                              expression: Term, integer: Term, decimal: String,
                              number: Integer, fraction: Rational) raises -> Int:
    var api = tm._o[].api
    comptime if mode == 0:
        comptime if raw:
            return Int(api[].cvc5_term_get_num_children(expression._h))
        else:
            return expression.getNumChildren()
    comptime if mode == 1:
        comptime if raw:
            var copied = api[].cvc5_term_copy(expression._h)
            var n = Int(api[].cvc5_term_get_num_children(copied))
            api[].cvc5_term_release(copied)
            return n
        else:
            var copied = expression
            return copied.getNumChildren()
    comptime if (mode >= 2 and mode <= 4) or mode == 12:
        comptime if raw:
            var t: Cvc5Term
            comptime if mode == 2 or mode == 3:
                t = api[].cvc5_mk_integer_int64(tm._handle(), 42)
            else:
                var text = c_bytes(decimal)
                t = api[].cvc5_mk_integer(tm._handle(), text.unsafe_ptr())
            var result = Int(api[].cvc5_term_is_integer_value(t))
            api[].cvc5_term_release(t)
            return result
        else:
            var t: Term
            comptime if mode == 2:
                t = tm.mkInteger(Int(42))
            elif mode == 3:
                t = tm.mkInteger(42)
            elif mode == 12:
                t = tm.mkInteger(2**256 - 1)
            else:
                t = tm.mkInteger(decimal)
            return Int(t.isIntegerValue())
    comptime if mode >= 5 and mode <= 7:
        comptime if raw:
            var args = List[Cvc5Term]()
            for i in range(2 if mode == 5 else 8):
                args.append(inputs[i]._h)
            var t = api[].cvc5_mk_term(tm._handle(), Kind.ADD, UInt(len(args)), args.unsafe_ptr())
            var result = Int(api[].cvc5_term_get_num_children(t))
            api[].cvc5_term_release(t)
            return result
        else:
            var t: Term
            comptime if mode == 5:
                t = tm.mkTerm(Kind.ADD, inputs[0], inputs[1])
            elif mode == 6:
                t = tm.mkTerm(Kind.ADD, inputs[0], inputs[1], inputs[2], inputs[3],
                              inputs[4], inputs[5], inputs[6], inputs[7])
            else:
                t = tm.mkTerm(Kind.ADD, inputs)
            return t.getNumChildren()
    comptime if mode == 8:
        comptime if raw:
            var args = List[Cvc5Term]()
            for item in inputs:
                args.append(item._h)
            var n = UInt(0)
            var native = api[].cvc5_get_values(solver._handle(), UInt(len(args)), args.unsafe_ptr(), Pointer(to=n))
            var owned = List[Cvc5Term]()
            for i in range(Int(n)):
                owned.append(native[unsafe_offset=i])
            var result = len(owned)
            for h in owned:
                result += Int(api[].cvc5_term_is_integer_value(h))
                api[].cvc5_term_release(h)
            return result
        else:
            var values = solver.getValue(inputs)
            var result = len(values)
            for value in values:
                result += Int(value.isIntegerValue())
            return result
    comptime if mode == 9:
        comptime if raw:
            return checksum(to_string(api[].cvc5_term_to_string(integer._h)))
        else:
            return checksum(String(integer))
    comptime if mode == 10:
        # A conversion-helper control: copy the returned decimal string in
        # both modes. Public getIntegerValue additionally parses apn.Integer;
        # this workload deliberately does not claim to benchmark that method.
        return checksum(to_string(api[].cvc5_term_get_integer_value(integer._h)))
    comptime if mode == 11:
        comptime if raw:
            return checksum(to_string(api[].cvc5_term_to_string(integer._h)))
        else:
            return checksum(integer.toString())
    comptime if mode == 13:
        comptime if raw:
            var n = Int(api[].cvc5_term_get_num_children(expression._h))
            var owned = List[Cvc5Term]()
            for i in range(n):
                owned.append(api[].cvc5_term_get_child(expression._h, UInt(i)))
            var result = 0
            for h in owned:
                result += 1 + Int(api[].cvc5_term_is_integer_value(h))
                api[].cvc5_term_release(h)
            return result
        else:
            var result = 0
            for child in expression:
                result += 1 + Int(child.isIntegerValue())
            return result
    comptime if mode == 14:
        comptime if raw:
            var n = UInt(0)
            var native = api[].cvc5_get_assertions(solver._handle(), Pointer(to=n))
            var owned = List[Cvc5Term]()
            for i in range(Int(n)):
                owned.append(native[unsafe_offset=i])
            var result = len(owned)
            for h in owned:
                result += Int(api[].cvc5_term_has_symbol(h))
                api[].cvc5_term_release(h)
            return result
        else:
            var values = solver.getAssertions()
            var result = len(values)
            for value in values:
                result += Int(value.hasSymbol())
            return result
    comptime if mode == 15:
        var values = List[String]()
        comptime if raw:
            var n = UInt(0)
            var native = api[].cvc5_get_option_names(solver._handle(), Pointer(to=n))
            for i in range(Int(n)):
                values.append(to_string(native[unsafe_offset=i]))
        else:
            values = solver.getOptionNames()
        return Int("produce-models" in values)
    comptime if mode == 16 or mode == 24:
        comptime if raw:
            var t: Cvc5Term
            comptime if mode == 16:
                t = api[].cvc5_mk_integer_int64(tm._handle(), 42)
            else:
                var text = c_bytes(decimal)
                t = api[].cvc5_mk_integer(tm._handle(), text.unsafe_ptr())
            var result = Int(api[].cvc5_term_is_integer_value(t))
            api[].cvc5_term_release(t)
            return result
        else:
            return Int(tm.mkInteger(number).isIntegerValue())
    comptime if mode == 17 or mode == 18:
        var value: Integer
        comptime if raw:
            if api[].cvc5_term_is_int64_value(integer._h):
                value = Integer(api[].cvc5_term_get_int64_value(integer._h))
            elif api[].cvc5_term_is_uint64_value(integer._h):
                value = Integer(api[].cvc5_term_get_uint64_value(integer._h))
            else:
                value = Integer(to_string(api[].cvc5_term_get_integer_value(integer._h)))
        else:
            value = integer.getIntegerValue()
        return Int(value == number)
    comptime if mode == 19 or mode == 20:
        comptime if raw:
            var t = api[].cvc5_mk_real_num_den(tm._handle(), 3, 7)
            var result = Int(api[].cvc5_term_is_real_value(t))
            api[].cvc5_term_release(t)
            return result
        elif mode == 19:
            return Int(tm.mkReal(fraction).isRealValue())
        else:
            return Int(tm.mkReal(fraction.numerator(), fraction.denominator()).isRealValue())
    comptime if mode == 21 or mode == 22:
        var value: Rational
        comptime if raw:
            if api[].cvc5_term_is_real64_value(integer._h):
                var num = Int64(0)
                var den = UInt64(0)
                api[].cvc5_term_get_real64_value(integer._h, Pointer(to=num), Pointer(to=den))
                value = Rational(Integer(num), Integer(den))
            else:
                value = Rational(to_string(api[].cvc5_term_get_real_value(integer._h)))
        else:
            value = integer.getRealValue()
        return Int(value == fraction)
    comptime if mode == 23:
        comptime if raw:
            var t = api[].cvc5_mk_bv_uint64(tm._handle(), 64, UInt64.MAX)
            var result = Int(api[].cvc5_term_is_bv_value(t))
            api[].cvc5_term_release(t)
            return result
        else:
            return Int(tm.mkBitVector(Int(64), number).isBitVectorValue())
    raise Error("unknown workload")


@no_inline
def execute[raw: Bool, mode: Int](count: Int, warmup: Int, maps: String) raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("produce-models", "true")
    var inputs = List[Term]()
    for i in range(8):
        inputs.append(tm.mkInteger(i))
    var decimal = String("115792089237316195423570985008687907853269984665640564039457584007913129639935")
    var integer = tm.mkInteger(decimal)
    var number = Integer(decimal)
    var fraction = Rational(Integer(3), Integer(7))
    comptime if mode == 16 or mode == 17:
        number = Integer(42)
        integer = tm.mkInteger(Int(42))
    elif mode == 21:
        integer = tm.mkReal("3/7")
    elif mode == 22:
        fraction = Rational(number, Integer(7))
        integer = tm.mkReal(decimal + "/7")
    elif mode == 23:
        number = Integer(UInt64.MAX)
    var expression = tm.mkTerm(Kind.ADD, inputs)
    comptime if mode == 14:
        for i in range(32):
            solver.assertFormula(tm.mkConst(tm.getBooleanSort(), String("assertion_", i)))
    assert_true(solver.checkSat().isSat())
    var warmed = 0
    for _ in range(warmup):
        warmed += step[raw, mode](tm, solver, inputs, expression, integer, decimal, number, fraction)
    var probe = AllocationProbe()
    probe.begin()
    var total = 0
    var before = Int(perf_counter_ns())
    for _ in range(count):
        total += step[raw, mode](tm, solver, inputs, expression, integer, decimal, number, fraction)
    var elapsed = Int(perf_counter_ns()) - before
    probe.end()
    _ = (expression^, integer^, inputs^, solver^, tm^)
    save_maps(maps + ".maps")
    print(mode, count, elapsed, total, warmed)
    print("overhead passed")
    probe.report()


def dispatch[raw: Bool](mode: Int, count: Int, warmup: Int, maps: String) raises:
    # Select a specialized loop once, before warmup and measurement.
    comptime for candidate in range(25):
        if mode == candidate:
            # decimal-copy intentionally exercises the same conversion helper
            # in both layers. Reuse that exact compiled control as well.
            execute[raw and candidate != 10, candidate](count, warmup, maps)
            return
    raise Error("unknown workload")


def main() raises:
    var args = argv()
    assert_equal(len(args), 6)
    if args[2] == "cold":
        var before = Int(perf_counter_ns())
        var api = c_api()
        var elapsed = Int(perf_counter_ns()) - before
        assert_true(not api[].cvc5_has_error())
        save_maps(args[5] + ".maps")
        print(-1, 1, elapsed, 1, 0)
        print("overhead passed")
        return
    var mode = Int(args[2])
    var count = Int(args[3])
    var warmup = Int(args[4])
    assert_true(count > 0 and warmup >= 0 and mode >= 0 and mode <= 24)
    if args[1] == "raw":
        dispatch[True](mode, count, warmup, args[5])
    elif args[1] == "public":
        dispatch[False](mode, count, warmup, args[5])
    else:
        raise Error("unknown layer")
