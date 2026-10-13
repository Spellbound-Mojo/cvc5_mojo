"""Deliberate defects: verify the sanitizer observes this toolchain's allocations."""
from std.sys import argv
from std.memory import OwnedPointer
from std.ffi import OwnedDLHandle, external_call


@no_inline
def lose_allocation():
    var p = OwnedPointer(Int(1234))
    var raw = p^.unsafe_take_allocation().unsafe_leak()
    print(raw)  # Keep the allocation observable; otherwise optimization removes it.


def main() raises:
    var mode = String(argv()[1])
    if mode == "leak" or mode == "checkpoint":
        lose_allocation()
        if mode == "checkpoint":
            external_call["__lsan_do_leak_check", NoneType]()
    elif mode == "native":
        var library = OwnedDLHandle(argv()[2])
        library.get_function[NoneType]("native_leak")()
    else:
        var data = List[Int](capacity=4)
        data.append(7)
        var offset = Int(argv()[2])
        data.unsafe_ptr()[unsafe_offset=offset] = 99
        print(data[0])
    print("sensitivity done")
