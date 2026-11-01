"""Local non-secret configuration. Credentials stay in environment variables."""
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

DEFAULT_CONFIG = Path.home() / '.config/k1-print/config.json'
FIELDS = {'printer_url', 'expected_hostname', 'orca_path', 'orca_resources', 'api_key_env'}


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
