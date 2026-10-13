"""Upstream bumps keep the release version, recipe, and oracle in step."""

import contextlib
import io
from pathlib import Path
import shutil
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from bindgen import bump, config


def release(version='1.4.2'):
    tag = 'cvc5-' + version
    return dict(tag_name=tag, assets=[
        dict(name=f'cvc5-{system}-{arch}-shared.zip',
             browser_download_url=f'https://github.com/cvc5/cvc5/releases/download/{tag}/cvc5-{system}-{arch}-shared.zip')
        for system, arch in [('Linux', 'x86_64'), ('Linux', 'arm64'), ('macOS', 'arm64')]])


class BumpTests(unittest.TestCase):
    def test_new_upstream_resets_revision_and_updates_both_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = root / 'recipe.yaml'
            shutil.copyfile(bump.RECIPE, recipe)
            shutil.copyfile(config.ROOT / 'pixi.toml', root / 'pixi.toml')
            version_file = root / 'cvc5-version.toml'
            version_file.write_text('version = "1.4.1"\n')
            with (patch.object(config, 'ROOT', root), patch.object(config, 'VERSION_FILE', version_file),
                  patch.object(bump, 'RECIPE', recipe), patch.object(bump.sys, 'argv', ['bump', '1.4.2']),
                  patch.object(bump, '_api', return_value=release()), patch.object(bump, '_commit', return_value='new-commit'),
                  patch.object(bump, '_sha256', side_effect=['a' * 64, 'b' * 64, 'c' * 64, 'd' * 64]), contextlib.redirect_stdout(io.StringIO())):
                bump.main()
            pixi = tomllib.loads((root / 'pixi.toml').read_text())
            self.assertEqual(pixi['workspace']['version'], '1.4.2.0')
            self.assertEqual(pixi['feature']['oracle']['pypi-dependencies']['cvc5'], '==1.4.2')
            self.assertIn('version: "1.4.2.0"', recipe.read_text())
            self.assertIn('cvc5_version: "1.4.2"', recipe.read_text())
            self.assertIn('tag: v${{ version }}', recipe.read_text())
            self.assertIn('sha256: ' + 'a' * 64, recipe.read_text())
            self.assertIn('sha256: ' + 'b' * 64, recipe.read_text())
            self.assertEqual(tomllib.loads(version_file.read_text())['commit'], 'new-commit')
            self.assertIn('sha256: ' + 'c' * 64, recipe.read_text())
            self.assertEqual(set(tomllib.loads(version_file.read_text())['binary']), {'linux-64', 'linux-aarch64', 'osx-arm64'})

    def test_current_upstream_does_not_reset_a_bindings_revision(self):
        with (patch.object(config, 'pinned', return_value={'version': '1.4.1'}),
              patch.object(bump.sys, 'argv', ['bump', '1.4.1']),
              patch.object(bump, '_api', return_value=release('1.4.1')), patch.object(bump, '_sha256') as download,
              patch.object(Path, 'write_text') as write, contextlib.redirect_stdout(io.StringIO())):
            bump.main()
        download.assert_not_called()
        write.assert_not_called()

    def test_missing_architecture_does_not_change_the_pin(self):
        missing = release()
        missing['assets'].pop()
        with (patch.object(bump, '_sha256', return_value='a' * 64),
              self.assertRaisesRegex(RuntimeError, 'missing a required')):
            bump.release_binaries(missing)

    def test_refresh_reuses_existing_archive_identity(self):
        old = {'linux-64': {'url': release()['assets'][0]['browser_download_url'], 'sha256': 'a' * 64}}
        with patch.object(bump, '_sha256', return_value='b' * 64) as download:
            actual = bump.release_binaries(release(), old)
        self.assertEqual(actual['linux-64']['sha256'], 'a' * 64)
        self.assertEqual(actual['linux-aarch64']['sha256'], 'b' * 64)
        self.assertEqual(actual['osx-arm64']['sha256'], 'b' * 64)
        self.assertEqual(download.call_count, 2)

    def test_refresh_preserves_bindings_revision_and_rejects_a_moved_tag(self):
        current = config.pinned()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = root / 'recipe.yaml'
            recipe.write_text(bump.RECIPE.read_text().replace('version: "1.4.1.0"', 'version: "1.4.1.7"'))
            manifest = root / 'pixi.toml'
            manifest.write_text((config.ROOT / 'pixi.toml').read_text().replace('version = "1.4.1.0"', 'version = "1.4.1.7"'))
            version_file = root / 'cvc5-version.toml'
            with (patch.object(config, 'ROOT', root), patch.object(config, 'pinned', return_value=current),
                  patch.object(config, 'VERSION_FILE', version_file), patch.object(bump, 'RECIPE', recipe),
                  patch.object(bump.sys, 'argv', ['bump', '--refresh-binaries']),
                  patch.object(bump, '_api', return_value=release('1.4.1')),
                  patch.object(bump, '_commit', return_value=current['commit']) as commit,
                  patch.object(bump, '_sha256') as download, contextlib.redirect_stdout(io.StringIO())):
                bump.main()
                self.assertEqual(tomllib.loads(manifest.read_text())['workspace']['version'], '1.4.1.7')
                self.assertIn('version: "1.4.1.7"', recipe.read_text())
                download.assert_not_called()
                before = version_file.read_bytes()
                commit.return_value = 'moved'
                with self.assertRaisesRegex(RuntimeError, 'tag moved'):
                    bump.main()
                self.assertEqual(version_file.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
