"""Reject invalid performance evidence rather than declaring a fast failure."""
from pathlib import Path
from copy import deepcopy
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from benchmark_binding_overhead import LAYERS, MODES, loop_inventory, measurement, summarize, paired_interval, compare_baselines


class BaselineComparisonTests(unittest.TestCase):
    def report(self, low, high):
        return dict(passed=True, protocol='isolated-workloads-v1', machine={'cpu': 'test'}, cpu=0,
                    versions={'mojo': {'stdout': 'pinned Mojo'}}, c_compiler={'stdout': 'pinned cc'},
                    settings=dict(route='package', assertions=False, warmup=10000, repetitions=9,
                                  operations=0, target_ms=150),
                    source_and_dependency_hashes={'pixi.lock': 'pinned', 'tests/binding/overhead.c': 'fixture'},
                    summary={'scalar': {'paired_delta_ns_vs_checked': {'public':
                        dict(bootstrap_95=[low, high], median=(low + high) / 2)}}})

    def test_overlap_is_not_a_regression(self):
        before = self.report(10, 20)
        for bounds, status in (((15, 25), 'overlap'), ((21, 30), 'higher'), ((1, 9), 'lower')):
            result = compare_baselines(before, self.report(*bounds))
            self.assertTrue(result['comparable'])
            self.assertEqual(result['changes']['scalar/public']['status'], status)

    def test_incompatible_or_insufficient_evidence_is_rejected(self):
        before = self.report(10, 20)
        for field, value in (('passed', False), ('protocol', 'old'), ('machine', {}), ('cpu', 1)):
            after = dict(before, **{field: value})
            self.assertFalse(compare_baselines(before, after)['comparable'])
        for key, value in (('repetitions', 1), ('route', 'source'), ('assertions', True), ('warmup', 0),
                           ('operations', 10), ('target_ms', 100)):
            after = deepcopy(before)
            after['settings'][key] = value
            self.assertFalse(compare_baselines(before, after)['comparable'])
        for key in ('route', 'assertions', 'warmup', 'operations', 'target_ms'):
            incomplete = deepcopy(before)
            del incomplete['settings'][key]
            self.assertFalse(compare_baselines(incomplete, incomplete)['comparable'])
        after = deepcopy(before)
        after['source_and_dependency_hashes']['pixi.lock'] = 'changed'
        self.assertFalse(compare_baselines(before, after)['comparable'])
        after = deepcopy(before)
        after['c_compiler']['stdout'] = 'different compiler'
        self.assertFalse(compare_baselines(before, after)['comparable'])


class OverheadEvidenceTests(unittest.TestCase):
    def test_only_complete_correct_observations_pass(self):
        good = dict(returncode=0, stdout='0 10 200 80 16\noverhead passed\n')
        self.assertEqual(measurement(good, 0, 10, 2)['ns_per_operation'], 20)
        for change in (dict(returncode=-11), dict(returncode=None), dict(returncode=1),
                       dict(stdout='0 10 200 80 16\n'), dict(stdout='overhead passed\n'),
                       dict(stdout='0 10 200 80 16\noverhead passed'),
                       dict(stdout='0 10 200 80 16\noverhead passed\nextra\n'),
                       dict(stdout='0 10 0 80 16\noverhead passed\n'),
                       dict(stdout='0 9 200 80 16\noverhead passed\n'),
                       dict(stdout='0 10 200 79 16\noverhead passed\n'),
                       dict(stdout='0 10 200 80 15\noverhead passed\n'),
                       dict(stdout='invalid\noverhead passed\n')):
            with self.subTest(change=change):
                self.assertIsNone(measurement(dict(good, **change), 0, 10, 2))

    def test_cold_initialization_is_one_operation_without_warmup(self):
        result = dict(returncode=0, stdout='-1 1 5000000 1 0\noverhead passed\n')
        self.assertIsNotNone(measurement(result, -1, 1, 0))
        self.assertIsNone(measurement(result, -1, 2, 0))

    def rows(self):
        return [dict(mode='scalar', layer=layer, repetition=i, passed=True,
                     metrics=dict(ns_per_operation=100 + i * 100 + (20 if layer == 'public' else 0)))
                for i in range(3) for layer in LAYERS]

    def test_comparisons_are_paired_by_repetition_despite_execution_order(self):
        summary = summarize(list(reversed(self.rows())), ['scalar'], 3)['scalar']
        self.assertTrue(summary['passed'])
        difference = summary['paired_delta_ns_vs_checked']['public']
        self.assertEqual(difference['median'], 20)
        self.assertEqual(difference['bootstrap_95'], [20, 20])

    def test_missing_duplicate_failed_or_wrong_repetition_cannot_pass(self):
        rows = self.rows()
        failed = [dict(row) for row in rows]
        failed[-1]['passed'] = False
        shifted = [dict(row, repetition=row['repetition'] + 1) for row in rows]
        for changed in (rows[:-1], rows + rows[:1], rows[:-1] + rows[:1], failed, shifted, []):
            self.assertFalse(summarize(changed, ['scalar'], 3)['scalar']['passed'])

    def test_uncertain_deltas_are_not_reported_as_certain_improvements(self):
        interval = paired_interval([-10, -5, 0, 5, 10])
        self.assertLess(interval['bootstrap_95'][0], 0)
        self.assertGreater(interval['bootstrap_95'][1], 0)

    def symbols(self, language):
        if language == 'c':
            names = [f'execute_{i}' for i in range(len(MODES))]
        else:
            names = [f'overhead::execute[::Bool,::SIMD[DType.int, 1]]'
                     f'(::SIMD[DType.int, 1],::SIMD[DType.int, 1],::String),raw={raw},mode={i}'
                     for i, mode in enumerate(MODES) for raw in ('false', 'true')
                     if not (raw == 'true' and mode == 'decimal-copy')]
        # Identical C controls are allowed to share a machine-code address.
        return [f'0000000000002c70 0000000000000145 t {name}' for name in names]

    def test_complete_compiled_loop_coverage(self):
        for language, expected in (('c', len(MODES)), ('mojo', 2 * len(MODES) - 1)):
            lines = self.symbols(language)
            lines.append('0000000000000010 0000000000000008 T unrelated')
            entries = loop_inventory(dict(returncode=0, stdout='\n'.join(lines)), language)
            self.assertEqual(len(entries), expected)
            self.assertEqual({entry['mode'] for entry in entries}, set(MODES))
            self.assertTrue(all(entry['size_bytes'] > 0 for entry in entries))

    def test_bad_compiled_loop_evidence_fails(self):
        for language in ('c', 'mojo'):
            lines = self.symbols(language)
            generic = ('execute_generic' if language == 'c' else
                       'overhead::execute[::Bool](::SIMD[DType.int, 1]),raw=true')
            for changed in ([], lines[:-1], lines + lines[:1],
                            lines[:-1] + [lines[-1].replace('0000000000000145', '0000000000000000')],
                            lines[:-1] + [lines[-1].replace(' t ', ' D ')],
                            lines + ['bad symbol ' + generic],
                            lines + ['0000000000001000 0000000000000100 t ' + generic]):
                with self.subTest(language=language, changed=changed[-1:]):
                    with self.assertRaises(ValueError):
                        loop_inventory(dict(returncode=0, stdout='\n'.join(changed)), language)
            for returncode in (1, -11, None):
                with self.assertRaises(ValueError):
                    loop_inventory(dict(returncode=returncode, stdout='\n'.join(lines)), language)


if __name__ == '__main__':
    unittest.main()
