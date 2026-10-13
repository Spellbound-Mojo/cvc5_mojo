"""Loading failures cannot hide crashes, incomplete workers, or late cleanup."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from check_runtime_loading import classified, closed_before_checkpoint


class LoadingClassificationTests(unittest.TestCase):
    def test_exact_success_and_expected_failure(self):
        success = dict(returncode=0, stdout='loaded\nattempts 2\n')
        failure = dict(returncode=0, stdout='load-error\nmissing symbol f\nattempts 2\n')
        self.assertTrue(classified(success, None, 'loaded\nattempts 2\n'))
        self.assertTrue(classified(failure, 'symbol f', 'attempts 2\n'))
        self.assertFalse(classified(success, 'symbol f', 'attempts 2\n'))
        self.assertFalse(classified(failure, None, 'loaded\nattempts 2\n'))
        for code in (1, -6, -11, None):
            self.assertFalse(classified(dict(failure, returncode=code), 'symbol f', 'attempts 2\n'))
        for text in ('', 'load-error\nmissing symbol f\n', 'load-error\nother failure\nattempts 2\n',
                     'load-error\nmissing symbol f\nattempts 1\n', failure['stdout'] + 'unexpected\n'):
            self.assertFalse(classified(dict(failure, stdout=text), 'symbol f', 'attempts 2\n'))

    def test_all_threads_and_rounds_must_finish(self):
        tail = 'threads passed: 16 of 16\nrounds 50\nthread test passed\n'
        self.assertTrue(classified(dict(returncode=0, stdout=tail), None, tail))
        for text in (tail.replace('16 of 16', '15 of 16'), tail.replace('50', '49'), tail.splitlines()[0]):
            self.assertFalse(classified(dict(returncode=0, stdout=text), None, tail))


class LoadingCleanupTests(unittest.TestCase):
    def test_unwind_must_finish_before_checkpoint(self):
        good = ['open main', 'open parser', 'close parser', 'close main', 'checkpoint']
        self.assertTrue(closed_before_checkpoint(good, ['main', 'parser'], 1))
        for bad in ([], good[:-1], good + ['checkpoint'], good[:2] + ['checkpoint'] + good[2:-1],
                    [good[3], *good[:3], good[-1]], [*good[:-2], good[-1]],
                    [*good[:-1], 'unknown', 'checkpoint']):
            self.assertFalse(closed_before_checkpoint(bad, ['main', 'parser'], 1))
        self.assertFalse(closed_before_checkpoint(good, ['main', 'parser'], 2))

    def test_bootstrap_owners_are_balanced_separately_from_library_handles(self):
        good = ['open main', 'create parent', 'create owner', 'destroy owner', 'destroy parent', 'close main', 'checkpoint']
        self.assertTrue(closed_before_checkpoint(good, ['main'], 1, ('parent', 'owner')))
        for omitted in ('destroy parent', 'destroy owner'):
            self.assertFalse(closed_before_checkpoint([x for x in good if x != omitted], ['main'], 1, ('parent', 'owner')))
        twice = [*good[:-1], *good]
        self.assertTrue(closed_before_checkpoint(twice, ['main'], 2, ('parent', 'owner')))


if __name__ == '__main__':
    unittest.main()
