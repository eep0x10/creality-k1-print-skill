"""Build a documented source/skill ZIP from tracked, audited repository files."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tomllib
import zipfile

from audit_publication import audit

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    _, errors = audit(ROOT)
    if errors:
        raise SystemExit('\n'.join(errors))
    names = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z'], capture_output=True, check=True).stdout.decode().split('\0')
    names = sorted(name for name in names if name)
    if 'README.md' not in names or 'skills/creality-k1-print/SKILL.md' not in names:
        raise SystemExit('Stage the audited project before packaging; required tracked files are missing')
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'creality-k1-print-skill-v{version}.zip'
    if archive.exists():
        raise SystemExit('Release archive already exists; preserve it and choose a new output directory')
    prefix = f'creality-k1-print-skill-v{version}'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name in names:
            path = ROOT / name
            if not path.is_file() or path.is_symlink():
                raise SystemExit('Invalid tracked file: ' + name)
            bundle.write(path, prefix + '/' + name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    print(archive)
    print(digest)


if __name__ == '__main__':
    main()
