"""Coverage summaries of the API snapshot and of cvc5's translated tests,
as data and as Markdown.

The documentation site renders these with the `coverage` directive, and
`python -m bindgen.snapshot --check` uses the same summary for its gate.
"""

import re

from . import config, gen_api, gen_raw

STATUSES = ("auto", "overloaded", "rule", "alias", "override", "manual", "skip", "deprecated", "unresolved")
RESOLVED = ("auto", "overloaded", "rule", "alias", "override", "manual")
AUTOMATIC = ("auto", "overloaded")
RUNTIME_SUFFIXES = ("_copy", "_release", "_new", "_delete")


def _methods(snap):
    for cls, info in snap["python"].items():
        for name, m in info["methods"].items():
            yield cls, name, m


def public_c_functions(snap):
    """Conservative native-call inventory of emitted public bindings and runtime.

    Used only to drop old trace entries that no longer have any public call
    site. Presence is not evidence that a test executed the function.
    """
    model, table = gen_api.generated(snap)
    texts = [gen_api.emit_module(model, cls, methods, snap["cvc5"]["version"])
             for cls, methods in table.items()]
    texts += [(config.PACKAGE_DIR / "_c/ffi.mojo").read_text(),
              "\n".join(gen_raw.version_probe(snap, model.raw_bound))]
    mentioned = set(re.findall(r"\bcvc5_\w+\b", "\n".join(texts)))
    return mentioned & snap["c_functions"].keys()


def summarize(snap):
    rows = {cls: dict.fromkeys(STATUSES, 0) for cls in snap["python"]}
    for cls, _, m in _methods(snap):
        rows[cls][m["binding"]["status"]] += 1
    total = {s: sum(r[s] for r in rows.values()) for s in STATUSES}
    joinable = [m for _, n, m in _methods(snap)
                if not n.startswith("__") and m["binding"]["status"] not in ("deprecated", "skip")]
    auto = [m for m in joinable if m["binding"]["status"] in AUTOMATIC]
    used = {c for _, _, m in _methods(snap) for c in m["binding"].get("c", [])}
    runtime = {n for n, f in snap["c_functions"].items() if n.endswith(RUNTIME_SUFFIXES) or f["section"] == "Error"}
    return {
        "rows": rows,
        "total": total,
        "auto_fraction": len(auto) / len(joinable) if joinable else 0.0,
        "c_total": len(snap["c_functions"]),
        "c_used": len(used),
        "c_used_names": used,
        "c_runtime": len(runtime),
        "c_runtime_names": runtime,
        "c_only": [n for n in snap["c_functions"] if n not in used and n not in runtime],
        "unresolved": [f"{c}.{n}" for c, n, m in _methods(snap) if m["binding"]["status"] == "unresolved"],
    }


def report_markdown(snap, min_auto_fraction):
    """The full coverage report: totals, the per-class table and review lists."""
    s = summarize(snap)
    t = s["total"]
    _, table = gen_api.generated(snap)
    mirrored = sum(len(methods) for methods in table.values())
    generated = sum(1 for methods in table.values() for ovs, _ in methods.values() if ovs)
    hand = sum(1 for methods in table.values() for ovs, _ in methods.values()
               if ovs and all(o.get("kind") == "manual" for o in ovs))
    lines = [
        f"- **C API functions:** {s['c_total']}. The C compiler checks every signature. "
        f"{s['c_used']} implement Python methods, {s['c_runtime']} manage lifetimes and errors, and "
        f"{len(s['c_only'])} have no Python counterpart; the raw layer binds those too.",
        f"- **Python methods:** {sum(t.values())}. {sum(t[x] for x in RESOLVED)} have a binding, "
        f"{t['skip']} are skipped, {t['deprecated']} are deprecated, and **{t['unresolved']}** are unresolved.",
        f"- **Automatic join:** {s['auto_fraction']:.1%} of the non-deprecated methods, operators such as "
        f"`__eq__` aside, are matched to C functions automatically. The gate requires {min_auto_fraction:.0%}.",
        f"- **Enums:** {len(snap['enums'])}, with {sum(len(e) for e in snap["enums"].values()):,} values.",
        f"- **Base API:** {generated} of the {mirrored} mirrored methods are generated, in {len(table)} classes. "
        f"{hand} of them use hand-written code from `bindgen/manual/`. The others are [listed below](#base-api).",
        "",
        "| Class | " + " | ".join(STATUSES) + " |",
        "|---|" + "---:|" * len(STATUSES),
    ]
    for cls, r in s["rows"].items():
        lines.append(f"| `{cls}` | " + " | ".join(str(r[x] or "") for x in STATUSES) + " |")
    lines.append("| **Total** | " + " | ".join(f"**{t[x]}**" for x in STATUSES) + " |")

    def section(title, intro, items):
        lines.extend(["", f"## {title}", "", intro, ""])
        lines.extend(items or ["None."])

    section("Unresolved", "Python methods without a binding. The gate fails while this list is not empty.",
            [f"- `{u}`" for u in s["unresolved"]])
    section("Redundant overrides",
            "Entries in `bindgen/overrides.toml` that the extracted data now resolves on its own. Delete them.",
            [f"- `{k}`" for k in snap.get("redundant_overrides", [])])
    section("Overloaded",
            "The join found several C functions for each of these methods, and each function becomes a Mojo "
            "overload. Review this list after a bump: a candidate that does not belong adds a wrong overload.",
            [f"- `{c}.{n}`: " + ", ".join(f"`{f}`" for f in m["binding"]["c"])
             for c, n, m in _methods(snap) if m["binding"]["status"] == "overloaded"])
    by_section = {}
    for n in s["c_only"]:
        by_section.setdefault(snap["c_functions"][n]["section"], []).append(n)
    section("C-only functions",
            "No Python method uses these functions. The raw layer binds them. Most are typed variants of "
            "Python methods, such as `cvc5_term_get_int64_value`.",
            [f"- **{sec}**: " + ", ".join(f"`{n}`" for n in names) for sec, names in by_section.items()])
    section("Base API",
            "Mirrored Python methods that `bindgen.gen_api` does not generate, and why.",
            [f"- `{cls}.{name}`: {reason}." for cls, methods in table.items()
             for name, (ovs, reason) in methods.items() if not ovs])
    bound, excluded = gen_raw.classify(snap)
    section("Raw layer",
            f"The generated raw layer binds {len(bound)} of the {s['c_total']} C functions. The others use C "
            "types that it does not represent:",
            [f"- `{n}` {reason}." for n, reason in excluded.items()])
    return "\n".join(lines) + "\n"


def tests_markdown(translation):
    """cvc5's Python unit tests and examples in Mojo, from
    tests/cvc5/translation.json: which run, and why the others do not."""
    files = translation["files"]
    keys = ("run", "left_out", "not_translated")
    total = {k: sum(len(f[k]) for f in files.values()) for k in keys}
    lines = [
        f"- **Tests:** {sum(total.values())} in the {len(files)} files of cvc5's `{translation['source']}`. "
        f"{total['run']} are translated by `bindgen.translate` and pass in Mojo, {total['left_out']} are "
        f"translated but left out, and {total['not_translated']} are not translated.",
        "",
        "| File | Run | Left out | Not translated |",
        "|---|---:|---:|---:|",
    ]
    for name, f in files.items():
        lines.append(f"| `{name}` | " + " | ".join(str(len(f[k]) or "") for k in keys) + " |")
    lines.append("| **Total** | " + " | ".join(f"**{total[k]}**" for k in keys) + " |")
    if translation["stale"]:
        lines += ["", "**Stale entries**, which make `pixi run --locked cvc5-tests` fail:", ""]
        lines += [f"- {problem}" for problem in translation["stale"]]
    lines += ["", "### Left out", "",
              "These translated tests cannot pass in Mojo. They are listed in `[tests]` of "
              "`bindgen/overrides.toml`, with the reason. `pixi run --locked cvc5-tests` builds each one on its "
              "own and requires the documented failure phase and diagnostic. Passing exclusions, unrelated failures, "
              "crashes, and timeouts fail the run.", ""]
    lines += [f"- `{name}` `{test}`: {reason}" for name, f in files.items()
              for test, reason in f["left_out"].items()] or ["None."]
    lines += ["", "### Not translated", "",
              "These tests use Python that the translator does not handle. Each line names the first such "
              "construct.", ""]
    lines += [f"- `{name}` `{test}`: {reason}" for name, f in files.items()
              for test, reason in f["not_translated"].items()] or ["None."]
    lines += ["", "### Argument rejection", "",
              f"{len(translation['compile_fail'])} generated compile-fail fixtures check argument errors that "
              "Mojo rejects before execution. Each must fail at its marked call. Where Python evaluates "
              "an inner call before a statically invalid outer call, its runtime rejection is also retained.", ""]
    examples = translation["examples"]
    run = [name for name, e in examples.items() if "run" in e]
    exact = [name for name in run if not examples[name].get("model_output")]
    model = [name for name in run if examples[name].get("model_output")]
    lines += ["", "### Examples", "",
              f"cvc5's `{translation['example_source']}` has {len(examples)} examples. {len(exact)} are translated "
              "and print exactly what the Python example prints under the official bindings, as "
              "`bindgen.oracle` records it: " + ", ".join(f"`{name}`" for name in exact) + ".", ""]
    if model:
        lines += ["Model checks: " + ", ".join(f"`{name}`" for name in model) + ". The translated example "
                  "evaluates each assertion in every SAT model and checks each printed model value's sort "
                  "and equality to its term in that model. Only those value fields may differ from Python; "
                  "solver results, explanatory text, line order and exit status must match.", ""]
    lines += [f"{len(run)} examples run in total. The others:", ""]
    lines += [f"- `{name}`: " + (f"left out (`[examples]` in `bindgen/overrides.toml`): {e['left_out']}"
                                 if "left_out" in e else f"not translated: {e['not_translated']}")
              for name, e in examples.items() if "run" not in e] or ["None."]
    return "\n".join(lines) + "\n"


def calls_markdown(snap, calls):
    """Which C functions cvc5's translated tests and examples call, from
    tests/cvc5/calls.json, and the generated methods they never reach."""
    called = set(calls["calls"])
    s = summarize(snap)
    _, table = gen_api.generated(snap)
    def c_functions(cls, name):
        b = snap["python"][cls]["methods"][name]["binding"]
        if b["status"] == "alias":  # `Solver.mkSkolem` is `TermManager.mkSkolem`
            return c_functions(*b["to"].split("."))
        return set(b.get("c", []))

    behind = {(cls, name): c_functions(cls, name)
              for cls, methods in table.items() for name, (ovs, _) in methods.items() if ovs}
    unmeasured = [key for key, cs in behind.items() if not cs]  # a NULL-handle check, in Mojo
    behind = {key: cs for key, cs in behind.items() if cs}
    reached = {key for key, cs in behind.items() if cs & called}
    lines = [
        f"- **C functions:** the translated tests and examples call {len(called)} of the {s['c_total']}. "
        f"That is {len(called & s['c_used_names'])} of the {s['c_used']} that implement Python methods, "
        f"{len(called & s['c_runtime_names'])} of the {s['c_runtime']} that manage lifetimes and errors, and "
        f"{len(called & set(s['c_only']))} of the {len(s['c_only'])} with no Python counterpart.",
        f"- **Generated methods:** {len(behind)} generated methods call C functions. In a test or an example, "
        f"{len(reached)} of them call at least one; the others are listed below. "
        f"{len(unmeasured)} more methods call no C function, because "
        + ", ".join(sorted({f"`{n}`" for _, n in unmeasured}))
        + " checks for a NULL handle in Mojo, so they are not counted.",
        "",
        "| Class | Generated methods | Reached |",
        "|---|---:|---:|",
    ]
    for cls in table:
        keys = [k for k in behind if k[0] == cls]
        if keys:
            lines.append(f"| `{cls}` | {len(keys)} | {sum(k in reached for k in keys)} |")
    lines += ["", "### Methods no test or example reaches", ""]
    lines += [f"- `{cls}`: " + ", ".join(f"`{n}`" for c, n in behind if c == cls and (c, n) not in reached)
              for cls in table if any(k[0] == cls and k not in reached for k in behind)] or ["None."]
    lines += ["", "### C functions of reached methods that are not called", "",
              "No test or example takes these overloads or variants.", ""]
    lines += [f"- `{cls}.{name}`: " + ", ".join(f"`{c}`" for c in sorted(cs - called))
              for (cls, name), cs in behind.items() if (cls, name) in reached and cs - called] or ["None."]
    return "\n".join(lines) + "\n"


def handles_markdown(snap):
    """How a wrapper takes ownership of each handle type the C API returns."""
    lines = ["| Handle | Exported by | Receive |", "|---|---|---|"]
    for handle, info in snap["handles"].items():
        lines.append(f"| `{handle}` | `{info['exporter']}` | {info['receive']} |")
    return "\n".join(lines) + "\n"
