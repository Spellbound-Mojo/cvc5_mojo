"""Shared resident-memory measurement for the built lifecycle tests."""


def status_kb(field: String) raises -> Int:
    with open("/proc/self/status", "r") as f:
        for line in f.read().split("\n"):
            if line.startswith(field):
                return Int(line.removeprefix(field).strip().removesuffix("kB").strip())
    raise Error(field + " not found in /proc/self/status")


def resident_kb() raises -> Int:
    return status_kb("VmRSS:")


def peak_resident_kb() raises -> Int:
    return status_kb("VmHWM:")


def save_maps(path: String) raises:
    """Record actual loaded library paths for the native comparison runners."""
    var maps: String
    with open("/proc/self/maps", "r") as file:
        maps = file.read()
    with open(path, "w") as file:
        file.write(maps)
