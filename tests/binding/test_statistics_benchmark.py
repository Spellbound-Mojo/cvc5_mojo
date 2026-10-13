"""Statistics timings must carry a complete, correctly counted native oracle."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from benchmark_statistics import observation


class StatisticsEvidenceTests(unittest.TestCase):
    def test_counts_and_completion_are_required(self):
        good = dict(returncode=0, stdout='3 10 2000 5050 1010\noverhead passed\nexpected 505\n')
        self.assertEqual(observation(good, 3, 10, 2)['entries'], 505)
        for output in (good['stdout'].replace('5050', '5049'),
                       good['stdout'].replace('1010', '1009'),
                       good['stdout'].replace('expected 505', 'expected 504'),
                       good['stdout'].replace('expected 505', 'expected 505 extra'),
                       good['stdout'].replace('expected 505', 'expected 0'),
                       good['stdout'].replace('expected 505', 'expected nan'),
                       good['stdout'].removesuffix('\n'),
                       good['stdout'] + 'extra\n'):
            with self.subTest(output=output):
                self.assertIsNone(observation(dict(good, stdout=output), 3, 10, 2))
        for code in (None, -11, 1):
            self.assertIsNone(observation(dict(good, returncode=code), 3, 10, 2))


if __name__ == '__main__':
    unittest.main()
