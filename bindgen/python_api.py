"""Extract the cvc5 Python API from the Cython bindings (cvc5.pxi).

For every public method of every class: its name, parameter list,
docstring, whether it is deprecated, the C++ API methods it calls, and the
methods it delegates to on another wrapper (for example, deprecated
`Solver.mkInteger` calls `self.tm.mkInteger`), and for each C++ call, the
Python parameters each argument reads (`cpp_args`). A method that returns a C++
string as a Python number (`return int(self.cterm.getIntegerValue().decode())`)
also records the number type, `int` or `Fraction`. For every class: its
docstring and its constructor's parameters (`__cinit__`, else `__init__`).

Usage: python -m bindgen.python_api   (prints a summary)
"""

import inspect
import re

from . import config, cpp_api, reference

PXI = "src/api/python/cvc5.pxi"
CLASS_RE = re.compile(r"^cdef class (\w+)")
DEF_RE = re.compile(r"^    (?:def|cpdef)\s+(?:[\w\[\]]+\s+)?(\w+)\s*\(")
DECORATOR_RE = re.compile(r"^    @(\w+)")
CPP_CALL_RE = re.compile(r"\bc\w*\s*(?:\.|->|\[0\]\.)\s*(\w+)\s*\(")
DEREF_CALL_RE = re.compile(r"dereference\(\s*self\.c\w+\s*\)\s*\.\s*(\w+)\s*\(")
DELEGATE_RE = re.compile(r"\bself\.(tm|solver|sm)\.(\w+)\s*\(")
DEPRECATED_RE = re.compile(r"\bis deprecated\b")
NUMBER_RE = re.compile(r"\breturn\s+(int|Fraction)\(\s*self\.c\w+\.\w+\(\)\.decode\(\)\s*\)")

# Dunder methods that are part of the Python API surface.
DUNDERS = {
    "__eq__", "__ne__", "__lt__", "__gt__", "__le__", "__ge__", "__hash__",
    "__str__", "__repr__", "__getitem__", "__iter__", "__len__", "__bool__",
    "__int__", "__float__", "__call__", "__contains__",
}


def _docstring(body):
    """The leading docstring of `body`, dedented with its structure kept."""
    m = re.match(r'\s*(r?)"""(.*?)"""', body, re.S)
    if not m:
        return ""
    text = m.group(2) if m.group(1) else m.group(2).replace("\\\\", "\\")
    return inspect.cleandoc(text)


def _parameter_names(params):
    """The names in a Cython parameter list, without self."""
    names = []
    for p in reference._split(params):
        p = p.split("=", 1)[0].replace("not None", "").strip()
        if p and p != "self":
            names.append(p.split()[-1].lstrip("*"))
    return names


def _cpp_arguments(body, names, vocabulary):
    """{C++ method: [[the parameters in `names` each argument reads] per call]}:
    which Python parameter feeds which argument, whatever their order."""
    out = {}
    for m in list(CPP_CALL_RE.finditer(body)) + list(DEREF_CALL_RE.finditer(body)):
        if m.group(1) not in vocabulary:
            continue
        depth, end = 0, m.end() - 1
        for end in range(m.end() - 1, len(body)):
            depth += (body[end] == "(") - (body[end] == ")")
            if depth == 0:
                break
        args = reference._split(body[m.end() : end])
        site = [[n for n in names if re.search(rf"\b{re.escape(n)}\b", a)] for a in args]
        if site not in out.setdefault(m.group(1), []):
            out[m.group(1)].append(site)
    return out


def _in_body(line):
    """A method body is everything indented deeper than the `def` (tabs count)."""
    expanded = line.expandtabs(8)
    return not expanded.strip() or len(expanded) - len(expanded.lstrip()) > 4


def _signature(lines, i):
    """Join a possibly multi-line `def` and return (params text, end index)."""
    text = lines[i]
    j = i
    while not re.search(r"\)\s*(?:->\s*[^:]+)?:\s*(?:#.*)?$", text) and j + 1 < len(lines):
        j += 1
        text += " " + lines[j].strip()
    m = re.search(r"\((.*)\)\s*(?:->\s*[^:]+)?:", text)
    return (" ".join(m.group(1).split()) if m else ""), j


def parse(source_dir=None):
    """Return {class: [method records]} for the public Python API."""
    return parse_with_docs(source_dir)[0]


def parse_with_docs(source_dir=None):
    """Return ({class: [method records]}, {class: class docstring},
    {class: constructor parameters})."""
    source_dir = source_dir or config.SOURCE_DIR
    vocabulary = cpp_api.methods(source_dir)
    lines = (source_dir / PXI).read_text(encoding="utf-8").splitlines()
    classes = {}
    docs = {}
    inits = {}
    cls = None
    decorators = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = CLASS_RE.match(line)
        if m:
            cls = m.group(1)
            k = i + 1
            # A class body is indented one level: take everything up to the first method.
            while k < len(lines) and (not lines[k].strip() or lines[k][0].isspace()) and not DEF_RE.match(lines[k]):
                k += 1
            docs[cls] = _docstring("\n".join(lines[i + 1 : k]))
            classes[cls] = []
            i += 1
            continue
        if line and not line[0].isspace() and not line.startswith("#"):
            cls = None
        d = DECORATOR_RE.match(line)
        if d and cls:
            decorators.append(d.group(1))
            i += 1
            continue
        m = DEF_RE.match(line)
        if not (m and cls):
            i += 1
            continue
        name = m.group(1)
        params, end = _signature(lines, i)
        if name == "__cinit__" or (name == "__init__" and cls not in inits):
            inits[cls] = params
        k = end + 1
        while k < len(lines) and _in_body(lines[k]):
            k += 1
        body = "\n".join(lines[end + 1 : k])
        if not name.startswith("_") or name in DUNDERS:
            calls = set(CPP_CALL_RE.findall(body)) | set(DEREF_CALL_RE.findall(body))
            doc = _docstring(body)
            number = NUMBER_RE.search(body)
            classes[cls].append(
                {
                    "name": name,
                    "params": params,
                    "decorators": decorators,
                    "deprecated": bool(DEPRECATED_RE.search(doc)),
                    "cpp_calls": sorted(calls & vocabulary),
                    "cpp_args": _cpp_arguments(body, _parameter_names(params), vocabulary),
                    "delegates": sorted({f"{o}.{n}" for o, n in DELEGATE_RE.findall(body)}),
                    "doc": doc,
                    **({"number": number.group(1)} if number else {}),
                }
            )
        decorators = []
        i = k
    return classes, docs, inits


def main():
    classes = parse()
    total = sum(len(v) for v in classes.values())
    print(f"{total} public Python methods in {len(classes)} classes")
    for cls, methods in classes.items():
        dep = sum(1 for m in methods if m["deprecated"])
        print(f"  {cls}: {len(methods)}" + (f" ({dep} deprecated)" if dep else ""))


if __name__ == "__main__":
    main()
