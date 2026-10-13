"""Dependency provenance follows the installed package rather than a source archive."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bindgen import config


class InstalledDependencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.prefix = Path(temporary.name)
        self.package = self.prefix / 'lib/mojo'
        self.package.mkdir(parents=True)
        self.artifact = self.package / 'apn_mojo.mojoc'
        self.artifact.write_bytes(b'installed package')
        metadata = self.prefix / 'conda-meta'
        metadata.mkdir()
        self.metadata = metadata / 'apn_mojo-test-build.json'
        self.record = dict(name='apn_mojo', version='test', build='build',
                           channel='https://example.invalid/channel/',
                           url='https://example.invalid/channel/package.conda',
                           sha256='archive-checksum', files=['lib/mojo/apn_mojo.mojoc'])
        self.metadata.write_text(json.dumps(self.record))
        prefix = patch.object(config, 'ENV_PREFIX', self.prefix)
        package = patch.object(config, 'APN_PACKAGE_DIR', self.package)
        prefix.start()
        package.start()
        self.addCleanup(prefix.stop)
        self.addCleanup(package.stop)

    def test_records_the_installed_build_and_archive_identity(self):
        actual = config.apn_installed()
        self.assertEqual(actual, {k: v for k, v in self.record.items() if k != 'files'})

    def test_missing_artifact_does_not_accept_metadata_alone(self):
        self.artifact.unlink()
        with self.assertRaisesRegex(RuntimeError, 'pixi install --locked'):
            config.apn_installed()

    def test_missing_or_ambiguous_metadata_fails(self):
        self.metadata.unlink()
        with self.assertRaises(RuntimeError):
            config.apn_installed()
        self.metadata.write_text(json.dumps(self.record))
        self.metadata.with_name('apn_mojo-other-build.json').write_text(json.dumps(self.record))
        with self.assertRaises(RuntimeError):
            config.apn_installed()


if __name__ == '__main__':
    unittest.main()
