"""Run inside Blender; no external Python packages required."""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def args():
    p = argparse.ArgumentParser()
    p.add_argument('--job', required=True)
    p.add_argument('--mode', choices=['build', 'verify-render'], required=True)
    return p.parse_args(sys.argv[sys.argv.index('--') + 1:])


def material(name, color, metallic=0, roughness=.55):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    m['data_class'] = 'artistic_synthetic'
    return m


def box(name, dims, loc, mat, collection, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for c in list(o.users_collection): c.objects.unlink(o)
    collection.objects.link(o)
    if mat: o.data.materials.append(mat)
    o['data_class'] = 'artistic_synthetic'
    if bevel:
        mod = o.modifiers.new('Editable edge highlights', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
        o.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return o


def label(text, loc, size, mat, collection, rotation=(0,0,0)):
    curve = bpy.data.curves.new('Type / ' + text, 'FONT')
    curve.body = text
    curve.size = size
    curve.extrude = .004
    obj = bpy.data.objects.new('Label / ' + text, curve)
    collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = rotation
    curve.materials.append(mat)
    obj['data_class'] = 'artistic_synthetic'
    return obj


def aim(obj, target):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z', 'Y').to_euler()


def build(job):
    cfg = job['config']
    cal = cfg['calibration']
    random.seed(cfg['project']['seed'])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = 'LA / Stage 01 / Metric calibration only'
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = 'METERS'
    scene['data_class'] = 'artistic_synthetic'
    scene['represents_real_city_geometry'] = False
    scene['seed'] = cfg['project']['seed']
    scene['build_fingerprint'] = job['fingerprint']
    scene['selected_region'] = job['region']
    scene['georeference'] = json.dumps(job['origin'])
    scene['coordinate_note'] = 'Calibration at local origin; flat z0 is NOT surveyed terrain.'
    collections = {}
    for name in ['Terrain', 'Buildings', 'Calibration', 'Materials', 'Lights', 'Cameras', 'Assets']:
        c = bpy.data.collections.new(name)
        scene.collection.children.link(c)
        collections[name] = c
    ground = material('Ground / blue slate', (.06,.095,.12))
    stone = material('Facade / warm mineral', (.59,.52,.40))
    trim = material('Frames / chalk', (.82,.81,.73))
    dark = material('Roof and reveals', (.10,.14,.17))
    glass = material('Test glazing / opaque visual proxy', (.065,.21,.28), .45, .22)
    gold = material('Calibration / amber', (.94,.48,.08))
    white = material('Typography / white', (.92,.94,.90))
    red = material('Axis X / grid east', (.85,.15,.1))
    green = material('Axis Y / grid north', (.16,.67,.36))
    blue = material('Axis Z / up', (.1,.4,.95))
    dims = cal['ground_dimensions_m']
    box('Ground_60m_x_50m', dims, (0,0,-dims[2]/2), ground, collections['Terrain'], .08)
    # Grid every five meters; measured scale objects use exact unmodified bounds.
    for x in range(-25,30,5): box('Grid East ' + str(x), (.018,46,.006), (x,0,.004), dark, collections['Calibration'])
    for y in range(-20,25,5): box('Grid North ' + str(y), (56,.018,.006), (0,y,.004), dark, collections['Calibration'])
    dx,dy,dz = cal['building_dimensions_m']
    b = box('TestBuilding_12x18x24m', (dx,dy,dz), (0,2,dz/2), stone, collections['Buildings'], .05)
    b['dimensions_contract_m'] = json.dumps([dx,dy,dz])
    b['synthetic_not_landmark'] = True
    # Repeated elements remain editable; no dependency on external asset textures.
    for floor in range(7):
        z = 2.5 + floor*3
        for x in [-4.5,-1.5,1.5,4.5]:
            box('South frame', (1.85,.14,2.15), (x,-7.10,z), trim, collections['Buildings'], .025)
            box('South glazing proxy', (1.55,.06,1.85), (x,-7.20,z), glass, collections['Buildings'])
        for y in [-5.2,-2.2,.8,3.8,6.8,9.8]:
            box('East frame', (.14,1.85,2.15), (6.10,y,z), trim, collections['Buildings'], .025)
            box('East glazing proxy', (.06,1.55,1.85), (6.20,y,z), glass, collections['Buildings'])
    for z in [0.25,3.9,6.9,9.9,12.9,15.9,18.9,21.9,23.85]:
        box('Facade course / editable', (12.15,18.15,.12), (0,2,z), trim, collections['Buildings'], .02)
    box('Roof inset / visual test', (10.8,16.8,.04), (0,2,24.03), dark, collections['Buildings'])
    box('Roof service enclosure / synthetic', (3,4,1.5), (-2,5,24.8), dark, collections['Buildings'], .08)
    box('Door / simple exterior proxy', (1.7,.08,2.7), (0,-7.25,1.35), dark, collections['Buildings'])
    # Meter ruler: edge endpoints exactly twenty meters apart.
    ruler = box('Ruler_20m', (cal['ruler_length_m'],.6,.08), (0,-14,.04), gold, collections['Calibration'])
    ruler['tick_spacing_m'] = cal['ruler_tick_m']
    for i in range(21):
        x = -10+i
        box('Ruler tick ' + str(i), (.035, 1.0 if i%5 == 0 else .45, .03), (x,-14,.1), white, collections['Calibration'])
        if i%5 == 0: label(str(i), (x-.3,-16,.02), .8, white, collections['Calibration'])
    label('20 METERS / 1 m divisions', (-10,-18,.025), .8, gold, collections['Calibration'])
    # Axis tails at (-21,-8,0); unit vectors retain the Blender/UTM convention.
    start = Vector((-21,-8,.1))
    for axis, direction, mat in [('X', Vector((1,0,0)),red),('Y',Vector((0,1,0)),green),('Z',Vector((0,0,1)),blue)]:
        end = start + direction*cal['axis_length_m']
        dims = [0.10,0.10,0.10]
        dims['XYZ'.index(axis)] = cal['axis_length_m']
        box('Axis_' + axis, dims, (start+end)/2, mat, collections['Calibration'])
        bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=.32, depth=.8, location=end)
        o = bpy.context.object
        o.name = 'Axis_' + axis + '_arrow'
        o.rotation_euler = direction.to_track_quat('Z','Y').to_euler()
        for c in list(o.users_collection):c.objects.unlink(o)
        collections['Calibration'].objects.link(o)
        o.data.materials.append(mat)
        label(axis + (' / EAST' if axis=='X' else ' / NORTH' if axis=='Y' else ' / UP'), tuple(end+Vector((.3,.3,.1))), .7, mat, collections['Calibration'])
    label('LOS ANGELES / 01', (-25,21,.02), 1.5, white, collections['Calibration'])
    label('METRIC CALIBRATION / SYNTHETIC TEST BUILDING', (-25,18.5,.02), .60, gold, collections['Calibration'])
    label('BODY 12 x 18 x 24 m', (9,-8,.02), .7, white, collections['Calibration'])
    camera_data = bpy.data.cameras.new('Calibration orthographic camera')
    camera = bpy.data.objects.new('Camera / inspection', camera_data)
    collections['Cameras'].objects.link(camera)
    camera.location = (56,-72,66)
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = 86
    aim(camera, (0,0,6))
    scene.camera = camera
    sun_data = bpy.data.lights.new('Sun / afternoon test', 'SUN')
    sun = bpy.data.objects.new('Sun', sun_data)
    collections['Lights'].objects.link(sun)
    sun.rotation_euler = (math.radians(25), math.radians(-25), math.radians(-30))
    sun_data.energy = 2.5
    sun_data.angle = math.radians(10)
    area_data = bpy.data.lights.new('Large soft fill', 'AREA')
    area = bpy.data.objects.new('Fill', area_data)
    collections['Lights'].objects.link(area)
    area.location = (10,-20,35)
    aim(area,(0,0,8))
    area_data.energy = 2200
    area_data.shape = 'DISK'
    area_data.size = 25
    scene.world = bpy.data.worlds.new('Blue ambient world')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.16,.22,.31,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .5
    scene.render.engine = 'CYCLES'
    scene.cycles.device = cfg['build']['device']
    scene.cycles.use_denoising = cfg['build']['denoising']
    quality = cfg['quality'][job['quality']]['render']
    scene.cycles.samples = quality['samples']
    scene.cycles.seed = cfg['project']['seed']
    scene.render.resolution_x = quality['width']
    scene.render.resolution_y = quality['height']
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = cfg['build']['threads']
    scene.view_settings.view_transform = 'AgX'
    scene.render.filepath = job['render_path']
    bpy.ops.wm.save_as_mainfile(filepath=job['blend_path'], check_existing=False)
    print('STAGE01_SAVED', job['blend_path'], flush=True)


def verify_render(job):
    scene = bpy.context.scene
    cal = job['config']['calibration']
    checks = []
    def check(name, value, expected, ok):
        checks.append({'name':name,'actual':value,'expected':expected,'passed':bool(ok)})
        if not ok: raise AssertionError(name + ': ' + str(value))
    check('reopened_saved_blend', bpy.data.filepath, job['blend_path'], Path(bpy.data.filepath).resolve() == Path(job['blend_path']).resolve())
    check('fingerprint', scene.get('build_fingerprint'), job['fingerprint'], scene.get('build_fingerprint') == job['fingerprint'])
    check('metric_system', scene.unit_settings.system, 'METRIC', scene.unit_settings.system == 'METRIC')
    check('unit_scale', scene.unit_settings.scale_length, 1.0, scene.unit_settings.scale_length == 1)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for name, expected in [('TestBuilding_12x18x24m',cal['building_dimensions_m']),('Ground_60m_x_50m',cal['ground_dimensions_m']),('Ruler_20m',[20,.6,.08])]:
        o = bpy.data.objects[name]
        # Measure evaluated geometry, including modifiers, in world meters.
        evaluated = o.evaluated_get(depsgraph)
        corners = [evaluated.matrix_world @ Vector(v) for v in evaluated.bound_box]
        dims = [max(v[i] for v in corners)-min(v[i] for v in corners) for i in range(3)]
        check(name+'_world_dimensions_m',dims,expected,all(abs(a-b)<cal['measurement_tolerance_m'] for a,b in zip(dims,expected)))
    for axis in 'XYZ':
        o = bpy.data.objects['Axis_'+axis]
        d = o.dimensions['XYZ'.index(axis)]
        check('axis_'+axis+'_length_m', d, 14, abs(d-14)<cal['measurement_tolerance_m'])
    ticks = [o for o in bpy.data.objects if o.name.startswith('Ruler tick ')]
    xs = sorted(o.location.x for o in ticks)
    check('ruler_21_ticks_one_meter_apart',xs,list(range(-10,11)), len(xs)==21 and all(abs((b-a)-1)<1e-6 for a,b in zip(xs,xs[1:])))
    meshes = [o for o in scene.objects if o.type == 'MESH']
    tri = 0
    for o in meshes:
        mesh = o.evaluated_get(depsgraph).to_mesh()
        mesh.calc_loop_triangles()
        tri += len(mesh.loop_triangles)
        o.evaluated_get(depsgraph).to_mesh_clear()
    check('triangle_budget',tri,cal['triangle_limit'],tri <= cal['triangle_limit'])
    check('editable_collections', list(bpy.data.collections.keys()), 'Terrain Buildings Calibration Lights Cameras Assets Materials', all(n in bpy.data.collections for n in ['Terrain','Buildings','Calibration','Lights','Cameras','Assets','Materials']))
    check('camera_present',bool(scene.camera),'camera',bool(scene.camera))
    check('lights_present',len([o for o in scene.objects if o.type=='LIGHT']),2,len([o for o in scene.objects if o.type=='LIGHT'])>=2)
    scene.render.filepath = job['render_path']
    bpy.ops.render.render(write_still=True)
    report = {'status':'passed','blender_version':bpy.app.version_string,'blender_python_version':sys.version,'blend_path':bpy.data.filepath,
              'checks':checks,'mesh_objects':len(meshes),'evaluated_triangles':tri,
              'render_path':job['render_path'],'render_samples':scene.cycles.samples,
              'device':'CPU','denoising':scene.cycles.use_denoising,
              'geometry_class':'artistic_synthetic','real_city_geometry':False}
    Path(job['check_path']).write_text(json.dumps(report,indent=2)+'\n')
    print('STAGE01_REOPEN_RENDER_CHECK_OK', json.dumps({'triangles':tri,'checks':len(checks)}), flush=True)


if __name__ == '__main__':
    a = args()
    job = json.loads(Path(a.job).read_text())
    if a.mode == 'build': build(job)
    else: verify_render(job)
