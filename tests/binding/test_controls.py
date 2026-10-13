"""Guard against false passes in matched ownership measurements."""
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from run_matched_controls import analyze, balanced, compare, equivalent_calls, libraries, per_operation, reference_pairs
from run_contract_tests import compound_equivalent, ownership_accounting
from bindgen import config


def metric(growth, checksum=200):
    return dict(complete=True, operations=100, checksum=checksum, peak_growth_kib=growth)


class MatchedControlsTests(unittest.TestCase):
    def test_results_must_agree_even_when_memory_is_stable(self):
        self.assertFalse(compare(metric(0), metric(0, checksum=199), 4096, 1024)['passed'])

    def test_excess_growth_is_not_hidden_by_absolute_budget(self):
        self.assertFalse(compare(metric(100), metric(1500), 4096, 1024)['passed'])
        self.assertTrue(compare(metric(100), metric(300), 4096, 1024)['passed'])

    def test_growing_native_control_cannot_certify_a_clean_comparison(self):
        self.assertFalse(compare(metric(5000), metric(5000), 4096, 1024)['passed'])

    def test_incomplete_run_cannot_pass(self):
        self.assertFalse(compare(metric(0), dict(complete=False), 4096, 1024)['passed'])
        rows = [dict(phase=0, operations=0, elapsed_ns=0, rss_kib=100, checksum=0),
                dict(phase=1, operations=100, elapsed_ns=1000, rss_kib=104, checksum=200)]
        self.assertFalse(analyze(rows, 100)['complete'])
        self.assertEqual(analyze(rows, 100)['operations'], 100)
        self.assertIsNone(analyze(rows, 100)['after_cleanup_rss_kib'])
        rows.append(dict(phase=2, operations=100, elapsed_ns=0, rss_kib=102, checksum=0))
        self.assertTrue(analyze(rows, 100)['complete'])
        self.assertEqual(analyze(rows, 100)['peak_growth_kib'], 4)
        self.assertFalse(analyze(rows, 101)['complete'])

    def test_trace_subtraction_removes_initialization_and_teardown(self):
        small = Counter(cvc5_new=2, cvc5_delete=2, cvc5_check_sat=1, cvc5_result_release=1)
        large = Counter(cvc5_new=2, cvc5_delete=2, cvc5_check_sat=33, cvc5_result_release=33)
        self.assertEqual(per_operation(small, large), dict(cvc5_check_sat=1, cvc5_result_release=1))
        large['cvc5_new'] += 1
        with self.assertRaises(ValueError):
            per_operation(small, large)

    def test_known_extra_reference_fails_but_balanced_copy_is_allowed(self):
        c = dict(cvc5_result_copy=1, cvc5_result_release=2)
        self.assertTrue(balanced(c, dict(cvc5_result_copy=2, cvc5_result_release=3)))
        self.assertFalse(balanced(c, dict(cvc5_result_copy=2, cvc5_result_release=2)))

    def test_every_extracted_handle_family_is_accounted_for(self):
        snapshot = json.loads(config.SNAPSHOT_FILE.read_text())
        pairs = reference_pairs(snapshot)
        self.assertEqual(len(pairs), len(snapshot['handles']))
        self.assertIn(('cvc5_stat_copy', 'cvc5_stat_release'), pairs)
        for copy, release in pairs:
            with self.subTest(copy=copy):
                self.assertFalse(balanced({copy: 1, release: 2}, {copy: 1, release: 1}, pairs))
        changed = json.loads(json.dumps(snapshot))
        del changed['c_functions']['cvc5_stat_release']
        with self.assertRaises(ValueError):
            reference_pairs(changed)

    def test_trace_equivalence_requires_exports_and_owner_cleanup(self):
        pairs = reference_pairs(json.loads(config.SNAPSHOT_FILE.read_text()))
        c = dict(cvc5_get_statistics=1, cvc5_stats_release=1, cvc5_new=1, cvc5_delete=1)
        self.assertTrue(equivalent_calls(c, c, pairs))
        for name in ('cvc5_get_statistics', 'cvc5_delete'):
            missing = c.copy()
            del missing[name]
            self.assertFalse(equivalent_calls(c, missing, pairs))
        # The established String(value) amplification stays visible in reports
        # but is classified separately from reference/export balance.
        self.assertTrue(equivalent_calls(dict(cvc5_grammar_to_string=2), dict(cvc5_grammar_to_string=4), pairs))

    def test_loaded_library_identity_uses_bytes_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lib = root / 'lib'
            lib.mkdir()
            main = lib / 'libcvc5.so'
            main.write_bytes(b'pinned-main')
            (lib / 'libcvc5parser.so').write_bytes(b'pinned-parser')
            alias = lib / 'libcvc5.so.1'
            alias.write_bytes(main.read_bytes())
            maps = root / 'maps'
            def line(path):
                return f'1-2 r-xp 0 00:00 1 {path}\n'
            with patch('run_matched_controls.config.BINARY_DIR', root):
                maps.write_text(line(alias))
                self.assertTrue(libraries(maps)['matched'])
                maps.write_text(line(alias) + line(main))
                self.assertFalse(libraries(maps)['matched'])
                alias.write_bytes(b'same-version-different-build')
                maps.write_text(line(alias))
                self.assertFalse(libraries(maps)['matched'])


class CompoundComparisonTests(unittest.TestCase):
    def test_only_complete_equal_observations_pass(self):
        good = dict(returncode=0, stdout='value 4294967295\ncompound FFI passed\n')
        self.assertTrue(compound_equivalent(good, good))
        bad = [None, dict(good, returncode=1), dict(good, returncode=-11),
               dict(good, returncode=None), dict(good, stdout=''),
               dict(good, stdout='compound FFI passed\n'),
               dict(good, stdout='value 4294967295\n'),
               dict(good, stdout='value -1\ncompound FFI passed\n')]
        for value in bad:
            with self.subTest(value=value):
                self.assertFalse(compound_equivalent(good, value))
                self.assertFalse(compound_equivalent(value, good))


class OwnershipAccountingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(config.SNAPSHOT_FILE.read_text())

    def fixture(self, *calls):
        basic = ['cvc5_term_manager_new', 'cvc5_term_manager_delete']
        query = ['cvc5_check_sat', 'cvc5_result_release']
        return ['ownership:borrowed', *(calls or [*basic, *query]), 'ownership:handles', *basic, *query,
                'ownership:exceptions', *basic, *query, 'ownership:buffers', *basic, 'ownership:done']

    def test_final_owner_and_result_references_must_be_released(self):
        calls = ['cvc5_new', 'cvc5_check_sat', 'cvc5_result_copy',
                 'cvc5_result_release', 'cvc5_result_release', 'cvc5_delete']
        self.assertTrue(ownership_accounting(self.fixture(*calls), self.snapshot)['passed'])
        for missing in ('cvc5_result_release', 'cvc5_delete'):
            fewer = calls.copy()
            fewer.remove(missing)
            self.assertFalse(ownership_accounting(self.fixture(*fewer), self.snapshot)['passed'])
        self.assertFalse(ownership_accounting(self.fixture(*calls, 'cvc5_delete'), self.snapshot)['passed'])

    def test_incomplete_or_duplicated_sections_cannot_pass(self):
        for lines in [[], self.fixture()[:-1], self.fixture() + ['cvc5_delete'],
                      self.fixture() + ['ownership:done']]:
            self.assertFalse(ownership_accounting(lines, self.snapshot)['passed'])

    def test_empty_sections_or_corrupt_calls_cannot_pass(self):
        empty = ['ownership:' + name for name in ('borrowed', 'handles', 'exceptions', 'buffers', 'done')]
        self.assertFalse(ownership_accounting(empty, self.snapshot)['passed'])
        valid = self.fixture()
        self.assertTrue(ownership_accounting(valid, self.snapshot)['passed'])
        for lines in [[valid[0], 'unrecognized', *valid[1:]], ['cvc5_new', *valid]]:
            self.assertFalse(ownership_accounting(lines, self.snapshot)['passed'])


if __name__ == '__main__':
    unittest.main()
