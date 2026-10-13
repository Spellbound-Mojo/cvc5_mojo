"""Check native staging against the cached release and reject stale inventories."""

import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from bindgen import bump, c_library, config, package_native


class NativePackagingTests(unittest.TestCase):
    def test_all_platforms_stage_and_wrong_architecture_fails(self):
        for target in config.pinned()['binary']:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                manifest = package_native.stage(config.binary_dir(target), Path(tmp) / 'prefix', target=target)
                self.assertEqual(manifest['platform'], target)
                other = next(t for t in config.pinned()['binary'] if t != target)
                with self.assertRaisesRegex(ValueError, 'differ from'):
                    package_native.stage(config.binary_dir(target), Path(tmp) / 'wrong', target=other)

    def test_staged_release_loads_with_preserved_bytes_and_relative_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / 'prefix with spaces'
            manifest = package_native.stage(config.BINARY_DIR, prefix)
            lib = prefix / 'lib/cvc5_mojo/lib'
            self.assertEqual(set(p.name for p in lib.iterdir()),
                             {alias for name, info in manifest['libraries'].items()
                              for alias in [name, *info['aliases']]})
            for name, info in manifest['libraries'].items():
                self.assertFalse((lib / name).is_symlink())
                self.assertEqual(hashlib.sha256((lib / name).read_bytes()).hexdigest(), info['sha256'])
                for alias in info['aliases']:
                    self.assertEqual((lib / alias).readlink(), Path(name))
                    self.assertTrue((lib / alias).is_file())
            licenses = prefix / 'share/licenses/cvc5_mojo'
            for original in (config.BINARY_DIR / 'licenses').rglob('*'):
                if original.is_file():
                    installed = licenses / 'cvc5-bundled-licenses' / original.relative_to(config.BINARY_DIR / 'licenses')
                    self.assertEqual(installed.read_bytes(), original.read_bytes())
            for original, installed in [(config.BINARY_DIR / 'COPYING', licenses / 'cvc5-COPYING'),
                                        (config.ROOT / 'NOTICE', licenses / 'NOTICE'),
                                        (config.ROOT / 'LICENSE', licenses / 'LICENSE')]:
                self.assertEqual(original.read_bytes(), installed.read_bytes())
            # A separate loader process cannot reuse the source tree's loaded libraries.
            subprocess.run([sys.executable, '-c',
                            'import ctypes, sys; handles = [ctypes.CDLL(p) for p in sys.argv[1:]]',
                            *(str(lib / root) for root in manifest['roots'])],
                           cwd=tmp, env={'PATH': '/usr/bin:/bin'}, check=True)
            with self.assertRaisesRegex(ValueError, 'already exists'):
                package_native.stage(config.BINARY_DIR, prefix)

    def test_recipe_libstdcxx_bound_covers_the_shipped_linux_libraries(self):
        # The newest GLIBCXX symbol version each libstdcxx lower bound provides,
        # from GCC's ABI history. Add an entry when the bound has to rise.
        provides = {11: (3, 4, 29)}
        bound = re.search(r'libstdcxx >=(\d+)', bump.RECIPE.read_text())
        self.assertIsNotNone(bound, "the recipe must require libstdcxx on Linux")
        bound = int(bound[1])
        self.assertIn(bound, provides, "record the GLIBCXX version this libstdcxx bound provides")
        snapshot = json.loads(config.SNAPSHOT_FILE.read_text())
        needed = max(tuple(int(part) for part in version.removeprefix('GLIBCXX_').split('.'))
                     for target in snapshot['native_libraries'] if target.startswith('linux-')
                     for info in package_native.shipped(snapshot, target)[1].values()
                     for version in info['symbol_versions'] if version.startswith('GLIBCXX_'))
        self.assertLessEqual(needed, provides[bound], "raise the recipe's libstdcxx bound")

    def test_changed_library_is_rejected_before_staging(self):
        inventory = copy.deepcopy(json.loads(config.SNAPSHOT_FILE.read_text())['native_libraries'][config.platform_name()])
        inventory[next(iter(inventory))]['sha256'] = 'changed'
        with tempfile.TemporaryDirectory() as tmp, patch.object(c_library, 'native_inventory', return_value=inventory):
            prefix = Path(tmp) / 'prefix'
            with self.assertRaisesRegex(ValueError, 'differ from'):
                package_native.stage(config.BINARY_DIR, prefix)
            self.assertFalse(prefix.exists())

    def test_missing_root_and_conflicting_soname_are_rejected(self):
        inventory = {'libexample.so.2.0': dict(aliases=['libexample.so'], soname=['libexample.so.2'], needed=[])}
        with self.assertRaisesRegex(ValueError, 'missing C API'):
            package_native.dependency_closure(inventory, ['missing.so'])
        with self.assertRaisesRegex(ValueError, 'SONAME'):
            package_native.dependency_closure(inventory, ['libexample.so'])

    def test_closure_excludes_unused_libraries_and_reports_system_dependencies(self):
        inventory = {
            'root.so': dict(aliases=[], soname=['root.so'], needed=['dep.so.1', 'system.so']),
            'dep.so.1.0': dict(aliases=['dep.so.1'], soname=['dep.so.1'], needed=[]),
            'unused.so': dict(aliases=[], soname=[], needed=[]),
        }
        selected, external = package_native.dependency_closure(inventory, ['root.so'])
        self.assertEqual(set(selected), {'root.so', 'dep.so.1.0'})
        self.assertEqual(external, ['system.so'])


if __name__ == '__main__':
    unittest.main()
