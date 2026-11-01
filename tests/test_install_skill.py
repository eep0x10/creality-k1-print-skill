import importlib.util
from pathlib import Path
import tempfile
import unittest


class InstallSkillTests(unittest.TestCase):
    def installer(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/install_skill.py'
        self.assertTrue(path.exists(), 'The skill installer has not been implemented')
        spec = importlib.util.spec_from_file_location('skill_installer_test_target', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def source(self, root):
        source = root / 'source'
        source.mkdir()
        (source / 'SKILL.md').write_text('---\nname: test-skill\ndescription: Test\n---\nTest', encoding='utf-8')
        (source / 'scripts').mkdir()
        (source / 'scripts/helper.py').write_text('print("ready")', encoding='utf-8')
        return source

    def test_installs_skill_without_bytecode_or_local_secrets(self):
        module = self.installer()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.source(root)
            (source / '.env').write_text('private fixture', encoding='utf-8')
            (source / '__pycache__').mkdir()
            (source / '__pycache__/helper.pyc').write_bytes(b'cache')
            (source / 'snapshots').mkdir()
            (source / 'snapshots/private-camera.png').write_bytes(b'private image fixture')
            destination = root / 'installed'
            module.install_skill(source, destination)
            self.assertTrue((destination / 'SKILL.md').exists())
            self.assertTrue((destination / 'scripts/helper.py').exists())
            self.assertFalse((destination / '.env').exists())
            self.assertFalse((destination / '__pycache__').exists())
            self.assertFalse((destination / 'snapshots').exists())

    def test_existing_skill_is_preserved(self):
        module = self.installer()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.source(root)
            destination = root / 'installed'
            destination.mkdir()
            (destination / 'keep.md').write_text('keep', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                module.install_skill(source, destination)
            self.assertEqual((destination / 'keep.md').read_text(), 'keep')

    def test_missing_skill_is_not_installed(self):
        module = self.installer()
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'empty'
            source.mkdir()
            with self.assertRaises(ValueError):
                module.install_skill(source, Path(temp) / 'installed')
            self.assertFalse((Path(temp) / 'installed').exists())
