"""Native controls: the model checks must reject deliberately corrupted values."""
from pathlib import Path
import sys
import tempfile
import unittest

from bindgen import config, translate

sys.path.insert(0, str(config.ROOT / 'scripts'))
from verify_docs_examples import precompile, run


class ModelCheckControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.folder = Path(cls.tmp.name)
        cls.package, _ = precompile(cls.folder, 180)

    def check(self, name, helper, expected_error=None):
        source = self.folder / f'{name}.mojo'
        binary = self.folder / name
        source.write_text('''from std.testing import assert_true
from cvc5_mojo import Kind, Solver, Result, Term, TermManager

''' + helper + '''
def main() raises:
    var tm = TermManager()
    var solver = Solver(tm)
    solver.setOption("produce-models", "true")
    var x = tm.mkConst(tm.getBooleanSort(), "x")
    solver.assertFormula(x)
    assert_true(_checked_sat(solver).isSat())
    assert_true(_checked_value(solver, x).getBooleanValue())
''')
        compiled = run(['mojo', 'build', '-I', str(self.package), str(source), '-o', str(binary)], 180)
        self.assertEqual(compiled['returncode'], 0, compiled['stderr'])
        executed = run([str(binary)], 30)
        if expected_error is None:
            self.assertEqual(executed['returncode'], 0, executed['stderr'])
        else:
            self.assertIsNotNone(executed['returncode'])
            self.assertGreater(executed['returncode'], 0, executed['stderr'])
            self.assertIn(expected_error, executed['stdout'] + executed['stderr'])

    def test_correct_model_passes(self):
        self.check('correct', translate.SUPPORT['model'])

    def test_false_assertion_evaluation_fails(self):
        helper = translate.SUPPORT['model'].replace('solver.getValue(assertion).getBooleanValue()', 'False')
        self.check('false_assertion', helper, 'model violates an assertion')

    def test_wrong_model_value_of_the_same_sort_fails(self):
        helper = translate.SUPPORT['model'].replace('var value = solver.getValue(term)',
                                                   'var value = solver.getTermManager().mkBoolean(False)')
        self.check('wrong_value', helper, 'model value disagrees with the evaluated term')


if __name__ == '__main__':
    unittest.main()
