"""Exact semantic models, reproducible streams, and failure-preserving reduction."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from binding_sequences import BOUNDARIES, WIDTHS, encode, execute, expected, failure, generate, minimize, read


class SequenceModelTests(unittest.TestCase):
    def test_collections_are_snapshots_across_mutation_and_reset(self):
        ops = [('I', 0, 18446744073709551617, 1), ('C', 1, 0), ('V', 3, 0, 1, 0),
               ('I', 0, -2, 0), ('A', 1, 1, 0, 1), ('E', 4, 1, 8, 256), ('R',), ('G',), ('P', 0, 1)]
        self.assertEqual(expected(ops),
            '0 I 18446744073709551617\n1 C 18446744073709551617\n'
            '2 V [18446744073709551617,18446744073709551617,18446744073709551617]\n'
            '3 I -2\n4 A 18446744073709551619\n5 E recovered 18446744073709551619\n'
            '6 R reset\n7 G [18446744073709551617,18446744073709551617,18446744073709551617]\n'
            '8 P 0\nsequence passed\n')

    def test_exact_rationals_and_signed_bitvectors(self):
        self.assertEqual(expected([('Q', -6, 3, 0), ('Q', 0, 7, 5), ('Q', 10, 6, 2),
                                   ('B', 64, 10, '-1', 1), ('B', 8, 16, '80', 0)]),
            '0 Q -2/1\n1 Q 0/1\n2 Q 5/3\n3 B 18446744073709551615\n4 B 128\nsequence passed\n')

    def test_reproducible_inputs_and_mandatory_coverage(self):
        a, b = generate(42, 64), generate(43, 64)
        self.assertEqual(encode(a), encode(generate(42, 64)))
        self.assertNotEqual(encode(a), encode(b))
        prefix = generate(42, 0)
        self.assertEqual(a[:len(prefix)], prefix)
        self.assertTrue(set(BOUNDARIES) <= {op[2] for op in prefix if op[0] == 'I'})
        self.assertEqual({op[1] for op in prefix if op[0] == 'B'}, set(WIDTHS))
        self.assertEqual({op[3] for op in prefix if op[0] == 'Q'}, set(range(6)))
        self.assertEqual({op[1] for op in prefix if op[0] == 'E'}, set(range(6)))
        self.assertEqual({op[0] for op in a}, set('ICAQBVGREP'))


class SequenceFailureTests(unittest.TestCase):
    def test_crashes_timeouts_and_incomplete_or_wrong_output_fail(self):
        ops = [('I', 0, 9223372036854775808, 1)]
        good = dict(returncode=0, stdout=expected(ops))
        self.assertIsNone(failure(good, ops))
        for code in (None, -11, -6, 1):
            self.assertIsNotNone(failure(dict(good, returncode=code), ops))
        for text in ('', 'sequence passed\n', good['stdout'][:-1], good['stdout'] + '\n',
                     good['stdout'].replace('9223372036854775808', '-9223372036854775808')):
            self.assertIsNotNone(failure(dict(good, stdout=text), ops))
        self.assertEqual(failure(dict(good, stdout=good['stdout'].replace('9223372036854775808', '0')), ops), ('output', 'I'))

    def test_reduction_keeps_required_state_and_observation(self):
        ops = [('G',), ('I', 0, 19, 0), ('C', 1, 0), ('G',), ('P', 0, 1), ('R',)]
        # A stand-in discrepancy requires both the value and its later copy.
        def reproduces(candidate):
            return ('I', 0, 19, 0) in candidate and ('C', 1, 0) in candidate
        reduced, calls = minimize(ops, reproduces)
        self.assertEqual(reduced, [('I', 0, 19, 0), ('C', 1, 0)])
        self.assertLessEqual(calls, 80)
        self.assertEqual(expected(reduced), '0 I 19\n1 C 19\nsequence passed\n')

    def test_reduction_obeys_budget_and_handles_startup_failure(self):
        ops = generate(0, 0)
        reduced, calls = minimize(ops, lambda _: False, budget=3)
        self.assertEqual(reduced, ops)
        self.assertEqual(calls, 3)
        reduced, calls = minimize(ops, lambda _: True)
        self.assertEqual(reduced, [])
        self.assertEqual(expected(reduced), 'sequence passed\n')

    def test_execution_preserves_original_and_saves_reduced_replay(self):
        ops = [('G',), ('I', 0, 2**64 + 1, 1), ('C', 1, 0), ('R',), ('G',)]
        # A simulated executable narrows integer inputs, even if C and Mojo
        # were to agree on that wrong result. The independent model must fail.
        def narrowed(command, timeout):
            candidate = read(command[-2])
            changed = []
            for row in candidate:
                if row[0] == 'I':
                    op, a, value, form = row
                    changed.append((op, a, int(value) % 2**64, form))
                else:
                    changed.append(row)
            return dict(returncode=0, stdout=expected(changed), stderr='')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'original.txt'
            path.write_text(encode(ops))
            case = dict(path=path, operations=ops)
            control = dict(run=narrowed(['fake', str(path), 'maps'], 1))
            with patch('binding_sequences.run', side_effect=narrowed), patch('binding_sequences.libraries', return_value={'matched': True}):
                result = execute('fake', None, case, root / 'case', control)
            self.assertFalse(result['passed'])
            self.assertTrue(result['matches_c'])
            self.assertTrue(result['reduction']['preserved'])
            self.assertEqual(path.read_text(), encode(ops))
            self.assertEqual(read(result['reduction']['input']), [('I', '0', str(2**64 + 1), '1')])


if __name__ == '__main__':
    unittest.main()
