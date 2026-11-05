import importlib.util
from pathlib import Path
import tempfile
import unittest
import contextlib
import io
import subprocess
from unittest.mock import patch


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

    def recognized(self, root):
        target = root / 'recognized'
        (target / 'scripts').mkdir(parents=True)
        (target / 'SKILL.md').write_text('---\nname: creality-k1-print\ndescription: Test\n---\nLocal custom instructions\n')
        (target / 'requirements.txt').write_text('requests>=2.32,<3\n')
        (target / 'scripts/k1.py').write_text('print("local custom launcher")\n')
        return target

    def test_repair_only_rebuilds_runtime_preserving_custom_files(self):
        module = self.installer()
        with tempfile.TemporaryDirectory() as temp:
            target = self.recognized(Path(temp))
            before = {path: path.read_bytes() for path in target.rglob('*') if path.is_file()}
            with patch.object(module.venv, 'EnvBuilder') as builder, patch.object(module.subprocess, 'run') as run:
                interpreter = module.repair_runtime(target)
            self.assertEqual(before, {path: path.read_bytes() for path in before})
            builder.return_value.create.assert_called_once_with(target / '.venv')
            self.assertEqual(run.call_args.args[0], [str(interpreter), '-m', 'pip', 'install', '-r', str(target / 'requirements.txt')])
            self.assertTrue(run.call_args.kwargs['check'])

    def test_unknown_installation_cannot_be_repaired(self):
        module = self.installer()
        with tempfile.TemporaryDirectory() as temp:
            target = self.recognized(Path(temp))
            (target / 'SKILL.md').write_text('---\nname: unrelated\n---\n')
            with patch.object(module.venv, 'EnvBuilder') as builder, self.assertRaises(ValueError):
                module.repair_runtime(target)
            builder.assert_not_called()

    def test_runtime_symlink_is_refused(self):
        module = self.installer()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = self.recognized(root)
            elsewhere = root / 'elsewhere'
            elsewhere.mkdir()
            try:
                (target / '.venv').symlink_to(elsewhere, target_is_directory=True)
            except OSError:
                self.skipTest('Host does not permit directory symlinks')
            with patch.object(module.venv, 'EnvBuilder') as builder, self.assertRaises(ValueError):
                module.repair_runtime(target)
            builder.assert_not_called()

    def test_runtime_link_guard_without_platform_symlink_permission(self):
        module = self.installer()
        with tempfile.TemporaryDirectory() as temp:
            target = self.recognized(Path(temp))
            with patch.object(module, '_linked', side_effect=lambda path: path.name == '.venv'), patch.object(module.venv, 'EnvBuilder') as builder:
                with self.assertRaises(ValueError):
                    module.repair_runtime(target)
            builder.assert_not_called()

    def test_failed_repair_preserves_all_skill_files(self):
        module = self.installer()
        with tempfile.TemporaryDirectory() as temp:
            target = self.recognized(Path(temp))
            before = {path: path.read_bytes() for path in target.rglob('*') if path.is_file()}
            with patch.object(module.venv, 'EnvBuilder'), patch.object(module.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['pip'])):
                with self.assertRaises(subprocess.CalledProcessError):
                    module.repair_runtime(target)
            self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_generated_metadata_build_dist_excluded(self):
        module = self.installer()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.source(root)
            for name in ('generated.egg-info', 'build', 'dist'):
                (source / name).mkdir()
                (source / name / 'private.txt').write_text('generated fixture')
            module.install_skill(source, root / 'installed')
            for name in ('generated.egg-info', 'build', 'dist'):
                self.assertFalse((root / 'installed' / name).exists())

    def test_initial_dependency_failure_preserves_skill_and_suggests_repair(self):
        module = self.installer()
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'target'
            def install(_source, destination):
                created = self.recognized(Path(temp))
                created.rename(destination)
                return destination
            with patch.object(module, 'install_skill', side_effect=install), patch.object(module.venv, 'EnvBuilder'), patch.object(module.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['pip'])), contextlib.redirect_stderr(io.StringIO()) as error, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(['--target', str(target), '--with-runtime']), 2)
            self.assertTrue((target / 'SKILL.md').exists())
            self.assertIn('--repair-runtime', error.getvalue())
