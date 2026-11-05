"""Verify an extracted release or ZIP against its committed-source hash manifest."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024


def safe_name(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('Invalid release path')
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {'', '.', '..'} for part in name.split('/')):
        raise ValueError('Invalid release path')
    return name


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate manifest key')
        result[key] = value
    return result


def verify_release(path):
    path = Path(path).resolve(strict=True)
    archive = None
    try:
        if path.is_dir():
            names = []
            for file in path.rglob('*'):
                if file.is_symlink() or getattr(file, 'is_junction', lambda: False)():
                    raise ValueError('Linked release file is unsupported')
                if file.is_file():
                    if file.stat().st_size > MAX_FILE_BYTES:
                        raise ValueError('Release file exceeds verification limit')
                    names.append(file.relative_to(path).as_posix())
            read = lambda name: (path / name).read_bytes()
            sizes = sum((path / name).stat().st_size for name in names)
        else:
            archive = zipfile.ZipFile(path)
            for entry in archive.infolist():
                safe_name(entry.filename.rstrip('/'))
                mode = stat.S_IFMT(entry.external_attr >> 16)
                if mode not in {0, stat.S_IFREG, stat.S_IFDIR}:
                    raise ValueError('Linked or special release entry is unsupported')
            entries = [entry for entry in archive.infolist() if not entry.is_dir()]
            original_names = [safe_name(entry.filename) for entry in entries]
            if len(set(original_names)) != len(original_names):
                raise ValueError('Duplicate release entry')
            roots = {name.split('/')[0] for name in original_names}
            if len(roots) != 1 or any('/' not in name for name in original_names):
                raise ValueError('Release must have one top-level folder')
            prefix = next(iter(roots)) + '/'
            if any(entry.file_size > MAX_FILE_BYTES for entry in entries):
                raise ValueError('Release file exceeds verification limit')
            sizes = sum(entry.file_size for entry in entries)
            names = [name[len(prefix):] for name in original_names]
            read = lambda name: archive.read(prefix + name)
        if sizes > MAX_TOTAL_BYTES:
            raise ValueError('Release exceeds verification limit')
        for name in names:
            safe_name(name)
        manifest = json.loads(read('RELEASE-MANIFEST.json').decode('utf-8'), object_pairs_hook=strict_object)
        if not isinstance(manifest, dict) or not isinstance(manifest.get('source_commit'), str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', manifest['source_commit']):
            raise ValueError('Invalid source commit')
        if not isinstance(manifest.get('version'), str) or not manifest['version']:
            raise ValueError('Invalid release version')
        files = manifest.get('files')
        if not isinstance(files, dict) or set(names) != set(files) | {'RELEASE-MANIFEST.json'}:
            raise ValueError('Release files differ from manifest')
        for name, expected in files.items():
            safe_name(name)
            if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
                raise ValueError('Invalid file checksum')
            if hashlib.sha256(read(name)).hexdigest() != expected:
                raise ValueError('Release file checksum mismatch: ' + name)
        return {'source_commit': manifest['source_commit'], 'version': manifest['version'], 'verified_files': len(files)}
    finally:
        if archive is not None:
            archive.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path, help='Downloaded source/skill ZIP or clean extracted top-level folder')
    args = parser.parse_args()
    try:
        print(json.dumps(verify_release(args.path)))
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        parser.exit(2, 'Release verification failed: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
