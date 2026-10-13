"""The C++ API as cvc5.pxd declares it: method names, and the maps.

The C API and the Python bindings are both thin wrappers over the C++ API.
bindgen joins them on the C++ methods they call. Calls are only counted
if the method is part of the C++ API as declared in cvc5.pxd, which filters
out helper calls (`push_back`, `size`, ...) without a hand-kept noise list.

`maps()` lists the C++ methods that return or take a `std::map`. Python
turns these into dictionaries, and the C API into parallel arrays.
"""

import re

from . import c_headers, config

PXD = "src/api/python/cvc5.pxd"
EXTERN_RE = re.compile(r'^cdef extern from "<?([^">]+)>?"(?:\s+namespace\s+"([^"]+)")?')
CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
CLASS_RE = re.compile(r"^    cdef cppclass (\w+)")
DECL_RE = re.compile(r"^(?P<result>.*?)\b(?P<name>\w+)\s*\((?P<params>.*)\)\s*(?:const\s*)?(?:except\s*\+)?\s*;?\s*$")
MAP_RE = re.compile(r"^(?:const\s+)?map\[\s*(\w+)\s*,\s*(\w+)\s*\]\s*&?")


def _cvc5_lines(source_dir):
    """The lines of cvc5.pxd inside `cdef extern` blocks of a cvc5 namespace."""
    in_cvc5 = False
    for line in (source_dir / PXD).read_text(encoding="utf-8").splitlines():
        m = EXTERN_RE.match(line)
        if m:
            in_cvc5 = (m.group(2) or "").startswith("cvc5")
            continue
        if line and not line[0].isspace():
            in_cvc5 = False
            continue
        if in_cvc5:
            yield line


def methods(source_dir=None):
    """Return the set of C++ method names declared for cvc5 classes."""
    source_dir = source_dir or config.SOURCE_DIR
    names = set()
    for line in _cvc5_lines(source_dir):
        if "cppclass" not in line:
            names.update(n for n in CALL_RE.findall(line) if n != "operator")
    return names


def none_bool_defaults(policy, include_dir=None):
    """Extract an unambiguous Boolean default for explicitly opted-in methods."""
    include_dir = include_dir or config.INCLUDE_DIR
    text = (include_dir / "cvc5/cvc5.h").read_text(encoding="utf-8")
    text = c_headers._strip_comments(text)
    out = {}
    for python_method, cpp_method in policy.items():
        declarations = re.findall(rf"\b{re.escape(cpp_method)}\s*\(([^()]*)\)\s*;", text)
        defaults = [re.findall(r"\bbool\s+\w+\s*=\s*(true|false)\b", d) for d in declarations]
        if not defaults or any(len(d) != 1 for d in defaults) or len({d[0] for d in defaults}) != 1:
            raise SystemExit(f"{python_method}: no unambiguous C++ Boolean default; review policy")
        out[python_method] = defaults[0][0].title()
    return out


def _split_params(text):
    parts, depth, cur = [], 0, ""
    for ch in text:
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
            continue
        depth += ch in "(["
        depth -= ch in ")]"
        cur += ch
    return parts + ([cur.strip()] if cur.strip() else [])


def maps(source_dir=None):
    """{method: {"class", "result": [key, value] or None, "params": {position: [key, value]}}}
    for every C++ method whose declaration returns or takes a `map[K, V]`.

    Declarations may span lines. A name declared with different maps in two
    places would make the C functions that call it ambiguous, so it stops
    the extraction.
    """
    source_dir = source_dir or config.SOURCE_DIR
    out = {}
    cls, pending = None, ""
    for line in _cvc5_lines(source_dir):
        m = CLASS_RE.match(line)
        if m:
            cls, pending = m.group(1), ""
            continue
        pending = (pending + " " + line.strip()).strip()
        if pending.count("(") > pending.count(")"):
            continue
        decl, pending = pending, ""
        if "map[" not in decl:
            continue
        d = DECL_RE.match(decl)
        if not d:
            raise SystemExit(f"cvc5.pxd: cannot parse the declaration `{decl}`")
        result = MAP_RE.match(d.group("result").strip())
        params = {}
        for k, p in enumerate(_split_params(d.group("params"))):
            pm = MAP_RE.match(p)
            if pm:
                params[str(k)] = [pm.group(1), pm.group(2)]
        record = {"class": cls, "result": [result.group(1), result.group(2)] if result else None, "params": params}
        name = d.group("name")
        if name in out and out[name] != record:
            raise SystemExit(f"cvc5.pxd: `{name}` is declared with different maps: {out[name]} and {record}")
        out[name] = record
    return dict(sorted(out.items()))
