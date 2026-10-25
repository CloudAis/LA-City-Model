"""Blender-side inspection of actual stage08 PBR graphs and textured mesh UVs.

No build, render, shader repair or pass fabrication happens here. The caller
must reopen its saved checkpoint, invoke audit_materials(scene), and require
the three explicit checks before registering stage08 acceptance.
"""
from pathlib import Path
import json
import math

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _upstream_images(socket):
    """Image nodes actually reachable through this socket, rather than orphans."""
    pending = [link.from_node for link in socket.links]
    seen, images = set(), []
    while pending:
        node = pending.pop()
        if node.as_pointer() in seen:
            continue
        seen.add(node.as_pointer())
        if node.bl_idname == 'ShaderNodeTexImage':
            images.append(node)
        else:
            pending.extend(link.from_node for inp in node.inputs for link in inp.links)
    return images


def _actual_image_path(image):
    return Path(bpy.path.abspath(image.filepath, library=image.library)).resolve() if image.filepath else None


def _pixel_stats(image, cache):
    key = image.as_pointer()
    if key not in cache:
        data = np.empty(len(image.pixels), np.float32)
        image.pixels.foreach_get(data)
        count = int(image.size[0])*int(image.size[1])
        if not count or len(data) % count:
            cache[key] = {'finite': False, 'error': 'Image has no valid decoded pixel buffer'}
        else:
            pixels = data.reshape(count, -1)
            normal = pixels[:, :3]*2-1
            cache[key] = {
                'finite': bool(np.isfinite(pixels).all()),
                'min': pixels.min(axis=0).tolist(), 'max': pixels.max(axis=0).tolist(),
                'decoded_pixels': count,
                'normal_z_min': float(normal[:, 2].min()),
                'normal_unit_max_error': float(np.max(np.abs(np.linalg.norm(normal, axis=1)-1))),
            }
    return cache[key]


def _socket_source(socket):
    if len(socket.links) != 1:
        return None, None
    link = socket.links[0]
    return link.from_node, link.from_socket


def audit_materials(scene):
    """Return real graph, image and UV results; all three flags fail on defects."""
    cfg = json.loads((ROOT/'config/stage08.json').read_text())
    config = json.loads((ROOT/'config/stage08_materials.json').read_text())
    registry = json.loads((ROOT/'assets/materials/stage08/registry.json').read_text())['materials']
    pbr_errors, color_errors, uv_errors = [], [], []
    material_records, volume_records, uv_records, image_cache = [], [], [], {}

    def expect(ok, errors, message):
        if not ok:
            errors.append(message)

    # Material libraries include classes that need not occur in either accepted
    # city work window (paint, for example). Do not invent a city use for them.
    library = ROOT/'assets/materials/stage08/material_library.blend'
    library_names, library_classes = [], []
    if library.is_file():
        with bpy.data.libraries.load(str(library), link=False) as (source, target):
            library_names = list(source.materials)
            target.materials = []
        library_classes = sorted(key for key in registry if
                                 'S8_'+key+'_PBR_maps' in library_names and
                                 'S8_'+key+'_PBR_far' in library_names)
        expect(set(library_classes) == set(registry), pbr_errors,
               'Saved material library does not contain both variants of all14 configured classes')
    else:
        pbr_errors.append('Saved14-class material library is missing')

    materials = [m for m in bpy.data.materials if m.name.startswith('S8_')]
    expect(bool(materials), pbr_errors, 'No saved S8 PBR materials were found')
    for mat in materials:
        prefix = mat.name+': '
        # This exact authored finite atmosphere is a volume, not a surface PBR
        # class. Check its actual Volume output and configured physical density
        # rather than exempting arbitrary unclassified S8 shaders.
        if mat.name == 'S8_authored_atmosphere':
            expect(mat.use_nodes and mat.node_tree is not None, pbr_errors,
                   prefix+'volume node tree is missing')
            if not mat.use_nodes or mat.node_tree is None:
                continue
            outputs = [n for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeOutputMaterial' and n.is_active_output]
            scatter = [n for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeVolumeScatter']
            expect(len(outputs) == len(scatter) == 1, pbr_errors,
                   prefix+'requires one active output and one Volume Scatter')
            if len(outputs) != 1 or len(scatter) != 1:
                continue
            output, volume = outputs[0], scatter[0]
            source, socket = _socket_source(output.inputs['Volume'])
            expect(source == volume and socket is not None and socket.name == 'Volume', pbr_errors,
                   prefix+'Volume Scatter is not connected directly to active Volume output')
            expect(not output.inputs['Surface'].is_linked, pbr_errors,
                   prefix+'atmosphere unexpectedly has a surface shader')
            density = float(volume.inputs['Density'].default_value)
            anisotropy = float(volume.inputs['Anisotropy'].default_value)
            color = np.asarray(volume.inputs['Color'].default_value, float)
            expect(not volume.inputs['Density'].is_linked and math.isfinite(density) and 0 <= density <= .001,
                   pbr_errors, prefix+'constant density must be finite and between0 and0.001 per metre')
            expect(abs(density-float(cfg['atmosphere_density_per_m'])) < 1e-8, pbr_errors,
                   prefix+'saved density differs from configured authored density')
            expect(not volume.inputs['Anisotropy'].is_linked and math.isfinite(anisotropy) and -1 <= anisotropy <= 1,
                   pbr_errors, prefix+'constant phase anisotropy must be finite and between−1 and1')
            expect(bool(np.isfinite(color).all()) and bool(((color >= 0) & (color <= 1)).all()),
                   pbr_errors, prefix+'volume scatter color is nonfinite or out of range')
            volume_records.append({'name': mat.name, 'class': 'authored finite atmosphere volume',
                                   'density_per_m': density, 'anisotropy': anisotropy,
                                   'scatter_color_linear_rgba': color.tolist(),
                                   'direct_volume_scatter_output': source == volume,
                                   'observed_atmospheric_visibility': False})
            continue
        key = mat.get('stage08_material')
        textured = mat.get('texture_backed')
        if key not in registry:
            pbr_errors.append(prefix+'missing/unknown stage08_material identity')
            continue
        expect(isinstance(textured, bool), pbr_errors, prefix+'texture_backed must be a saved boolean')
        expected = registry[key]
        record = {'name': mat.name, 'class': key, 'texture_backed': bool(textured),
                  'double_sided': not mat.use_backface_culling,
                  'night_emission': bool(mat.get('stage08_night_emission')), 'images': []}
        material_records.append(record)
        expect(mat.use_nodes and mat.node_tree is not None, pbr_errors, prefix+'editable node tree is missing')
        if not mat.use_nodes or mat.node_tree is None:
            continue
        bsdfs = [n for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled']
        expect(len(bsdfs) == 1, pbr_errors, prefix+'requires exactly one Principled surface')
        if len(bsdfs) != 1:
            continue
        bsdf = bsdfs[0]
        outputs = [n for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeOutputMaterial' and n.is_active_output]
        expect(bool(outputs) and any(link.from_node == bsdf for n in outputs for link in n.inputs['Surface'].links),
               pbr_errors, prefix+'Principled surface is not connected to active Material Output')
        wanted_metal = 1.0 if key == 'metal' else 0.0
        metallic = bsdf.inputs['Metallic']
        roughness = bsdf.inputs['Roughness']
        expect(float(expected['metallic']) == wanted_metal, pbr_errors,
               prefix+'registry metallic semantics are inconsistent')
        for name in ('Metallic', 'Roughness', 'IOR', 'Transmission Weight'):
            value = float(bsdf.inputs[name].default_value)
            record[name.lower().replace(' ', '_')+'_default'] = value
            expect(math.isfinite(value), pbr_errors, prefix+name+' is nonfinite')
        if key in ('glass', 'water'):
            wanted_ior = 1.333 if key == 'water' else 1.5
            expect(abs(float(bsdf.inputs['IOR'].default_value)-wanted_ior) <= 1e-4,
                   pbr_errors, prefix+'dielectric IOR differs from configured material')
        if not textured:
            expect(not metallic.is_linked and abs(float(metallic.default_value)-wanted_metal) <= 1e-6,
                   pbr_errors, prefix+'constant material has incorrect metallic value')
            expect(not roughness.is_linked and 0 <= float(roughness.default_value) <= 1,
                   pbr_errors, prefix+'constant material roughness is invalid')
            expect(not bsdf.inputs['Base Color'].is_linked, pbr_errors,
                   prefix+'constant budget variant unexpectedly uses a color texture')
            continue

        maps = expected['maps'][cfg['texture_quality']]
        roles = {'base_color': bsdf.inputs['Base Color'], 'normal': bsdf.inputs['Normal'],
                 'orm': roughness}
        found = {}
        for role, socket in roles.items():
            nodes = _upstream_images(socket)
            expect(len(nodes) == 1, pbr_errors, prefix+role+' must have exactly one actual upstream image')
            if len(nodes) != 1:
                continue
            tex = nodes[0]
            image = tex.image
            expect(image is not None, pbr_errors, prefix+role+' texture node has no image')
            if image is None:
                continue
            packed = bool(image.packed_file or image.packed_files)
            path = _actual_image_path(image)
            exists = packed or (path is not None and path.is_file())
            expect(exists and min(image.size) > 0, pbr_errors, prefix+role+' image is missing or undecoded')
            expect(path == (ROOT/maps[role]).resolve(), pbr_errors,
                   prefix+role+' does not use its registered map path')
            wanted_space = 'sRGB' if role == 'base_color' else 'Non-Color'
            expect(image.colorspace_settings.name == wanted_space, color_errors,
                   prefix+role+' image colorspace must be '+wanted_space)
            expect(tex.extension == 'REPEAT' and tex.interpolation == 'Linear', pbr_errors,
                   prefix+role+' sampler differs from REPEAT/Linear convention')
            vector_images = [n for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeUVMap' and n.uv_map == 'PBR_Meters']
            expect(bool(vector_images), uv_errors, prefix+role+' has no PBR_Meters UV node')
            mapping, _ = _socket_source(tex.inputs['Vector'])
            expect(mapping is not None and mapping.bl_idname == 'ShaderNodeMapping', uv_errors,
                   prefix+role+' image is not driven by the metre mapping node')
            if mapping is not None and mapping.bl_idname == 'ShaderNodeMapping':
                uvnode, _ = _socket_source(mapping.inputs['Vector'])
                expect(uvnode is not None and uvnode.bl_idname == 'ShaderNodeUVMap' and uvnode.uv_map == 'PBR_Meters',
                       uv_errors, prefix+role+' mapping is not connected to PBR_Meters')
                scale = np.asarray(mapping.inputs['Scale'].default_value)
                tile = np.asarray(expected['tile_size_m'], float)
                wanted = np.ones(3) if key == 'leaf' else np.array([1/tile[0], 1/tile[1], 1])
                expect(np.max(np.abs(scale-wanted)) < 1e-5, uv_errors,
                       prefix+role+' tile scale differs from registered physical metres')
            stats = _pixel_stats(image, image_cache) if exists and min(image.size) > 0 else {'finite': False}
            expect(stats['finite'], pbr_errors, prefix+role+' image has nonfinite/invalid decoded pixels')
            info = {'role': role, 'name': image.name, 'path': str(path) if path else None,
                    'packed': packed, 'colorspace': image.colorspace_settings.name,
                    'size': list(image.size), 'decoded_pixel_checks': stats}
            record['images'].append(info)
            found[role] = tex

        split, output = _socket_source(metallic)
        rough_split, rough_output = _socket_source(roughness)
        expect(split is not None and split.bl_idname == 'ShaderNodeSeparateColor' and
               output.name == 'Blue' and rough_split == split and rough_output.name == 'Green',
               pbr_errors, prefix+'ORM metallic/roughness must use B/G of the same RGB separator')
        if split is not None and split.bl_idname == 'ShaderNodeSeparateColor':
            image_nodes = _upstream_images(split.inputs['Color'])
            expect(len(image_nodes) == 1 and image_nodes[0] == found.get('orm'), pbr_errors,
                   prefix+'metallic and roughness do not share the registered ORM image')
        if 'orm' in found and found['orm'].image:
            stats = _pixel_stats(found['orm'].image, image_cache)
            if stats.get('finite'):
                expect(abs(stats['min'][2]-wanted_metal) < .0041 and abs(stats['max'][2]-wanted_metal) < .0041,
                       pbr_errors, prefix+'actual ORM.B pixel values violate dielectric/metal semantics')
        normal, _ = _socket_source(bsdf.inputs['Normal'])
        expect(normal is not None and normal.bl_idname == 'ShaderNodeNormalMap' and
               normal.space == 'TANGENT' and normal.uv_map == 'PBR_Meters',
               pbr_errors, prefix+'normal must use a tangent Normal Map with PBR_Meters UV')
        expect('OpenGL' in str(mat.get('normal_convention', '')) and '+Y' in str(mat.get('normal_convention', '')),
               pbr_errors, prefix+'OpenGL +Y normal convention metadata missing')
        if normal is not None and normal.bl_idname == 'ShaderNodeNormalMap':
            raw, socket = _socket_source(normal.inputs['Color'])
            expect(raw == found.get('normal') and socket is not None and socket.name == 'Color',
                   pbr_errors, prefix+'normal image uses unexpected channel inversion or transform')
        if 'normal' in found and found['normal'].image:
            stats = _pixel_stats(found['normal'].image, image_cache)
            if stats.get('finite'):
                expect(stats['normal_z_min'] >= -.01 and stats['normal_unit_max_error'] < .025,
                       pbr_errors, prefix+'decoded tangent normals are nonunit or point below surface')
        # Check every emissive texture if future variants use one. Constant
        # linear-color emission is legitimate for the authored night states.
        for tex in _upstream_images(bsdf.inputs['Emission Color']):
            expect(tex.image is not None and tex.image.colorspace_settings.name == 'sRGB', color_errors,
                   prefix+'emissive color texture must be sRGB')
        if key == 'leaf':
            clip, _ = _socket_source(bsdf.inputs['Alpha'])
            expect(clip is not None and clip.bl_idname == 'ShaderNodeMath' and clip.operation == 'GREATER_THAN',
                   pbr_errors, prefix+'leaf alpha is not a binary Greater Than mask')
            if clip is not None and clip.bl_idname == 'ShaderNodeMath':
                alpha_tex, alpha_socket = _socket_source(clip.inputs[0])
                expect(alpha_tex == found.get('base_color') and alpha_socket is not None and alpha_socket.name == 'Alpha' and
                       abs(float(clip.inputs[1].default_value)-expected.get('alpha_cutoff', .4)) < 1e-6,
                       pbr_errors, prefix+'leaf mask does not use registered base alpha and cutoff')
            expect(not mat.use_backface_culling, pbr_errors, prefix+'leaf mask must be double sided')

    seen_uv = set()
    for ob in scene.objects:
        if ob.type != 'MESH' or not len(ob.data.polygons):
            continue
        effective = [slot.material for slot in ob.material_slots]
        textured_slots = {i for i, mat in enumerate(effective) if mat is not None and
                          mat.name.startswith('S8_') and mat.get('texture_backed') is True}
        if not textured_slots:
            continue
        leaf_slots = {i for i in textured_slots if effective[i].get('stage08_material') == 'leaf'}
        mesh = ob.data
        identity = (mesh.as_pointer(), tuple(sorted(textured_slots)), tuple(sorted(leaf_slots)))
        if identity in seen_uv:
            continue
        seen_uv.add(identity)
        layer = mesh.uv_layers.get('PBR_Meters')
        if layer is None:
            uv_errors.append(ob.name+': textured geometry lacks PBR_Meters UV layer')
            continue
        coords = np.empty(len(mesh.vertices)*3, np.float32)
        mesh.vertices.foreach_get('co', coords)
        coords = coords.reshape(-1, 3)
        uv = np.empty(len(mesh.loops)*2, np.float32)
        layer.data.foreach_get('uv', uv)
        uv = uv.reshape(-1, 2)
        if not np.isfinite(uv).all():
            uv_errors.append(ob.name+': UV coordinates contain nonfinite values')
            continue
        mesh.calc_loop_triangles()
        count = len(mesh.loop_triangles)
        vertices = np.empty(count*3, np.int32)
        loops = np.empty(count*3, np.int32)
        mi = np.empty(count, np.int32)
        mesh.loop_triangles.foreach_get('vertices', vertices)
        mesh.loop_triangles.foreach_get('loops', loops)
        mesh.loop_triangles.foreach_get('material_index', mi)
        vertices, loops = vertices.reshape(-1, 3), loops.reshape(-1, 3)
        selected = np.flatnonzero(np.isin(mi, list(textured_slots)))
        collapsed = stretch = relevant = leaves = 0
        minimum, maximum = math.inf, -math.inf
        for batch in np.array_split(selected, max(1, math.ceil(len(selected)/65536))):
            xyz = coords[vertices[batch]].astype(float)
            q = uv[loops[batch]].astype(float)
            area3d = np.linalg.norm(np.cross(xyz[:, 1]-xyz[:, 0], xyz[:, 2]-xyz[:, 0]), axis=1)/2
            area_uv = np.abs((q[:, 1, 0]-q[:, 0, 0])*(q[:, 2, 1]-q[:, 0, 1])-
                             (q[:, 1, 1]-q[:, 0, 1])*(q[:, 2, 0]-q[:, 0, 0]))/2
            real = area3d > 1e-10
            collapsed += int((real & (area_uv <= 1e-12)).sum())
            leaf = np.isin(mi[batch], list(leaf_slots))
            leaves += int(leaf.sum())
            metric = (area3d > 1e-7) & ~leaf
            if metric.any():
                ratios = area_uv[metric]/area3d[metric]
                relevant += len(ratios)
                minimum, maximum = min(minimum, float(ratios.min())), max(maximum, float(ratios.max()))
                stretch += int(((ratios < .50) | (ratios > 1.05)).sum())
        record = {'object': ob.name, 'mesh': mesh.name, 'textured_triangles': len(selected),
                  'finite_uv': True, 'collapsed_uv_triangles': collapsed,
                  'substantial_metre_projection_triangles': relevant,
                  'metre_projected_area_ratio_min': minimum if relevant else None,
                  'metre_projected_area_ratio_max': maximum if relevant else None,
                  'unexpected_metre_projection_stretch_triangles': stretch,
                  'single_leaf_normalized_uv_triangles': leaves,
                  'intentional_hard_corner_uv_seams': True}
        uv_records.append(record)
        expect(collapsed == 0, uv_errors, ob.name+f': {collapsed} textured triangles have collapsed UVs')
        expect(stretch == 0, uv_errors, ob.name+f': {stretch} triangles exceed documented dominant-plane metre projection range')
    expect(bool(uv_records), uv_errors, 'No actual textured mesh UVs were checked')

    return {
        'pbr_material_checks_passed': not pbr_errors,
        'uv_checks_passed': not uv_errors,
        'color_space_checks_passed': not color_errors,
        'material_audit': {
            'materials_checked': len(material_records), 'images_decoded_and_checked': len(image_cache),
            'volume_materials_checked': len(volume_records), 'volume_materials': volume_records,
            'library_classes': library_classes, 'library_material_names': library_names,
            'textured_mesh_variants_checked': len(uv_records),
            'materials': material_records, 'uv_meshes': uv_records,
            'errors': {'pbr': pbr_errors, 'uv': uv_errors, 'color_space': color_errors},
            'validation_limits': [
                'These tests validate saved shader links, decoded texture data and UV geometry; they are not measured material reflectance or architectural survey verification.',
                'OpenGL +Y is checked through a direct, uninverted image-to-Blender tangent Normal Map path and registered convention; physical derivative-sign correctness is separately established by the texture generator.',
                'Nonleaf UV area ratios use substantial triangles and permit0.50..1.05 for dominant-plane projection; normalized individual-leaf UVs deliberately have a different physical area ratio.',
                'This scene audit does not certify GLB alpha ordering, runtime normal appearance or cross-renderer color equality; actual export/reimport and browser checks remain required.',
            ],
        },
    }
