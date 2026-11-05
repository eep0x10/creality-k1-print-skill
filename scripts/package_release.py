"""Build a documented source/skill ZIP from tracked, audited repository files."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tomllib
import zipfile

from audit_publication import audit

ROOT = Path(__file__).resolve().parents[1]


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), *arguments], capture_output=True, check=True).stdout


def _clean_commit(root):
    if _git(root, 'status', '--porcelain=v1', '--untracked-files=all').strip():
        raise ValueError('Release packaging requires a clean committed tree, including untracked source files')
    commit = _git(root, 'rev-parse', '--verify', 'HEAD').decode('ascii').strip()
    if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', commit):
        raise ValueError('A committed source revision is required')
    return commit


def package_release(root, output):
    """Package audited, committed Git blobs; never the mutable working copies."""
    root = Path(root).resolve(strict=True)
    commit = _clean_commit(root)
    _, errors = audit(root)
    if errors:
        raise ValueError('\n'.join(errors))
    blobs = {}
    for entry in _git(root, 'ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
        if not entry:
            continue
        header, raw_name = entry.split(b'\t', 1)
        mode, kind, object_id = header.decode('ascii').split()
        name = raw_name.decode('utf-8')
        path = PurePosixPath(name)
        if mode not in {'100644', '100755'} or kind != 'blob' or path.is_absolute() or '..' in path.parts or '\\' in name or any(ord(character) < 32 for character in name):
            raise ValueError('Release sources must be regular files with safe relative paths')
        if name == 'RELEASE-MANIFEST.json':
            raise ValueError('RELEASE-MANIFEST.json is generated at packaging time')
        blobs[name] = _git(root, 'cat-file', 'blob', object_id)
    if not {'README.md', 'pyproject.toml', 'skills/creality-k1-print/SKILL.md'} <= blobs.keys():
        raise ValueError('Required source files must be committed before packaging')
    version = tomllib.loads(blobs['pyproject.toml'].decode('utf-8'))['project']['version']
    if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('A plain semantic release version is required')
    manifest = {'source_commit': commit, 'version': version, 'files': {name: hashlib.sha256(content).hexdigest() for name, content in sorted(blobs.items())}}
    if _clean_commit(root) != commit:
        raise ValueError('Source revision changed during release preparation')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'creality-k1-print-skill-v{version}.zip'
    if archive.exists():
        raise FileExistsError('Release archive already exists; preserve it and choose a new output directory')
    prefix = f'creality-k1-print-skill-v{version}'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        entries = dict(blobs)
        entries['RELEASE-MANIFEST.json'] = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode('utf-8')
        for name, content in sorted(entries.items()):
            info = zipfile.ZipInfo(prefix + '/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, content)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    return archive, digest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args(argv)
    try:
        archive, digest = package_release(ROOT, args.output)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(2, str(exc) + '\n')
    print(archive)
    print(digest)


if __name__ == '__main__':
    main()
