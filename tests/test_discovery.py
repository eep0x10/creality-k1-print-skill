from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/creality-k1-print/scripts'))
try:
    from k1print import discovery
except ImportError:
    discovery = None


class DiscoveryTests(unittest.TestCase):
    def test_public_or_large_network_never_probed(self):
        session = Mock()
        for network in ('8.8.8.0/24', '10.0.0.0/8', '127.0.0.0/24', '::1/128'):
            with self.assertRaises(ValueError):
                discovery.discover(network, session=session)
        session.get.assert_not_called()

    def test_bounded_discovery_uses_only_info_get(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {'result': {'hostname': 'synthetic-k1', 'state': 'ready'}}
        session.get.return_value = response
        results = discovery.discover('192.168.123.0/30', session=session)
        self.assertEqual(len(results), 2)
        self.assertEqual(session.get.call_count, 2)
        session.post.assert_not_called()
        for call in session.get.call_args_list:
            self.assertTrue(call.args[0].endswith('/printer/info'))
            self.assertFalse(call.kwargs['allow_redirects'])


if __name__ == '__main__':
    unittest.main()
