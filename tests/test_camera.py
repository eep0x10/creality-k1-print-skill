import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/creality-k1-print/scripts'))
try:
    from k1print import camera
except ImportError:
    camera = None
from k1print.config import validate_config


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / 'snapshot.png'
        self.config = {'printer_url': 'http://printer.example:7125', 'expected_hostname': 'synthetic-k1'}
        self.http = Mock()
        self.http.headers = {'X-Api-Key': 'private-test-key'}
        self.http.get.side_effect = self.get
        self.webcams = [{'name': 'front', 'enabled': True, 'snapshot_url': '/webcam/?action=snapshot'}]
        self.photo = Mock()
        self.response = Mock()
        self.response.status_code = 200
        self.response.headers = {'Content-Type': 'image/png'}
        buffer = io.BytesIO()
        Image.new('RGB', (8, 6), 'green').save(buffer, format='PNG')
        self.content = buffer.getvalue()
        self.response.iter_content.side_effect = lambda chunk_size: iter([self.content])
        self.photo.get.return_value = self.response
        self.state = 'printing'

    def get(self, url, **kwargs):
        response = Mock()
        if url.endswith('/printer/info'):
            response.json.return_value = {'result': {'hostname': 'synthetic-k1', 'state': 'ready'}}
        elif 'print_stats' in url:
            response.json.return_value = {'result': {'status': {'print_stats': {'state': self.state}}}}
        else:
            response.json.return_value = {'result': {'webcams': self.webcams}}
        return response

    def capture(self, **kwargs):
        return camera.capture_snapshot(self.config, self.output, session=self.http, image_session=self.photo, **kwargs)

    def test_relative_snapshot_uses_http_port80_and_never_forwards_key(self):
        result = self.capture()
        call = self.photo.get.call_args
        self.assertEqual(call.args[0], 'http://printer.example:80/webcam/?action=snapshot')
        self.assertNotIn('X-Api-Key', call.kwargs.get('headers', {}))
        self.assertFalse(call.kwargs['allow_redirects'])
        self.assertEqual(self.output.read_bytes(), self.content)
        self.assertEqual(result['sha256'], hashlib.sha256(self.content).hexdigest())
        self.assertEqual((result['format'], result['width'], result['height']), ('PNG', 8, 6))
        self.assertEqual(result['printer_status']['print_state'], 'printing')
        self.assertNotIn('printer.example', str(result))
        self.http.post.assert_not_called()
        self.photo.post.assert_not_called()

    def test_proxy_base_and_same_origin_key(self):
        self.config['camera_base_url'] = 'http://printer.example:7125'
        self.state = 'paused'
        self.capture()
        self.assertEqual(self.photo.get.call_args.args[0], 'http://printer.example:7125/webcam/?action=snapshot')
        self.assertEqual(self.photo.get.call_args.kwargs['headers']['X-Api-Key'], 'private-test-key')

    def test_override_bypasses_webcam_listing_and_supports_jpeg(self):
        self.output = self.output.with_suffix('.jpg')
        self.config['camera_url'] = 'http://printer.example:8080/?action=snapshot'
        buffer = io.BytesIO()
        Image.new('RGB', (9, 7)).save(buffer, format='JPEG')
        self.content = buffer.getvalue()
        self.response.headers = {'Content-Type': 'image/jpeg'}
        result = self.capture()
        self.assertEqual(result['format'], 'JPEG')
        self.assertFalse(any('/server/webcams/list' in call.args[0] for call in self.http.get.call_args_list))

    def test_first_snapshot_creates_parent_after_validation_only(self):
        self.output = Path(self.tmp.name) / 'new' / 'snapshots' / 'status.png'
        self.capture()
        self.assertEqual(self.output.read_bytes(), self.content)

    def test_invalid_image_does_not_create_parent_and_format_must_match_suffix(self):
        self.output = Path(self.tmp.name) / 'new' / 'snapshots' / 'status.jpg'
        with self.assertRaises(ValueError):
            self.capture()
        self.assertFalse(self.output.parent.exists())
        self.content = b'corrupt'
        with self.assertRaises(ValueError):
            self.capture()
        self.assertFalse(self.output.parent.exists())

    def test_unsupported_suffix_rejected_before_network(self):
        self.output = self.output.with_suffix('.html')
        with self.assertRaises(ValueError):
            self.capture()
        self.http.get.assert_not_called()
        self.photo.get.assert_not_called()

    def test_ambiguous_disabled_missing_or_wrong_name_rejected(self):
        cases = [([], None), ([{'name': 'front', 'enabled': False, 'snapshot_url': '/snap'}], None), ([{'name': 'front', 'enabled': True, 'camera_url': '/not-official'}], None), (self.webcams * 2, None), (self.webcams, 'missing')]
        for webcams, name in cases:
            self.webcams = webcams
            with self.subTest(name=name, webcams=webcams), self.assertRaises(ValueError):
                self.capture(camera_name=name)
        self.photo.get.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_named_selection(self):
        self.webcams.append({'name': 'back', 'enabled': True, 'snapshot_url': '/back/snapshot'})
        self.capture(camera_name='back')
        self.assertTrue(self.photo.get.call_args.args[0].endswith('/back/snapshot'))

    def test_unsafe_urls_are_rejected_before_photo_request(self):
        for url in ['http://other.example/snapshot', 'http://name:secret@printer.example/snapshot', 'http://printer.example/snapshot#secret', 'http://printer.example/snapshot?api_key=secret', '//other.example/snapshot', 'file:///snapshot']:
            self.webcams[0]['snapshot_url'] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.capture()
        self.photo.get.assert_not_called()

    def test_configuration_rejects_external_origins_and_secrets(self):
        for key, url in [('camera_url', '/snapshot'), ('camera_url', 'http://other.example/snapshot'), ('camera_url', 'http://printer.example/?token=secret'), ('camera_base_url', 'http://printer.example/proxy'), ('camera_base_url', 'http://other.example')]:
            with self.subTest(key=key, url=url), self.assertRaises(ValueError):
                validate_config(dict(self.config, **{key: url}))

    def test_existing_output_refused_before_network(self):
        self.output.write_bytes(b'preserve')
        with self.assertRaises((ValueError, FileExistsError)):
            self.capture()
        self.http.get.assert_not_called()
        self.photo.get.assert_not_called()
        self.assertEqual(self.output.read_bytes(), b'preserve')

    def test_html_corrupt_redirect_oversize_and_large_dimensions_leave_no_file(self):
        cases = [({'Content-Type': 'text/html'}, b'<html>private body</html>', 200), ({'Content-Type': 'image/png'}, b'corrupt', 200), ({'Content-Type': 'image/png'}, self.content, 302), ({'Content-Type': 'image/png', 'Content-Length': str(10 * 1024 * 1024 + 1)}, self.content, 200)]
        for headers, content, status in cases:
            self.response.headers, self.content, self.response.status_code = headers, content, status
            with self.subTest(headers=headers, status=status), self.assertRaises(ValueError):
                self.capture()
            self.assertFalse(self.output.exists())
        self.response.headers, self.response.status_code = {'Content-Type': 'image/png'}, 200
        with patch('k1print.camera.MAX_PIXELS', 10):
            buffer = io.BytesIO()
            Image.new('RGB', (8, 6)).save(buffer, format='PNG')
            self.content = buffer.getvalue()
            with self.assertRaises(ValueError):
                self.capture()
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

    def test_stream_limit_and_deadline(self):
        with patch('k1print.camera.MAX_BYTES', 32):
            with self.assertRaises(ValueError):
                self.capture()
        with patch('k1print.camera.time.monotonic', side_effect=[0, 31, 32]):
            with self.assertRaises(ValueError):
                self.capture()
        self.assertFalse(self.output.exists())

    def test_owned_sessions_are_closed_on_failure(self):
        with patch('k1print.camera.create_session', return_value=self.http), patch('k1print.camera.requests.Session', return_value=self.photo):
            self.webcams = []
            with self.assertRaises(ValueError):
                camera.capture_snapshot(self.config, self.output)
        self.http.close.assert_called_once()

    def test_owned_image_session_and_response_close_on_invalid_image(self):
        self.content = b'corrupt image'
        with patch('k1print.camera.create_session', return_value=self.http), patch('k1print.camera.requests.Session', return_value=self.photo):
            with self.assertRaises(ValueError):
                camera.capture_snapshot(self.config, self.output)
        self.http.close.assert_called_once()
        self.photo.close.assert_called_once()
        self.response.close.assert_called_once()
        self.assertFalse(self.output.exists())

    def test_concurrent_output_creation_is_preserved_without_partial_file(self):
        def create_other_then_fail(source, destination):
            Path(destination).write_bytes(b'other process output')
            raise FileExistsError()
        with patch('k1print.camera.os.link', side_effect=create_other_then_fail):
            with self.assertRaises(FileExistsError):
                self.capture()
        self.assertEqual(self.output.read_bytes(), b'other process output')
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [self.output])

    def test_wrong_printer_never_downloads_image(self):
        original = self.get
        def wrong_identity(url, **kwargs):
            response = original(url, **kwargs)
            if url.endswith('/printer/info'):
                response.json.return_value = {'result': {'hostname': 'different-printer', 'state': 'ready'}}
            return response
        self.http.get.side_effect = wrong_identity
        with self.assertRaises(ValueError):
            self.capture()
        self.photo.get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
