"""Keep extracted option metadata authoritative across rendering and upgrades."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bindgen import diff, fetch, options, reference


DECLARATION = '''name = "Example module"
[[option]]
name = "internal"
long = "strategy=MODE"
category = "regular"
default = "someCppExpression()"
help = "Choose ``strategy``."
[[option.mode.FAST]]
name = "fast"
help = "Use :math:`x` | :math:`y`."
[[option]]
name = "internalOnly"
'''


class OptionMetadata(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.folder = self.root / 'src/options'
        self.folder.mkdir(parents=True)
        (self.folder / 'example_options.toml').write_text(DECLARATION)
        self.declared = options.declarations(self.root)
        self.info = dict(name='strategy', aliases=['old-strategy'], no_support=[],
                         value_kind='modes', default='fast', modes=['fast'])

    def test_canonical_aliases_and_binary_defaults(self):
        joined = options.join(self.declared, [self.info, dict(self.info)])
        self.assertEqual(list(joined), ['strategy'])
        self.assertEqual(joined['strategy']['default'], 'fast')
        self.assertEqual(joined['strategy']['declaration']['default'], 'someCppExpression()')
        self.assertEqual(joined['strategy']['source'], 'src/options/example_options.toml')
        self.assertEqual(joined['strategy']['aliases'], ['old-strategy'])

    def test_missing_source_conflicts_and_empty_extraction_fail(self):
        with self.assertRaisesRegex(AssertionError, 'no source declaration'):
            options.join({}, [self.info])
        with self.assertRaisesRegex(AssertionError, 'Conflicting option alias'):
            options.join(self.declared, [self.info, {**self.info, 'default': 'different'}])
        with self.assertRaisesRegex(AssertionError, 'No option information'):
            options.join(self.declared, [])
        (self.folder / 'duplicate_options.toml').write_text(DECLARATION)
        with self.assertRaisesRegex(AssertionError, 'Duplicate option'):
            options.declarations(self.root)

    def test_renderer_uses_runtime_values_and_canonical_docstring_conversion(self):
        snap = {'options': options.join(self.declared, [self.info]), 'cvc5': {'commit': 'pinned-sha'}}
        table = reference.options_markdown(snap, ['strategy'])
        self.assertIn('`fast`', table)
        self.assertIn('Choose `strategy`.', table)
        self.assertNotIn('someCppExpression', table)
        catalog = reference.options_markdown(snap)
        self.assertIn('Use `x` &#124; `y`.', catalog)
        self.assertIn('blob/pinned-sha/src/options/example_options.toml', catalog)
        self.assertIn('#option-strategy .api-name', catalog)
        with self.assertRaises(KeyError):
            reference.options_markdown(snap, ['missing'])
        snap['options']['strategy']['default'] = ''
        self.assertIn('`""` (empty string)', reference.options_markdown(snap))
        snap['options']['strategy']['default'] = None
        self.assertIn('No scalar default reported', reference.options_markdown(snap))

    def test_option_changes_appear_in_upgrade_report(self):
        old = dict(cvc5={'version': 'old'}, c_functions={}, enums={}, python={},
                   options=options.join(self.declared, [self.info]))
        new = copy.deepcopy(old)
        new['options']['strategy']['default'] = 'different'
        self.assertIn('`strategy`: default', diff.diff(old, new))
        del new['options']['strategy']
        self.assertIn('Solver options removed', diff.diff(old, new))
        self.assertIn('Solver options added', diff.diff(new, old))


class SourceCache(unittest.TestCase):
    def test_matching_hash_with_missing_input_refreshes_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / fetch.STAMP).write_text('hash\n')
            (root / 'old').mkdir()
            pin = {'version': 'test', 'source': {'url': 'unused', 'sha256': 'hash', 'root': 'archive'}}
            with patch.object(fetch.config, 'SOURCE_DIR', root), \
                 patch.object(fetch, 'SOURCE_PATHS', ['old/', 'new/']), \
                 patch.object(fetch, 'download', return_value=b'archive') as download, \
                 patch.object(fetch, 'extract_sources') as extract:
                fetch.fetch_sources(pin)
                download.assert_called_once_with('unused', 'hash')
                extract.assert_called_once_with(b'archive', 'archive', root)
                (root / 'new').mkdir()
                fetch.fetch_sources(pin)
                self.assertEqual(download.call_count, 1)


if __name__ == '__main__':
    unittest.main()
