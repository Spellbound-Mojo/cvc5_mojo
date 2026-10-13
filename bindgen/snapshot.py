"""Build the API snapshot: join the C API with the Python API.

Inputs, all extracted from the pinned cvc5 release (cvc5-version.toml):

  C headers  -> C functions, compiler-verified    bindgen.c_headers
  C headers  -> enum values, compiled and run      bindgen.enums
  libraries  -> library exporting each function    bindgen.c_library
  C API impl -> C function -> C++ methods          bindgen.c_impl
  C API impl -> parameters tested for NULL         bindgen.c_impl.null_tested
  cvc5.pxi   -> Python method -> C++ methods       bindgen.python_api
  cvc5.pxi   -> parameter each C++ argument reads  bindgen.python_api
  cvc5.pxd   -> C++ methods with std::map types    bindgen.cpp_api

plus the one hand-maintained input, bindgen/overrides.toml.

Output, committed so that a cvc5 upgrade shows up as a git diff:

  api/cvc5-api.json  every C function, C type, enum and Python method, the
                     binding chosen for each Python method, handle ownership,
                     and the C++ methods whose maps Python makes dictionaries

The documentation site renders the coverage report and the API reference
from this file (bindgen.report, bindgen.reference).

Every Python method gets exactly one binding status:

  auto        the join found exactly one C function
  overloaded  the join found several C functions (Mojo overloads)
  rule        a generic rule from overrides.toml (e.g. __eq__ -> *_is_equal)
  alias       delegates to another wrapper (e.g. Solver -> TermManager)
  override    C functions named explicitly in overrides.toml
  manual      hand-written Mojo; overrides.toml names the C functions used
  skip        not mirrored; overrides.toml gives the reason
  deprecated  deprecated in cvc5; not mirrored by policy
  unresolved  none of the above

Usage: python -m bindgen.snapshot [--check]

--check exits non-zero on unresolved methods, stale overrides, or an
automatic-join fraction below policy.min_auto_fraction.
"""

import argparse
import json
import sys

from . import c_headers, c_impl, c_library, config, cpp_api, enums, options, python_api
from .report import AUTOMATIC, STATUSES, summarize


def _resolve(cls, method, cinfo, cfuncs, by_section, ov, problems):
    """Return the binding record for one Python method."""
    key = f"{cls}.{method['name']}"
    entry = ov.get("methods", {}).get(key)
    if entry:
        for c in entry.get("c", []) + entry.get("manual", []):
            if c not in cfuncs:
                problems.append(f"overrides.toml [{key}] names unknown C function {c}")
        note = {k: entry[k] for k in ("note", "kind", "private") if k in entry}
        if "skip" in entry:
            return {"status": "skip", "reason": entry["skip"]}
        if "alias" in entry:
            return {"status": "alias", "to": entry["alias"], **note}
        if "manual" in entry:
            return {"status": "manual", "c": entry["manual"], **note}
        return {"status": "override", "c": entry["c"], **note}

    if method["deprecated"] and ov["policy"].get("skip_deprecated", True):
        return {"status": "deprecated"}

    calls = set(method["cpp_calls"])
    if calls and cinfo:
        cands = sorted(c for c in by_section.get(cinfo["section"], []) if calls & set(cfuncs[c]["cpp_calls"]))
        # Prefer C functions that call exactly the same C++ methods. This
        # drops e.g. cvc5_term_get_symbol (which checks hasSymbol first)
        # from Term.hasSymbol.
        exact = [c for c in cands if set(cfuncs[c]["cpp_calls"]) == calls]
        cands = exact or cands
        if len(cands) == 1:
            return {"status": "auto", "c": cands}
        if cands:
            return {"status": "overloaded", "c": cands}

    for rule in ov.get("rules", []):
        if method["name"] in rule["methods"] and cinfo:
            for template in rule["c"]:
                c = template.format(prefix=cinfo["prefix"])
                if c in cfuncs:
                    return {"status": "rule", "c": [c]}
            if "fallback" in rule:
                return {"status": "rule", "c": [], "fallback": rule["fallback"]}

    if method["delegates"]:
        target = method["delegates"][0].split(".", 1)
        owner = {"tm": "TermManager", "solver": "Solver", "sm": "SymbolManager"}[target[0]]
        return {"status": "alias", "to": f"{owner}.{target[1]}"}

    return {"status": "unresolved"}


def build():
    pin = config.pinned()
    ov = config.overrides()
    problems = []

    impl = c_impl.parse()
    records = c_headers.parse()
    libraries = c_library.exports([r["name"] for r in records])
    for target in pin['binary']:
        if c_library.exports(libraries, config.binary_dir(target) / 'lib') != libraries:
            raise ValueError(f"C API exporting libraries differ on {target}")
    tested = c_impl.null_tested({r["name"]: [p["name"] for p in r["params"] if "*" in p["type"] and p["name"]]
                                 for r in records})
    cfuncs = {}
    for r in records:
        r["cpp_calls"] = impl.get(r["name"], [])
        r["library"] = libraries[r["name"]]
        if r["name"] in tested:
            r["null_tested"] = tested[r["name"]]
        cfuncs[r.pop("name")] = r
    by_section = {}
    for name, r in cfuncs.items():
        by_section.setdefault(r["section"], []).append(name)

    py, class_docs, inits = python_api.parse_with_docs()
    classes = ov["classes"]
    python = {}
    for cls, methods in py.items():
        cinfo = classes.get(cls)
        if cinfo is None:
            problems.append(f"Python class {cls} has no [classes] entry in overrides.toml")
        out = {}
        for m in methods:
            m = dict(m)
            m["binding"] = _resolve(cls, m, cinfo, cfuncs, by_section, ov, problems)
            out[m.pop("name")] = m
        python[cls] = {**(cinfo or {}), "doc": class_docs.get(cls, ""), "init": inits.get(cls, "self"), "methods": out}

    enum_values = enums.values()
    null_values = json.loads(config.NULL_VALUES_FILE.read_text())
    if null_values["cvc5"] != pin["version"]:
        problems.append("null formatting oracle is stale; run the pinned oracle environment")
    for cls, value in null_values["classes"].items():
        if cls not in python:
            problems.append(f"null formatting oracle names an unknown class: {cls}")
        else:
            python[cls]["null_printing"] = value
    for cls, queries in null_values.get("queries", {}).items():
        for name, value in queries.items():
            method = python.get(cls, {}).get("methods", {}).get(name)
            if method is None or method["params"] != "self":
                problems.append(f"null query oracle names an invalid method: {cls}.{name}")
            else:
                method["null_result"] = value
    if set(null_values.get("queries", {})) != set(ov["null_compatibility"]["classes"]):
        problems.append("null query oracle is stale; run the pinned oracle environment")
    for cls, info in python.items():
        for name, m in info["methods"].items():
            kind = m["binding"].get("kind")
            if kind is not None and kind not in dict(enum_values["Kind"]):
                problems.append(f"overrides.toml [methods.\"{cls}.{name}\"] names unknown Kind {kind}")

    redundant = []
    extensions = {}
    for key, entry in ov.get("extensions", {}).items():
        cls, _, name = key.partition(".")
        native = entry.get("manual", [])
        if (cls not in python or name in python[cls]["methods"] or len(native) != 1
                or native[0] not in cfuncs or cfuncs[native[0]]["section"] != classes[cls]["section"]):
            problems.append(f"overrides.toml extension {key} is not an unambiguous C-only method")
            continue
        extensions.setdefault(cls, {})[name] = {
            "doc": cfuncs[native[0]]["doc"],
            "binding": {"status": "manual", "c": native},
        }
    without = {**ov, "methods": {}}
    for key, entry in ov.get("methods", {}).items():
        cls, _, name = key.partition(".")
        method = python.get(cls, {}).get("methods", {}).get(name)
        if method is None:
            problems.append(f"overrides.toml [methods.\"{key}\"] is stale: no such Python method")
            continue
        # An entry is redundant if the extracted data alone gives the same C functions.
        auto = _resolve(cls, {"name": name, **method}, classes.get(cls), cfuncs, by_section, without, [])
        if "c" in entry and auto["status"] in AUTOMATIC + ("rule",) and auto.get("c") == entry["c"]:
            redundant.append(key)

    return {
        "cvc5": {"version": pin["version"], "commit": pin["commit"]},
        "runtime": ov["runtime"],
        "generation": ov["generation"],
        "none_bool_defaults": cpp_api.none_bool_defaults(ov["none_bool_defaults"]),
        "handles": c_impl.handles(),
        "callbacks": c_impl.callbacks(),
        "extensions": extensions,
        "c_types": c_headers.types(),
        "c_functions": cfuncs,
        "native_libraries": {target: c_library.native_inventory(config.binary_dir(target) / "lib")
                             for target in sorted(pin["binary"])},
        "enums": {e: dict(v) for e, v in enum_values.items()},
        "cpp_maps": cpp_api.maps(),
        "enum_docs": enums.documentation(),
        "options": options.extract(),
        "python": python,
        "redundant_overrides": redundant,
    }, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail on unresolved methods or stale overrides")
    args = ap.parse_args()

    snap, problems = build()
    summary = summarize(snap)
    ov = config.overrides()
    config.API_DIR.mkdir(exist_ok=True)
    with open(config.SNAPSHOT_FILE, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    t = summary["total"]
    print(
        f"cvc5 {snap['cvc5']['version']}: {summary['c_total']} C functions, "
        f"{sum(t.values())} Python methods; " + ", ".join(f"{s} {t[s]}" for s in STATUSES if t[s])
    )
    print(f"automatic join fraction {summary['auto_fraction']:.1%}")
    print(f"wrote {config.SNAPSHOT_FILE.relative_to(config.ROOT)}")
    for p in problems:
        print(f"problem: {p}")
    for name in summary["unresolved"]:
        print(f"unresolved: {name} (add an entry to bindgen/overrides.toml)")

    if args.check:
        from . import gen_api, gen_raw, generation_policy
        _, excluded = gen_raw.classify(snap)
        generation_policy.check(excluded, snap["generation"]["unbound_c"], "raw C API")
        _, table = gen_api.generated(snap)
        generation_policy.check(generation_policy.missing_methods(table), snap["generation"]["missing_methods"], "base API")
        failures = list(problems)
        if t["unresolved"]:
            failures.append(f"{t['unresolved']} unresolved Python methods (listed above)")
        if summary["auto_fraction"] < ov["policy"]["min_auto_fraction"]:
            failures.append("automatic join fraction below policy minimum")
        if failures:
            sys.exit("check failed:\n  " + "\n  ".join(failures))
        print("check passed")


if __name__ == "__main__":
    main()
