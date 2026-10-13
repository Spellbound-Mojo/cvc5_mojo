"""Regression checks for translating upstream tests without changing their meaning."""
import ast
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from bindgen import config, translate

sys.path.insert(0, str(config.ROOT / 'scripts'))
from run_cvc5_tests import comparable_output, record_calls


class TranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = translate.Api(json.loads(config.SNAPSHOT_FILE.read_text()))

    def translate(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test_fixture.py'
            path.write_text(source)
            return translate.translate_file(path, self.api)

    def test_fraction_literal_keeps_binary_and_decimal_meanings_distinct(self):
        translator = translate.Translator(self.api, {})
        binary = translator.expr(ast.parse('Fraction(0.3)', mode='eval').body)
        decimal = translator.expr(ast.parse('Fraction("0.3")', mode='eval').body)
        self.assertEqual(binary, 'Rational(5404319552844595, 18014398509481984)')
        self.assertEqual(decimal, 'Rational(3, 10)')

    def test_large_integer_local_does_not_narrow_to_machine_int(self):
        result = self.translate('def test_big():\n    den = 2**64 + 1\n    assert den > 0\n')
        self.assertEqual(result['run'], ['test_big'])
        self.assertIn('var den = Integer(18446744073709551617)', result['text'])

    def test_term_argument_keeps_scalar_and_variadic_overloads(self):
        result = self.translate('''def test_overloads():
    tm = TermManager()
    solver = Solver(tm)
    x = tm.mkBoolean(True)
    solver.getValue(x)
    tm.mkTerm(Kind.NOT, x)
    solver.mkGrammar(x, [x])
''')
        self.assertEqual(result['run'], ['test_overloads'])
        self.assertIn('solver.getValue(x)', result['text'])
        self.assertIn('tm.mkTerm(Kind.NOT, x)', result['text'])
        self.assertIn('solver.mkGrammar(_collect_Term(x), [x])', result['text'])

    def test_mutating_a_record_field_list_prevents_fixed_unpacking(self):
        source = '''def test_record():
    tm = TermManager()
    fields = [("a", tm.getIntegerSort())]
    {mutation}
    tm.mkRecordSort(*fields)
'''
        stable = self.translate(source.format(mutation='pass'))
        changed = self.translate(source.format(mutation='fields.append(("b", tm.getIntegerSort()))'))
        self.assertEqual(stable['run'], ['test_record'])
        self.assertEqual(changed['run'], [])
        self.assertIn('argument unpacking', changed['not_translated']['test_record'])

    def test_collection_comprehension_filters_are_not_discarded(self):
        result = self.translate('''def test_children():
    tm = TermManager()
    x = tm.mkBoolean(True)
    children = [c for c in x if c.isBooleanValue()]
''')
        self.assertEqual(result['run'], [])
        self.assertIn('list comprehension', result['not_translated']['test_children'])

    def test_collection_comprehension_does_not_depend_on_ast_dump_format(self):
        # Python 3.15's ast.dump omits the default load context.
        dump = ast.dump
        def dump_without_load(node, **options):
            return dump(node, **options).replace(', ctx=Load()', '').replace('ctx=Load()', '')
        with patch.object(ast, 'dump', dump_without_load):
            result = self.translate('''def test_children():
    tm = TermManager()
    x = tm.mkBoolean(True)
    children = [c for c in x]
''')
        self.assertEqual(result['run'], ['test_children'])
        self.assertIn('_collect_Term(x)', result['text'])

    def test_metadata_comparison_checks_presence_and_unsigned_alternative(self):
        result = self.translate('''def test_info():
    tm = TermManager()
    solver = Solver(tm)
    info = solver.getOptionInfo("rlimit")
    assert info["current"] == 0
''')
        self.assertEqual(result['run'], ['test_info'])
        self.assertIn('Bool(info.current)', result['text'])
        self.assertIn('.isa[Int]()', result['text'])
        self.assertIn('.isa[UInt64]()', result['text'])

    def test_partial_stat_dictionary_cannot_satisfy_equality(self):
        result = self.translate('''def test_stats():
    tm = TermManager()
    stats = tm.getStatistics()
    assert stats["x"] == {"internal": False}
''')
        self.assertEqual(result['run'], [])
        self.assertIn('all fields', result['not_translated']['test_stats'])

    def test_static_outer_rejection_retains_inner_runtime_check(self):
        result = self.translate('''def test_negative():
    tm = TermManager()
    with pytest.raises(RuntimeError):
        tm.mkEmptySet(tm.mkCardinalityConstraint(tm.getIntegerSort(), 0))
''')
        self.assertEqual(result['rejections']['test_negative'], [3])
        self.assertIn('_ = tm.mkCardinalityConstraint(tm.getIntegerSort(), 0)', result['text'])
        self.assertIn('expected an error', result['text'])

    def test_wrong_arity_is_separate_from_valid_runtime_error(self):
        source = '''def test_negative():
    tm = TermManager()
    solver = Solver(tm)
    with pytest.raises(RuntimeError):
        solver.checkSat(tm.mkBoolean(False))
    with pytest.raises(RuntimeError):
        solver.setOption("non-existing", "true")
'''
        result = self.translate(source)
        self.assertEqual(result['rejections']['test_negative'], [4])
        self.assertIn('solver.setOption("non-existing", "true")', result['text'])

    def test_example_main_keeps_exit_status_and_rejection_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'example.py'
            path.write_text('''def main():
    tm = TermManager()
    try:
        sort = tm.getIntegerSort()
        tm.mkConst("x", sort)
        unreachable_name()
        return 1
    except:
        pass
    return 0
if __name__ == "__main__":
    sys.exit(main())
''')
            normal = translate.translate_example(path, self.api)
            negative = translate.translate_example(path, self.api, compile_failure_line=3)
        self.assertIsNone(normal['not_translated'])
        self.assertEqual(normal['rejections'], [3])
        self.assertIn('_example_main() == 0', normal['text'])
        self.assertNotIn('unreachable_name', negative['text'])
        self.assertIn('    var sort = tm.getIntegerSort()\n    # Expected compile failure', negative['text'])


class ModelOutputTests(unittest.TestCase):
    patterns = [r'Value of `a`: (.+)', r'Value of `b`: (.+)']
    expected = 'Expect SAT.\ncvc5: sat\nValue of `a`: 1\nValue of `b`: 2\n'

    def normalized(self, text):
        return comparable_output(text, self.patterns)

    def test_nonunique_witness_values_can_differ(self):
        actual = self.expected.replace('`: 1', '`: 3').replace('`: 2', '`: 4')
        self.assertEqual(self.normalized(actual), self.normalized(self.expected))

    def test_solver_status_and_other_output_still_must_match(self):
        for old, new in [('cvc5: sat', 'cvc5: unsat'), ('Expect SAT.', 'Expect UNKNOWN.')]:
            with self.subTest(old=old):
                self.assertNotEqual(self.normalized(self.expected.replace(old, new)), self.normalized(self.expected))

    def test_missing_reordered_or_empty_model_output_fails(self):
        lines = self.expected.splitlines(keepends=True)
        for text in (''.join(lines[:-1]), ''.join(lines[:2] + lines[2:][::-1]), self.expected.replace('`: 1', '`: ')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.normalized(text)

    def test_additional_model_output_is_not_masked(self):
        self.assertNotEqual(self.normalized(self.expected + 'Value of `a`: 9\n'), self.normalized(self.expected))

    def test_exact_comparisons_preserve_every_byte(self):
        text = 'sat\r\nvalue: 1\n\n'
        self.assertEqual(comparable_output(text, []), text)


class CallCoverageTests(unittest.TestCase):
    def test_targeted_traces_extend_baseline_but_ignore_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'calls.json'
            path.write_text(json.dumps(dict(cvc5='fixture', calls=['old'])))
            records = [dict(kind='selected test', passed=True, calls=['new']),
                       dict(kind='selected test', passed=False, calls=['failed']),
                       dict(kind='left-out test', passed=True, calls=['stale'])]
            with patch.object(config, 'CALLS_FILE', path):
                record_calls(records, 'fixture', extend=True)
                self.assertEqual(json.loads(path.read_text())['calls'], ['new', 'old'])
                with self.assertRaises(ValueError):
                    record_calls(records, 'another-release', extend=True)
                record_calls(records, 'fixture', extend=True, reachable={'new'})
                self.assertEqual(json.loads(path.read_text())['calls'], ['new'])
                with self.assertRaisesRegex(ValueError, 'absent from the public inventory'):
                    record_calls(records, 'fixture', extend=True, reachable=set())
                record_calls(records, 'fixture')
                self.assertEqual(json.loads(path.read_text())['calls'], ['new'])


if __name__ == '__main__':
    unittest.main()
