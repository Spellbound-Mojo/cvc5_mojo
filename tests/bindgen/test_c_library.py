"""Portable native metadata extraction, including Darwin dependency names."""
import unittest
from unittest.mock import patch

from bindgen import c_library, package_native


class NativeMetadataTests(unittest.TestCase):
    def test_macho_load_commands_distinguish_deployment_target_and_linker_version(self):
        headers = '''Mach header
Load command 0
          cmd LC_ID_DYLIB
         name @rpath/root.1.dylib (offset 24)
Load command 1
          cmd LC_LOAD_DYLIB
         name @rpath/dep.2.dylib (offset 24)
Load command 2
          cmd LC_LOAD_DYLIB
         name /usr/lib/libSystem.B.dylib (offset 24)
Load command 3
          cmd LC_RPATH
         path @loader_path/../lib (offset 12)
Load command 4
          cmd LC_BUILD_VERSION
     platform macos
          sdk 15.5
        minos 11.0
       ntools 1
         tool ld
      version 1167.5
'''
        with patch.object(c_library, '_inspect', return_value=headers):
            metadata = c_library._macho_metadata('example.dylib')
        self.assertEqual(metadata['minimum_os'], ['11.0'])
        self.assertEqual(metadata['soname'], ['@rpath/root.1.dylib'])
        self.assertEqual(metadata['needed'], ['@rpath/dep.2.dylib', '/usr/lib/libSystem.B.dylib'])
        self.assertEqual(metadata['rpath'], ['@loader_path/../lib'])

    def test_malformed_macho_dependency_fails_extraction(self):
        with patch.object(c_library, '_inspect', return_value='Load command 0\n cmd LC_LOAD_DYLIB\n'), \
                self.assertRaisesRegex(ValueError, 'missing name'):
            c_library._macho_metadata('example.dylib')

    def test_macho_closure_keeps_system_paths_external(self):
        inventory = {
            'root.1.dylib': dict(aliases=['root.dylib'], soname=['@rpath/root.1.dylib'],
                                needed=['@rpath/dep.2.dylib', '/usr/lib/system.dylib']),
            'dep.2.dylib': dict(aliases=['dep.dylib'], soname=['@rpath/dep.2.dylib'], needed=[]),
            'system.dylib': dict(aliases=[], soname=[], needed=[]),
        }
        selected, external = package_native.dependency_closure(inventory, ['root.dylib'])
        self.assertEqual(set(selected), {'root.1.dylib', 'dep.2.dylib'})
        self.assertEqual(external, ['/usr/lib/system.dylib'])
        del inventory['dep.2.dylib']
        with self.assertRaisesRegex(ValueError, 'missing bundled Mach-O'):
            package_native.dependency_closure(inventory, ['root.dylib'])


if __name__ == '__main__':
    unittest.main()
