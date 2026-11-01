"""Geometry-only STL/3MF loading with bounded archive traversal.

Embedded slicer settings, scripts and G-code are never extracted or executed.
"""
from pathlib import Path, PurePosixPath
import math
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
import trimesh

CORE = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
PRODUCTION = '{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}'
UNITS = {'micron': .001, 'millimeter': 1., 'centimeter': 10., 'inch': 25.4, 'foot': 304.8, 'meter': 1000.}
MAX_SOURCE_BYTES = 128 * 1024 * 1024
MAX_XML_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_VERTICES = 2_000_000
MAX_FACES = 4_000_000


def _matrix(value):
    matrix = np.eye(4)
    if value:
        try:
            values = np.asarray([float(x) for x in value.split()])
            if values.shape != (12,):
                raise ValueError('3MF transform must contain twelve numbers')
            matrix[:, :3] = values.reshape(4, 3)
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid 3MF transform') from exc
    if not np.isfinite(matrix).all() or abs(np.linalg.det(matrix[:3, :3])) < 1e-15:
        raise ValueError('Non-finite or singular 3MF transform')
    return matrix


def _archive_path(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('External or malformed 3MF reference')
    path = PurePosixPath(value.lstrip('/'))
    if '..' in path.parts or path.as_posix().startswith('/'):
        raise ValueError('Archive traversal is not allowed')
    return path.as_posix()


def _load_3mf(source):
    meshes, transforms, cache = [], [], {}
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(entries) > 5000 or len(set(names)) != len(names):
            raise ValueError('Too many or duplicate archive entries')
        total = 0
        for entry in entries:
            _archive_path(entry.filename)
            total += entry.file_size
            if entry.flag_bits & 1 or entry.file_size > MAX_XML_BYTES or total > MAX_ARCHIVE_BYTES:
                raise ValueError('Encrypted or oversized 3MF archive')
            if entry.file_size > max(1024 * 1024, entry.compress_size * 1000):
                raise ValueError('Excessive archive compression ratio')
        def document(path):
            if path not in cache:
                if path not in names or not path.lower().endswith('.model'):
                    raise ValueError('Missing internal 3MF model reference')
                raw = archive.read(path)
                if b'\x00' in raw or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
                    raise ValueError('Only UTF-8 XML without DTD/entity declarations is supported')
                try:
                    root = ET.fromstring(raw)
                except ET.ParseError as exc:
                    raise ValueError('Invalid 3MF XML') from exc
                if root.tag != CORE + 'model' or root.get('unit', 'millimeter') not in UNITS:
                    raise ValueError('Unsupported 3MF model or unit')
                objects = {}
                for obj in root.findall(CORE + 'resources/' + CORE + 'object'):
                    oid = obj.get('id')
                    if not oid or not oid.isdigit() or oid in objects:
                        raise ValueError('Invalid or duplicate object identifier')
                    objects[oid] = obj
                cache[path] = (root, objects, UNITS[root.get('unit', 'millimeter')])
            return cache[path]
        instance_count = [0]
        vertex_count, face_count = [0], [0]
        def walk(path, oid, parent, stack):
            key = (path, oid)
            if key in stack or len(stack) >= 64:
                raise ValueError('Cyclic or excessive 3MF component nesting')
            instance_count[0] += 1
            if instance_count[0] > 256:
                raise ValueError('Too many 3MF instances')
            _, objects, unit = document(path)
            if oid not in objects:
                raise ValueError('Unknown component object')
            obj = objects[oid]
            mesh = obj.find(CORE + 'mesh')
            if mesh is not None:
                vertices_xml = mesh.findall(CORE + 'vertices/' + CORE + 'vertex')
                triangles_xml = mesh.findall(CORE + 'triangles/' + CORE + 'triangle')
                vertex_count[0] += len(vertices_xml)
                face_count[0] += len(triangles_xml)
                if vertex_count[0] > MAX_VERTICES or face_count[0] > MAX_FACES:
                    raise ValueError('Geometry exceeds supported complexity')
                try:
                    vertices = np.asarray([[float(v.get(k)) for k in ('x','y','z')] for v in vertices_xml])
                    faces = np.asarray([[int(t.get(k)) for k in ('v1','v2','v3')] for t in triangles_xml])
                except (TypeError, ValueError) as exc:
                    raise ValueError('Malformed 3MF geometry') from exc
                if vertices.ndim != 2 or vertices.shape[1:] != (3,) or faces.ndim != 2 or faces.shape[1:] != (3,) or not len(faces):
                    raise ValueError('Empty or malformed mesh')
                if not np.isfinite(vertices).all() or np.min(faces) < 0 or np.max(faces) >= len(vertices):
                    raise ValueError('Non-finite vertices or invalid triangle index')
                vertices = (np.column_stack((vertices, np.ones(len(vertices)))) @ parent)[:, :3]
                if np.linalg.det(parent[:3, :3]) < 0:
                    faces = faces[:, ::-1]
                meshes.append(trimesh.Trimesh(vertices, faces, process=False))
                transforms.append({'model': path, 'object': oid, 'row_matrix_mm': parent.tolist()})
            for component in obj.findall(CORE + 'components/' + CORE + 'component'):
                ref = component.get(PRODUCTION + 'path')
                child_path = _archive_path(ref) if ref else path
                _, _, child_unit = document(child_path)
                change_units = np.diag([child_unit / unit] * 3 + [1.])
                walk(child_path, component.get('objectid'), change_units @ _matrix(component.get('transform')) @ parent, stack + (key,))
        root, _, unit = document('3D/3dmodel.model')
        scale_units = np.diag([unit] * 3 + [1.])
        for item in root.findall(CORE + 'build/' + CORE + 'item'):
            if item.get('printable', '1') in ('0','false'):
                continue
            walk('3D/3dmodel.model', item.get('objectid'), _matrix(item.get('transform')) @ scale_units, ())
    if not meshes:
        raise ValueError('No printable mesh instances found')
    return trimesh.util.concatenate(meshes), {'geometry_only': True, 'assembly_transforms': transforms, 'source_units': root.get('unit', 'millimeter')}


def load_geometry(source):
    """Return a millimeter mesh and extraction provenance; never import slicer state."""
    source = Path(source).expanduser().resolve(strict=True)
    if source.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError('Source file exceeds 128 MiB limit')
    if source.suffix.lower() == '.3mf':
        mesh, info = _load_3mf(source)
    elif source.suffix.lower() == '.stl':
        mesh = trimesh.load(source, force='mesh', process=False)
        info = {'geometry_only': True, 'source_units': 'millimeter (STL convention)', 'assembly_transforms': []}
    else:
        raise ValueError('Only STL and geometry-only 3MF sources are supported')
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.vertices) > MAX_VERTICES or len(mesh.faces) > MAX_FACES or not len(mesh.faces):
        raise ValueError('Empty or oversized geometry')
    if not np.isfinite(mesh.vertices).all() or not np.isfinite(mesh.extents).all() or np.any(mesh.extents <= 0):
        raise ValueError('Geometry must have finite coordinates and three positive dimensions')
    mesh.merge_vertices()
    if not np.isfinite(mesh.vertices).all() or not np.isfinite(mesh.extents).all() or np.any(mesh.extents <= 0):
        raise ValueError('Vertex merging collapsed geometry below supported resolution')
    return mesh, info


def prepare_model(source, output_path, height_mm=None):
    mesh, info = load_geometry(source)
    original = mesh.extents.copy()
    factor = 1.
    if height_mm is not None:
        if isinstance(height_mm, bool) or not math.isfinite(float(height_mm)) or not 0 < float(height_mm) <= 250:
            raise ValueError('Requested anatomical height must be between 0 and 250 mm')
        factor = float(height_mm) / original[2]
        if not math.isfinite(factor) or factor <= 0:
            raise ValueError('Requested scale cannot be represented safely')
        mesh.apply_scale(factor)
    mesh.apply_translation(-mesh.bounds[0])
    if not np.isfinite(mesh.vertices).all() or not np.isfinite(mesh.extents).all() or np.any(mesh.extents <= 0):
        raise ValueError('Scaled geometry must retain finite positive dimensions')
    destination = Path(output_path)
    if destination.exists():
        raise FileExistsError('Refusing to replace prepared geometry')
    destination.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(destination, file_type='stl')
    info.update({'source_name': Path(source).name, 'original_dimensions_mm': original.tolist(), 'dimensions_mm': mesh.extents.tolist(), 'uniform_scale': factor, 'vertices': len(mesh.vertices), 'triangles': len(mesh.faces), 'watertight': bool(mesh.is_watertight), 'winding_consistent': bool(mesh.is_winding_consistent), 'height_basis': 'original assembled Z axis; subsequent print orientation does not change anatomical scale', 'physical_print_tested': False})
    return info
