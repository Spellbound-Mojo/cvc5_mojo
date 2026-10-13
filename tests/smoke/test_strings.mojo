"""String boundaries preserve SMT data and reject truncating C arguments."""

from std.testing import assert_equal, assert_true
from cvc5_mojo import InputLanguage, InputParser, Kind, Solver, TermManager
from cvc5_mojo._c.ffi import c_bytes, to_string


def rejected_inputs(tm: TermManager) raises:
    var zero = chr(0)
    var rejected = False
    try:
        _ = tm.mkInteger("123" + zero + "garbage")
    except e:
        rejected = "NUL" in String(e)
    assert_true(rejected, "numeric text must not silently truncate at NUL")
    assert_equal(String(tm.mkInteger(123)), "123")

    rejected = False
    try:
        _ = tm.mkConst(tm.getIntegerSort(), "x" + zero + "y")
    except e:
        rejected = "NUL" in String(e)
    assert_true(rejected, "symbols must not silently truncate at NUL")

    var solver = Solver(tm)
    var parser = InputParser(solver)
    rejected = False
    try:
        parser.setStringInput(InputLanguage.SMT_LIB_2_6, "(set-logic QF_UF)" + zero + "(assert false)", "nul")
    except e:
        rejected = "NUL" in String(e)
    assert_true(rejected, "parser input must not silently lose constraints")
    parser.setStringInput(InputLanguage.SMT_LIB_2_6, "(set-logic QF_UF)(assert false)", "valid")
    while not parser.done():
        var cmd = parser.nextCommand()
        if cmd.isNull():
            break
        _ = cmd.invoke(solver, parser.getSymbolManager())
    assert_true(solver.checkSat().isUnsat())


def values(tm: TermManager) raises:
    var samples: List[String] = ["", "abc", "éĀ😀", chr(0), "a" + chr(0) + "b", chr(0) + "end", "start" + chr(0), '""', "\\u{0}\\u0041", "\t\n\r", "\\", "a\\\"b", "a" + chr(0) + "é"]
    var solver = Solver(tm)
    solver.setOption("produce-models", "true")
    for s in samples:
        var t = tm.mkString(s)
        assert_equal(t.getStringValue(), s)
        var length = 0
        for _ in s.codepoints():
            length += 1
        assert_equal(String(solver.simplify(tm.mkTerm(Kind.STRING_LENGTH, t))), String(length))
        # Model values, not just terms constructed by the wrapper.
        solver.push()
        var x = tm.mkConst(tm.getStringSort(), "value")
        solver.assertFormula(tm.mkTerm(Kind.EQUAL, x, t))
        assert_true(solver.checkSat().isSat())
        assert_equal(solver.getValue(x).getStringValue(), s)
        solver.pop()
    assert_equal(tm.mkString("a\\u{0}b", True).getStringValue(), "a" + chr(0) + "b")
    assert_equal(tm.mkString("\\u0041", True).getStringValue(), "A")
    assert_equal(tm.mkString("\\u0041", False).getStringValue(), "\\u0041")
    assert_equal(tm.mkString("\\u0041").getStringValue(), "\\u0041")
    for flag in [False, True]:
        var rejected = False
        try:
            _ = tm.mkString("a" + chr(0) + "b", flag)
        except e:
            rejected = "NUL" in String(e)
        assert_true(rejected)
    var rejected = False
    try:
        _ = tm.mkInteger(1).getStringValue()
    except:
        rejected = True
    assert_true(rejected, "a non-string value must still be rejected")


def utf8(tm: TermManager) raises:
    assert_equal(tm.mkConst(tm.getIntegerSort(), "π😀").getSymbol(), "π😀")
    var message = String()
    try:
        _ = tm.mkInteger("π")
    except e:
        message = String(e)
    assert_true("π" in message)
    assert_equal(String(tm.mkInteger(1)), "1")
    var rejected = False
    try:
        _ = tm.mkString("é", False)
    except e:
        rejected = String(e).startswith("cvc5: ")
    assert_true(rejected, "malformed native UTF-8 diagnostics must remain recoverable")
    assert_equal(tm.mkString("ok").getStringValue(), "ok")



def buffers() raises:
    # Exercise empty, small-string, vector-width, allocation, and page boundaries.
    for n in [0, 1, 7, 15, 16, 17, 31, 32, 33, 63, 64, 65, 127, 128, 129, 255, 256, 257, 4095, 4096, 4097]:
        for unit in ["a", "é", "π😀"]:
            var text = String()
            for _ in range(n):
                text += unit
            var encoded = c_bytes(text)
            assert_equal(len(encoded), text.byte_length() + 1)
            assert_equal(encoded[len(encoded) - 1], Int8(0))
            for i in range(text.byte_length()):
                assert_equal(UInt8(encoded[i]), text.as_bytes()[i])
            var copied = to_string(encoded.unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]())
            # Native memory may change or disappear immediately after decoding.
            encoded[0] = 0
            _ = encoded^
            assert_equal(copied, text)

            # Outgoing buffers own their bytes after the source is changed.
            encoded = c_bytes(text)
            var expected = text
            text = "replacement"
            copied = to_string(encoded.unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]())
            _ = text^
            _ = encoded^
            assert_equal(copied, expected)

    for text in [chr(0), chr(0) + "prefix", "prefix" + chr(0), "π" + chr(0) + "😀"]:
        var caught = False
        try:
            _ = c_bytes(text)
        except e:
            caught = String(e) == "cvc5_mojo: embedded NUL in a C string argument"
        assert_true(caught, "every embedded NUL position must be rejected")

    var invalid: List[List[UInt8]] = [
        [0x80], [0xff], [0xc0, 0x80], [0xc2], [0xe2, 0x82],
        [0xed, 0xa0, 0x80], [0xf0, 0x9f, 0x98], [0xf4, 0x90, 0x80, 0x80],
        [0xf5, 0x80, 0x80, 0x80], [0xe2, 0x28, 0xa1],
    ]
    for prefix in [0, 15, 16, 31, 32, 63, 64, 4096]:
        for bad in invalid:
            var encoded = List[Int8](length=prefix, fill=Int8(97))
            for b in bad:
                encoded.append(Int8(b))
            encoded.append(0)
            var caught = False
            try:
                _ = to_string(encoded.unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]())
            except e:
                caught = "Cannot construct a String from invalid UTF-8 data" in String(e)
            finally:
                _ = encoded^  # Keep explicitly untracked input alive through validation.
            assert_true(caught, "invalid UTF-8 must raise instead of being copied unchecked")

    # A C string ends at its first terminator, even if invalid bytes follow.
    var terminated: List[Int8] = [111, 107, 0, -1, 0]
    var copied = to_string(terminated.unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]())
    _ = terminated^
    assert_equal(copied, "ok")


def main() raises:
    buffers()
    var tm = TermManager()
    rejected_inputs(tm)
    values(tm)
    utf8(tm)
    print("string boundary test passed")
