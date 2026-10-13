"""Replay stateful numeric, collection, and error operations against C controls."""
from std.sys import argv
from std.testing import assert_equal, assert_true
from apn_mojo import Integer, Rational
from cvc5_mojo import Kind, Solver, Term, TermManager
from cvc5_mojo._c.ffi import c_bytes, to_string
from cvc5_mojo._c.raw import Cvc5Term
from memory_support import save_maps
from test_ownership import containers


def solver_new(tm: TermManager) raises -> Solver:
    var solver = Solver(tm)
    solver.setLogic("QF_LIA")
    solver.setOption("produce-models", "true")
    return solver^


def integer(term: Term, raw: Bool) raises -> String:
    if raw:
        return to_string(term._api[].cvc5_term_get_integer_value(term._h))
    return String(term.getIntegerValue())


def make_integer(tm: TermManager, text: String, form: Int, raw: Bool) raises -> Term:
    if raw:
        var bytes = c_bytes(text)
        var api = tm._o[].api
        var h = api[].cvc5_mk_integer_int64(tm._handle(), Int64(Int(text))) if form == 2 else api[].cvc5_mk_integer(tm._handle(), bytes.unsafe_ptr())
        return Term(api, tm._handle(), h)
    if form == 0:
        return tm.mkInteger(text)
    if form == 1:
        return tm.mkInteger(Integer(text))
    return tm.mkInteger(Int(text))


def rational(tm: TermManager, n: String, d: String, form: Int, raw: Bool) raises -> String:
    var text = String(n, "/", d)
    var term = Term()
    if raw:
        var bytes = c_bytes(text)
        var api = tm._o[].api
        term = Term(api, tm._handle(), api[].cvc5_mk_real(tm._handle(), bytes.unsafe_ptr()))
        var result = to_string(api[].cvc5_term_get_real_value(term._h))
        _ = term^
        return result^
    if form == 0:
        term = tm.mkReal(text)
    elif form == 1:
        term = tm.mkReal(n, d)
    elif form == 2:
        term = tm.mkReal(Integer(n), Integer(d))
    elif form == 3:
        term = tm.mkReal(Integer(n), d)
    elif form == 4:
        term = tm.mkReal(n, Integer(d))
    else:
        term = tm.mkReal(Rational(text))
    # Compare rational values in n/d form; Python-style formatting omits /1.
    var value = String(term.getRealValue())
    return value if "/" in value else value + "/1"


def bitvector(tm: TermManager, width: Int, base: Int, text: String, form: Int, raw: Bool) raises -> String:
    var term = Term()
    if raw:
        var bytes = c_bytes(text)
        var api = tm._o[].api
        term = Term(api, tm._handle(), api[].cvc5_mk_bv(tm._handle(), UInt32(width), bytes.unsafe_ptr(), UInt32(base)))
        var result = to_string(api[].cvc5_term_get_bv_value(term._h, 10))
        _ = term^
        return result^
    term = tm.mkBitVector(width, text, base) if form == 0 else tm.mkBitVector(width, Integer(text))
    return term.getBitVectorValue(10)


def values(items: List[Term], raw: Bool) raises -> String:
    var result = String("[")
    for i in range(len(items)):
        if i:
            result += ","
        result += integer(items[i], raw)
    return result + "]"


def reject(tm: TermManager, solver: Solver, term: Term, kind: Int, width: Int, overflow: String, raw: Bool) raises:
    # Local references must unwind before the caller checks recovery.
    var held: List[Term] = [term]
    var boolean = tm.mkTrue()
    var api = tm._o[].api
    if raw:
        var bad_int = c_bytes("not_an_integer")
        var bad_real = c_bytes("1/0")
        var big = c_bytes(overflow)
        var children: List[Cvc5Term] = [held[0]._h, boolean._h]
        try:
            if kind == 0:
                _ = api[].cvc5_mk_integer(tm._handle(), bad_int.unsafe_ptr())
            elif kind == 1:
                _ = api[].cvc5_mk_real(tm._handle(), bad_real.unsafe_ptr())
            elif kind == 2:
                _ = api[].cvc5_mk_bv(tm._handle(), UInt32(width), big.unsafe_ptr(), 10)
            elif kind == 3:
                _ = api[].cvc5_term_get_boolean_value(held[0]._h)
            elif kind == 4:
                api[].cvc5_assert_formula(solver._handle(), held[0]._h)
            else:
                _ = api[].cvc5_mk_term(tm._handle(), Kind.ADD, 2, children.unsafe_ptr())
        finally:
            _ = (held^, boolean^)
    else:
        if kind == 0:
            _ = tm.mkInteger("not_an_integer")
        elif kind == 1:
            _ = tm.mkReal("1/0")
        elif kind == 2:
            _ = tm.mkBitVector(width, overflow, 10)
        elif kind == 3:
            _ = held[0].getBooleanValue()
        elif kind == 4:
            solver.assertFormula(held[0])
        else:
            _ = tm.mkTerm(Kind.ADD, held[0], boolean)


def main() raises:
    var args = argv()
    assert_equal(len(args), 4)
    assert_true(args[1] == "raw" or args[1] == "public")
    var raw = args[1] == "raw"
    var text: String
    with open(args[2], "r") as file:
        text = file.read()
    var tm = TermManager()
    var api = tm._o[].api
    var solver = solver_new(tm)
    var slots = List[Term]()
    for _ in range(8):
        slots.append(tm.mkInteger(0))
    var saved = List[Term]()
    var step = 0
    for line in text.split("\n"):
        if not line:
            continue
        var parts = line.split(" ")
        var op = parts[0]
        var output: String
        if op == "I":
            var a = Int(parts[1])
            slots[a] = make_integer(tm, String(parts[2]), Int(parts[3]), raw)
            output = integer(slots[a], raw)
        elif op == "C":
            var a = Int(parts[1])
            var b = Int(parts[2])
            if raw:
                slots[a] = Term(api, tm._handle(), api[].cvc5_term_copy(slots[b]._h))
            else:
                slots[a] = containers(slots[a], slots[b])
            output = integer(slots[a], raw)
        elif op == "A":
            var a = Int(parts[1])
            var b = Int(parts[2])
            var c = Int(parts[3])
            var kind = Kind.SUB if Int(parts[4]) else Kind.ADD
            if raw:
                var children: List[Cvc5Term] = [slots[b]._h, slots[c]._h]
                var expr = api[].cvc5_mk_term(tm._handle(), kind, 2, children.unsafe_ptr())
                var h = api[].cvc5_simplify(solver._handle(), expr, False)
                api[].cvc5_term_release(expr)
                slots[a] = Term(api, tm._handle(), h)
            else:
                slots[a] = solver.simplify(tm.mkTerm(kind, slots[b], slots[c]))
            output = integer(slots[a], raw)
        elif op == "Q":
            output = rational(tm, String(parts[1]), String(parts[2]), Int(parts[3]), raw)
        elif op == "B":
            output = bitvector(tm, Int(parts[1]), Int(parts[2]), String(parts[3]), Int(parts[4]), raw)
        elif op == "V":
            var inputs = List[Term]()
            for i in range(Int(parts[1])):
                inputs.append(slots[Int(parts[i + 2])])
            assert_true(solver.checkSat().isSat())
            if raw:
                saved.clear()
                var handles = List[Cvc5Term]()
                for term in inputs:
                    handles.append(term._h)
                var size = UInt(0)
                var native = api[].cvc5_get_values(solver._handle(), UInt(len(handles)), handles.unsafe_ptr(), Pointer(to=size))
                assert_equal(Int(size), len(inputs))
                for i in range(Int(size)):
                    saved.append(Term(api, tm._handle(), native[unsafe_offset=i]))
                var later = api[].cvc5_get_values(solver._handle(), 1, Pointer(to=slots[0]._h), Pointer(to=size))
                assert_equal(size, UInt(1))
                api[].cvc5_term_release(later[])
                _ = inputs^
            else:
                saved = solver.getValue(inputs)
                _ = solver.getValue([slots[0]])
            output = values(saved, raw)
        elif op == "G":
            output = values(saved, raw)
        elif op == "R":
            solver = solver_new(tm)
            output = "reset"
        elif op == "E":
            var slot = Int(parts[2])
            var caught = False
            try:
                reject(tm, solver, slots[slot], Int(parts[1]), Int(parts[3]), String(parts[4]), raw)
            except e:
                caught = String(e).startswith("cvc5: ")
            assert_true(caught)
            output = "recovered " + integer(slots[slot], raw)
        elif op == "P":
            var a = Int(parts[1])
            var b = Int(parts[2])
            var eq: Bool
            if raw:
                eq = api[].cvc5_term_is_equal(slots[a]._h, slots[b]._h)
                var ab = api[].cvc5_term_compare(slots[a]._h, slots[b]._h)
                var ba = api[].cvc5_term_compare(slots[b]._h, slots[a]._h)
                assert_true((ab == 0) == eq and (ab < 0) == (ba > 0) and (ab > 0) == (ba < 0))
                assert_true(not eq or api[].cvc5_term_hash(slots[a]._h) == api[].cvc5_term_hash(slots[b]._h))
            else:
                eq = slots[a] == slots[b]
                assert_true(eq == (not (slots[a] < slots[b]) and not (slots[a] > slots[b])))
                assert_true((slots[a] < slots[b]) == (slots[b] > slots[a]))
                var table = Dict[Term, Int]()
                table[slots[a]] = 1
                table[slots[b]] = 2
                assert_equal(len(table), 1 if eq else 2)
                assert_equal(table[slots[b]], 2)
            output = String(Int(eq))
        else:
            raise Error("unknown sequence operation")
        assert_true(not api[].cvc5_has_error())
        print(step, op, output)
        step += 1
    _ = saved^
    _ = slots^
    _ = solver^
    _ = tm^
    save_maps(args[3] + ".maps")
    print("sequence passed")
