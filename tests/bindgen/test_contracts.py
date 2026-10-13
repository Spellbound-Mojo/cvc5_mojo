"""Regression tests for fail-closed generation and negative-test classification."""
import json
import copy
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from bindgen import c_impl, config, cpp_api, gen_api, gen_raw, generation_policy

sys.path.insert(0, str(config.ROOT / 'scripts'))
from run_cvc5_tests import expected_failure


class GenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = json.loads(config.SNAPSHOT_FILE.read_text())

    def test_current_surface_is_accounted_for(self):
        _, missing = gen_raw.classify(self.snap)
        generation_policy.check(missing, self.snap['generation']['unbound_c'], 'raw')
        _, table = gen_api.generated(self.snap)
        generation_policy.check(generation_policy.missing_methods(table),
                                self.snap['generation']['missing_methods'], 'base')

    def test_new_and_stale_omissions_fail(self):
        for actual, allowed in [({'new': 'unsupported'}, {}), ({}, {'old': 'unsupported'})]:
            with self.subTest(actual=actual, allowed=allowed), self.assertRaises(SystemExit):
                generation_policy.check(actual, allowed, 'fixture')

    def test_none_is_not_a_boolean_default(self):
        with self.assertRaises(gen_api.Unsupported):
            gen_api.Model(self.snap)._default('None', 'Bool')

    def test_existing_to_string_must_match_the_native_formatter(self):
        model, table = gen_api.generated(self.snap)
        # Command already mirrors a raising toString(). A different native
        # function under the same name must not silently override the helper.
        changed = copy.deepcopy(table['Command'])
        changed['toString'][0][0]['cname'] = 'different_function'
        with self.assertRaisesRegex(SystemExit, 'collides'):
            gen_api.emit_class(model, 'Command', changed)

    def test_private_numeric_helpers_reuse_generation_without_public_overloads(self):
        model, table = gen_api.generated(self.snap)
        for method in ('mkReal', 'mkBitVector'):
            bindings = self.snap['python']['TermManager']['methods'][method]['binding']
            public = gen_api.signatures(model, 'TermManager', method, table['TermManager'][method][0])
            emitted = gen_api.emit_module(model, 'TermManager', table['TermManager'], 'test')
            for native, helper in bindings['private'].items():
                self.assertIn('def ' + helper + '(', emitted)
                self.assertIn('api[].' + native + '(', emitted)
                self.assertFalse(any(helper in signature for signature in public))
            self.assertTrue(public)
            if method == 'mkReal':
                self.assertFalse(any('numerator: Int, denominator: Int)' in signature for signature in public))

    def test_invalid_private_helper_policies_fail(self):
        for mapping in ({'missing_native': '_native_missing'},
                        {'cvc5_mk_real_num_den': 'mkReal'},
                        {'cvc5_mk_real_num_den': '__init__'},
                        {'cvc5_mk_real_num_den': '_native_mkBitVector64'}):
            changed = copy.deepcopy(self.snap)
            changed['python']['TermManager']['methods']['mkReal']['binding']['private'] = mapping
            with self.subTest(mapping=mapping), self.assertRaisesRegex(SystemExit, 'private overload'):
                gen_api.Model(changed)

    def test_borrowed_owner_cycle_fails_generation(self):
        changed = copy.deepcopy(self.snap)
        # A reverse borrow from Solver to InputParser would close the existing
        # InputParser -> Solver keeper chain. Refuse cyclic ArcPointer state.
        changed['c_functions']['cvc5_get_tm']['returns'] = 'Cvc5InputParser*'
        with self.assertRaisesRegex(SystemExit, 'form a cycle'):
            gen_api.Model(changed)

    def test_borrowed_owner_self_cycle_and_unknown_keeper_fail(self):
        changed = copy.deepcopy(self.snap)
        changed['c_functions']['cvc5_get_tm']['returns'] = 'Cvc5*'
        with self.assertRaisesRegex(SystemExit, 'form a cycle'):
            gen_api.Model(changed)
        model = gen_api.Model(self.snap)
        with self.assertRaisesRegex(gen_api.Unsupported, 'keeper relationship'):
            model.borrowed(model.tm_ctype, 'result', 'InputParser')

    def test_owner_without_a_term_manager_parent_fails(self):
        model = gen_api.Model(self.snap)
        with self.assertRaisesRegex(SystemExit, 'no parent'):
            model.owner_tm('Solver', 'h', [])

    def test_unknown_receipt_and_invalid_anchor_exporter_fail(self):
        for field, value, diagnostic in (('receive', 'unrecognized', 'receipt mode'),
                                          ('exporter', 'Cvc5Term', 'pointer owner'),
                                          ('exporter', 'UnmappedOwner', 'pointer owner')):
            changed = copy.deepcopy(self.snap)
            changed['handles']['Cvc5Result'][field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(SystemExit, diagnostic):
                gen_api.Model(changed)

    def test_iterators_and_term_builders_follow_changed_receipt_policy(self):
        # Simulate a future ownership change. Every Term-returning path must
        # propagate the solver anchor, including the specialized emitters.
        changed = copy.deepcopy(self.snap)
        changed['handles']['Cvc5Term'].update(receive='anchor', exporter='Cvc5')
        model = gen_api.Model(changed)
        methods = model.classify()['Term']
        selected = {name: spec for name, spec in methods.items()
                    if spec[0] and spec[0][0].get('kind') in ('iterate', 'mk_term')}
        self.assertIn('__iter__', selected)
        self.assertGreater(len(selected), 1)
        for name, (overloads, _) in selected.items():
            emitted = gen_api._method_lines(model, 'Term', name, overloads, '')
            receipts = [line for line in emitted if 'Term._received(' in line]
            with self.subTest(method=name):
                self.assertEqual(len(receipts), 1)
                self.assertIn(', self._anchor.value())', receipts[0])
                self.assertNotIn('__ANCHOR_', '\n'.join(emitted))

        # Solver.mkSkolem delegates to a TermManager method, but the actual
        # Solver receiver supplies the anchor under this hypothetical policy.
        emitted = gen_api._method_lines(model, 'Solver', 'mkSkolem', model.method('Solver', 'mkSkolem'), '')
        receipts = [line for line in emitted if 'Term._received(' in line]
        self.assertTrue(receipts)
        self.assertTrue(all(', self._o)' in line for line in receipts))

    def test_wrong_receiver_cannot_supply_an_anchor(self):
        changed = copy.deepcopy(self.snap)
        changed['handles']['Cvc5Result']['exporter'] = 'Cvc5TermManager'
        model = gen_api.Model(changed)
        with self.assertRaisesRegex(gen_api.Unsupported, 'cannot supply TermManager anchor'):
            gen_api.emit_class(model, 'Solver', model.classify()['Solver'])

        # An unanchored handle cannot return an anchored child either.
        changed = copy.deepcopy(self.snap)
        changed['handles']['Cvc5DatatypeConstructor'].update(receive='anchor', exporter='Cvc5')
        model = gen_api.Model(changed)
        with self.assertRaisesRegex(gen_api.Unsupported, 'cannot supply Solver anchor'):
            gen_api._method_lines(model, 'Datatype', '__iter__', model.method('Datatype', '__iter__'), '')

    def test_changed_cpp_defaults_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            include = Path(folder)
            (include / 'cvc5').mkdir()
            header = include / 'cvc5/cvc5.h'
            header.write_text('void fixture(bool flag = true);\nvoid fixture(int n, bool flag = false);')
            with self.assertRaises(SystemExit):
                cpp_api.none_bool_defaults({'Fixture.make': 'fixture'}, include)

    def test_changed_native_release_protocol_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            for rel in [*c_impl.STRUCT_FILES, 'src/api/c/cvc5_c_structs.h']:
                target = source / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(config.SOURCE_DIR / rel, target)
            path = source / c_impl.STRUCT_FILES[0]
            text = path.read_text()
            self.assertIn('d_cvc5->deregister(this)', text)
            path.write_text(text.replace('d_cvc5->deregister(this)', 'changed_protocol(this)'))
            with self.assertRaises(SystemExit):
                c_impl.handles(source)


def record(code, stdout='', stderr=''):
    return dict(returncode=code, stdout=stdout, stderr=stderr)


class ExpectedFailureTests(unittest.TestCase):
    def test_compile_failure_needs_expected_diagnostic(self):
        spec = dict(phase='compile', match='wrong argument')
        self.assertTrue(expected_failure(spec, record(1, stderr='wrong argument'), None, ''))
        for code, text in [(0, 'wrong argument'), (1, 'unrelated failure'), (-11, 'wrong argument'), (None, 'wrong argument')]:
            with self.subTest(code=code, text=text):
                self.assertFalse(expected_failure(spec, record(code, stderr=text), None, ''))

    def test_runtime_failure_requires_successful_build_and_expected_error(self):
        spec = dict(phase='run', match='invalid result')
        self.assertTrue(expected_failure(spec, record(0), record(1, stdout='invalid result'), ''))
        for compiled, executed in [(record(1), None), (record(None), None),
                                   (record(0), record(1, stderr='another error')),
                                   (record(0), record(-6, stderr='invalid result')),
                                   (record(0), record(None, stderr='invalid result'))]:
            self.assertFalse(expected_failure(spec, compiled, executed, ''))

    def test_output_difference_does_not_excuse_execution_failure(self):
        spec = dict(phase='output')
        self.assertTrue(expected_failure(spec, record(0), record(0), 'output differs:\nvalues'))
        for code in [1, -11, None]:
            self.assertFalse(expected_failure(spec, record(0), record(code), 'output differs:'))
        self.assertFalse(expected_failure(spec, record(0), record(0), ''))


if __name__ == '__main__':
    unittest.main()
