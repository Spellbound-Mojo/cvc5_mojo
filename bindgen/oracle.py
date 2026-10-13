"""Record what cvc5's Python examples print under the official bindings.

Runs every example of examples/api/python in the pinned source archive (a
script with an `if __name__ == "__main__":` block) with this Python, which in
the `oracle` pixi environment has cvc5 from PyPI at the pinned version. Each
example's standard output goes to tests/cvc5/examples/<name>.out and every
exit status to tests/cvc5/examples/status.json; `pixi run --locked cvc5-tests`
compares the translated examples with them.

Usage, in the oracle environment: python -m bindgen.oracle
"""

import json
import enum
import subprocess
import sys

from . import config, python_api, translate


def _null_query(cls, method):
    """Serialize a measured result without guessing its value or enum member."""
    import cvc5
    try:
        value = getattr(getattr(cvc5, cls)(), method)()
        if isinstance(value, bool):
            return dict(kind="bool", value=value)
        if isinstance(value, enum.Enum):
            return dict(kind="enum", type=type(value).__name__, name=value.name)
        if isinstance(value, list) and not value:
            return dict(kind="empty-list")
        if hasattr(value, "isNull") and value.isNull():
            return dict(kind="null", type=type(value).__name__)
        raise TypeError(f"unsupported null query result: {value!r}")
    except RuntimeError as e:
        return dict(kind="error", message=str(e))


def null_values():
    """Measure null formatting in isolated processes: some upstream types crash."""
    from importlib.metadata import version as package_version
    version = package_version("cvc5")
    if version != config.pinned()["version"]:
        raise SystemExit(f"oracle version {version} does not match the pin")
    classes, _, inits = python_api.parse_with_docs()
    values = {}
    for cls, methods in classes.items():
        if inits.get(cls, "self") != "self" or not any(m["name"] == "__str__" for m in methods):
            continue
        code = ("import cvc5, json\ntry:\n"
                f"    print(json.dumps(dict(text=str(cvc5.{cls}()))))\n"
                "except Exception as e:\n    print(json.dumps(dict(error=type(e).__name__)))\n")
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
        if proc.returncode < 0:
            values[cls] = {"error": f"signal {-proc.returncode}"}
        elif proc.returncode:
            raise SystemExit(f"null formatting oracle failed for {cls}: {proc.stderr}")
        else:
            values[cls] = json.loads(proc.stdout)
    queries = {}
    for cls in config.overrides()["null_compatibility"]["classes"]:
        if inits.get(cls, "self") != "self":
            raise SystemExit(f"{cls}: null query policy requires a default constructor")
        queries[cls] = {}
        for method in classes[cls]:
            name = method["name"]
            if name.startswith("_") or method["params"] != "self" or method["deprecated"]:
                continue
            code = ("import json\nfrom bindgen.oracle import _null_query\n"
                    f"print(json.dumps(_null_query({cls!r}, {name!r})))")
            proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
            if proc.returncode < 0:
                queries[cls][name] = dict(kind="unsafe", signal=-proc.returncode)
                continue
            if proc.returncode:
                raise SystemExit(f"null query oracle failed for {cls}.{name}: {proc.returncode}: {proc.stderr}")
            queries[cls][name] = json.loads(proc.stdout)
    config.API_DIR.mkdir(exist_ok=True)
    config.NULL_VALUES_FILE.write_text(json.dumps(dict(cvc5=version, classes=values, queries=queries), indent=1) + "\n")


def main():
    null_values()
    out = config.CVC5_EXAMPLES_DIR
    out.mkdir(parents=True, exist_ok=True)
    status = {}
    for path in translate.example_sources():
        name = translate.example_name(path)
        proc = subprocess.run([sys.executable, path.name], cwd=path.parent, capture_output=True, text=True,
                              timeout=600)
        (out / f"{name}.out").write_text(proc.stdout, encoding="utf-8")
        status[name] = proc.returncode
        print(f"{path.name}: exit {proc.returncode}, {len(proc.stdout.splitlines())} lines")
    (out / "status.json").write_text(json.dumps(status, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(config.ROOT)}: {len(status)} examples")


if __name__ == "__main__":
    main()
