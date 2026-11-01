import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/creality-k1-print/scripts'))
try:
    from k1print import cli, config
except ImportError:
    cli = config = None


class CliTests(unittest.TestCase):
    def test_init_roundtrip_and_version(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as output:
            filename = Path(tmp) / 'config.json'
            result = cli.main(['--config', str(filename), 'init', '--printer-url', 'http://printer.example:7125', '--expected-hostname', 'synthetic-k1', '--orca-path', '/tools/orca'])
            self.assertEqual(result, 0)
            data = config.load_config(filename)
            self.assertEqual(data['expected_hostname'], 'synthetic-k1')
            self.assertNotIn('api_key', data)
        self.assertIn('config', output.getvalue())

    def test_reject_secret_fields_and_url_credentials(self):
        for data in [{'printer_url': 'http://name:secret@printer.example:7125', 'expected_hostname': 'test'}, {'printer_url': 'http://printer.example:7125', 'expected_hostname': 'test', 'api_key': 'secret'}]:
            with self.assertRaises(ValueError):
                config.validate_config(data)

    def test_camera_init_and_snapshot_command(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            filename = Path(tmp) / 'config.json'
            result = cli.main(['--config', str(filename), 'init', '--printer-url', 'http://printer.example:7125', '--expected-hostname', 'synthetic-k1', '--orca-path', '/tools/orca', '--camera-url', 'http://printer.example:8080/?action=snapshot', '--camera-base-url', 'http://printer.example'])
            self.assertEqual(result, 0)
            self.assertIn('camera_url', config.load_config(filename))
            with patch('k1print.camera.capture_snapshot', return_value={'path': 'synthetic.png'}) as capture:
                self.assertEqual(cli.main(['--config', str(filename), 'snapshot', '--output', str(Path(tmp) / 'snapshot.png'), '--camera-name', 'front']), 0)
            self.assertEqual(capture.call_args.kwargs['camera_name'], 'front')

    def test_snapshot_network_errors_do_not_expose_urls_or_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            filename = Path(tmp) / 'config.json'
            config.save_config({'printer_url': 'http://printer.example:7125', 'expected_hostname': 'synthetic-k1'}, filename)
            with contextlib.redirect_stderr(io.StringIO()) as error, patch('k1print.camera.capture_snapshot', side_effect=requests.Timeout('http://printer.example/?token=private-test-key')):
                result = cli.main(['--config', str(filename), 'snapshot', '--output', str(Path(tmp) / 'snapshot.png')])
            self.assertEqual(result, 2)
            self.assertNotIn('printer.example', error.getvalue())
            self.assertNotIn('private-test-key', error.getvalue())


if __name__ == '__main__':
    unittest.main()
