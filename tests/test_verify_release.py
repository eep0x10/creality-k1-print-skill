import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


class VerifyReleaseTests(unittest.TestCase):
    def setUp(self):
        file = Path(__file__).resolve().parents[1] / 'scripts/verify_release.py'
        spec = importlib.util.spec_from_file_location('release_verifier', file)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {'source_commit': 'a' * 40, 'version': '0.3.0', 'files': {'README.md': hashlib.sha256(b'original').hexdigest()}}

    def bundle(self, entries=None):
        path = self.root / 'release.zip'
        with zipfile.ZipFile(path, 'w') as bundle:
            for name, data in (entries or {'release/README.md': b'original', 'release/RELEASE-MANIFEST.json': json.dumps(self.manifest).encode()}).items():
                bundle.writestr(name, data)
        return path

    def test_verifies_zip_and_extracted_directory_without_git(self):
        path = self.bundle()
        result = self.module.verify_release(path)
        self.assertEqual(result['verified_files'], 1)
        with zipfile.ZipFile(path) as bundle:
            bundle.extractall(self.root / 'extracted')
        self.assertEqual(self.module.verify_release(self.root / 'extracted/release'), result)

    def test_rejects_tampered_or_extra_payload(self):
        for files in [{'release/README.md': b'changed'}, {'release/README.md': b'original', 'release/extra.py': b'payload'}]:
            files['release/RELEASE-MANIFEST.json'] = json.dumps(self.manifest).encode()
            with self.subTest(files=list(files)), self.assertRaises(ValueError):
                self.module.verify_release(self.bundle(files))

    def test_malformed_commit_is_a_validation_error(self):
        self.manifest['source_commit'] = ['unexpected']
        with self.assertRaises(ValueError):
            self.module.verify_release(self.bundle())

    def test_rejects_unsafe_archive_path_without_extraction(self):
        path = self.bundle({'release/../outside.py': b'payload'})
        with self.assertRaises(ValueError):
            self.module.verify_release(path)
        self.assertFalse((self.root / 'outside.py').exists())

    def test_rejects_unsafe_directory_entries_and_archive_symlinks(self):
        for name, mode in [('release/../outside/', 0o40755), ('release/link', 0o120777)]:
            with self.subTest(name=name):
                path = self.root / 'special.zip'
                with zipfile.ZipFile(path, 'w') as bundle:
                    info = zipfile.ZipInfo(name)
                    info.external_attr = mode << 16
                    bundle.writestr(info, b'outside')
                with self.assertRaises(ValueError):
                    self.module.verify_release(path)
