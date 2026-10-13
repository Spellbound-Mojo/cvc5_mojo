"""Verification selection stays cached-only and keeps slower diagnostics separate."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from verify_binding import gates


class VerificationTests(unittest.TestCase):
    def test_tiers_are_complete_unique_and_do_not_fetch(self):
        folder = Path('/tmp/verification-test')
        core = gates('core', folder, 2)
        extended = gates('extended', folder, 2)
        combined = gates('all', folder, 2)
        self.assertEqual(combined, core + extended)
        self.assertEqual(len(combined), len({name for name, _ in combined}))
        for _, command in combined:
            self.assertNotIn('fetch', command)
            self.assertNotIn('generate', command)
        self.assertIn('upstream', dict(core))
        self.assertIn('sanitizers', dict(extended))
        self.assertEqual(extended[-1][0], 'overhead')


if __name__ == '__main__':
    unittest.main()
