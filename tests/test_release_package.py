import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], capture_output=True, check=True).stdout


class ReleaseTests(unittest.TestCase):
    def packager(self):
        scripts = Path(__file__).resolve().parents[1] / 'scripts'
        sys.path.insert(0, str(scripts))
        spec = importlib.util.spec_from_file_location('release_packager_test', scripts / 'package_release.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def repository(self, root):
        repo = root / 'repo'
        repo.mkdir()
        git(repo, 'init', '-q')
        git(repo, 'config', 'user.name', 'Synthetic test')
        git(repo, 'config', 'user.email', 'synthetic@example.invalid')
        files = {'README.md': '# Synthetic\n', 'AGENTS.md': 'Synthetic instructions\n', 'config.example.json': '{}\n', 'docs/setup.md': 'Synthetic setup\n', 'tests/test_synthetic.py': '# Synthetic test\n', 'pyproject.toml': '[project]\nversion = "0.3.0"\n', 'skills/creality-k1-print/SKILL.md': '---\nname: creality-k1-print\n---\n'}
        for name, text in files.items():
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode())
        git(repo, 'add', '.')
        git(repo, '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Synthetic baseline')
        return repo

    def test_dirty_and_untracked_sources_refuse_packaging(self):
        module = self.packager()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.repository(root)
            with patch.object(module, 'audit', return_value=([], [])):
                (repo / 'README.md').write_text('changed')
                with self.assertRaises(ValueError):
                    module.package_release(repo, root / 'out')
                git(repo, 'restore', 'README.md')
                (repo / 'untracked.md').write_text('new eligible file')
                with self.assertRaises(ValueError):
                    module.package_release(repo, root / 'out')
                git(repo, 'add', 'untracked.md')
                with self.assertRaises(ValueError):
                    module.package_release(repo, root / 'out')
            self.assertFalse((root / 'out').exists())

    def test_clean_archive_records_exact_commit_and_hashes(self):
        module = self.packager()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.repository(root)
            with patch.object(module, 'audit', return_value=([], [])):
                archive, digest = module.package_release(repo, root / 'out')
            self.assertEqual(archive.name, 'creality-k1-print-skill-v0.3.0.zip')
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), digest)
            with zipfile.ZipFile(archive) as bundle:
                prefix = 'creality-k1-print-skill-v0.3.0/'
                manifest = json.loads(bundle.read(prefix + 'RELEASE-MANIFEST.json'))
                self.assertEqual(manifest['source_commit'], git(repo, 'rev-parse', 'HEAD').decode().strip())
                self.assertEqual(manifest['version'], '0.3.0')
                self.assertIn('AGENTS.md', manifest['files'])
                self.assertIn('config.example.json', manifest['files'])
                self.assertIn('docs/setup.md', manifest['files'])
                self.assertIn('tests/test_synthetic.py', manifest['files'])
                for name, expected in manifest['files'].items():
                    content = bundle.read(prefix + name)
                    self.assertEqual(hashlib.sha256(content).hexdigest(), expected)
                    self.assertEqual(content, git(repo, 'show', 'HEAD:' + name))
            self.assertEqual((root / 'out/SHA256SUMS').read_text(), digest + '  ' + archive.name + '\n')
            self.assertNotIn('timestamp', manifest)

    def test_same_committed_source_produces_identical_archives(self):
        module = self.packager()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.repository(root)
            with patch.object(module, 'audit', return_value=([], [])):
                first, digest_a = module.package_release(repo, root / 'out-a')
                second, digest_b = module.package_release(repo, root / 'out-b')
            self.assertEqual(digest_a, digest_b)
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == '__main__':
    unittest.main()
