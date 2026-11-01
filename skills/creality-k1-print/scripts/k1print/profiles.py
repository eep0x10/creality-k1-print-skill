"""Derive local K1 presets from the user's own installed Orca resources."""
from pathlib import Path
import json

STRENGTH = {'economy': (2, '8%'), 'balanced': (3, '12%'), 'robust': (4, '25%')}
FINISH = {'fast': ('0.24', '90', '40'), 'balanced': ('0.16', '60', '35'), 'detailed': ('0.12', '45', '30')}


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
