"""Errors from cvc5 are Mojo errors: an ill-sorted term raises, and work continues."""

from std.testing import assert_true

from cvc5_mojo import TermManager, Kind


def main() raises:
    var tm = TermManager()
    var x = tm.mkConst(tm.getRealSort(), "x")
    var flag = tm.mkConst(tm.getBooleanSort(), "flag")

    var message = String()
    try:
        _ = tm.mkTerm(Kind.ADD, x, flag)
    except e:
        message = String(e)
    assert_true(message.startswith("cvc5: "))
    print("caught:", message)

    # The term manager is unaffected by the failed call.
    print("next term:", tm.mkTerm(Kind.ADD, x, x))
