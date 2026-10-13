"""Check repeated loading, cached failure, and cleanup before process exit."""

from std.os import getenv
from std.sys import argv
from std.testing import assert_equal
from cvc5_mojo import TermManager
from cvc5_mojo._c.raw import CApi
from memory_support import save_maps


def main() raises:
    var args = argv()
    var direct = len(args) > 1 and args[1] == "direct"
    var attempts = Int(args[2]) if len(args) > 2 else 2
    var failures = List[String]()
    for _ in range(attempts):
        try:
            if direct:
                var api = CApi()
                if api.cvc5_has_error():
                    raise Error("unexpected bootstrap error state")
            else:
                var tm = TermManager()
                _ = tm.getBooleanSort()
        except e:
            failures.append(String(e))
    var events = getenv("CVC5_MOJO_TEST_EVENTS")
    if events:
        with open(events, "a") as file:
            file.write("checkpoint\n")
    if len(args) > 3:
        save_maps(args[3])
    if failures:
        assert_equal(len(failures), attempts)
        for message in failures:
            assert_equal(message, failures[0])
        print("load-error")
        print(failures[0])
    else:
        print("loaded")
    print("attempts", attempts)
