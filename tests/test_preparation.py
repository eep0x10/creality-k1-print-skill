import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/creality-k1-print/scripts'))


def module(name):
    try:
        return importlib.import_module('k1print.' + name)
    except ImportError:
        return None


def write_3mf(path, *, transform='1 0 0 0 1 0 0 0 1 10 20 30', component=None, unit='millimeter'):
    core='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
    if component is None:
        body='<mesh><vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="2" z="0"/><vertex x="0" y="0" z="3"/></vertices><triangles><triangle v1="0" v2="2" v3="1"/><triangle v1="0" v2="1" v3="3"/><triangle v1="1" v2="2" v3="3"/><triangle v1="2" v2="0" v3="3"/></triangles></mesh>'
    else:
        body=component
    xml=f'<model xmlns="{core}" unit="{unit}"><resources><object id="1" type="model">{body}</object></resources><build><item objectid="1" transform="{transform}"/></build></model>'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('3D/3dmodel.model',xml)
        z.writestr('Metadata/unsafe.gcode','M112\n')


def fake_profiles(root):
    d=root/'resources/profiles/Creality'
    profiles={
      'machine/common':{'type':'machine','name':'common','machine_start_gcode':'START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single]','machine_end_gcode':'END_PRINT','printable_area':['0x0','220x0','220x220','0x220'],'nozzle_diameter':['0.4']},
      'machine/k1':{'type':'machine','name':'Creality K1 (0.4 nozzle)','inherits':'common','printer_model':'Creality K1','printable_height':'250'},
      'process/base':{'type':'process','name':'process base','wall_loops':'2','enable_support':'0'},
      'process/k1':{'type':'process','name':'0.20mm Standard @Creality K1 (0.4 nozzle)','inherits':'process base','layer_height':'0.2'},
      'filament/pla':{'type':'filament','name':'Creality Generic PLA @K1-all','nozzle_temperature':['220'],'textured_plate_temp':['55']}}
    for rel,data in profiles.items():
        p=d/(rel+'.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data))
    return root/'resources'


class ModelTests(unittest.TestCase):
    def test_vertex_merge_collapse_cannot_generate_nonfinite_scaled_stl(self):
        m=module('model');self.assertIsNotNone(m,'geometry preparation module missing')
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);source=r/'tiny.3mf';write_3mf(source,transform='1 0 0 0 1 0 0 0 1 0 0 0')
            with zipfile.ZipFile(source) as z:xml=z.read('3D/3dmodel.model').decode()
            xml=xml.replace('x="1"','x="0.0000000001"').replace('y="2"','y="0.0000000002"').replace('z="3"','z="0.0000000003"')
            with zipfile.ZipFile(source,'w') as z:z.writestr('3D/3dmodel.model',xml)
            with self.assertRaises(ValueError):m.load_geometry(source)
            with self.assertRaises(ValueError):m.prepare_model(source,r/'invalid.stl',height_mm=60)
            self.assertFalse((r/'invalid.stl').exists())

    def test_utf16_dtd_cannot_bypass_entity_guard(self):
        m=module('model');self.assertIsNotNone(m,'geometry preparation module missing')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'entity.3mf';write_3mf(p)
            with zipfile.ZipFile(p) as z:xml=z.read('3D/3dmodel.model').decode()
            xml='<!DOCTYPE model [<!ENTITY x "0">]>'+xml
            with zipfile.ZipFile(p,'w') as z:z.writestr('3D/3dmodel.model',xml.encode('utf-16'))
            with self.assertRaises(ValueError):m.load_geometry(p)

    def test_nested_production_component_rotation_is_preserved(self):
        m=module('model');self.assertIsNotNone(m,'geometry preparation module missing')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'assembly.3mf';write_3mf(p)
            with zipfile.ZipFile(p) as z:child=z.read('3D/3dmodel.model')
            core='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
            root=f'<model xmlns="{core}" xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"><resources><object id="7"><components><component objectid="1" p:path="/3D/Objects/part.model" transform="0 1 0 -1 0 0 0 0 1 1 2 3"/></components></object></resources><build><item objectid="7" transform="1 0 0 0 1 0 0 0 1 10 20 30"/></build></model>'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('3D/3dmodel.model',root);z.writestr('3D/Objects/part.model',child)
            mesh,info=m.load_geometry(p)
            self.assertEqual(list(mesh.bounds[0]),[9,22,33]);self.assertEqual(list(mesh.extents),[2,1,3]);self.assertEqual(len(info['assembly_transforms']),1)

    def test_geometry_only_units_transform_and_uniform_scaling(self):
        m=module('model');self.assertIsNotNone(m,'geometry preparation module missing')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.3mf';write_3mf(source,unit='centimeter')
            mesh,info=m.load_geometry(source)
            self.assertEqual(list(mesh.bounds[0]),[100,200,300])
            self.assertEqual(list(mesh.extents),[10,20,30])
            report=m.prepare_model(source,root/'scaled.stl',height_mm=60)
            self.assertEqual(report['dimensions_mm'],[20,40,60])
            self.assertTrue(report['watertight']);self.assertEqual(report['uniform_scale'],2)
            self.assertFalse((root/'unsafe.gcode').exists())

    def test_component_cycle_and_external_reference_rejected(self):
        m=module('model');self.assertIsNotNone(m,'geometry preparation module missing')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,body in [('cycle','<components><component objectid="1"/></components>'),('external','<components xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"><component objectid="1" p:path="https://invalid.example/a.model"/></components>')]:
                p=root/(name+'.3mf');write_3mf(p,component=body)
                with self.assertRaises(ValueError):m.load_geometry(p)

    def test_malicious_xml_and_nonfinite_transform_rejected(self):
        m=module('model');self.assertIsNotNone(m,'geometry preparation module missing')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.3mf';write_3mf(p,transform='nan 0 0 0 1 0 0 0 1 0 0 0')
            with self.assertRaises(ValueError):m.load_geometry(p)
            with zipfile.ZipFile(p,'w') as z:z.writestr('3D/3dmodel.model','<!DOCTYPE model [<!ENTITY a "bad">]><model/>')
            with self.assertRaises(ValueError):m.load_geometry(p)


class ProfileTests(unittest.TestCase):
    def test_inheritance_priorities_and_no_source_mutation(self):
        m=module('profiles');self.assertIsNotNone(m,'profiles module missing')
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);resources=fake_profiles(r);cfg={'orca_path':str(r/'fake-orca'),'orca_resources':str(resources)}
            before={p:p.read_bytes() for p in resources.rglob('*.json')}
            robust=m.prepare_profiles(cfg,r/'robust','robust','detailed');economy=m.prepare_profiles(cfg,r/'economy','economy','fast')
            a=json.loads(Path(robust['process']).read_text());b=json.loads(Path(economy['process']).read_text())
            self.assertGreater(int(a['wall_loops']),int(b['wall_loops']));self.assertLess(float(a['layer_height']),float(b['layer_height']));self.assertNotIn('inherits',a)
            machine=json.loads(Path(robust['machine']).read_text());self.assertTrue(machine['machine_start_gcode'].startswith('START_PRINT'))
            self.assertEqual(before,{p:p.read_bytes() for p in resources.rglob('*.json')})

    def test_profile_inheritance_cycle_rejected(self):
        m=module('profiles');self.assertIsNotNone(m,'profiles module missing')
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);res=fake_profiles(r);p=res/'profiles/Creality/machine/common.json';d=json.loads(p.read_text());d['inherits']='Creality K1 (0.4 nozzle)';p.write_text(json.dumps(d))
            with self.assertRaises(ValueError):m.prepare_profiles({'orca_resources':str(res)},r/'out')


class PreviewTests(unittest.TestCase):
    def test_source_mutation_after_scan_cannot_receive_new_hash(self):
        from unittest.mock import patch
        m=module('preview');self.assertIsNotNone(m,'preview module missing')
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);g=r/'actual.gcode';g.write_text('G90\nM83\nG0 X10 Y10 Z0.2\nG1 X20 E1\n')
            original_scan=m._scan
            def mutate_after_scan(path,budget):
                result=original_scan(path,budget)
                g.write_text('G90\nM83\nG0 X110 Y10 Z0.2\nG1 X120 E1\n')
                return result
            with patch.object(m,'_scan',side_effect=mutate_after_scan):
                with self.assertRaisesRegex(ValueError,'changed'):
                    m.render_preview(g,r/'preview.png')
            self.assertFalse((r/'preview.png').exists())

    def test_scan_uses_snapshot_even_when_source_changes_then_restores(self):
        from unittest.mock import patch
        import hashlib
        m=module('preview');self.assertIsNotNone(m,'preview module missing')
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);g=r/'actual.gcode';old=b'G90\nM83\nG0 X10 Y10 Z0.2\nG1 X20 E1\n';g.write_bytes(old)
            original_scan=m._scan
            def mutate_and_restore(path,budget):
                g.write_bytes(old.replace(b'X10',b'X110').replace(b'X20',b'X120'))
                try:return original_scan(path,budget)
                finally:g.write_bytes(old)
            with patch.object(m,'_scan',side_effect=mutate_and_restore):
                report=m.render_preview(g,r/'preview.png')
            self.assertEqual(report['bounds']['x'],[10,20])
            self.assertEqual(report['gcode_sha256'],hashlib.sha256(old).hexdigest())

    def test_true_gcode_full_circles_support_bounds_and_hash(self):
        m=module('preview');self.assertIsNotNone(m,'preview module missing')
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);g=r/'actual.gcode';g.write_text('G90\nM83\nG1 X10 Y0 Z0.2 E1\n;TYPE:Support interface\nG2 X10 Y0 I-5 J0 E2\nG3 X10 Y0 I-5 J0 E2\n; estimated printing time (normal mode) = 1m 2s\n; total filament used [g] = 0.1\n')
            report=m.render_preview(g,r/'preview.png',max_segments=30)
            self.assertTrue((r/'preview.png').stat().st_size>1000)
            self.assertLessEqual(report['display_segments'],30);self.assertGreater(report['support_segments'],20)
            self.assertAlmostEqual(report['bounds']['y'][0],-5,places=5);self.assertAlmostEqual(report['bounds']['y'][1],5,places=5)
            self.assertEqual(report['estimates']['filament_g'],'0.1')
            self.assertEqual(len(report['gcode_sha256']),64)

    def test_unsupported_plane_and_radius_arc_rejected(self):
        m=module('preview');self.assertIsNotNone(m,'preview module missing')
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp)
            for n,code in [('plane','G18\nG1 X1 Z1 E1'),('radius','M83\nG1 X10 Z0.2 E1\nG2 X20 R10 E1'),('multiturn','M83\nG1 X10 Z0.2 E1\nG2 X10 Y0 I-5 J0 P2 E1')]:
                g=r/(n+'.gcode');g.write_text(code)
                with self.assertRaises(ValueError):m.render_preview(g,r/(n+'.png'))


class SlicingTests(unittest.TestCase):
    def test_malformed_slicer_output_is_rejected_before_preview_approval(self):
        m=module('slicing');self.assertIsNotNone(m,'slicing module missing')
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);res=fake_profiles(r);source=r/'source.3mf';write_3mf(source)
            fake=r/'fake.py';fake.write_text('import sys,pathlib\na=sys.argv[1:]\no=pathlib.Path(a[a.index("--outputdir")+1]);o.mkdir(exist_ok=True)\n(o/"plate_1.gcode").write_text("G90\\nM83\\nG1 X10 Y0 Z0.2 E1\\n")\n')
            with self.assertRaises(ValueError):
                m.prepare_job(source,r/'job',{'orca_path':str(fake),'orca_resources':str(res)})
            self.assertFalse((r/'job/job.json').exists());self.assertFalse((r/'job/preview.png').exists())

    def test_fake_cli_spaces_manifest_hashes_and_no_shell(self):
        m=module('slicing');self.assertIsNotNone(m,'slicing module missing')
        import hashlib
        with tempfile.TemporaryDirectory(prefix='k1 shell & spaces ') as tmp:
            r=Path(tmp);res=fake_profiles(r);source=r/'source.3mf';write_3mf(source)
            fake=r/'fake orca.py';fake.write_text('import sys,pathlib\na=sys.argv[1:]\no=pathlib.Path(a[a.index("--outputdir")+1]);o.mkdir(exist_ok=True)\n(o/"plate_1.gcode").write_text("START_PRINT EXTRUDER_TEMP=220 BED_TEMP=55\\nG90\\nM83\\nG1 X10 Y0 Z0.2 F1200\\nG1 X10 Y10 E1\\nEND_PRINT\\n; total filament used [g] = 0.1\\n")\n')
            result=m.prepare_job(source,r/'job & safe',{'orca_path':str(fake),'orca_resources':str(res)},height_mm=30)
            self.assertEqual(result['schema_version'],1);self.assertEqual(result['settings']['strength'],'balanced')
            for key in ['gcode','preview','preview_report']:
                p=Path(result[key]);self.assertFalse(p.is_absolute());artifact=(r/'job & safe')/p;self.assertTrue(artifact.is_file());self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(),result[key+'_sha256'])
            self.assertEqual(json.loads(((r/'job & safe')/'job.json').read_text()),result)
            with self.assertRaises((ValueError,FileExistsError)):m.prepare_job(source,r/'job & safe',{'orca_path':str(fake),'orca_resources':str(res)})

if __name__=='__main__':unittest.main()
