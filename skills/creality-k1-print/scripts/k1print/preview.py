"""Stream actual deposited G-code and render a bounded, explicitly sampled preview."""
from pathlib import Path
import hashlib
import math
import random
import re
import tempfile

import numpy as np

NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)'
PARAM = re.compile(r'([XYZEFIJRP])\s*(' + NUMBER + ')', re.I)
TAU = 2 * math.pi
MAX_GCODE_BYTES = 512 * 1024 * 1024


def _file_digest(path):
    digest, size = hashlib.sha256(), 0
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(chunk)
            if size > MAX_GCODE_BYTES:
                raise ValueError('G-code exceeds 512 MiB preview limit')
            digest.update(chunk)
    return digest.hexdigest()


def _arc(start, end, args, clockwise):
    if 'R' in args or not any(k in args for k in ('I','J')):
        raise ValueError('Only relative I/J XY arcs are supported; R arcs are refused')
    if args.get('P', 1) != 1:
        raise ValueError('Only a single arc turn (P1) is supported')
    center = (start[0] + args.get('I', 0.), start[1] + args.get('J', 0.))
    radius = math.hypot(start[0] - center[0], start[1] - center[1])
    endpoint_radius = math.hypot(end[0] - center[0], end[1] - center[1])
    if not 0 < radius <= 10000 or abs(endpoint_radius - radius) > max(.06, radius * .001):
        raise ValueError('Invalid or excessive I/J arc radius')
    a = math.atan2(start[1] - center[1], start[0] - center[0])
    b = math.atan2(end[1] - center[1], end[0] - center[0])
    if clockwise:
        delta = -((a - b) % TAU)
        if abs(delta) < 1e-12:
            delta = -TAU
    else:
        delta = (b - a) % TAU
        if abs(delta) < 1e-12:
            delta = TAU
    extrema = [list(start), list(end)]
    for theta in (0., math.pi/2, math.pi, 3*math.pi/2):
        distance = (a - theta) % TAU if clockwise else (theta - a) % TAU
        if distance <= abs(delta) + 1e-12:
            extrema.append([center[0] + radius * math.cos(theta), center[1] + radius * math.sin(theta), start[2] + (end[2] - start[2]) * distance / abs(delta)])
    count = max(4, math.ceil(abs(delta) * radius / .25))
    if count > 10000:
        raise ValueError('Arc requires excessive display subdivision')
    def points():
        for i in range(count + 1):
            angle = a + delta * i / count
            yield [center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle), start[2] + (end[2] - start[2]) * i / count]
    return points(), extrema


def _scan(gcode, max_segments):
    position, e = [0., 0., 0.], 0.
    absolute, relative_e = True, False
    feature, plane = 'Unknown', 'G17'
    sample, sample_support = [], []
    segments, moves, support_segments = 0, 0, 0
    support_extrusion, model_extrusion = 0., 0.
    bounds = [[math.inf, -math.inf] for _ in range(3)]
    estimates, levels = {}, set()
    rng = random.Random(42)
    with gcode.open(encoding='utf-8', errors='strict') as stream:
        for raw in stream:
            if raw.startswith(';TYPE:'):
                feature = raw.split(':', 1)[1].strip()
            if raw.startswith(';') and '=' in raw:
                for label, key in (('estimated printing time (normal mode)', 'estimated_time'), ('total filament used [g]', 'filament_g'), ('filament used [mm]', 'filament_mm')):
                    if label in raw:
                        estimates[key] = raw.split('=', 1)[1].strip()
            line = raw.split(';', 1)[0].strip().upper()
            match = re.match(r'^([GMT]\d+(?:\.\d+)?)', line)
            if not match:
                continue  # Manufacturer macros are separately validated before send.
            cmd = match.group(1)
            if cmd in ('G18','G19','G20','G90.1'):
                raise ValueError('Unsupported G-code plane, units, or absolute arc centers')
            if cmd == 'G17':
                plane = cmd
            if cmd == 'G90':
                absolute = True
            elif cmd == 'G91':
                absolute = False
            elif cmd == 'M82':
                relative_e = False
            elif cmd == 'M83':
                relative_e = True
            if cmd not in ('G0','G00','G1','G01','G2','G02','G3','G03','G92'):
                continue
            args = {k.upper(): float(v) for k, v in PARAM.findall(line[match.end():])}
            if any(not math.isfinite(value) or abs(value) > 1e7 for value in args.values()):
                raise ValueError('Non-finite or excessive G-code value')
            if cmd == 'G92':
                for i, axis in enumerate('XYZ'):
                    if axis in args:
                        position[i] = args[axis]
                e = args.get('E', e)
                continue
            target = [args.get(axis, position[i]) if absolute else position[i] + args.get(axis, 0.) for i, axis in enumerate('XYZ')]
            delta_e = args.get('E', 0.) if relative_e else args.get('E', e) - e
            e += delta_e
            is_arc = cmd in ('G2','G02','G3','G03')
            if is_arc:
                points, extrema = _arc(position, target, args, cmd in ('G2','G02'))
            else:
                points, extrema = iter((position, target)), (position, target)
            depositing = delta_e > 0 and (is_arc or any(abs(target[i] - position[i]) > 1e-9 for i in (0,1)))
            if depositing:
                moves += 1
                is_support = feature.lower().startswith('support')
                if is_support:
                    support_extrusion += delta_e
                else:
                    model_extrusion += delta_e
                levels.add(round(target[2], 5))
                for point in extrema:
                    for i, value in enumerate(point):
                        bounds[i][0] = min(bounds[i][0], value)
                        bounds[i][1] = max(bounds[i][1], value)
                previous = next(points)
                for point in points:
                    segments += 1
                    support_segments += int(is_support)
                    segment = (list(previous), list(point))
                    if len(sample) < max_segments:
                        sample.append(segment)
                        sample_support.append(is_support)
                    else:
                        chosen = rng.randrange(segments)
                        if chosen < max_segments:
                            sample[chosen], sample_support[chosen] = segment, is_support
                    previous = point
            position = target
    if not segments:
        raise ValueError('No deposited XY toolpaths found in sliced G-code')
    total = model_extrusion + support_extrusion
    return sample, sample_support, {'bounds': dict(zip('xyz', bounds)), 'extrusion_segments': segments, 'extrusion_moves': moves, 'support_segments': support_segments, 'layer_count': len(levels), 'model_extrusion_mm': model_extrusion, 'support_extrusion_mm': support_extrusion, 'support_extrusion_fraction': support_extrusion / total if total else 0., 'estimates': estimates}


def render_preview(gcode, output_png, max_segments=120000):
    """PNG reflects real G-code deposition; metrics scan every movement.

    Plot storage is capped; bounds include exact circular extrema independent of
    display subdivision. Firmware macros and physical extrusion are not simulated.
    """
    gcode = Path(gcode).resolve(strict=True)
    output_png = Path(output_png).resolve()
    if gcode.stat().st_size > MAX_GCODE_BYTES:
        raise ValueError('G-code exceeds 512 MiB preview limit')
    if isinstance(max_segments, bool) or not 1 <= max_segments <= 250000:
        raise ValueError('Display segment budget must be between 1 and 250000')
    # Parse a private disk snapshot, not a path another process can rewrite
    # during the scan. Its digest is computed from the exact copied bytes.
    # A source A -> B -> A change therefore cannot mix B's metrics with A's hash.
    with tempfile.TemporaryDirectory(prefix='k1-preview-') as temporary:
        snapshot = Path(temporary) / 'snapshot.gcode'
        snapshot_hash, copied = hashlib.sha256(), 0
        with gcode.open('rb') as source, snapshot.open('xb') as destination:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                copied += len(chunk)
                if copied > MAX_GCODE_BYTES:
                    raise ValueError('G-code exceeds 512 MiB preview limit')
                snapshot_hash.update(chunk)
                destination.write(chunk)
        digest = snapshot_hash.hexdigest()
        segments, support, metrics = _scan(snapshot, max_segments)
        if _file_digest(gcode) != digest:
            raise ValueError('G-code changed while its preview was being scanned')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    colors = ['#ed7418' if flag else '#156881' for flag in support]
    data = np.asarray(segments, dtype=np.float32)
    fig = plt.figure(figsize=(14,8), facecolor='white')
    ax = fig.add_subplot(121, projection='3d')
    ax.add_collection3d(Line3DCollection(data, colors=colors, linewidths=.6, alpha=.85))
    bounds = metrics['bounds']
    ax.set_xlim(bounds['x'][0]-1, bounds['x'][1]+1)
    ax.set_ylim(bounds['y'][0]-1, bounds['y'][1]+1)
    ax.set_zlim(min(0, bounds['z'][0]), bounds['z'][1]+1)
    ax.set_box_aspect([max(1, bounds[a][1]-bounds[a][0]) for a in 'xyz'])
    ax.view_init(25, 65)
    ax.set_xlabel('X mm'); ax.set_ylabel('Y mm'); ax.set_zlabel('Z mm')
    ax.set_title('Deposited toolpaths, 3D')
    top = fig.add_subplot(122)
    top.add_collection(LineCollection(data[:, :, :2], colors=colors, linewidths=.45, alpha=.7))
    top.set_xlim(bounds['x'][0]-1, bounds['x'][1]+1)
    top.set_ylim(bounds['y'][0]-1, bounds['y'][1]+1)
    top.set_aspect('equal'); top.set_xlabel('X mm'); top.set_ylabel('Y mm')
    top.set_title('Deposited toolpaths, top projection')
    fig.suptitle('Actual sliced G-code preview', fontsize=16)
    fig.legend(handles=[Line2D([0],[0],color='#156881',label='Model'), Line2D([0],[0],color='#ed7418',label='Support / interface')], loc='upper center', bbox_to_anchor=(.5,.95), ncol=2)
    estimate = metrics['estimates']
    fig.text(.04,.035, f"Slicer estimate: {estimate.get('estimated_time', 'unavailable')} | {estimate.get('filament_g', 'unavailable')} g | {metrics['layer_count']} layers\nDisplay: {len(segments):,} / {metrics['extrusion_segments']:,} segments (deterministic bounded sample). All movements included in metrics.\nFirmware preparation time may be additional. No physical calibration or print is implied.", fontsize=10)
    fig.tight_layout(rect=(0,.12,1,.92))
    if output_png.exists():
        raise FileExistsError('Refusing to replace an existing preview')
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=140)
    plt.close(fig)
    if _file_digest(gcode) != digest:
        raise ValueError('G-code changed while its preview was being rendered')
    metrics.update({'schema_version': 1, 'gcode': str(gcode), 'gcode_sha256': digest, 'sha256': digest, 'preview': str(output_png), 'source': 'actual deposited G0/G1/G2/G3 toolpaths; no model rendering', 'display_segments': len(segments), 'sampling': {'method': 'deterministic reservoir', 'seed': 42, 'max_segments': max_segments, 'metrics_cover_all_movements': True, 'arc_display_step_mm': .25}, 'limitations': ['Firmware macros are not expanded', 'R arcs, non-XY planes and inch units refused', 'Slicer estimates are not measured physical results', 'Displayed paths may be sampled; full bounds and metrics are not sampled']})
    return metrics
