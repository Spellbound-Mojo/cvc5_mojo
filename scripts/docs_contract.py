"""Documentation inventories and rendering; no MkDocs or CLI dependency."""
import json
import html
import posixpath
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bindgen import config, reference, report  # noqa: E402

CONTENT = ROOT / 'docs/content'
EXAMPLES = ROOT / 'docs/examples'
TRANSLATED = config.CVC5_EXAMPLES_DIR
DIRECTIVE = re.compile(r'<!--\s*(api|example|python-example|excerpt|source|coverage|translated|kinds|options):\s*([^>]*?)\s*-->')
FENCE = re.compile(r'(^```[^\n]*\n.*?^```[ \t]*$)', re.M | re.S)
REGION = re.compile(r'^\s*# docs:(begin|end) ([a-z][a-z0-9_-]*)\s*$')
COVERAGE = ('report', 'handles', 'tests', 'calls')


def data(name):
    return json.loads((ROOT / 'docs' / name).read_text())


def snapshot():
    return json.loads(config.SNAPSHOT_FILE.read_text())


def relative(page, destination):
    return posixpath.relpath(destination, posixpath.dirname(page) or '.')


def directives(text):
    """The directives of a page, ignoring any inside fenced code."""
    return DIRECTIVE.findall(''.join(FENCE.split(text)[::2]))


def api_pages():
    """{API topic: page path} from the `api` directives of the content pages."""
    found = {}
    for page in sorted(CONTENT.rglob('*.md')):
        for kind, value in directives(page.read_text()):
            if kind == 'api':
                found[value] = page.relative_to(CONTENT).as_posix()
    return found


def _example_bar(key, page):
    """The header line of an example: its file name and a download link."""
    # A Markdown link, so MkDocs resolves the download for the page's own URL.
    source = relative(page, 'downloads/' + key)
    return (f'<div class="example-bar" markdown="span"><span class="example-file">{posixpath.basename(key)}</span> '
            f'[Download]({source}){{ .example-download }}</div>')


def example_source(key):
    """Read source and named excerpts once, validating every region marker."""
    path = (ROOT / key).resolve()
    assert path.is_relative_to(EXAMPLES) and path.suffix in ('.mojo', '.py') and path.is_file(), \
        f'Expected a source file in docs/examples: {key}'
    clean, regions, active, selected = [], {}, None, []
    for line in path.read_text().splitlines():
        match = REGION.fullmatch(line)
        if match:
            action, name = match.groups()
            if action == 'begin':
                assert active is None and name not in regions, f'Nested or repeated region: {key}#{name}'
                active, selected = name, []
            else:
                assert active == name, f'Mismatched region end: {key}#{name}'
                assert any(line.strip() for line in selected), f'Empty region: {key}#{name}'
                regions[name] = textwrap.dedent('\n'.join(selected)).strip()
                active = None
        else:
            assert '# docs:begin' not in line and '# docs:end' not in line, f'Invalid region marker: {key}: {line}'
            clean.append(line)
            if active is not None:
                selected.append(line)
    assert active is None, f'Unclosed region: {key}#{active}'
    return '\n'.join(clean).rstrip(), regions


def excerpt_markdown(value, page):
    key, separator, name = value.partition('#')
    manifest = data('examples.json')['examples']
    tested = set(manifest) | {s['python'] for s in manifest.values() if 'python' in s}
    assert separator and key in tested, f'Excerpt must use a tested program: {value}'
    _, regions = example_source(key)
    assert name in regions, f'Unknown example region: {value}'
    return (f'<div class="example excerpt" markdown="1">\n{_example_bar(key, page)}\n\n'
            f'```{source_language(key)}\n{regions[name]}\n```\n\n</div>\n')


def source_language(key):
    return 'python' if key.endswith('.py') else 'mojo'


def example_markdown(key, page, python=False):
    """A complete program as one unit: its file, the code, how to run it and what it prints."""
    spec = data('examples.json')['examples'][key]
    if python:
        key = spec['python']
    command = f'pixi run --locked -e oracle python {key}' if python else f'pixi run --locked mojo run -I src {key}'
    code, _ = example_source(key)
    return (f'<div class="example" markdown="1">\n{_example_bar(key, page)}\n\n'
            f'```{source_language(key)}\n{code}\n```\n\n'
            f'<div class="example-run" markdown="1"><span class="example-label">Run from the repository root</span> '
            f'`{command}`</div>\n\n'
            f'<div class="example-output" markdown="1"><span class="example-label">Output</span>\n\n'
            f'```text\n{spec["stdout"].rstrip()}\n```\n\n</div>\n</div>\n')


def translated_markdown(name, page):
    """A translated example with recorded Python output and its comparison policy."""
    path = TRANSLATED / f'{name}.mojo'
    key = path.relative_to(ROOT).as_posix()
    code = '\n'.join(line for line in path.read_text().splitlines() if not line.startswith('#')).strip()
    output = (TRANSLATED / f'{name}.out').read_text().rstrip()
    translation = json.loads(config.TRANSLATION_FILE.read_text())
    model = any(e.get('run') == name and e.get('model_output') for e in translation['examples'].values())
    label = 'Python output; model values may differ' if model else 'Output, as in Python'
    return (f'<div class="example" markdown="1">\n{_example_bar(key, page)}\n\n'
            f'```mojo\n{code}\n```\n\n'
            f'<div class="example-run" markdown="1"><span class="example-label">Run from the repository root</span> '
            f'`pixi run --locked mojo run -I src {key}`</div>\n\n'
            f'<div class="example-output" markdown="1"><span class="example-label">{label}</span>\n\n'
            f'```text\n{output}\n```\n\n</div>\n</div>\n')


def source_markdown(key, page):
    """Show a maintained example file that is not run on its own."""
    code, _ = example_source(key)
    return f'<div class="example" markdown="1">\n{_example_bar(key, page)}\n\n```{source_language(key)}\n{code}\n```\n\n</div>\n'


def api_markdown(topic, page):
    snap = snapshot()
    if topic == 'enums':
        return reference.enums_markdown(snap)
    pages = api_pages()

    def link(cls, method):
        return relative(page, pages[cls]) + '#' + reference.anchor(cls, method)
    return reference.class_markdown(topic, snap, link)


def coverage_markdown(topic):
    snap = snapshot()
    if topic == 'handles':
        return report.handles_markdown(snap)
    if topic == 'tests':
        return report.tests_markdown(json.loads(config.TRANSLATION_FILE.read_text()))
    if topic == 'calls':
        return report.calls_markdown(snap, json.loads(config.CALLS_FILE.read_text()))
    return report.report_markdown(snap, config.overrides()['policy']['min_auto_fraction'])


def render_markdown(text, page):
    def replace(match):
        kind, value = match.groups()
        if kind == 'api':
            return api_markdown(value, page)
        if kind == 'example':
            return example_markdown(value, page)
        if kind == 'python-example':
            return example_markdown(value, page, python=True)
        if kind == 'excerpt':
            return excerpt_markdown(value, page)
        if kind == 'coverage':
            return coverage_markdown(value)
        if kind == 'translated':
            return translated_markdown(value, page)
        if kind == 'kinds':
            return reference.kinds_markdown(snapshot(), value.split())
        if kind == 'options':
            return reference.options_markdown(snapshot(), None if value == 'all' else value.split())
        return source_markdown(value, page)
    def render_fence(part):
        if part.startswith('```math\n'):
            equation = part[len('```math\n'):].rsplit('```', 1)[0].strip()
            return f'<div class="math-display">{html.escape(equation)}</div>'
        return part
    return ''.join(render_fence(part) if index % 2 else DIRECTIVE.sub(replace, part)
                   for index, part in enumerate(FENCE.split(text)))


def audit_docs():
    snap = snapshot()
    topics, examples, python_examples = [], set(), set()
    pages = sorted(CONTENT.rglob('*.md'))
    for page in pages:
        text = page.read_text()
        assert text.startswith('# '), f'Missing page title: {page}'
        # Executable Mojo comes from maintained files, never drifting copies.
        assert not re.search(r'^```mojo\s*$', text, re.M), f'Use an example directive: {page}'
        for kind, value in directives(text):
            if kind == 'api':
                topics.append(value)
            elif kind == 'example':
                examples.add(value)
                example_source(value)
            elif kind == 'python-example':
                python_examples.add(value)
                spec = data('examples.json')['examples'][value]
                example_source(spec['python'])
            elif kind == 'excerpt':
                excerpt_markdown(value, page.relative_to(CONTENT).as_posix())
            elif kind == 'coverage':
                assert value in COVERAGE, f'Unknown coverage topic: {page}: {value}'
            elif kind == 'translated':
                run = {e['run'] for e in json.loads(config.TRANSLATION_FILE.read_text())['examples'].values()
                       if 'run' in e}
                assert value in run, f'Not a translated example that runs: {page}: {value}'
            elif kind == 'kinds':
                names = value.split()
                assert names and len(names) == len(set(names)), f'Empty or repeated kinds: {page}'
                for name in names:
                    assert name in snap['enums']['Kind'], f'Unknown Kind: {page}: {name}'
                    assert snap['enum_docs']['Kind'].get(name), f'Undocumented Kind: {page}: {name}'
            elif kind == 'source':
                example_source(value)
            elif kind == 'options':
                names = list(snap['options']) if value == 'all' else value.split()
                assert names and len(names) == len(set(names)), f'Empty or repeated options: {page}'
                assert all(name in snap['options'] for name in names), f'Unknown option: {page}: {value}'
    # Every mirrored Python class, and the enums, are documented exactly once.
    expected = sorted(list(snap['python']) + ['enums'])
    assert sorted(topics) == expected, \
        f'API topics differ from the snapshot: missing {sorted(set(expected) - set(topics))}, ' \
        f'extra or repeated {sorted(t for t in topics if t not in expected or topics.count(t) > 1)}'
    for cls, info in snap['python'].items():
        assert info['doc'], f'Class without a description: {cls}'
    manifest = data('examples.json')['examples']
    assert examples == set(manifest), 'Unused or missing executable example'
    assert python_examples == {p for p, spec in manifest.items() if 'python' in spec}, 'Unused or missing Python counterpart'
    for name, spec in manifest.items():
        assert (ROOT / name).is_file() and name.endswith('.mojo'), f'Missing example: {name}'
        assert isinstance(spec['stdout'], str) and spec['stdout'].endswith('\n'), f'Bad expected output: {name}'
        if 'python' in spec:
            assert spec['python'].endswith('.py'), f'Expected Python counterpart: {name}'
            example_source(spec['python'])
        assert spec.get('working_directory', 'repository') in ('repository', 'isolated'), f'Unknown run directory: {name}'
    return dict(pages=len(pages), api_topics=len(topics), examples=len(examples),
                python_methods=sum(len(i['methods']) for i in snap['python'].values()))
