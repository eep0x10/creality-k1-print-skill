"""Native Moonraker transport with one-shot approval-bound mutations."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

import requests

from .config import validate_config
from .validation import require, validate_job

IDLE_STATES = {'standby', 'complete', 'cancelled'}


def create_session(config):
    session = requests.Session()
    session.trust_env = False
    session.mount('http://', requests.adapters.HTTPAdapter(max_retries=0))
    session.mount('https://', requests.adapters.HTTPAdapter(max_retries=0))
    variable = config.get('api_key_env')
    if variable:
        value = os.environ.get(variable)
        require(bool(value), 'Configured API key environment variable is missing')
        session.headers['X-Api-Key'] = value
    return session


def get_result(session, config, endpoint):
    response = session.get(config['printer_url'] + endpoint, timeout=10, allow_redirects=False)
    response.raise_for_status()
    payload = response.json()
    require(isinstance(payload, dict) and 'error' not in payload and 'result' in payload, 'Unexpected Moonraker GET response')
    return payload['result']


def printer_status(config, session=None):
    config = validate_config(config)
    own = session is None
    http = session or create_session(config)
    try:
        info = get_result(http, config, '/printer/info')
        require(isinstance(info, dict) and info.get('hostname') == config['expected_hostname'], 'Printer identity mismatch')
        result = get_result(http, config, '/printer/objects/query?print_stats')
        stats = result['status']['print_stats']
        # Only explicitly selected fields may leave the HTTP boundary.
        return {'hostname': config['expected_hostname'], 'firmware_state': info.get('state'), 'print_state': stats.get('state')}
    finally:
        if own:
            http.close()


def check_ready(session, config):
    state = printer_status(config, session)
    require(state['firmware_state'] == 'ready' and state['print_state'] in IDLE_STATES, 'Printer is busy, paused or unavailable')


def check_server_compatibility(session, config):
    """Require the release that implements upload checksum verification.

    This is a compatibility check against a trusted Moonraker installation,
    not an attestation of arbitrary forks that report the same version.
    """
    info = get_result(session, config, '/server/info')
    require(isinstance(info, dict), 'Moonraker server information missing')
    version = info.get('moonraker_version')
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-\d+-g[0-9A-Za-z]+(?:-dirty)?)?', version) if isinstance(version, str) else None
    require(match is not None and tuple(map(int, match.groups())) >= (0, 10, 0), 'Moonraker 0.10.0 or newer with upload checksum support is required')
    api = info.get('api_version')
    require(isinstance(api, list) and len(api) == 3 and all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in api) and api[0] == 1, 'Moonraker API major version 1 is required')


def check_maker_macros(session, config):
    values = get_result(session, config, '/printer/objects/query?configfile')['status']['configfile']['config']
    values = {key.upper(): value for key, value in values.items()}
    start = values.get('GCODE_MACRO START_PRINT', {}).get('gcode', '')
    end = values.get('GCODE_MACRO END_PRINT', {}).get('gcode', '')
    require(isinstance(start, str) and isinstance(end, str) and bool(start) and bool(end), 'Maker START_PRINT/END_PRINT macros missing')
    commands = []
    for line in start.splitlines():
        code = line.split(';', 1)[0].split('#', 1)[0].strip().upper()
        if code:
            commands.append(code.split()[0])
    require('CX_ROUGH_G28' in commands and 'ACCURATE_G28' in commands, 'Maker START_PRINT homing routine differs from supported K1')


def send_job(manifest_path, config, approved_sha256=None, approval_ref=None, dry_run=False, session=None):
    """Send immutable validated bytes once; never retry upload or start.

    A real-attempt receipt is reserved atomically before the first mutation.
    After an uncertain response, inspection must happen before a new job is
    deliberately prepared. Deleting a receipt is not an automatic recovery.
    """
    config = validate_config(config)
    manifest_path = Path(manifest_path).resolve(strict=True)
    root = manifest_path.parent
    receipt_path = root / ('dry-run-receipt.json' if dry_run else 'receipt.json')
    if not dry_run:
        require(not receipt_path.exists(), 'A real send receipt already exists; inspect printer and receipt before any recovery')
        require(isinstance(approved_sha256, str) and re.fullmatch(r'[a-fA-F0-9]{64}', approved_sha256) is not None, 'Explicit approved G-code SHA256 required')
        require(isinstance(approval_ref, str) and 0 < len(approval_ref.strip()) <= 300, 'Explicit preview approval reference required')
    manifest, content = validate_job(manifest_path)
    sha = manifest['gcode_sha256']
    if not dry_run:
        require(approved_sha256.lower() == sha, 'Approval SHA256 differs from prepared G-code')
    receipt = {'schema_version': 1, 'utc': datetime.now(timezone.utc).isoformat(), 'gcode_sha256': sha, 'dry_run': bool(dry_run), 'approval_recorded': not dry_run, 'uploaded': False, 'start_requested': False, 'outcome': 'preflight'}
    if not dry_run:
        receipt['approval_ref_sha256'] = hashlib.sha256(approval_ref.encode()).hexdigest()
    own = session is None
    http = session or create_session(config)
    reserved = False

    def persist():
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')

    try:
        check_server_compatibility(http, config)
        check_ready(http, config)
        check_maker_macros(http, config)
        if dry_run:
            receipt['outcome'] = 'dry_run'
            persist()
            return receipt
        # O_EXCL protects simultaneous invocations as well as normal repeats.
        with receipt_path.open('x', encoding='utf-8') as stream:
            json.dump(receipt, stream, indent=2)
        reserved = True
        filename = f'job-{sha}.gcode'
        receipt['outcome'] = 'upload_unconfirmed'
        persist()
        response = http.post(config['printer_url'] + '/server/files/upload', data={'root': 'gcodes', 'print': 'false', 'checksum': sha}, files={'file': (filename, content, 'application/octet-stream')}, timeout=120, allow_redirects=False)
        response.raise_for_status()
        payload = response.json()
        require(isinstance(payload, dict) and 'error' not in payload, 'Unexpected upload response; no start requested')
        uploaded = payload.get('result', payload)
        require(isinstance(uploaded, dict) and isinstance(uploaded.get('item'), dict), 'Missing uploaded item')
        require(uploaded['item'].get('root') == 'gcodes' and uploaded['item'].get('path') == filename and uploaded.get('print_started') is False and uploaded.get('print_queued') is False, 'Upload response does not confirm an idle unqueued file')
        receipt['uploaded'], receipt['outcome'] = True, 'uploaded_not_started'
        persist()
        check_ready(http, config)
        check_maker_macros(http, config)
        receipt['start_requested'], receipt['outcome'] = True, 'start_unconfirmed'
        persist()
        try:
            response = http.post(config['printer_url'] + '/printer/print/start', json={'filename': filename}, timeout=30, allow_redirects=False)
            response.raise_for_status()
            require(response.json().get('result') == 'ok', 'Start acknowledgment uncertain; do not resend')
        except (requests.RequestException, ValueError):
            pass
        try:
            stats = get_result(http, config, '/printer/objects/query?print_stats')['status']['print_stats']
            receipt['observed_state'] = stats.get('state') if stats.get('state') in IDLE_STATES | {'printing', 'paused', 'error'} else 'unknown'
            if stats.get('state') == 'printing' and stats.get('filename') == filename:
                receipt['outcome'] = 'printing_confirmed'
        except (requests.RequestException, ValueError, KeyError, TypeError):
            receipt['observed_state'] = 'unknown'
        return receipt
    finally:
        if reserved:
            persist()
        if own:
            http.close()
