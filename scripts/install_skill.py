"""Copy the self-contained skill without overwriting an existing installation."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import venv

IGNORED = {'.git', '.venv', '__pycache__', 'jobs', 'outputs', 'snapshots', 'captures', '.validation', 'build', 'dist'}
SUFFIXES = {'.md', '.py', '.yaml', '.yml', '.txt', '.svg', '.png'}


def install_skill(source, destination):
    source, destination = Path(source).resolve(), Path(destination).expanduser().resolve()
    if not (source / 'SKILL.md').is_file():
        raise ValueError('Source must contain SKILL.md')
    candidates = []
    for path in source.rglob('*'):
        relative = path.relative_to(source)
        if any(part in IGNORED or part.startswith('.') or part.endswith('.egg-info') for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError('Symlinks are not copied into the skill installation')
        if path.is_file() and (path.suffix.lower() in SUFFIXES or path.name == 'LICENSE'):
            candidates.append((path, relative))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(exist_ok=False)
    for path, relative in candidates:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return destination


def _linked(path):
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def repair_runtime(destination):
    """Complete/rebuild only the runtime of a recognized existing skill.

    Skill instructions, custom references and helper code are never recopied.
    Existing runtime contents are retained for pip to reconcile, rather than
    recursively deleting a user-provided path.
    """
    target = Path(destination).expanduser().absolute()
    if _linked(target) or not target.is_dir():
        raise ValueError('Runtime repair requires an existing regular skill directory')
    target = target.resolve(strict=True)
    for relative in ('SKILL.md', 'requirements.txt', 'scripts/k1.py'):
        filename = target / relative
        if not filename.is_file() or not filename.resolve().is_relative_to(target):
            raise ValueError('Runtime repair requires a recognized Creality K1 skill installation')
    text = (target / 'SKILL.md').read_text(encoding='utf-8-sig')
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)', text, re.S)
    if match is None:
        raise ValueError('Runtime repair requires Creality K1 skill frontmatter')
    names = re.findall(r'^name:\s*(.*?)\s*$', match[1], re.M)
    if len(names) != 1 or names[0].strip('\'"') != 'creality-k1-print':
        raise ValueError('Runtime repair requires the creality-k1-print skill identity')
    runtime = target / '.venv'
    if _linked(runtime) or runtime.exists() and (not runtime.is_dir() or not runtime.resolve().is_relative_to(target)):
        raise ValueError('Runtime must be a local directory, never a linked path')
    venv.EnvBuilder(with_pip=True).create(runtime)
    interpreter = runtime / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    subprocess.run([str(interpreter), '-m', 'pip', 'install', '-r', str(target / 'requirements.txt')], check=True)
    return interpreter


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, default=Path.home() / '.agents/skills/creality-k1-print')
    runtime = parser.add_mutually_exclusive_group()
    runtime.add_argument('--with-runtime', action='store_true', help='Create an isolated Python environment and install the declared dependencies')
    runtime.add_argument('--repair-runtime', action='store_true', help='Complete/rebuild only .venv for a recognized existing skill; preserve custom instructions and scripts')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        if args.repair_runtime:
            interpreter = repair_runtime(args.target)
            print(f'Runtime repaired: {interpreter}. Skill files were preserved.')
            return 0
        target = install_skill(root / 'skills/creality-k1-print', args.target)
    except (FileExistsError, ValueError) as exc:
        print(f'Not installed/repaired: {exc}. Existing skill files are never replaced.', file=sys.stderr)
        return 2
    except (OSError, subprocess.CalledProcessError):
        print('Runtime incomplete; skill files were preserved. Retry with --repair-runtime --target PATH after resolving the dependency/environment failure.', file=sys.stderr)
        return 2
    print(f'Skill installed: {target}')
    if args.with_runtime:
        try:
            interpreter = repair_runtime(target)
        except (OSError, ValueError, subprocess.CalledProcessError):
            print('Runtime incomplete; installed skill files were preserved. Retry with --repair-runtime --target PATH after resolving the dependency/environment failure.', file=sys.stderr)
            return 2
        print(f'Runtime: {interpreter}')
    print('Invoke $creality-k1-print in a compatible agent. Configure the printer and OrcaSlicer locally; installation never starts a print.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
