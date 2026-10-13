"""Summarize the API difference between two snapshots.

Used for cvc5 upgrade pull requests: compares the committed snapshot
(git HEAD) with the freshly generated one and prints Markdown.

Usage:
    python -m bindgen.diff                  # HEAD:api/cvc5-api.json vs working tree
    python -m bindgen.diff OLD.json NEW.json
"""

import json
import subprocess
import sys

from . import config


def _load_head():
    rel = config.SNAPSHOT_FILE.relative_to(config.ROOT)
    out = subprocess.run(
        ["git", "show", f"HEAD:{rel}"], cwd=config.ROOT, capture_output=True, text=True
    )
    if out.returncode != 0:
        sys.exit(f"cannot read {rel} at HEAD: {out.stderr.strip()}")
    return json.loads(out.stdout)


def _sig(r):
    return f"{r['returns']} ({', '.join(p['type'] for p in r['params'])})"


def diff(old, new):
    lines = [f"## cvc5 API changes: {old['cvc5']['version']} -> {new['cvc5']['version']}", ""]

    def block(title, items):
        if items:
            lines.extend([f"### {title} ({len(items)})", ""] + items + [""])

    oc, nc = old["c_functions"], new["c_functions"]
    block("C functions added", [f"- `{n}` {_sig(nc[n])}" for n in nc if n not in oc])
    block("C functions removed", [f"- `{n}`" for n in oc if n not in nc])
    block(
        "C signatures changed",
        [f"- `{n}`: {_sig(oc[n])} -> {_sig(nc[n])}" for n in nc if n in oc and _sig(oc[n]) != _sig(nc[n])],
    )
    block(
        "C functions newly deprecated",
        [f"- `{n}`: {nc[n]['deprecated']}" for n in nc if nc[n].get("deprecated") and not oc.get(n, {}).get("deprecated")],
    )

    block(
        "C parameters tested for NULL changed",
        [f"- `{n}`: {oc[n].get('null_tested', [])} -> {nc[n].get('null_tested', [])}"
         for n in nc if n in oc and oc[n].get("null_tested", []) != nc[n].get("null_tested", [])],
    )

    block(
        "C functions moved between libraries",
        [f"- `{n}`: {oc[n].get('library', 'unknown')} -> {nc[n]['library']}"
         for n in nc if n in oc and oc[n].get("library") and oc[n].get("library") != nc[n].get("library")],
    )

    ot, nt = old.get("c_types", {}), new.get("c_types", {})

    def type_change(t):
        a, b = ot.get(t, {}), nt.get(t, {})
        if a.get("kind") != b.get("kind"):
            return f"{a.get('kind', 'absent')} -> {b.get('kind', 'absent')}"
        fields = lambda info: {f["name"]: (f["type"], f["offset"], f["size"]) for f in info.get("fields", [])}
        changed = sorted(n for n in set(fields(a)) | set(fields(b)) if fields(a).get(n) != fields(b).get(n))
        if changed or (a.get("size"), a.get("align")) != (b.get("size"), b.get("align")):
            return f"layout changed (size {a.get('size')} -> {b.get('size')}; fields {', '.join(changed) or 'none'})"
        return f"values {a.get('values')} -> {b.get('values')}" if a.get("values") != b.get("values") else "changed"

    block("C type changes", [f"- `{t}`: {type_change(t)}" for t in sorted(set(ot) | set(nt)) if ot.get(t) != nt.get(t)])

    oh, nh = old.get("handles", {}), new.get("handles", {})
    block(
        "Handle ownership changes",
        [f"- `{h}`: {oh.get(h, {}).get('receive', 'absent')} -> {nh.get(h, {}).get('receive', 'absent')}"
         for h in sorted(set(oh) | set(nh)) if oh.get(h) != nh.get(h)],
    )

    old_maps, new_maps = old.get("cpp_maps", {}), new.get("cpp_maps", {})
    block(
        "C++ map declarations changed",
        [f"- `{m}`: {old_maps.get(m, 'absent')} -> {new_maps.get(m, 'absent')}"
         for m in sorted(set(old_maps) | set(new_maps)) if old_maps.get(m) != new_maps.get(m)],
    )

    enum_items = []
    for e in sorted(set(old["enums"]) | set(new["enums"])):
        ov, nv = old["enums"].get(e, {}), new["enums"].get(e, {})
        added = [k for k in nv if k not in ov]
        removed = [k for k in ov if k not in nv]
        changed = [k for k in nv if k in ov and nv[k] != ov[k]]
        if added:
            enum_items.append(f"- {e}: added " + ", ".join(added))
        if removed:
            enum_items.append(f"- {e}: removed " + ", ".join(removed))
        if changed:
            enum_items.append(f"- {e}: renumbered " + ", ".join(f"{k} {ov[k]}->{nv[k]}" for k in changed))
    block("Enum changes", enum_items)

    oo, no = old.get('options', {}), new.get('options', {})
    block('Solver options added', [f'- `{n}`' for n in no if n not in oo])
    block('Solver options removed', [f'- `{n}`' for n in oo if n not in no])
    block('Solver option metadata changed', [
        f"- `{n}`: " + ', '.join(k for k in sorted(set(oo[n]) | set(no[n]))
                                if oo[n].get(k) != no[n].get(k))
        for n in no if n in oo and oo[n] != no[n]
    ])

    added, removed, status = [], [], []
    for cls in sorted(set(old["python"]) | set(new["python"])):
        om = old["python"].get(cls, {}).get("methods", {})
        nm = new["python"].get(cls, {}).get("methods", {})
        added += [f"- `{cls}.{n}({nm[n]['params']})`: {nm[n]['binding']['status']}" for n in nm if n not in om]
        removed += [f"- `{cls}.{n}`" for n in om if n not in nm]
        for n in nm:
            if n in om and om[n]["binding"] != nm[n]["binding"]:
                status.append(f"- `{cls}.{n}`: {om[n]['binding']} -> {nm[n]['binding']}")
    block("Python methods added", added)
    block("Python methods removed", removed)
    block("Binding changes", status)
    if len(lines) == 2:
        lines.append("No API changes.")
    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) == 3:
        old, new = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:])
    elif len(sys.argv) == 1:
        old, new = _load_head(), json.loads(config.SNAPSHOT_FILE.read_text(encoding="utf-8"))
    else:
        sys.exit(__doc__)
    sys.stdout.write(diff(old, new))


if __name__ == "__main__":
    main()
