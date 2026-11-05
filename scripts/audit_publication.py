"""Check repository files, local documentation links and common private-data patterns."""
import argparse
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {'.stl', '.3mf', '.gcode', '.gco', '.exe', '.dll', '.pyd', '.db', '.sqlite', '.log', '.pyc', '.zip', '.jpg', '.jpeg', '.webp'}
PRIVATE = [
    re.compile(r'[A-Za-z]:[\\/]+Users[\\/]+[A-Za-z0-9_.-]+', re.I),
    re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b'),
    re.compile(r'\bgithub_pat_[A-Za-z0-9_]{20,}\b'),
    re.compile(r'\b[A-Za-z0-9_.+-]+@(?:gmail|hotmail|outlook)\.com\b', re.I),
    re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
]


def repository_files(root):
    result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], check=True, capture_output=True)
    return sorted({root / name for name in result.stdout.decode('utf-8').split('\0') if name})


def audit(root=ROOT):
    root = Path(root).resolve()
    files = repository_files(root)
    errors = []
    for path in files:
        name = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.is_file():
            errors.append(f'{name}: only regular files may be published')
            continue
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or any(part in {'.venv', '__pycache__', 'jobs', 'outputs', 'snapshots', 'captures', '.validation'} for part in path.relative_to(root).parts):
            errors.append(f'{name}: private/generated/binary artifact is not allowed')
        if path.suffix.lower() == '.png' and name != 'docs/assets/toolpath-demo.png':
            errors.append(f'{name}: unreviewed image; camera captures must stay local')
        if path.name.startswith('.env') or path.name.endswith('.local.json'):
            errors.append(f'{name}: local configuration is not distributable')
        if path.suffix.lower() not in {'.md', '.py', '.json', '.toml', '.txt', '.yaml', '.yml', '.svg', '.gitignore'} and path.name not in {'LICENSE', '.gitignore'}:
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            errors.append(f'{name}: expected UTF-8 text')
            continue
        if any(pattern.search(text) for pattern in PRIVATE):
            errors.append(f'{name}: possible private path, credential or personal email')
        if path.suffix.lower() == '.md':
            targets = re.findall(r'\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text)
            targets += re.findall(r'<img\b[^>]*\bsrc="([^"]+)"', text, re.I)
            for target in targets:
                target = target.strip('<>')
                parsed = urlsplit(target)
                if parsed.scheme or target.startswith('#'):
                    continue
                local = (path.parent / unquote(parsed.path)).resolve()
                if not local.is_relative_to(root) or not local.exists():
                    errors.append(f'{name}: missing/outside local link {target}')
    for required in ['LICENSE', 'README.md', 'README.en.md', 'AGENTS.md', 'CLAUDE.md', 'CHANGELOG.md', 'docs/AI_GUIDE.md', 'docs/PROJECT_STATE.md', 'docs/CONTINUITY.md', 'docs/RELEASING.md', 'pyproject.toml', 'skills/creality-k1-print/SKILL.md', 'skills/creality-k1-print/references/physical-quality.md', 'skills/creality-k1-print/agents/openai.yaml', 'docs/assets/banner.svg', 'docs/assets/toolpath-demo.png']:
        if not (root / required).is_file():
            errors.append(f'Required file missing: {required}')
    skill_license = root / 'skills/creality-k1-print/LICENSE'
    if skill_license.exists() and skill_license.read_bytes() != (root / 'LICENSE').read_bytes():
        errors.append('The self-contained skill license differs from the root license')
    return files, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    files, errors = audit()
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Publication audit passed: {len(files)} files; no missing local links or matched private-data patterns.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
