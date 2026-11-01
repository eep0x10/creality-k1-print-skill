"""Copy the self-contained skill without overwriting an existing installation."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import venv

IGNORED = {'.git', '.venv', '__pycache__', 'jobs', 'outputs', 'snapshots', 'captures', '.validation'}
SUFFIXES = {'.md', '.py', '.yaml', '.yml', '.txt', '.svg', '.png'}


def install_skill(source, destination):
    source, destination = Path(source).resolve(), Path(destination).expanduser().resolve()
    if not (source / 'SKILL.md').is_file():
        raise ValueError('Source must contain SKILL.md')
    candidates = []
    for path in source.rglob('*'):
        relative = path.relative_to(source)
        if any(part in IGNORED or part.startswith('.') for part in relative.parts):
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, default=Path.home() / '.agents/skills/creality-k1-print')
    parser.add_argument('--with-runtime', action='store_true', help='Create an isolated Python environment and install the declared dependencies')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        target = install_skill(root / 'skills/creality-k1-print', args.target)
    except (FileExistsError, ValueError) as exc:
        parser.exit(2, f'Not installed: {exc}. Existing installations are never replaced.\n')
    print(f'Skill installed: {target}')
    if args.with_runtime:
        venv.EnvBuilder(with_pip=True).create(target / '.venv')
        interpreter = target / '.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
        subprocess.run([str(interpreter), '-m', 'pip', 'install', '-r', str(target / 'requirements.txt')], check=True)
        print(f'Runtime: {interpreter}')
    print('Invoke $creality-k1-print in a compatible agent. Configure the printer and OrcaSlicer locally; installation never starts a print.')


if __name__ == '__main__':
    main()
