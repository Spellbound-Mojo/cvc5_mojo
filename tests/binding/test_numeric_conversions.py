"""Exact values alone cannot establish that decimal conversions were removed."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from bindgen import config
from run_contract_tests import numeric_accounting, numeric_cases


class NumericEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(config.SNAPSHOT_FILE.read_text())

    def fixture(self):
        lines = []
        for (kind, values), phases in numeric_cases(self.snapshot).items():
            lines += ['numeric:' + kind, *values]
            for phase, calls in phases.items():
                lines += ['numeric:' + phase, *calls.elements()]
            lines += ['numeric:end']
        return lines + ['numeric:done']

    def test_complete_inventory_and_phase_order_are_required(self):
        good = self.fixture()
        self.assertTrue(numeric_accounting(good, self.snapshot)['passed'])
        end = good.index('numeric:end') + 1
        for bad in ([], good[:-1], good[end:], good[:end] + good,
                    good + ['numeric:done'], good[:1] + ['unknown'] + good[2:],
                    [line.replace('numeric:new', 'numeric:rational') for line in good]):
            self.assertFalse(numeric_accounting(bad, self.snapshot)['passed'])

    def test_missing_duplicate_and_text_calls_are_rejected(self):
        good = self.fixture()
        # A lost, repeated, or additional call in every phase must be visible.
        for index, line in enumerate(good):
            if not line.startswith('cvc5_'):
                continue
            for replacement in ([], [line, line], ['cvc5_term_to_string']):
                bad = good[:index] + replacement + good[index + 1:]
                self.assertFalse(numeric_accounting(bad, self.snapshot)['passed'])


if __name__ == '__main__':
    unittest.main()
