"""Convert cvc5's reStructuredText docstrings to Markdown.

One converter serves the documentation site now and the base-API generator
later (Mojo docstrings). It covers the subset cvc5.pxi uses:

* fields `:param name:` and `:return:`;
* directives `.. warning::`, `.. note::`, `.. code-block:: lang`, `.. code::`,
  nested inside each other;
* literal blocks introduced by a paragraph ending in `::`;
* roles `:py:meth:`, `:py:obj:`, `:cpp:class:`, `:math:`, `:ref:` and
  similar, and ``double-backtick`` literals, all rendered as code spans.

cvc5's docstrings mix indentation levels (a directive at column 0 next to
text at column 2), so every construct is delimited relative to the
indentation of the line that opens it, never to column 0.

Usage: `parse(doc)` returns the parts; `markdown(doc)` renders them.
"""

import re

ROLE_RE = re.compile(r":(?:[a-z]+:)?[a-z]+:`([^`]*)`")
LITERAL_RE = re.compile(r"``(.+?)``")
FIELD_RE = re.compile(r"^:(param|return|returns)(?:\s+([^:]+))?:\s*(.*)$")
DIRECTIVE_RE = re.compile(r"^\.\.\s+([a-z-]+)::\s*(.*)$")
ADMONITIONS = {"warning", "note"}
CODE = {"code-block", "code"}
FENCE_LANGUAGES = {"python": "python", "c": "c", "cpp": "cpp", "c++": "cpp"}


def _role(match):
    text = match.group(1)
    # :ref:`label <target>` shows the label; cross-references drop `~` and `cvc5.`.
    labelled = re.match(r"^(.*\S)\s+<[^>]+>$", text)
    text = (labelled.group(1) if labelled else text).lstrip("~")
    text = re.sub(r"^(?:cvc5\.|cvc5::)", "", text)
    return f"`{text}`"


def inline(text):
    """Render inline markup: roles and double-backtick literals become code spans."""
    text = LITERAL_RE.sub(lambda m: f"`{m.group(1)}`", text)
    return ROLE_RE.sub(_role, text)


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _block(lines, i, parent):
    """The lines after i that are blank or indented deeper than `parent`, dedented."""
    end = i
    while end < len(lines) and (not lines[end].strip() or _indent(lines[end]) > parent):
        end += 1
    block = lines[i:end]
    while block and not block[-1].strip():
        block.pop()
    while block and not block[0].strip():
        block.pop(0)
    if not block:
        return [], end
    depth = min(_indent(l) for l in block if l.strip())
    return [l[depth:] for l in block], end


def _render(lines, fields):
    """Render prose lines to Markdown lines; collect fields into `fields`."""
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        text = line.strip()
        depth = _indent(line)
        field = FIELD_RE.match(text)
        if field:
            block, i = _block(lines, i + 1, depth)
            first = [field.group(3)] if field.group(3) else []
            body = "\n".join(_render(first + block, fields)).strip()
            if field.group(1) == "param":
                fields["params"].append((field.group(2).strip(), body))
            else:
                fields["returns"] = body
            continue
        directive = DIRECTIVE_RE.match(text)
        if directive:
            kind, arg = directive.groups()
            block, i = _block(lines, i + 1, depth)
            if kind in ADMONITIONS:
                inner = _render(([arg] if arg else []) + ([""] if arg and block else []) + block, fields)
                out += ["", f"!!! {kind}", ""] + [f"    {l}" if l else "" for l in inner] + [""]
            elif kind in CODE:
                lang = FENCE_LANGUAGES.get(arg.strip().lower(), "text")
                out += ["", f"```{lang}"] + block + ["```", ""]
            continue
        if text.endswith("::") and not text.startswith(".."):
            # A literal block: "Example::" keeps "Example:"; a bare "::" disappears.
            lead = text[:-1]
            if lead != ":":
                out.append(inline(lead))
            block, i = _block(lines, i + 1, depth)
            out += ["", "```text"] + block + ["```", ""]
            continue
        # Indentation carries no meaning in prose here; keep list nesting
        # below Markdown's 4-space code-block threshold.
        nested = min(depth, 2) if text.startswith(("- ", "* ")) else 0
        out.append(" " * nested + inline(text) if text else "")
        i += 1
    return out


def _tidy(lines):
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def parse(doc):
    """Split a docstring into {summary, body, params: [(name, text)], returns}."""
    # C-only extensions carry their original Doxygen comments in the snapshot.
    # Normalize their directives here, at the same conversion boundary as RST.
    doc = re.sub(r"^@param\s+(\w+)\s+", r":param \1: ", doc, flags=re.M)
    doc = re.sub(r"^@return\s+", ":return: ", doc, flags=re.M)
    doc = re.sub(r"^@warning\s+", ".. warning:: ", doc, flags=re.M)
    doc = re.sub(r"^\\(?:verbatim[^\n]*|endverbatim)\s*\n?", "", doc, flags=re.M)
    fields = {"params": [], "returns": ""}
    text = _tidy(_render(doc.expandtabs(8).splitlines(), fields))
    first, _, rest = text.partition("\n\n")
    if first.startswith(("!!!", "```")):
        first, rest = "", text
    return {"summary": " ".join(first.split()), "body": rest.strip(), **fields}


def short(summary):
    """The first sentence of a summary, for tables."""
    m = re.match(r"(.+?[.!?])(?:\s|$)", summary)
    return m.group(1) if m else summary


def markdown(doc):
    """The whole docstring as Markdown: summary, body, parameters, result."""
    parts = parse(doc)
    out = [parts["summary"], "", parts["body"], ""]
    if parts["params"]:
        out += ["**Parameters**", ""]
        for name, text in parts["params"]:
            lines = text.splitlines() or [""]
            out.append(f"- **`{name}`**: {lines[0]}")
            out += [f"    {l}" if l else "" for l in lines[1:]]
        out.append("")
    if parts["returns"]:
        out += ["**Returns**", "", parts["returns"], ""]
    return _tidy(out) + "\n"
