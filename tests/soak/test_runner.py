"""Check that the soak analysis distinguishes plateaus from sustained growth."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from run_soak_tests import analyze, percentile_upper_ns, samples
import run_soak_tests
from benchmark_solver_batches import summarize


def series(rss):
    return [dict(elapsed_ns=i * 1_000_000_000, requests=i * 100,
                 rss_kib=value, work_ns=i * 900_000_000, max_request_ns=10_000_000,
                 histogram=[0] * 23 + [i * 100] + [0] * 40) for i, value in enumerate(rss)]


class SoakAnalysisTests(unittest.TestCase):
    def test_fingerprints_include_dependencies_outside_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            dependency = Path(directory) / 'apn_mojo.mojoc'
            dependency.write_bytes(b'installed dependency')
            result = run_soak_tests.fingerprint([dependency])
            self.assertEqual(result[str(dependency)], hashlib.sha256(dependency.read_bytes()).hexdigest())

    def test_allocator_plateau_is_stable(self):
        rows = series([100_000 + min(i, 5) * 100 for i in range(121)])
        result = analyze(rows, 32768, 8192, 64)
        self.assertTrue(result['memory_passed'])
        self.assertEqual(result['tail_slope_kib_s'], 0)

    def test_small_linear_growth_is_not_hidden_by_peak_budget(self):
        rows = series([100_000 + i * 100 for i in range(121)])
        result = analyze(rows, 32768, 8192, 64)
        self.assertFalse(result['memory_passed'])
        self.assertIn('second-half slope', result['violations'])
        self.assertEqual(result['tail_slope_kib_s'], 100)

    def test_large_transient_peak_is_not_hidden_by_final_rss(self):
        rss = [100_000] * 121
        rss[40] += 40_000
        result = analyze(series(rss), 32768, 8192, 64)
        self.assertFalse(result['memory_passed'])
        self.assertEqual(result['violations'], ['peak growth'])

    def test_short_runs_do_not_establish_memory_stability(self):
        result = analyze(series([100_000, 110_000, 120_000]), 32768, 8192, 64)
        self.assertFalse(result['assessed'])
        self.assertIsNone(result['memory_passed'])

    def test_histogram_quantiles_are_upper_bounds(self):
        self.assertEqual(percentile_upper_ns([1, 8, 1], .5), 3)
        self.assertEqual(percentile_upper_ns([1, 8, 1], .99), 7)
        self.assertIsNone(percentile_upper_ns([0, 0], .99))

    def test_truncated_checkpoint_is_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'samples.tsv'
            path.write_text('elapsed_ns\trequests\trss_kib\twork_ns\tmax_request_ns\thistogram\n'
                            + '0\t0\t100\t0\t0\t' + json.dumps([0] * 64) + '\n1\tpartial')
            self.assertEqual(len(samples(path)), 1)


class BatchSelectionTests(unittest.TestCase):
    @staticmethod
    def record(size, rate, peak=64, passed=True, assessed=False):
        return dict(batch_size=size, passed=passed, complete=True, peak_rss_kib=peak * 1024,
                    metrics=dict(requests_per_second=rate, assessed=assessed))

    def test_smallest_batch_within_band_wins(self):
        records = [self.record(8, 80), self.record(32, 96), self.record(128, 100)]
        result = summarize(records, 1, 128, .95)
        self.assertEqual(result['recommended_batch_size'], 32)
        self.assertFalse(result['recommendation_memory_assessed'])

    def test_fast_but_over_budget_or_failed_runs_cannot_win(self):
        records = [self.record(8, 80), self.record(32, 96, passed=False), self.record(128, 100, peak=129)]
        self.assertEqual(summarize(records, 1, 128, .95)['recommended_batch_size'], 8)

    def test_missing_repetition_cannot_win(self):
        records = [self.record(8, 100), self.record(32, 90), self.record(32, 92)]
        self.assertEqual(summarize(records, 2, 128, .95)['recommended_batch_size'], 32)

    def test_all_repetitions_must_establish_memory_plateau(self):
        records = [self.record(32, 95, assessed=True), self.record(32, 100)]
        self.assertFalse(summarize(records, 2, 128, .95)['recommendation_memory_assessed'])
        records[1]['metrics']['assessed'] = True
        self.assertTrue(summarize(records, 2, 128, .95)['recommendation_memory_assessed'])

    def test_no_eligible_candidate(self):
        self.assertIsNone(summarize([self.record(8, 100, passed=False)], 1, 128, .95)['recommended_batch_size'])


if __name__ == '__main__':
    unittest.main()
