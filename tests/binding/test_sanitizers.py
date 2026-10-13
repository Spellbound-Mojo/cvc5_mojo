"""Sanitizer reports must identify the deliberate defect, not merely fail."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from check_sanitizers import detected


class SensitivityTests(unittest.TestCase):
    def test_diagnostic_and_exit_status_are_required(self):
        report = dict(returncode=1, stderr='ERROR: heap-buffer-overflow\nSUMMARY: AddressSanitizer: heap-buffer-overflow')
        self.assertTrue(detected(report, 'heap-buffer-overflow'))
        for code in (0, -4, -6, -11, None):
            self.assertFalse(detected(dict(report, returncode=code), 'heap-buffer-overflow'))
        self.assertFalse(detected(report, 'Direct leak of 8 byte(s)'))
        self.assertFalse(detected(dict(report, stderr='heap-buffer-overflow'), 'heap-buffer-overflow'))


if __name__ == '__main__':
    unittest.main()
