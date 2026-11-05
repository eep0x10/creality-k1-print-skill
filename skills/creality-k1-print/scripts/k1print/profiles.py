"""Derive local K1 presets from the user's own installed Orca resources."""
from pathlib import Path
import hashlib
import json
import math

from .validation import ValidationError

STRENGTH = {'economy': (2, '8%'), 'balanced': (3, '12%'), 'robust': (4, '25%')}
FINISH = {'fast': ('0.24', '90', '40'), 'balanced': ('0.16', '60', '35'), 'detailed': ('0.12', '45', '30')}


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError('Duplicate custom profile JSON key')
        result[key] = value
    return result


def _finite_profile(value):
    if isinstance(value, dict):
        if 'inherits' in value:
            raise ValidationError('Custom profiles must be flattened; inherits is unsupported')
        for key, item in value.items():
            if key in {'post_process', 'post_process_script', 'post_process_scripts'} and item not in (None, '', []) and not (isinstance(item, list) and all(entry == '' for entry in item)):
                raise ValidationError('Custom profile host post-processing is unsupported')
            _finite_profile(item)
    elif isinstance(value, list):
        for item in value:
            _finite_profile(item)
    elif isinstance(value, (float, str)):
        try:
            number = float(value)
        except ValueError:
            return
        if not math.isfinite(number):
            raise ValidationError('Non-finite custom profile value')


def _number(data, key, array=False):
    value = data.get(key)
    if value is None:
        return None
    if array:
        if not isinstance(value, list) or len(value) != 1:
            raise ValidationError('Custom profiles require one filament/extruder setting')
        value = value[0]
    if isinstance(value, bool):
        raise ValidationError('Invalid custom profile numeric setting')
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValidationError('Invalid custom profile numeric setting') from None
    if not math.isfinite(result):
        raise ValidationError('Non-finite custom profile value')
    return result


def import_profiles(source_dir, output_dir):
    """Copy three explicit trusted local presets verbatim into a fresh job.

    Imported presets are candidates, never evidence of physical calibration.
    No inheritance, external postprocessor, executable profile or G-code file
    is imported. The normal final G-code gates still run before any preview.
    """
    source, target = Path(source_dir).expanduser(), Path(output_dir).expanduser()
    for path in (source, target):
        if ';' in str(path) or any(ord(character) < 32 for character in str(path)) or path.is_symlink():
            raise ValidationError('Unsupported custom profile directory path')
    source, target = source.resolve(strict=True), target.resolve()
    if not source.is_dir() or target == source or target.is_relative_to(source):
        raise ValidationError('Custom profile source and destination must be separate directories')
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise FileExistsError('Use a fresh profile destination; existing files are preserved')
    data, snapshots, hashes = {}, {}, {}
    for kind in ('machine', 'process', 'filament'):
        path = source / (kind + '.json')
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            raise ValidationError('Missing, linked or oversized custom profile JSON')
        content = path.read_bytes()
        if len(content) > 2 * 1024 * 1024:
            raise ValidationError('Oversized custom profile JSON')
        try:
            profile = json.loads(content.decode('utf-8-sig'), object_pairs_hook=_strict_object)
        except (UnicodeError, json.JSONDecodeError):
            raise ValidationError('Invalid UTF-8 custom profile JSON') from None
        if not isinstance(profile, dict) or profile.get('type') != kind or not isinstance(profile.get('name'), str) or not profile['name'].strip():
            raise ValidationError('Custom profile type/name does not match its file')
        _finite_profile(profile)
        data[kind], snapshots[kind] = profile, content
        hashes[kind] = hashlib.sha256(content).hexdigest()
    machine, process, filament = (data[kind] for kind in ('machine', 'process', 'filament'))
    if machine.get('printer_model') != 'Creality K1' or machine.get('nozzle_diameter') != ['0.4'] or _number(machine, 'printable_height') != 250 or machine.get('printable_area') is None:
        raise ValidationError('Custom machine must be the original K1, 0.4 mm, 220 x 220 x 250 mm')
    area = machine['printable_area']
    if not isinstance(area, list) or len(area) != 4 or set(area) != {'0x0', '220x0', '220x220', '0x220'}:
        raise ValidationError('Custom machine printable area differs from the original K1')
    if machine.get('gcode_flavor', 'klipper') != 'klipper':
        raise ValidationError('Only Klipper custom machine profiles are supported')
    for field, expected in (('machine_start_gcode', 'START_PRINT'), ('machine_end_gcode', 'END_PRINT')):
        code = machine.get(field)
        if not isinstance(code, str):
            raise ValidationError('Custom machine must preserve maker START_PRINT and END_PRINT')
        commands = [line.split(';', 1)[0].strip().split()[0] for line in code.splitlines() if line.split(';', 1)[0].strip()]
        if commands.count(expected) != 1:
            raise ValidationError('Custom machine must preserve maker START_PRINT and END_PRINT')
    if filament.get('filament_type') != ['PLA']:
        raise ValidationError('Custom filament must explicitly identify single-extruder PLA')
    temperature = _number(filament, 'nozzle_temperature', array=True)
    first_temperature = _number(filament, 'nozzle_temperature_initial_layer', array=True)
    if temperature is None or first_temperature is None or not 170 <= temperature <= 240 or not 170 <= first_temperature <= 240:
        raise ValidationError('Custom PLA nozzle temperatures must be between 170 and 240 C')
    settings = {'profile_source': 'custom', 'physical_calibration': False, 'calibration_status': 'not_verified', 'nozzle_diameter_mm': .4, 'nozzle_temperature_c': temperature, 'initial_nozzle_temperature_c': first_temperature, 'filament_flow_ratio': _number(filament, 'filament_flow_ratio', array=True), 'max_volumetric_speed_mm3_s': _number(filament, 'filament_max_volumetric_speed', array=True), 'layer_height_mm': _number(process, 'layer_height'), 'outer_wall_speed_mm_s': _number(process, 'outer_wall_speed'), 'profile_sha256': hashes}
    # These are supplied profile settings, not measured printer telemetry.
    settings['process_values'] = dict(process)
    settings['filament_values'] = dict(filament)
    provenance = {'source': 'custom', 'source_profiles': {kind: data[kind]['name'] for kind in data}, 'sha256': hashes, 'settings': settings}
    target.mkdir(parents=True, exist_ok=True)
    result = {}
    for kind in data:
        destination = target / (kind + '.json')
        with destination.open('xb') as stream:
            stream.write(snapshots[kind])
        result[kind] = str(destination)
    with (target / 'provenance.json').open('x', encoding='utf-8') as stream:
        json.dump(provenance, stream, indent=2, allow_nan=False)
        stream.write('\n')
    result.update(settings=settings, source_profiles=provenance['source_profiles'], source='custom', sha256=hashes)
    return result


def _resources(config):
    value = config.get('orca_resources')
    if value:
        root = Path(value).expanduser().resolve(strict=True)
    else:
        executable = Path(config.get('orca_path', '')).expanduser().resolve(strict=True)
        root = executable.parent / 'resources'
    directory = root / 'profiles' / 'Creality'
    if not directory.is_dir():
        raise ValueError('Creality Orca profiles not found; set orca_resources to the resources directory')
    return directory


def prepare_profiles(config, output_dir, strength='balanced', finish='balanced'):
    """Write three resolved JSON presets without changing installed presets.

    Returns machine/process/filament paths, settings and source profile names.
    These presets are starting points; they do not constitute spool calibration.
    """
    if strength not in STRENGTH or finish not in FINISH:
        raise ValueError('Unknown strength or finish priority')
    source = _resources(config)
    lookup = {}
    for path in sorted(source.rglob('*.json')):
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Oversized installed profile JSON')
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict) or not isinstance(data.get('name'), str):
            continue
        key = (data.get('type'), data['name'])
        if key in lookup:
            raise ValueError('Duplicate installed preset identity')
        lookup[key] = data
    lineage = {}
    def resolved(kind, name, active=()):
        key = (kind, name)
        if key in active or len(active) >= 64:
            raise ValueError('Cyclic or excessive preset inheritance')
        if key not in lookup:
            raise ValueError('Missing installed profile ancestor: ' + name)
        data = dict(lookup[key])
        base, names = {}, []
        parent = data.pop('inherits', None)
        if parent:
            base, names = resolved(kind, parent, active + (key,))
        base.update(data)
        return base, names + [name]
    identities = {'machine': 'Creality K1 (0.4 nozzle)', 'process': '0.20mm Standard @Creality K1 (0.4 nozzle)', 'filament': 'Creality Generic PLA @K1-all'}
    # Recent releases may use the same machine identity with a different spelling.
    if ('machine', identities['machine']) not in lookup and ('machine', 'Creality K1 0.4 nozzle') in lookup:
        identities['machine'] = 'Creality K1 0.4 nozzle'
    if ('filament', identities['filament']) not in lookup:
        for candidate in ('Creality HF Generic PLA', 'Creality Generic PLA'):
            if ('filament', candidate) in lookup:
                identities['filament'] = candidate
                break
    data = {}
    for kind, name in identities.items():
        data[kind], lineage[kind] = resolved(kind, name)
    machine = data['machine']
    if machine.get('printer_model') != 'Creality K1' or machine.get('nozzle_diameter') != ['0.4']:
        raise ValueError('Only original K1 with a 0.4 mm nozzle is supported')
    walls, infill = STRENGTH[strength]
    layer, outer_speed, small_speed = FINISH[finish]
    data['process'].update({'layer_height': layer, 'initial_layer_print_height': '0.2', 'wall_loops': str(walls), 'sparse_infill_density': infill, 'sparse_infill_pattern': 'gyroid', 'outer_wall_speed': outer_speed, 'inner_wall_speed': '90', 'small_perimeter_speed': small_speed, 'small_perimeter_threshold': '10', 'top_surface_speed': '45' if finish == 'detailed' else '50', 'sparse_infill_speed': '120', 'initial_layer_speed': '30', 'initial_layer_infill_speed': '40', 'enable_support': '1', 'support_type': 'tree(auto)', 'support_style': 'organic', 'support_on_build_plate_only': '1', 'support_threshold_angle': '35', 'support_top_z_distance': '0.2', 'support_bottom_z_distance': '0.2', 'support_object_xy_distance': '0.35', 'support_interface_top_layers': '3', 'brim_type': 'auto_brim', 'brim_width': '5'})
    filament = data['filament']
    filament.update({'filament_max_volumetric_speed': ['12'], 'nozzle_temperature': ['220'], 'nozzle_temperature_initial_layer': ['220']})
    for bed in ('hot_plate_temp', 'textured_plate_temp', 'cool_plate_temp', 'eng_plate_temp'):
        filament[bed] = ['55']
        filament[bed + '_initial_layer'] = ['55']
    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    result = {}
    for kind in identities:
        destination = target / (kind + '.json')
        if destination.exists():
            raise FileExistsError('Refusing to replace a local derived profile')
        destination.write_text(json.dumps(data[kind], indent=2) + '\n', encoding='utf-8')
        result[kind] = str(destination)
    settings = {'strength': strength, 'finish': finish, 'layer_height_mm': float(layer), 'walls': walls, 'infill': infill + ' gyroid', 'nozzle_diameter_mm': .4, 'nozzle_temperature_c': 220, 'bed_temperature_c': 55, 'max_volumetric_speed_mm3_s': 12, 'outer_wall_speed_mm_s': float(outer_speed), 'small_perimeter_speed_mm_s': float(small_speed), 'supports': 'tree(auto), organic, build-plate only; inspect cavities and removability', 'physical_calibration': False}
    result.update(settings=settings, source_profiles=identities, inheritance=lineage)
    (target / 'provenance.json').write_text(json.dumps({'source_profiles': identities, 'inheritance': lineage, 'settings': settings}, indent=2) + '\n', encoding='utf-8')
    return result
