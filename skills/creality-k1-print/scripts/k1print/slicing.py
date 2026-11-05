"""Offline geometry -> installed OrcaSlicer -> real preview -> hash-bound manifest."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

from .model import prepare_model
from .profiles import import_profiles, prepare_profiles
from .preview import render_preview
from .validation import validate_gcode


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_job(source, jobdir, config, height_mm=None, strength=None, finish=None, orientation=False, profiles_dir=None):
    """Prepare offline only. No printer client or network operation is used.

    The job directory must be empty. Failure preserves intermediate artifacts for
    diagnosis; retry in a fresh directory. Original presets and models are read-only.
    """
    if profiles_dir is not None and (strength is not None or finish is not None):
        raise ValueError('Custom profiles cannot be combined with strength or finish priorities')
    source = Path(source).expanduser().resolve(strict=True)
    job = Path(jobdir).expanduser()
    if job.is_symlink():
        raise ValueError('Job directory must not be a symlink')
    job = job.resolve()
    if ';' in str(job) or any(ord(character) < 32 for character in str(job)):
        raise ValueError('Job path contains unsupported Orca profile separators')
    if job.exists() and (not job.is_dir() or any(job.iterdir())):
        raise FileExistsError('Use a new or empty job directory to preserve existing work')
    executable = Path(config.get('orca_path', '')).expanduser().resolve(strict=True)
    if not executable.is_file() or executable.suffix.lower() in ('.bat', '.cmd', '.ps1', '.sh'):
        raise ValueError('Configure a native Orca executable, not a shell script')
    if not isinstance(orientation, bool):
        raise ValueError('Orientation must be an explicit boolean')
    job.mkdir(parents=True, exist_ok=True)
    model_path = job / 'geometry' / 'model.stl'
    geometry = prepare_model(source, model_path, height_mm)
    (job / 'geometry.json').write_text(json.dumps(geometry, indent=2) + '\n', encoding='utf-8')
    profiles = import_profiles(profiles_dir, job / 'profiles') if profiles_dir is not None else prepare_profiles(config, job / 'profiles', strength or 'balanced', finish or 'balanced')
    output = job / 'output'
    output.mkdir()
    # .py supports explicit local executable wrappers and the offline test harness.
    # Every invocation uses argv, never a shell or command string.
    command = ([sys.executable, str(executable)] if executable.suffix.lower() == '.py' else [str(executable)])
    command += ['--debug', '3', '--datadir', str(job / 'orca-data'), '--load-settings', profiles['machine'] + ';' + profiles['process'], '--load-filaments', profiles['filament']]
    if orientation:
        command += ['--orient', '1']
    command += ['--slice', '0', '--outputdir', str(output), str(model_path)]
    completed = subprocess.run(command, shell=False, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1200, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    (job / 'orca-stdout.txt').write_text(completed.stdout, encoding='utf-8')
    (job / 'orca-stderr.txt').write_text(completed.stderr, encoding='utf-8')
    if completed.returncode:
        raise RuntimeError('OrcaSlicer failed with exit code ' + str(completed.returncode) + '; inspect local job logs')
    gcodes = sorted(output.glob('*.gcode'))
    if len(gcodes) != 1 or gcodes[0].is_symlink() or not gcodes[0].stat().st_size:
        raise ValueError('Expected exactly one nonempty local G-code artifact')
    gcode = gcodes[0]
    if gcode.stat().st_size > 512 * 1024 * 1024:
        raise ValueError('Sliced G-code exceeds 512 MiB preparation limit')
    # Fail before displaying an approvable preview, not only at send time.
    # Bind this validation to the exact bytes later scanned by the renderer.
    validated_bytes = gcode.read_bytes()
    validate_gcode(validated_bytes.decode('utf-8-sig'))
    validated_digest = hashlib.sha256(validated_bytes).hexdigest()
    del validated_bytes
    preview = job / 'preview.png'
    report = render_preview(gcode, preview)
    if report['gcode_sha256'] != validated_digest:
        raise ValueError('G-code changed between command validation and preview')
    for axis, limit in (('x',220),('y',220),('z',250)):
        values = report['bounds'][axis]
        if values[0] < -0.001 or values[1] > limit + 0.001:
            raise ValueError('Deposited toolpaths exceed original K1 ' + axis.upper() + ' limits')
    report['gcode'] = gcode.relative_to(job).as_posix()
    report['preview'] = preview.relative_to(job).as_posix()
    report_path = job / 'preview-report.json'
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    digest = _sha256(gcode)
    if digest != report['gcode_sha256']:
        raise ValueError('G-code changed during preparation')
    settings = dict(profiles['settings'])
    settings.update({'orientation': orientation, 'height_mm': height_mm, 'dimensions_mm': geometry['dimensions_mm'], 'watertight': geometry['watertight']})
    manifest = {'schema_version': 1, 'gcode': gcode.relative_to(job).as_posix(), 'gcode_sha256': digest, 'preview': preview.relative_to(job).as_posix(), 'preview_sha256': _sha256(preview), 'preview_report': report_path.relative_to(job).as_posix(), 'preview_report_sha256': _sha256(report_path), 'settings': settings, 'estimates': report['estimates'], 'state': 'awaiting_preview_approval', 'uploaded': False, 'print_started': False}
    (job / 'job.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest
