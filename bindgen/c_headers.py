"""Extract every exported function prototype from the cvc5 C API headers.

Parsing is regex-based and therefore checked: `verify()` writes a C file
that assigns every function to a pointer of exactly the parsed type and
compiles it with -Werror against the same headers. A parsing mistake
becomes a compile error instead of a wrong binding.

`types()` classifies the type names the prototypes use: handles (pointer
typedefs such as `Cvc5Term`), opaque structs (`Cvc5TermManager`, only ever
used through a pointer), complete structs (`Cvc5OptionInfo`, whose layout
callers see) and enums (`Cvc5Kind`). The raw-layer generator checks how it
represents each of them with `compile_check()`.

For complete structs, `layouts()` parses the fields and has the C compiler
measure them: a generated program checks each parsed field type, then prints
every offset and size. It also prints the values of the plain C enums that
only struct fields use (`Cvc5OptionInfoKind`). Layouts are never computed
from the parse.

Usage: python -m bindgen.c_headers   (prints a summary; verifies)
"""

import re
import subprocess
import sys
import tempfile

from . import config


def owner_lifecycle(functions, ctype):
    """Find the unique constructor/destructor of an opaque C owner type."""
    section = [n for n, f in functions.items() if f["section"] == ctype]
    new = [n for n in section if n.endswith("_new") and functions[n]["returns"] == ctype + "*"]
    delete = [n for n in section if n.endswith("_delete")
              and [p["type"] for p in functions[n]["params"]] == [ctype + "*"]]
    if len(new) != 1 or len(delete) != 1:
        raise SystemExit(f"{ctype}: expected one _new and one _delete function, found {new} {delete}")
    return new[0], delete[0]

ENUM_HEADERS = [
    "cvc5/cvc5_kind.h",
    "cvc5/cvc5_types.h",
    "cvc5/cvc5_proof_rule.h",
    "cvc5/cvc5_skolem_id.h",
]
HEADERS = ["cvc5/c/cvc5.h", "cvc5/c/cvc5_parser.h"] + ENUM_HEADERS
SECTION_RE = re.compile(r"^/\*\s+(Cvc5\w*)\s+\*/\s*$")
PROTO_RE = re.compile(r"CVC5_EXPORT\s+([^;{}#]+?)\b(cvc5_\w+)\s*\(([^;{}#]*?)\)\s*;", re.S)
DOC_RE = re.compile(r"/\*\*((?:(?!\*/).)*)\*/\s*$", re.S)

# Functions in headers without section markers are classified by prefix.
PREFIX_SECTIONS = [
    ("cvc5_has_error", "Error"),
    ("cvc5_get_error_message", "Error"),
    ("cvc5_reset_error", "Error"),
    ("cvc5_symbol_manager_", "Cvc5SymbolManager"),
    ("cvc5_sm_", "Cvc5SymbolManager"),
    ("cvc5_parser_", "Cvc5InputParser"),
    ("cvc5_cmd_", "Cvc5Command"),
]


def _strip_comments(text):
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


DEPRECATED_RE = re.compile(r"__attribute__\s*\(\(\s*deprecated\s*\(\s*\"([^\"]*)\"\s*\)\s*\)\)")
FNPTR_RE = re.compile(r"(.+?)\(\s*\*\s*(\w+)\s*\)\s*\((.*)\)$")


def _top_level_split(text):
    """Split on commas that are not inside parentheses."""
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
            continue
        depth += ch == "("
        depth -= ch == ")"
        cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts]


def _normalize(ctype):
    return re.sub(r"\s*\*", "*", " ".join(ctype.split()))


def _split_params(params):
    params = " ".join(params.split())
    if params in ("", "void"):
        return []
    out = []
    for raw in _top_level_split(params):
        fn = FNPTR_RE.match(raw)
        if fn:
            args = ", ".join(_normalize(a) for a in _top_level_split(fn.group(3)))
            out.append({"type": f"{_normalize(fn.group(1))} (*)({args})", "name": fn.group(2), "callback": True,
                        "returns": _normalize(fn.group(1)), "params": _split_params(fn.group(3))})
            continue
        m = re.match(r"(.+?)\s*\b(\w+)\s*(\[\s*\])?$", raw)
        if m:
            out.append({"type": _normalize(m.group(1)) + ("*" if m.group(3) else ""), "name": m.group(2)})
        else:
            out.append({"type": raw, "name": ""})
    return out


def _doc_before(raw_lines, lineno):
    """Return the doxygen comment that ends on the line before `lineno`."""
    end = lineno - 1
    while end >= 0 and not raw_lines[end].strip():
        end -= 1
    if end < 0 or not raw_lines[end].strip().endswith("*/"):
        return ""
    start = end
    while start >= 0 and "/**" not in raw_lines[start]:
        start -= 1
    if start < 0:
        return ""
    body = []
    for line in raw_lines[start : end + 1]:
        line = line.strip().removeprefix("/**").removesuffix("*/").strip()
        body.append(re.sub(r"^\*\s?", "", line))
    return "\n".join(body).strip()


def parse(include_dir=None):
    include_dir = include_dir or config.INCLUDE_DIR
    records = []
    for rel in HEADERS:
        raw = (include_dir / rel).read_text(encoding="utf-8")
        raw_lines = raw.splitlines()
        sections = []
        for lineno, line in enumerate(raw_lines):
            m = SECTION_RE.match(line.strip())
            if m:
                sections.append((lineno, m.group(1)))
        # Comments are blanked (newlines kept), so line numbers in `code`
        # and `raw` agree.
        code = _strip_comments(raw)
        for m in PROTO_RE.finditer(code):
            lineno = code.count("\n", 0, m.start())
            section = None
            for start, name in sections:
                if start <= lineno:
                    section = name
            if section is None and rel in ENUM_HEADERS:
                section = "Enums"
            if section is None:
                section = next((s for p, s in PREFIX_SECTIONS if m.group(2).startswith(p)), "?")
            returns = m.group(1)
            dep = DEPRECATED_RE.search(returns)
            records.append(
                {
                    "name": m.group(2),
                    "header": rel,
                    "section": section,
                    "returns": _normalize(DEPRECATED_RE.sub("", returns)),
                    "params": _split_params(m.group(3)),
                    "deprecated": dep.group(1) if dep else None,
                    "doc": _doc_before(raw_lines, lineno),
                }
            )
    return records


TYPEDEF_HANDLE_RE = re.compile(r"^typedef\s+struct\s+\w+\s*\*\s*(\w+)\s*;", re.M)
TYPEDEF_STRUCT_RE = re.compile(r"^typedef\s+struct\s+(\w+)\s+(\w+)\s*;", re.M)
STRUCT_BODY_RE = re.compile(r"^struct\s+(\w+)\s*\{", re.M)
TYPEDEF_ENUM_RE = re.compile(r"^typedef\s+enum\s+ENUM\((\w+)\)\s+ENUM\(\1\)\s*;", re.M)
ENUM_MACRO_RE = re.compile(r"#define\s+ENUM\(name\)\s+(\w+)##name")


def types(include_dir=None, cc=None):
    """Return {C type name: {"kind": "handle" | "opaque" | "struct" | "enum" | "c_enum", ...}}.

    Enums also carry their cvc5 name (`Cvc5Kind` -> "Kind"), the name of the
    generated Mojo enum. Structs carry their layout and C enums their values,
    both measured by `layouts()`.
    """
    include_dir = include_dir or config.INCLUDE_DIR
    texts = [_strip_comments((include_dir / rel).read_text(encoding="utf-8")) for rel in HEADERS]
    defined = {m.group(1) for text in texts for m in STRUCT_BODY_RE.finditer(text)}
    out = {}
    for text in texts:
        for m in TYPEDEF_HANDLE_RE.finditer(text):
            out[m.group(1)] = {"kind": "handle"}
        for m in TYPEDEF_STRUCT_RE.finditer(text):
            if m.group(1) == m.group(2):
                out[m.group(2)] = {"kind": "struct" if m.group(2) in defined else "opaque"}
        macro = ENUM_MACRO_RE.search(text)
        for m in TYPEDEF_ENUM_RE.finditer(text):
            if macro is None:
                sys.exit(f"enum {m.group(1)}: no C expansion of the ENUM macro")
            out[macro.group(1) + m.group(1)] = {"kind": "enum", "enum": m.group(1)}
    structs, c_enums = layouts(include_dir, cc)
    for name, layout in structs.items():
        out[name].update(layout)
    for name, values in c_enums.items():
        out[name] = {"kind": "c_enum", "values": values}
    return out


def _compile(lines, what, include_dir, cc, run):
    """Compile C `lines` after the C API headers with -Werror; exit on failure.
    With `run`, link and run the program and return its output."""
    include_dir = include_dir or config.INCLUDE_DIR
    cc = cc or config.c_compiler()
    source = ["#include <cvc5/c/cvc5.h>", "#include <cvc5/c/cvc5_parser.h>"] + lines
    flags = ["-std=c11", "-Werror", "-Wno-deprecated-declarations", "-I", str(include_dir)]
    with tempfile.TemporaryDirectory() as tmp:
        path = f"{tmp}/check.c"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(source) + "\n")
        target = ["-o", f"{tmp}/check"] if run else ["-fsyntax-only"]
        proc = subprocess.run([cc, *flags, path, *target], capture_output=True, text=True)
        if proc.returncode != 0:
            sys.exit(f"{what} failed:\n" + proc.stderr[-4000:])
        if run:
            return subprocess.run([f"{tmp}/check"], check=True, capture_output=True, text=True).stdout
    return None


def compile_check(lines, what, include_dir=None, cc=None):
    """Compile C `lines` after the C API headers with -Werror; exit on failure."""
    _compile(lines, what, include_dir, cc, run=False)


def run_program(lines, what, include_dir=None, cc=None):
    """Compile C `lines` (a program with `main`) after the C API headers with
    -Werror, run it, and return its output; exit on failure."""
    return _compile(lines, what, include_dir, cc, run=True)


STRUCT_DEF_RE = re.compile(r"^struct\s+(\w+)\s*\{", re.M)
PLAIN_ENUM_RE = re.compile(r"^typedef\s+enum\s*\{(.*?)\}\s*(\w+)\s*;", re.M | re.S)
NESTED_RE = re.compile(r"^struct\s+\w*\s*\{(.*)\}\s*(\w+)$", re.S)
FIELD_DEPRECATED_RE = re.compile(r"__attribute__\s*\(\(\s*deprecated\s*\(((?:\s*\"[^\"]*\")+)\s*\)\s*\)\)")


def _braced(text, start):
    """The text between the brace at `start` and the brace that closes it."""
    depth = 0
    for i in range(start, len(text)):
        depth += (text[i] == "{") - (text[i] == "}")
        if depth == 0:
            return text[start + 1 : i]
    sys.exit("unbalanced braces in a struct definition")


def _fields(body, prefix=""):
    """The leaf fields of a struct body: [{"name", "type", "deprecated"}].
    A member of a nested struct is named `outer.inner`."""
    decls, depth, cur = [], 0, ""
    for ch in body:
        if ch == ";" and depth == 0:
            decls.append(" ".join(cur.split()))
            cur = ""
            continue
        depth += (ch == "{") - (ch == "}")
        cur += ch
    if cur.strip():
        sys.exit(f"unterminated struct member `{cur.strip()}`")
    out = []
    for decl in decls:
        nested = NESTED_RE.match(decl)
        if nested:
            out += _fields(nested.group(1), prefix + nested.group(2) + ".")
            continue
        dep = FIELD_DEPRECATED_RE.search(decl)
        parsed = _split_params(FIELD_DEPRECATED_RE.sub("", decl))
        if len(parsed) != 1 or not parsed[0]["name"]:
            sys.exit(f"cannot parse the struct member `{decl}`")
        field = {"name": prefix + parsed[0]["name"], "type": parsed[0]["type"],
                 "deprecated": "".join(re.findall(r'"([^"]*)"', dep.group(1))) if dep else None}
        if parsed[0].get("callback"):
            field.update({k: parsed[0][k] for k in ("callback", "returns", "params")})
        out.append(field)
    return out


def layouts(include_dir=None, cc=None):
    """Return ({struct: {"size", "align", "fields"}}, {C enum: {name: value}}).

    Structs are those defined in the C API headers; each field gets its
    `offset` and `size`. The C enums are the `typedef enum { ... } Name`
    types, which only struct fields use. The C compiler checks every parsed
    field type and measures everything.
    """
    include_dir = include_dir or config.INCLUDE_DIR
    texts = [_strip_comments((include_dir / rel).read_text(encoding="utf-8")) for rel in HEADERS]
    structs, enums = {}, {}
    for text in texts:
        for m in STRUCT_DEF_RE.finditer(text):
            structs[m.group(1)] = _fields(_braced(text, m.end() - 1))
        for m in PLAIN_ENUM_RE.finditer(text):
            enums[m.group(2)] = [e.split("=")[0].strip() for e in m.group(1).split(",") if e.strip()]
    lines = ["#include <stddef.h>", "#include <stdio.h>", "int main(void) {"]
    for name, fields in structs.items():
        t = f"struct {name}"
        lines.append(f'  printf("struct|{name}|%zu|%zu\\n", sizeof({t}), _Alignof({t}));')
        for f in fields:
            member = f"((({t}*)0)->{f['name']})"
            lines += [f'  _Static_assert(__builtin_types_compatible_p(__typeof__({member}), {f["type"]}), '
                      f'"{name}.{f["name"]} is {f["type"]}");',
                      f'  printf("field|{name}|{f["name"]}|%zu|%zu\\n", offsetof({t}, {f["name"]}), sizeof({member}));']
    for name, entries in enums.items():
        lines += [f'  printf("enum|{name}|{e}|%lld\\n", (long long){e});' for e in entries]
    lines += ["  return 0;", "}"]
    measured = {"struct": {}, "field": {}, "enum": {}}
    for row in run_program(lines, "C layout extraction", include_dir, cc).splitlines():
        kind, owner, *rest = row.split("|")
        if kind == "struct":
            measured[kind][owner] = rest
        else:
            measured[kind][(owner, rest[0])] = rest[1:]
    out = {}
    for name, fields in structs.items():
        size, align = measured["struct"][name]
        for f in fields:
            offset, fsize = measured["field"][(name, f["name"])]
            f["offset"], f["size"] = int(offset), int(fsize)
        out[name] = {"size": int(size), "align": int(align), "fields": fields}
    values = {name: {e: int(measured["enum"][(name, e)][0]) for e in entries} for name, entries in enums.items()}
    return out, values


def verify(records, include_dir=None, cc=None):
    """Compile a pointer assignment per function; exit on any mismatch."""
    lines = []
    for r in records:
        params = ", ".join(p["type"] for p in r["params"]) or "void"
        lines.append(f"{r['returns']} (*const check_{r['name']})({params}) = {r['name']};")
    compile_check(lines, "C API signature verification", include_dir, cc)


def main():
    records = parse()
    verify(records)
    counts = {}
    for r in records:
        counts[r["section"]] = counts.get(r["section"], 0) + 1
    print(f"{len(records)} C API functions, all signatures verified by the C compiler")
    for name, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {name}: {n}")


if __name__ == "__main__":
    main()
