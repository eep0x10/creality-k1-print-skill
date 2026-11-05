"""Synthetic private-preset reuse; no printer or external model is used."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/creality-k1-print/scripts'))
from k1print import profiles, slicing
from test_preparation import write_3mf


def custom_profiles(root):
    root.mkdir()
    data = {
        'machine': {'type': 'machine', 'name': 'Local K1 0.4', 'printer_model': 'Creality K1', 'nozzle_diameter': ['0.4'], 'printable_area': ['0x0', '220x0', '220x220', '0x220'], 'printable_height': '250', 'machine_start_gcode': 'START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single]\nSET_VELOCITY_LIMIT SQUARE_CORNER_VELOCITY=5', 'machine_end_gcode': 'END_PRINT'},
        'process': {'type': 'process', 'name': 'Local finish candidate', 'layer_height': '0.12', 'initial_layer_print_height': '0.2', 'wall_loops': '3', 'sparse_infill_density': '15%', 'sparse_infill_pattern': 'gyroid', 'outer_wall_speed': '40', 'outer_wall_acceleration': '2000', 'enable_support': '0', 'post_process': []},
        'filament': {'type': 'filament', 'name': 'Local PLA candidate', 'filament_type': ['PLA'], 'nozzle_temperature': ['215'], 'nozzle_temperature_initial_layer': ['215'], 'textured_plate_temp': ['55'], 'filament_flow_ratio': ['0.98'], 'filament_max_volumetric_speed': ['12']},
    }
    for kind, value in data.items():
        (root / (kind + '.json')).write_text(json.dumps(value, indent=4) + '\n', encoding='utf-8')
    return root


class CustomProfileTests(unittest.TestCase):
    def test_copy_preserves_exact_bytes_and_records_actual_candidate_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = custom_profiles(root / 'private source')
            before = {path.name: path.read_bytes() for path in source.iterdir()}
            result = profiles.import_profiles(source, root / 'copied')
            for kind in ('machine', 'process', 'filament'):
                self.assertEqual(Path(result[kind]).read_bytes(), before[kind + '.json'])
            self.assertEqual(before, {path.name: path.read_bytes() for path in source.iterdir()})
            self.assertEqual(result['settings']['nozzle_temperature_c'], 215)
            self.assertEqual(result['settings']['filament_flow_ratio'], 0.98)
            self.assertEqual(result['settings']['layer_height_mm'], 0.12)
            self.assertFalse(result['settings']['physical_calibration'])
            provenance = json.loads((root / 'copied/provenance.json').read_text())
            self.assertEqual(provenance['source'], 'custom')
            self.assertEqual(provenance['sha256']['filament'], hashlib.sha256(before['filament.json']).hexdigest())

    def test_bad_profiles_fail_before_slicer(self):
        changes = [
            ('machine', {'printer_model': 'Other printer'}),
            ('machine', {'nozzle_diameter': ['0.6']}),
            ('machine', {'printable_height': '300'}),
            ('machine', {'machine_start_gcode': 'G28'}),
            ('process', {'inherits': ''}),
            ('process', {'type': 'machine'}),
            ('process', {'post_process': ['external-program']}),
            ('process', {'outer_wall_speed': float('nan')}),
            ('process', {'outer_wall_speed': 'inf'}),
            ('filament', {'filament_type': ['PETG']}),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.3mf'
            write_3mf(source)
            executable = root / 'fake.py'
            executable.write_text('raise AssertionError("slicer must not run")')
            for index, (kind, update) in enumerate(changes):
                directory = custom_profiles(root / ('profiles-' + str(index)))
                filename = directory / (kind + '.json')
                data = json.loads(filename.read_text())
                data.update(update)
                filename.write_text(json.dumps(data))
                with self.subTest(update=update), patch('k1print.slicing.subprocess.run') as run:
                    with self.assertRaises(ValueError):
                        slicing.prepare_job(source, root / ('job-' + str(index)), {'orca_path': str(executable)}, profiles_dir=directory)
                    run.assert_not_called()

    def test_missing_malformed_and_duplicate_json_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = custom_profiles(root / 'profiles')
            filename = directory / 'process.json'
            for content in (None, b'{broken', b'{"type":"process","type":"machine"}'):
                if content is None:
                    filename.unlink()
                else:
                    filename.write_bytes(content)
                with self.subTest(content=content), self.assertRaises((ValueError, FileNotFoundError)):
                    profiles.import_profiles(directory, root / 'output')
                self.assertFalse((root / 'output').exists())

    def test_preparation_uses_custom_copies_without_generic_reset(self):
        with tempfile.TemporaryDirectory(prefix='k1 custom & spaces ') as tmp:
            root = Path(tmp)
            source = root / 'source.3mf'
            write_3mf(source)
            directory = custom_profiles(root / 'private profiles')
            fake = root / 'fake orca.py'
            fake.write_text('import sys,json,pathlib\na=sys.argv[1:]\nm,p=a[a.index("--load-settings")+1].split(";")\nf=json.loads(pathlib.Path(a[a.index("--load-filaments")+1]).read_text())\nassert f["nozzle_temperature"]==["215"] and f["filament_flow_ratio"]==["0.98"]\nassert json.loads(pathlib.Path(p).read_text())["layer_height"]=="0.12"\no=pathlib.Path(a[a.index("--outputdir")+1]);o.mkdir(exist_ok=True)\n(o/"plate_1.gcode").write_text("START_PRINT EXTRUDER_TEMP=215 BED_TEMP=55\\nSET_VELOCITY_LIMIT SQUARE_CORNER_VELOCITY=5\\nG90\\nM83\\nG1 X10 Y0 Z0.2 F1200\\nG1 X10 Y10 E1\\nEND_PRINT\\n")\n')
            result = slicing.prepare_job(source, root / 'new job', {'orca_path': str(fake)}, profiles_dir=directory)
            self.assertEqual(result['settings']['profile_source'], 'custom')
            self.assertEqual(result['settings']['nozzle_temperature_c'], 215)
            self.assertNotIn('strength', result['settings'])
            self.assertFalse(result['settings']['physical_calibration'])
            self.assertEqual((root / 'new job/profiles/filament.json').read_bytes(), (directory / 'filament.json').read_bytes())
            self.assertFalse((root / 'new job/receipt.json').exists())

    def test_explicit_priority_and_nonempty_target_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.3mf'
            write_3mf(source)
            directory = custom_profiles(root / 'profiles')
            fake = root / 'fake.py'
            fake.write_text('raise AssertionError()')
            for kwargs in ({'strength': 'balanced'}, {'finish': 'detailed'}):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    slicing.prepare_job(source, root / 'new', {'orca_path': str(fake)}, profiles_dir=directory, **kwargs)
            destination = root / 'existing'
            destination.mkdir()
            (destination / 'receipt.json').write_text('preserve')
            with self.assertRaises((FileExistsError, ValueError)):
                profiles.import_profiles(directory, destination)
            self.assertEqual((destination / 'receipt.json').read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
