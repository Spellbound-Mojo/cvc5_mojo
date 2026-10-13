"""Formatting trace and intentional-abort evidence must fail closed."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from run_contract_tests import formatting_accounting, formatting_failure
from bindgen import config, gen_api


class FormattingEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(config.SNAPSHOT_FILE.read_text())
        _, table = gen_api.generated(cls.snapshot)
        cls.calls = {name: methods['__str__'][0][0]['cname'] for name, methods in table.items()
                     if '__str__' in methods}

    def fixture(self):
        lines = []
        for name, call in self.calls.items():
            lines += ['formatting:' + name, 'formatting:once', call,
                      'formatting:write', call, 'formatting:constructor', call, call, 'formatting:end']
        return lines + ['formatting:nulls', 'formatting:end']

    def test_missing_duplicate_or_repeated_formatting_is_rejected(self):
        good = self.fixture()
        self.assertTrue(formatting_accounting(good, self.snapshot)['passed'])
        bad = [[], good[:-1], good[:-2], good[9:], good[:9] + good,
               good[:2] + [good[2]] + good[2:],
               good[:-1] + [self.calls['Term']] + good[-1:]]
        for lines in bad:
            self.assertFalse(formatting_accounting(lines, self.snapshot)['passed'])

    def test_phase_order_and_correct_native_formatter_are_required(self):
        good = self.fixture()
        changed = good.copy()
        changed[2] = 'unrelated_native_function'
        self.assertFalse(formatting_accounting(changed, self.snapshot)['passed'])
        changed = good.copy()
        changed[1] = 'formatting:constructor'
        self.assertFalse(formatting_accounting(changed, self.snapshot)['passed'])

    def test_only_deliberate_matching_abort_is_accepted(self):
        for fault, text in [('native', "cvc5: invalid argument '42'"),
                            ('utf8', 'Cannot construct a String from invalid UTF-8 data')]:
            good = dict(returncode=-4, stdout='ABORT: term.mojo:1:1: ' + text, stderr='')
            self.assertTrue(formatting_failure(good, fault))
            for change in [dict(returncode=0), dict(returncode=None), dict(returncode=1),
                           dict(returncode=-11), dict(returncode=-6), dict(stdout='unrelated crash'),
                           dict(stdout=text), dict(stderr='formatting unexpectedly returned')]:
                self.assertFalse(formatting_failure(dict(good, **change), fault))


if __name__ == '__main__':
    unittest.main()
