"""Map each C API function to the C++ API methods its implementation calls.

Reads the C API implementation (src/api/c/*.cpp) from the source archive.
Example: cvc5_mk_bv_sort's body calls `tm->d_tm.mkBitVectorSort(size)`, so
it maps to {"mkBitVectorSort"}.

Usage: python -m bindgen.c_impl   (prints a summary)
"""

import re

from . import config, cpp_api

IMPL_FILES = ["src/api/c/cvc5.cpp", "src/api/c/cvc5_parser.cpp"]
STRUCT_FILES = ["src/api/c/cvc5_c_structs.cpp", "src/api/c/cvc5_parser.cpp"]
EXPORT_RE = re.compile(r"^(Cvc5\w+)\s+(\w+)::export_\w+\(", re.M)
FUNC_RE = re.compile(r"^[A-Za-z][\w\s\*:<>,]*?\b(cvc5_\w+)\s*\([^;{]*?\)\s*\{(.*?)^\}", re.S | re.M)
CALL_RE = re.compile(r"(?:\.|->)\s*(\w+)\s*\(")


def parse(source_dir=None):
    """Return {c_function: sorted list of C++ API methods it calls}."""
    source_dir = source_dir or config.SOURCE_DIR
    vocabulary = cpp_api.methods(source_dir)
    out = {}
    for rel in IMPL_FILES:
        text = (source_dir / rel).read_text(encoding="utf-8")
        for m in FUNC_RE.finditer(text):
            calls = set(CALL_RE.findall(m.group(2))) & vocabulary
            out[m.group(1)] = sorted(calls)
    return out


def null_tested(params_of, source_dir=None):
    """Return {c_function: [pointer parameters its body tests for NULL]}.

    `params_of` maps each C function to its parameter names. A parameter the
    implementation tests (`if (symbol)`, `p ? ... : ...`, `p == nullptr`)
    accepts NULL even where the header's comment does not say so.
    """
    source_dir = source_dir or config.SOURCE_DIR
    out = {}
    for rel in IMPL_FILES:
        text = (source_dir / rel).read_text(encoding="utf-8")
        for m in FUNC_RE.finditer(text):
            body = m.group(2)
            for name in params_of.get(m.group(1), []):
                n = re.escape(name)
                if re.search(rf"\bif\s*\(\s*!?\s*{n}\s*\)|\b{n}\s*\?|\b{n}\s*[!=]=\s*nullptr|nullptr\s*[!=]=\s*{n}\b", body):
                    out.setdefault(m.group(1), []).append(name)
    return out


def handles(source_dir=None):
    """Return {handle type: {"exporter": class, "receive": "own" | "anchor"}}.

    Every handle the C API returns is created by an `export_*` method of the
    object that manages it. Objects exported by the solver (`Cvc5::export_*`:
    results, synthesis results, proofs, grammars) are created holding the
    solver's reference, which `~Cvc5()` drops, so the returned handle is
    shared with the solver. Adopt that reference and keep the solver alive
    until release deregisters the handle. Copying on receipt would leave
    every discarded object in the solver's cache until solver destruction.
    Everything else (term manager and parser exports) hands the caller its
    own reference. See the `cvc5_delete` documentation in cvc5.h.
    """
    source_dir = source_dir or config.SOURCE_DIR
    out = {}
    structures = (source_dir / "src/api/c/cvc5_c_structs.h").read_text(encoding="utf-8")
    for rel in STRUCT_FILES:
        text = (source_dir / rel).read_text(encoding="utf-8")
        for m in EXPORT_RE.finditer(text):
            handle, exporter = m.groups()
            info = out.setdefault(handle, {"exporter": exporter, "exporters": [], "receive": "own"})
            info["exporters"].append(exporter)
            if exporter == "Cvc5":
                # Refuse an upstream ownership change rather than assuming
                # an exporter name alone proves that adopting is safe.
                body = text[m.end():text.index("\n}", m.end())]
                allocated = re.search(r"\bnew\s+(\w+)\s*\(", body)
                native = allocated.group(1) if allocated else ""
                release = re.search(rf"void {re.escape(native)}::release\(\)\s*\{{(.*?)^\}}", text, re.M | re.S)
                declaration = re.search(rf"^struct {re.escape(native)}\s*\{{(.*?)^\}};", structures, re.M | re.S)
                required = (r"d_refs\s*-=\s*1", r"if\s*\(d_refs\s*==\s*0\)",
                            r"d_cvc5->deregister\(this\)", r"delete this;")
                if (not allocated or not release or not declaration
                        or not re.search(r"d_refs\s*=\s*1\s*;", declaration.group(1))
                        or not all(re.search(pattern, release.group(1)) for pattern in required)):
                    raise SystemExit(f"{handle}: solver export/release protocol changed; review ownership")
                info.update(exporter=exporter, receive="anchor", release_deregisters=True)
    for info in out.values():
        info["exporters"] = sorted(set(info["exporters"]))
    return out


def callbacks(source_dir=None):
    """Extract the C plugin's forwarding, exports and retained callback table.

    Fail when the pinned implementation changes its storage or callback protocol;
    a callback export must follow the same receipt policy as an ordinary return.
    """
    source_dir = source_dir or config.SOURCE_DIR
    header = (source_dir / "src/api/c/cvc5_c_structs.h").read_text()
    impl = (source_dir / "src/api/c/cvc5_c_structs.cpp").read_text()
    exported = dict((name, handle) for handle, name in re.findall(
        r"^(Cvc5\w+)\s+\w+::(export_\w+)\(", impl, re.M))
    registration = (source_dir / "src/api/c/cvc5.cpp").read_text()
    if not all(re.search(pattern, text) for pattern, text in (
        (r"Cvc5Plugin\* d_plugin;", header), (r"d_plugin\(plugin\)", header),
        (r"d_plugins.push_back\(\s*std::make_unique<Cvc5::PluginCpp>\([^;]*plugin\)\)", registration),
    )):
        raise SystemExit("plugin callback table retention changed; review ownership")
    methods = {}
    for m in re.finditer(r"Cvc5::PluginCpp::(\w+)\([^)]*\)\s*\{(.*?)^\}", impl, re.M | re.S):
        body = m.group(2)
        call = re.search(r"d_plugin->(\w+)\(", body)
        if not call:
            raise SystemExit(f"Plugin.{m.group(1)}: callback forwarding changed")
        states = set(re.findall(r"d_plugin->(\w+)\b(?!\w|\s*\()", body)) - {call.group(1)}
        if len(states) > 1:
            raise SystemExit("plugin callback has ambiguous state")
        exports = set(re.findall(r"->(export_\w+)\(", body))
        if not exports <= exported.keys():
            raise SystemExit("plugin callback export protocol changed")
        methods[m.group(1)] = {"field": call.group(1), "state": next(iter(states), None),
                               "exports": sorted(exported[name] for name in exports)}
    # The native wrapper exports each argument reference, borrows the returned
    # handle, and captures the state and function pointer in the solver.
    oracle = re.search(r"cvc5::Term call_oracle\((.*?)^\}", registration, re.M | re.S)
    declare = re.search(r"Cvc5Term cvc5_declare_oracle_fun\((.*?)^\}", registration, re.M | re.S)
    checker = (source_dir / "src/theory/quantifiers/oracle_checker.cpp").read_text()
    if not oracle or not declare or not all(re.search(pattern, text) for pattern, text in (
        (r"cterms.push_back\(cvc5->d_tm->export_term\(t\)\)", oracle.group(1)),
        (r"return fun\(cterms.size\(\), cterms.data\(\), state\)->d_term;", oracle.group(1)),
        (r"\[cvc5, state, fun\]", declare.group(1)),
        (r"declareOracleFun\(symbol, csorts, sort->d_sort, cfun\)", declare.group(1)),
        (r"if \(!CVC5_EQUAL\(ret.getType\(\), app.getType\(\)\)\).*?throw LogicException\(ss.str\(\)\);", checker.replace("\n", " ")),
    )):
        raise SystemExit("oracle callback ownership or recoverable output type check changed; review bridge")
    return {"retained_table": True, "methods": methods,
            "oracle": {"function": "cvc5_declare_oracle_fun", "arguments": exported["export_term"],
                       "result": "borrow", "retained_state": True, "type_error": "LogicException"}}


def main():
    impl = parse()
    print(f"{len(impl)} C functions implemented in {', '.join(IMPL_FILES)}")
    print(f"{sum(1 for v in impl.values() if v)} call at least one C++ API method")
    for handle, info in handles().items():
        print(f"  {handle}: exported by {info['exporter']}, receive by {info['receive']}")


if __name__ == "__main__":
    main()
