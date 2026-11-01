"""Independent conservative G-code gates for K1/PLA; no third-party validator.

Only the supported Orca command vocabulary is accepted. Limits apply to
travel and extrusion, including directed XY arc extrema and relative moves.
Firmware macro execution itself cannot be simulated by this local validator.
"""
import hashlib
import json
import math
from pathlib import Path
import re

NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)'
NUMERIC = {'G0', 'G1', 'G2', 'G3', 'G4', 'G17', 'G21', 'G90', 'G91', 'G92', 'M73', 'M82', 'M83', 'M104', 'M109', 'M140', 'M190', 'M106', 'M107', 'M204', 'T0'}


class ValidationError(ValueError):
    """Sanitized local validation failure."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def bound(value, low, high):
    require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and low <= value <= high, 'Value outside supported K1 limits')


def parameters(text, limits, required=(), named=False):
    expression = r'([A-Z_]+)=(' + NUMBER + ')' if named else r'([A-Z])(' + NUMBER + ')'
    remaining = text.strip()
    result = {}
    while remaining:
        match = re.match(expression, remaining)
        require(match is not None, 'Malformed numeric parameters')
        key, raw = match.groups()
        require(key in limits and key not in result, 'Unsupported or duplicate parameter')
        value = float(raw)
        bound(value, *limits[key])
        result[key] = value
        remaining = remaining[match.end():]
        require(not named or not remaining or remaining[0].isspace(), 'Malformed macro parameters')
        remaining = remaining.lstrip()
    require(set(required) <= result.keys(), 'Missing required parameters')
    return result


def arc_extrema(start, end, params, clockwise):
    require(('I' in params or 'J' in params) and 'R' not in params, 'Only I/J XY arcs are supported')
    cx, cy = start['X'] + params.get('I', 0), start['Y'] + params.get('J', 0)
    radius = math.hypot(params.get('I', 0), params.get('J', 0))
    end_radius = math.hypot(end['X'] - cx, end['Y'] - cy)
    require(radius > 0 and abs(radius - end_radius) <= 0.02, 'Invalid arc radius')
    begin = math.atan2(start['Y'] - cy, start['X'] - cx)
    finish = math.atan2(end['Y'] - cy, end['X'] - cx)
    direction, tau = (-1 if clockwise else 1), math.tau
    full = math.hypot(end['X'] - start['X'], end['Y'] - start['Y']) <= 1e-9
    sweep = tau if full else ((finish - begin) * direction) % tau
    for angle in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
        if full or ((angle - begin) * direction) % tau <= sweep + 1e-10:
            bound(cx + radius * math.cos(angle), 0, 220)
            bound(cy + radius * math.sin(angle), 0, 220)


def object_macro(command, args):
    require(command in {'EXCLUDE_OBJECT_DEFINE', 'EXCLUDE_OBJECT_START', 'EXCLUDE_OBJECT_END'}, 'Unknown object macro')
    match = re.fullmatch(r'NAME=([A-Za-z0-9_.-]+)(?: CENTER=([^ ]+) POLYGON=(\[.*\]))?', args)
    require(match is not None, 'Unsafe object macro arguments')
    if command != 'EXCLUDE_OBJECT_DEFINE':
        require(match[2] is None, 'Unexpected object geometry')
        return
    require(match[2] is not None, 'Object geometry required')
    try:
        center = [float(v) for v in match[2].split(',')]
        polygon = json.loads(match[3])
        require(len(center) == 2 and isinstance(polygon, list) and 3 <= len(polygon) <= 10000, 'Invalid object polygon')
        for point in [center] + polygon:
            require(isinstance(point, list) and len(point) == 2, 'Invalid object point')
            for coordinate in point:
                bound(coordinate, 0, 220)
    except (TypeError, json.JSONDecodeError):
        raise ValidationError('Invalid object geometry') from None


def validate_gcode(text):
    position, absolute = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}, True
    extrusion, relative_extrusion = 0.0, True
    known_axes = set()
    started = ended = False
    moves = 0
    for raw in text.splitlines():
        line = raw.split(';', 1)[0].strip()
        if not line:
            continue
        tokens = line.split(maxsplit=1)
        command, args = tokens[0], tokens[1] if len(tokens) > 1 else ''
        if ended:
            require(command in {'M73', 'M107'} or line in {'M104 S0', 'M140 S0'}, 'Unsafe command after END_PRINT')
        if command == 'START_PRINT':
            require(not started and not ended, 'Misplaced START_PRINT')
            parameters(args, {'EXTRUDER_TEMP': (170, 240), 'BED_TEMP': (0, 80)}, ('EXTRUDER_TEMP', 'BED_TEMP'), named=True)
            started = True
        elif command == 'END_PRINT':
            require(started and not ended and not args, 'Misplaced END_PRINT')
            ended = True
        elif command == 'SET_VELOCITY_LIMIT':
            require(bool(args), 'Velocity parameters required')
            parameters(args, {'ACCEL': (1, 20000), 'ACCEL_TO_DECEL': (0, 20000), 'SQUARE_CORNER_VELOCITY': (0, 20), 'VELOCITY': (1, 500), 'MINIMUM_CRUISE_RATIO': (0, 1)}, named=True)
        elif command == 'SET_PRESSURE_ADVANCE':
            parameters(args, {'ADVANCE': (0, 1), 'SMOOTH_TIME': (0.001, 0.2)}, ('ADVANCE',), named=True)
        elif command.startswith('EXCLUDE_OBJECT_'):
            object_macro(command, args)
        else:
            require(command in NUMERIC, 'Command outside supported Orca K1 vocabulary')
            if command in {'G0', 'G1', 'G2', 'G3'}:
                require(started and not ended, 'Motion requires START_PRINT')
                limits = {'X': (-10000, 10000), 'Y': (-10000, 10000), 'Z': (-1000, 1000), 'E': (-10000000, 10000000), 'F': (1, 30000)}
                if command in {'G2', 'G3'}:
                    # Orca uses P1 on single-turn helical arcs. Multiple turns
                    # remain outside this conservative preparation contract.
                    limits.update({'I': (-1000000, 1000000), 'J': (-1000000, 1000000), 'P': (1, 1)})
                params = parameters(args, limits)
                moved_axes = set(params) & {'X', 'Y', 'Z'}
                require(absolute or moved_axes <= known_axes, 'Relative motion origin is not known after firmware macro')
                if 'E' in params:
                    delta = params['E'] if relative_extrusion else params['E'] - extrusion
                    bound(delta, -100, 100)
                    extrusion += delta
                end = {key: params.get(key, position[key] if absolute else 0) + (0 if absolute else position[key]) for key in position}
                for key, maximum in [('X', 220), ('Y', 220), ('Z', 250)]:
                    bound(end[key], 0, maximum)
                if command in {'G2', 'G3'}:
                    require({'X', 'Y'} <= known_axes, 'Arc origin is not known after firmware macro')
                    arc_extrema(position, end, params, command == 'G2')
                position = end
                known_axes.update(moved_axes)
                moves += 1
            elif command in {'G90', 'G91', 'G17', 'G21', 'M82', 'M83', 'M107', 'T0'}:
                require(not args, 'Unexpected command arguments')
                if command in {'G90', 'G91'}:
                    absolute = command == 'G90'
                elif command in {'M82', 'M83'}:
                    relative_extrusion = command == 'M83'
            elif command == 'G92':
                extrusion = parameters(args, {'E': (-10000000, 10000000)}, ('E',))['E']
            elif command in {'M104', 'M109', 'M140', 'M190'}:
                maximum = 300 if command in {'M104', 'M109'} else 100
                parameters(args, {'S': (0, maximum)}, ('S',))
            elif command == 'M106':
                parameters(args, {'P': (0, 3), 'S': (0, 255)}, ('S',))
            elif command == 'M73':
                parameters(args, {'P': (0, 100), 'R': (0, 100000), 'Q': (0, 100), 'S': (0, 100000)})
            elif command == 'M204':
                require(bool(args), 'Acceleration setting required')
                parameters(args, {'S': (1, 20000), 'P': (1, 20000), 'T': (1, 20000)})
            elif command == 'G4':
                require(bool(args), 'Dwell setting required')
                parameters(args, {'P': (0, 60000), 'S': (0, 60)})
    require(started and ended and moves > 0, 'Complete START_PRINT/motion/END_PRINT sequence required')


def artifact(root, name):
    require(isinstance(name, str) and bool(name), 'Artifact path missing')
    relative = Path(name)
    require(not relative.is_absolute(), 'Artifact paths must be relative to the job')
    path = (root / relative).resolve(strict=True)
    require(path.is_relative_to(root) and path.is_file(), 'Artifact escapes job directory')
    return path


def validate_job(manifest_path):
    manifest_path = Path(manifest_path).resolve(strict=True)
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    require(isinstance(manifest, dict) and manifest.get('schema_version') == 1, 'Unsupported job schema')
    blobs = {}
    for key in ('gcode', 'preview', 'preview_report'):
        content = artifact(root, manifest.get(key)).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        require(digest == manifest.get(key + '_sha256'), 'Prepared artifact hash mismatch')
        blobs[key] = content
    require(blobs['preview'].startswith(b'\x89PNG\r\n\x1a\n'), 'Preview PNG required')
    report = json.loads(blobs['preview_report'])
    require(report.get('gcode_sha256', report.get('sha256')) == manifest['gcode_sha256'], 'Report describes different G-code')
    for axis, maximum in [('x', 220), ('y', 220), ('z', 250)]:
        values = report.get('bounds', {}).get(axis)
        require(isinstance(values, list) and len(values) == 2, 'Extrusion bounds missing')
        for value in values:
            bound(value, 0, maximum)
        require(values[0] <= values[1], 'Invalid extrusion bounds')
    validate_gcode(blobs['gcode'].decode('utf-8-sig'))
    return manifest, blobs['gcode']
