"""Command line entrypoint; preparation imports remain offline and lazy."""
import argparse
import json
from pathlib import Path
import sys

import requests

from . import __version__
from .config import DEFAULT_CONFIG, load_config, save_config
from .validation import ValidationError


def build_parser():
    parser = argparse.ArgumentParser(description='Original K1 / PLA preparation and exact-preview approved printing')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG, help='Local non-secret JSON configuration')
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='Create local configuration; never contacts a printer')
    init.add_argument('--printer-url', required=True)
    init.add_argument('--expected-hostname', required=True)
    init.add_argument('--orca-path', required=True, help='User-installed OrcaSlicer executable')
    init.add_argument('--orca-resources', help='Optional Orca resources directory')
    init.add_argument('--api-key-env', help='Name of environment variable holding an API key; never the key itself')
    scan = commands.add_parser('discover', help='GET-only scan of an explicit private IPv4 subnet, at most /24')
    scan.add_argument('--subnet', required=True)
    scan.add_argument('--port', type=int, default=7125)
    scan.add_argument('--timeout', type=float, default=0.5)
    commands.add_parser('status', help='Read configured printer identity and state using GET only')
    profiles = commands.add_parser('profiles', help='Derive local K1/PLA profiles from the installed Orca resources')
    profiles.add_argument('--output-dir', type=Path, required=True)
    prepare = commands.add_parser('prepare', help='Prepare geometry, slice offline and render the real G-code preview')
    prepare.add_argument('model', type=Path)
    prepare.add_argument('--job-dir', type=Path, required=True)
    prepare.add_argument('--height-mm', type=float, help='Uniform target height; omitted preserves original scale')
    prepare.add_argument('--orient', action='store_true', help='Opt in to Orca orientation; review the resulting supports')
    for command in (profiles, prepare):
        command.add_argument('--strength', choices=('economy', 'balanced', 'robust'), default='balanced')
        command.add_argument('--finish', choices=('fast', 'balanced', 'detailed'), default='balanced')
    send = commands.add_parser('send', help='Upload/start the exact approved preview once, or validate with GET-only dry-run')
    send.add_argument('job_json', type=Path)
    send.add_argument('--approved-sha256', help='G-code SHA256 explicitly accepted with the preview')
    send.add_argument('--approval-ref', help='Reference to this job\'s explicit human acceptance')
    send.add_argument('--dry-run', action='store_true', help='No print approval recorded and no POST; optional approval arguments ignored')
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            data = {key: getattr(args, key) for key in ('printer_url', 'expected_hostname', 'orca_path', 'orca_resources', 'api_key_env') if getattr(args, key) is not None}
            result = {'config': str(save_config(data, args.config)), 'printer_contacted': False}
        elif args.command == 'discover':
            from .discovery import discover
            result = {'printers': discover(args.subnet, args.port, args.timeout)}
        else:
            config = load_config(args.config)
            if args.command == 'status':
                from .transport import printer_status
                result = printer_status(config)
            elif args.command == 'profiles':
                from .profiles import prepare_profiles
                result = prepare_profiles(config, args.output_dir, args.strength, args.finish)
            elif args.command == 'prepare':
                from .slicing import prepare_job
                result = prepare_job(args.model, args.job_dir, config, height_mm=args.height_mm, strength=args.strength, finish=args.finish, orientation=args.orient)
            else:
                from .transport import send_job
                result = send_job(args.job_json, config, approved_sha256=args.approved_sha256, approval_ref=args.approval_ref, dry_run=args.dry_run)
        print(json.dumps(result, indent=2, default=str))
        if args.command == 'send' and result['outcome'] not in {'dry_run', 'printing_confirmed'}:
            return 3
        return 0
    except (ValueError, OSError, KeyError, TypeError, requests.RequestException) as exc:
        error = {'outcome': 'blocked_or_unconfirmed', 'error_type': type(exc).__name__}
        if isinstance(exc, ValidationError):
            error['error_message'] = str(exc)[:400]
        print(json.dumps(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
