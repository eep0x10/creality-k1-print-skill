"""One bounded, read-only camera snapshot from the configured printer host.

Relative Moonraker snapshot URLs refer to HTTP port 80 by default, rather
than the Moonraker API port. A separately configured origin may override it.
No streaming fallback or camera-service mutation is performed.
"""
from datetime import datetime, timezone
import hashlib
import io
import os
from pathlib import Path
import tempfile
import time
from urllib.parse import urlsplit
import warnings

from PIL import Image
import requests

from .config import validate_camera_url, validate_config
from .transport import create_session, get_result, printer_status
from .validation import ValidationError, require

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
DEADLINE_SECONDS = 30


def origin(url):
    parsed = urlsplit(url)
    return parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80)


def resolve_snapshot_url(config, snapshot_url):
    require(isinstance(snapshot_url, str) and bool(snapshot_url.strip()), 'Camera snapshot URL unavailable')
    parsed = urlsplit(snapshot_url)
    if parsed.scheme or parsed.netloc:
        final = snapshot_url
    else:
        printer_host = urlsplit(config['printer_url']).hostname
        if ':' in printer_host:
            printer_host = '[' + printer_host + ']'
        base = config.get('camera_base_url', f'http://{printer_host}:80')
        final = base.rstrip('/') + '/' + snapshot_url.lstrip('/')
    try:
        return validate_camera_url(final, config['printer_url'])
    except ValueError:
        raise ValidationError('Camera snapshot URL is unsupported') from None


def select_snapshot(config, session, camera_name):
    if config.get('camera_url'):
        return config['camera_url']
    listing = get_result(session, config, '/server/webcams/list')
    webcams = listing.get('webcams') if isinstance(listing, dict) else None
    require(isinstance(webcams, list), 'Camera snapshot unavailable')
    candidates = [item for item in webcams if isinstance(item, dict) and item.get('enabled') is True and isinstance(item.get('snapshot_url'), str) and bool(item['snapshot_url'].strip())]
    if camera_name is not None:
        candidates = [item for item in candidates if item.get('name') == camera_name]
    require(len(candidates) == 1, 'Camera snapshot unavailable or ambiguous; select a configured camera name')
    return resolve_snapshot_url(config, candidates[0]['snapshot_url'])


def read_image(response, started):
    require(response.status_code == 200, 'Camera snapshot request failed or redirected')
    content_type = response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
    require(not (content_type.startswith(('text/', 'multipart/')) or content_type in {'application/json', 'application/xhtml+xml'} or content_type.endswith('+json')), 'Camera response is not a snapshot image')
    length = response.headers.get('Content-Length')
    if length is not None:
        try:
            declared = int(length)
        except (ValueError, TypeError):
            raise ValidationError('Invalid camera response length') from None
        require(0 < declared <= MAX_BYTES, 'Camera snapshot exceeds byte limit')
    content = bytearray()
    # A one-byte iterator makes the absolute deadline observable even if a
    # server drips bytes just before each socket timeout. A large requested
    # chunk could otherwise block while the underlying reader fills it.
    for chunk in response.iter_content(chunk_size=1):
        require(time.monotonic() - started <= DEADLINE_SECONDS, 'Camera snapshot deadline exceeded')
        if chunk:
            require(len(content) + len(chunk) <= MAX_BYTES, 'Camera snapshot exceeds byte limit')
            content.extend(chunk)
    require(bool(content) and time.monotonic() - started <= DEADLINE_SECONDS, 'Camera snapshot empty or deadline exceeded')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                image_format, width, height = image.format, image.width, image.height
                require(image_format in {'JPEG', 'PNG'} and 0 < width * height <= MAX_PIXELS, 'Camera image format or dimensions unsupported')
                image.verify()
            # Decode pixels as well: header/verify alone may miss truncation.
            with Image.open(io.BytesIO(content)) as image:
                image.load()
    except (OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValidationError('Camera image is corrupt or exceeds limits') from None
    return bytes(content), image_format, width, height


def capture_snapshot(config, output, camera_name=None, session=None, image_session=None):
    config = validate_config(config)
    output = Path(output).expanduser().absolute()
    require(not os.path.lexists(output), 'Snapshot output already exists')
    require(output.suffix.lower() in {'.jpg', '.jpeg', '.png'}, 'Snapshot output must use .jpg, .jpeg or .png')
    require(camera_name is None or isinstance(camera_name, str) and bool(camera_name.strip()), 'Camera name must be nonempty')
    own_api, own_image = session is None, image_session is None
    api = session or create_session(config)
    image_http, response, temporary = None, None, None
    try:
        status = printer_status(config, session=api)
        status = {'hostname': config['expected_hostname'], 'firmware_state': status['firmware_state'] if status['firmware_state'] in {'ready', 'startup', 'error', 'shutdown'} else 'unknown', 'print_state': status['print_state'] if status['print_state'] in {'standby', 'printing', 'paused', 'complete', 'cancelled', 'error'} else 'unknown'}
        url = select_snapshot(config, api, camera_name)
        # Independent session: Moonraker cookies, auth objects and API headers
        # cannot leak to another camera port. Only exact-origin API key passes.
        image_http = image_session or requests.Session()
        if own_image:
            image_http.trust_env = False
            image_http.mount('http://', requests.adapters.HTTPAdapter(max_retries=0))
            image_http.mount('https://', requests.adapters.HTTPAdapter(max_retries=0))
        headers = {}
        if origin(url) == origin(config['printer_url']):
            key = api.headers.get('X-Api-Key')
            if key:
                headers['X-Api-Key'] = key
        started = time.monotonic()
        response = image_http.get(url, headers=headers, stream=True, timeout=(5, 5), allow_redirects=False)
        content, image_format, width, height = read_image(response, started)
        require(output.suffix.lower() in ({'.jpg', '.jpeg'} if image_format == 'JPEG' else {'.png'}), 'Snapshot output extension does not match the captured image format')
        output.parent.mkdir(parents=True, exist_ok=True)
        # Commit a complete validated file atomically without replacing an
        # output created by a concurrent process. Both paths share a volume.
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix='.k1-snapshot-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
        return {'path': str(output), 'sha256': hashlib.sha256(content).hexdigest(), 'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'format': image_format, 'width': width, 'height': height, 'printer_status': status}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if response is not None:
            response.close()
        if own_image and image_http is not None:
            image_http.close()
        if own_api:
            api.close()
