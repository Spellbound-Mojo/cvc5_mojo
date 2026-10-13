"""Each native host selects its matching cached solver without changing discovery."""
import unittest
from unittest.mock import patch

from bindgen import config


class PlatformTests(unittest.TestCase):
    def test_native_and_foreign_archive_paths(self):
        for system, machine, target, other in [('Linux', 'x86_64', 'linux-64', 'linux-aarch64'),
                                              ('Linux', 'aarch64', 'linux-aarch64', 'linux-64'),
                                              ('Darwin', 'arm64', 'osx-arm64', 'linux-64')]:
            with (self.subTest(system=system, machine=machine), patch.object(config.platform, 'system', return_value=system),
                  patch.object(config.platform, 'machine', return_value=machine)):
                self.assertEqual(config.platform_name(), target)
                self.assertEqual(config.binary_dir(target), config.BINARY_DIR)
                self.assertEqual(config.binary_dir(other), config.THIRD_PARTY / ('cvc5-' + other))
                suffix = '.dylib' if system == 'Darwin' else '.so'
                self.assertEqual(config.library_filename('example'), 'example' + suffix)

    def test_intel_mac_is_not_apple_silicon(self):
        with (patch.object(config.platform, 'system', return_value='Darwin'),
              patch.object(config.platform, 'machine', return_value='x86_64'),
              self.assertRaisesRegex(RuntimeError, 'Apple Silicon')):
            config.platform_name()

    def test_32_bit_arm_is_not_arm64(self):
        with (patch.object(config.platform, 'system', return_value='Linux'),
              patch.object(config.platform, 'machine', return_value='armv7l'),
              self.assertRaisesRegex(RuntimeError, 'ARM64')):
            config.platform_name()


if __name__ == '__main__':
    unittest.main()
