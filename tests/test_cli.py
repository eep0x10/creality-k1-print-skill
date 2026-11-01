import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

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


if __name__ == '__main__':
    unittest.main()
