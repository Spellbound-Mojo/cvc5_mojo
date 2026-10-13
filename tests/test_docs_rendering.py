"""Check the contracts that keep reference signatures and tutorials truthful."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from bindgen import gen_api, reference
import docs_contract as docs


class Signatures(unittest.TestCase):
    def test_reference_uses_generated_overloads_and_defaults(self):
        snap = docs.snapshot()
        generated = gen_api.generated(snap)
        model, table = generated
        for cls, method in [('TermManager', 'mkTerm'), ('Solver', 'push')]:
            with self.subTest(method=method):
                declarations = gen_api.signatures(model, cls, method, table[cls][method][0])
                rendered = reference.class_markdown(cls, snap, lambda c, m: '#', generated)
                for declaration in declarations:
                    self.assertIn(declaration, rendered)
        self.assertIn('args: List[Term]', reference.class_markdown('TermManager', snap, lambda c, m: '#', generated))
        self.assertIn('nscopes: Int = 1', reference.class_markdown('Solver', snap, lambda c, m: '#', generated))

    def test_rendering_labels_languages_writable_and_unavailable_methods(self):
        result = reference.class_markdown('Result', docs.snapshot(), lambda c, m: '#')
        self.assertIn('def isSat(self) raises -> Bool', result)
        self.assertIn('**Upstream Python signature**', result)
        self.assertIn('Mojo uses the `Writable` protocol', result)
        plugin = reference.class_markdown('Plugin', docs.snapshot(), lambda c, m: '#')
        self.assertIn('Not mirrored: Callbacks from cvc5 into Mojo', plugin)


class Excerpts(unittest.TestCase):
    def source(self, contents):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / 'example.mojo').write_text(contents)
        return root

    def test_excerpts_dedent_and_full_program_omits_markers(self):
        root = self.source('def main():\n    # docs:begin query\n    print(1)\n    # docs:end query\n')
        with patch.object(docs, 'ROOT', root), patch.object(docs, 'EXAMPLES', root):
            full, regions = docs.example_source('example.mojo')
        self.assertEqual(regions, {'query': 'print(1)'})
        self.assertEqual(full, 'def main():\n    print(1)')

    def test_invalid_markers_fail(self):
        for source in ('# docs:begin a\nx\n', '# docs:end a\n',
                       '# docs:begin a\n# docs:begin b\nx\n# docs:end b\n',
                       '# docs:begin a\n# docs:end a\n',
                       '# docs:begin a\nx\n# docs:end a\n# docs:begin a\ny\n# docs:end a\n'):
            with self.subTest(source=source):
                root = self.source(source)
                with patch.object(docs, 'ROOT', root), patch.object(docs, 'EXAMPLES', root):
                    with self.assertRaises(AssertionError):
                        docs.example_source('example.mojo')

    def test_escape_outside_example_directory(self):
        with self.assertRaises(AssertionError):
            docs.example_source('docs/examples/../../src/cvc5_mojo/term.mojo')

    def test_unknown_excerpt_and_unregistered_program_fail(self):
        with self.assertRaisesRegex(AssertionError, 'Unknown example region'):
            docs.excerpt_markdown('docs/examples/quickstart.mojo#missing', 'index.md')
        with self.assertRaisesRegex(AssertionError, 'tested program'):
            docs.excerpt_markdown('docs/examples/missing.mojo#query', 'index.md')

    def test_fenced_directives_are_literal_and_math_is_escaped(self):
        literal = '```text\n<!-- excerpt: nonexistent -->\n```'
        self.assertEqual(docs.render_markdown(literal, 'index.md'), literal)
        self.assertEqual(docs.directives(literal), [])
        equation = docs.render_markdown('```math\nx < 1\n```', 'index.md')
        self.assertEqual(equation, '<div class="math-display">x &lt; 1</div>')

    def test_python_counterpart_shares_output_and_oracle_command(self):
        key = 'docs/examples/migration.mojo'
        rendered = docs.example_markdown(key, 'guides/python-migration.md', python=True)
        self.assertIn('```python', rendered)
        self.assertIn('pixi run --locked -e oracle python docs/examples/migration.py', rendered)
        self.assertIn(docs.data('examples.json')['examples'][key]['stdout'].strip(), rendered)
        self.assertNotIn('# docs:begin', rendered)
        excerpt = docs.excerpt_markdown('docs/examples/migration.py#setup', 'guides/python-migration.md')
        self.assertIn('```python', excerpt)
        self.assertIn('one = tm.mkReal(1)', excerpt)


if __name__ == '__main__':
    unittest.main()
