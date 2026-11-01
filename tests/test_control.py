import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/creality-k1-print/scripts'))
try:
    from k1print import transport, validation
except ImportError:
    transport = validation = None

GCODE = 'START_PRINT EXTRUDER_TEMP=220 BED_TEMP=55\nG90\nM83\nG1 X110 Y110 Z0.2 F1200\nG1 X111 E0.2\nEND_PRINT\n'


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = {'printer_url': 'http://printer.example:7125', 'expected_hostname': 'synthetic-k1'}
        self.manifest_path = self.root / 'job.json'
        self.manifest = {'schema_version': 1, 'settings': {}, 'estimates': {}}
        artifacts = {'gcode': GCODE.encode(), 'preview': b'\x89PNG\r\n\x1a\nsynthetic', 'preview_report': json.dumps({'gcode_sha256': hashlib.sha256(GCODE.encode()).hexdigest(), 'bounds': {'x': [110, 111], 'y': [110, 110], 'z': [0.2, 0.2]}}).encode()}
        for key, data in artifacts.items():
            name = {'gcode': 'part.gcode', 'preview': 'part.png', 'preview_report': 'report.json'}[key]
            (self.root / name).write_bytes(data)
            self.manifest[key] = name
            self.manifest[key + '_sha256'] = hashlib.sha256(data).hexdigest()
        self.manifest_path.write_text(json.dumps(self.manifest))
        self.events = []
        self.state = 'standby'
        self.hostname = 'synthetic-k1'
        self.queued = False
        self.wrapped = False
        self.server_version = 'v0.10.0-1-gsynthetic'
        self.api_version = [1, 5, 0]
        self.http = Mock()
        self.http.get.side_effect = self.get
        self.http.post.side_effect = self.post

    def response(self, payload):
        response = Mock()
        response.json.return_value = payload
        return response

    def get(self, url, **kwargs):
        self.events.append(('GET', url))
        if url.endswith('/server/info'):
            return self.response({'result': {'moonraker_version': self.server_version, 'api_version': self.api_version}})
        if url.endswith('/printer/info'):
            return self.response({'result': {'hostname': self.hostname, 'state': 'ready'}})
        if 'configfile' in url:
            return self.response({'result': {'status': {'configfile': {'config': {'gcode_macro START_PRINT': {'gcode': 'CX_ROUGH_G28\nACCURATE_G28'}, 'gcode_macro END_PRINT': {'gcode': 'M104 S0'}}}}}})
        return self.response({'result': {'status': {'print_stats': {'state': self.state, 'filename': f"job-{self.manifest['gcode_sha256']}.gcode"}}}})

    def post(self, url, **kwargs):
        self.events.append(('POST', url))
        if url.endswith('/upload'):
            self.assertEqual(kwargs['data'], {'root': 'gcodes', 'print': 'false', 'checksum': self.manifest['gcode_sha256']})
            self.assertEqual(kwargs['files']['file'][1], GCODE.encode())
            payload = {'item': {'root': 'gcodes', 'path': f"job-{self.manifest['gcode_sha256']}.gcode"}, 'print_started': False, 'print_queued': self.queued}
            return self.response({'result': payload} if self.wrapped else payload)
        self.state = 'printing'
        return self.response({'result': 'ok'})

    def send(self, **kwargs):
        args = dict(approved_sha256=self.manifest['gcode_sha256'], approval_ref='synthetic approval', session=self.http)
        args.update(kwargs)
        return transport.send_job(self.manifest_path, self.config, **args)

    def test_missing_approval_or_modified_artifacts_prevents_all_requests(self):
        for kwargs in ({'approved_sha256': None}, {'approval_ref': ''}):
            with self.assertRaises(ValueError):
                self.send(**kwargs)
        for name in ('part.gcode', 'part.png', 'report.json'):
            path = self.root / name
            original = path.read_bytes()
            path.write_bytes(original + b'changed')
            with self.assertRaises(ValueError):
                self.send()
            path.write_bytes(original)
        self.assertEqual(self.events, [])

    def test_dry_run_has_no_approval_no_posts(self):
        result = self.send(approved_sha256=None, approval_ref=None, dry_run=True)
        self.assertEqual(result['outcome'], 'dry_run')
        self.assertFalse(result['approval_recorded'])
        self.http.post.assert_not_called()

    def test_busy_or_wrong_identity_prevents_posts(self):
        for hostname, state in [('wrong', 'standby'), ('synthetic-k1', 'printing'), ('synthetic-k1', 'paused'), ('synthetic-k1', 'error')]:
            self.hostname, self.state = hostname, state
            with self.assertRaises(ValueError):
                self.send()
        self.http.post.assert_not_called()

    def test_direct_and_wrapped_upload_order_and_prior_receipt(self):
        for wrapped in (False, True):
            self.wrapped, self.state = wrapped, 'standby'
            receipt = self.root / 'receipt.json'
            receipt.unlink(missing_ok=True)
            self.events.clear()
            self.assertEqual(self.send()['outcome'], 'printing_confirmed')
            methods = [m for m, _ in self.events]
            a, b = [i for i, m in enumerate(methods) if m == 'POST']
            self.assertGreater(b - a, 1)
            self.assertTrue(self.events[a][1].endswith('/upload'))
            self.assertTrue(self.events[b][1].endswith('/start'))
            self.events.clear()
            with self.assertRaises(ValueError):
                self.send()
            self.assertEqual(self.events, [])

    def test_queued_upload_never_starts(self):
        self.queued = True
        with self.assertRaises(ValueError):
            self.send()
        self.assertEqual(len([m for m, _ in self.events if m == 'POST']), 1)

    def test_old_unknown_or_incompatible_server_prevents_upload(self):
        for version, api in [('v0.9.3', [1, 5, 0]), ('unknown', [1, 5, 0]), (None, [1, 5, 0]), ('v0.10.0', [2, 0, 0]), ('v0.10.0', None)]:
            self.server_version, self.api_version = version, api
            with self.subTest(version=version, api=api), self.assertRaises(ValueError):
                self.send()
        self.http.post.assert_not_called()

    def test_supported_server_checksum_capability_is_checked_before_upload(self):
        self.assertEqual(self.send()['outcome'], 'printing_confirmed')
        info = next(i for i, (method, url) in enumerate(self.events) if url.endswith('/server/info'))
        upload = next(i for i, (method, url) in enumerate(self.events) if url.endswith('/upload'))
        self.assertLess(info, upload)

    def test_timeout_never_retries_start(self):
        import requests
        def post(url, **kwargs):
            if url.endswith('/start'):
                self.events.append(('POST', url))
                raise requests.Timeout('private header')
            return self.post(url, **kwargs)
        self.http.post.side_effect = post
        self.assertEqual(self.send()['outcome'], 'start_unconfirmed')
        self.assertEqual(len([u for m, u in self.events if m == 'POST']), 2)
        self.assertNotIn('private header', (self.root / 'receipt.json').read_text())

    def test_busy_after_upload_does_not_start(self):
        def post(url, **kwargs):
            response = self.post(url, **kwargs)
            self.state = 'printing'
            return response
        self.http.post.side_effect = post
        with self.assertRaises(ValueError):
            self.send()
        self.assertEqual(len([m for m, _ in self.events if m == 'POST']), 1)

    def test_upload_timeout_no_retry_and_receipt_blocks_repeat(self):
        import requests
        self.http.post.side_effect = requests.Timeout('secret')
        with self.assertRaises(requests.Timeout):
            self.send()
        self.assertEqual(self.http.post.call_count, 1)
        self.events.clear()
        with self.assertRaises(ValueError):
            self.send()
        self.assertEqual(self.events, [])

    def test_artifact_path_escape_is_blocked_before_network(self):
        self.manifest['gcode'] = '../escape.gcode'
        self.manifest_path.write_text(json.dumps(self.manifest))
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.send()
        self.assertEqual(self.events, [])

    def test_unbounded_extrusion_is_blocked(self):
        for body in ['M83\nG1 E101', 'M82\nG92 E10\nG1 E111', 'M83\nG1 E-101']:
            with self.subTest(body=body), self.assertRaises(ValueError):
                validation.validate_gcode('START_PRINT EXTRUDER_TEMP=220 BED_TEMP=55\n' + body + '\nEND_PRINT')

    def test_orca_single_turn_helical_arc_parameter(self):
        body = 'START_PRINT EXTRUDER_TEMP=220 BED_TEMP=55\nG1 X110 Y110 Z0.5\nG3 Z.76 I-.883 J.838 P1 F30000\nEND_PRINT'
        validation.validate_gcode(body)
        for value in ('0', '2', '1.5'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validation.validate_gcode(body.replace('P1 ', 'P' + value + ' '))

    def test_command_arc_units_temperatures_and_macro_gates(self):
        good = ['G1 X120.158 Y108.929\nG2 X119.65 Y109.838 I175.102 J98.412 E.03879', 'G1 X219 Y109\nG3 X219 Y111 I-1 J1', 'G1 X219 Y111\nG2 X219 Y109 I-1 J-1', 'G1 X110 Y110\nG2 X110 Y110 I10 J0']
        bad = ['G01 X221', 'G20', 'G91\nG1 X1', 'G91\nG1 X150\nG1 X150', 'G1 X219 Y109\nG3 X219 Y111 I1 J1', 'G1 X210 Y110\nG2 X210 Y110 I20 J0', 'RUN_SHELL_COMMAND CMD=x', 'M104 S301', 'M140 S101', 'SET_VELOCITY_LIMIT ACCEL=20001']
        for body in good:
            validation.validate_gcode('START_PRINT EXTRUDER_TEMP=220 BED_TEMP=55\n' + body + '\nEND_PRINT')
        for body in bad:
            with self.subTest(body=body), self.assertRaises(ValueError):
                validation.validate_gcode('START_PRINT EXTRUDER_TEMP=220 BED_TEMP=55\n' + body + '\nEND_PRINT')
        for text in ['G1 X100\n' + GCODE, GCODE + 'G1 X100\n', GCODE.replace('220 BED_TEMP=55', '250 BED_TEMP=55')]:
            with self.assertRaises(ValueError):
                validation.validate_gcode(text)


if __name__ == '__main__':
    unittest.main()
