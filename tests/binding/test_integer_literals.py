"""An exact value is insufficient evidence if the constructor route is wrong."""
import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from run_contract_tests import integer_literal_accounting
from bindgen import config, gen_api


class IntegerLiteralEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(config.SNAPSHOT_FILE.read_text())
        _, table = gen_api.generated(cls.snapshot)
        cls.functions = {o['params'][0].mojo: o['cname']
                         for o in table['TermManager']['mkInteger'][0] if o.get('cname')}
        text = (config.ROOT / 'tests/smoke/test_integer_boundaries.mojo').read_text()
        cls.values = re.findall(r'check_literal\["(-?\d+)"\]', text)

    def fixture(self):
        lines = []
        for value in self.values:
            kind = 'Int' if -(2**63) <= int(value) < 2**63 else 'String'
            lines += ['integer_literal:begin', value, self.functions[kind], 'integer_literal:end']
        return lines + ['integer_literal:done']

    def test_every_case_must_complete_once(self):
        good = self.fixture()
        self.assertTrue(integer_literal_accounting(good, self.snapshot)['passed'])
        for bad in ([], good[:-1], good[4:], good[:4] + good, good + ['integer_literal:done'],
                    good[:-2] + good[-1:], good[:1] + ['unknown-value'] + good[2:]):
            self.assertFalse(integer_literal_accounting(bad, self.snapshot)['passed'])

    def test_boundary_routes_and_single_calls_are_required(self):
        good = self.fixture()
        for value in ('-9223372036854775808', '9223372036854775807',
                      '-9223372036854775809', '9223372036854775808'):
            index = good.index(value) + 1
            bad = good.copy()
            bad[index] = next(f for f in self.functions.values() if f != good[index])
            self.assertFalse(integer_literal_accounting(bad, self.snapshot)['passed'])
            self.assertFalse(integer_literal_accounting(good[:index] + good[index + 1:], self.snapshot)['passed'])
            self.assertFalse(integer_literal_accounting(good[:index] + [good[index]] + good[index:], self.snapshot)['passed'])


if __name__ == '__main__':
    unittest.main()
