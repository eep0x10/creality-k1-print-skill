"""Local non-secret configuration. Credentials stay in environment variables."""
import json
import os
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlsplit

DEFAULT_CONFIG = Path.home() / '.config/k1-print/config.json'
FIELDS = {'printer_url', 'expected_hostname', 'orca_path', 'orca_resources', 'api_key_env', 'camera_url', 'camera_base_url'}
SECRET_QUERY_KEYS = {'token', 'accesstoken', 'apikey', 'key', 'auth', 'authorization', 'password', 'pass', 'passwd', 'secret', 'session', 'sessionid', 'sid', 'signature', 'xapikey', 'xamzcredential', 'xamzsignature', 'xamzsecuritytoken'}


def validate_camera_url(value, printer_url, origin_only=False):
    """Accept same-host HTTP URLs without URL credentials or secret queries."""
    if not isinstance(value, str) or not value or any(character.isspace() or ord(character) < 32 for character in value) or '\\' in value or '#' in value:
        raise ValueError('Invalid camera URL configuration')
    try:
        parsed, printer = urlsplit(value), urlsplit(printer_url)
        parsed.port
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.hostname != printer.hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError('Camera URL must use the configured printer hostname')
        if origin_only and (parsed.path not in {'', '/'} or parsed.query):
            raise ValueError('Camera base URL must be an HTTP origin')
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
            normalized = re.sub(r'[^a-z0-9]', '', key.lower())
            if normalized in SECRET_QUERY_KEYS:
                raise ValueError('Camera URL secret query parameters are unsupported')
    except (ValueError, UnicodeError):
        raise ValueError('Invalid or unsupported camera URL configuration') from None
    return value.rstrip('/') if origin_only else value


def validate_config(data):
    if not isinstance(data, dict) or set(data) - FIELDS:
        raise ValueError('Unsupported configuration keys; store secrets in environment variables')
    result = dict(data)
    url = result.get('printer_url', '')
    if not isinstance(url, str):
        raise ValueError('printer_url must be an HTTP origin')
    parsed = urlsplit(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment:
        raise ValueError('printer_url must be an HTTP origin without credentials, path or query')
    try:
        parsed.port
    except ValueError:
        raise ValueError('Invalid printer port') from None
    result['printer_url'] = url.rstrip('/')
    name = result.get('expected_hostname')
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', name):
        raise ValueError('An exact expected_hostname is required')
    for key in ('orca_path', 'orca_resources'):
        if key in result and (not isinstance(result[key], str) or not result[key].strip()):
            raise ValueError('Tool paths must be nonempty strings')
    env = result.get('api_key_env')
    if env is not None and (not isinstance(env, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', env)):
        raise ValueError('api_key_env must name an environment variable')
    for key in ('camera_url', 'camera_base_url'):
        if key in result:
            result[key] = validate_camera_url(result[key], result['printer_url'], origin_only=key == 'camera_base_url')
    return result


def load_config(path=None):
    return validate_config(json.loads(Path(path or DEFAULT_CONFIG).expanduser().read_text(encoding='utf-8')))


def save_config(data, path=None):
    data = validate_config(data)
    filename = Path(path or DEFAULT_CONFIG).expanduser()
    filename.parent.mkdir(parents=True, exist_ok=True)
    # Refuse accidental replacement of an existing local setup.
    with filename.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')
    os.chmod(filename, 0o600)
    return filename
