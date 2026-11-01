"""Explicit bounded RFC1918 discovery; GET /printer/info only."""
import ipaddress

import requests

from .validation import require

PRIVATE = tuple(ipaddress.ip_network(value) for value in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


def discover(subnet, port=7125, timeout=0.5, session=None):
    network = ipaddress.ip_network(subnet, strict=True)
    require(isinstance(network, ipaddress.IPv4Network) and network.num_addresses <= 256 and any(network.subnet_of(allowed) for allowed in PRIVATE), 'Discovery requires an explicit RFC1918 IPv4 network of at most 256 addresses')
    require(isinstance(port, int) and 1 <= port <= 65535, 'Invalid discovery port')
    require(isinstance(timeout, (int, float)) and 0 < timeout <= 2, 'Discovery timeout must be greater than zero and at most two seconds')
    own = session is None
    http = session or requests.Session()
    if own:
        http.trust_env = False
    found = []
    try:
        for address in network.hosts():
            url = f'http://{address}:{port}'
            try:
                response = http.get(url + '/printer/info', timeout=timeout, allow_redirects=False)
                response.raise_for_status()
                info = response.json().get('result', {})
                if isinstance(info, dict) and isinstance(info.get('hostname'), str) and info.get('state') in {'ready', 'startup', 'error', 'shutdown'}:
                    found.append({'printer_url': url, 'hostname': info['hostname'], 'state': info['state']})
            except (requests.RequestException, ValueError, AttributeError):
                continue
    finally:
        if own:
            http.close()
    return found
