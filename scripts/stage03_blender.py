"""Build, close, reopen, measure and render the actual stage03 Blender checkpoint."""
import json
import math
import sys
from pathlib import Path
import numpy as np
import bpy
from mathutils import Vector

job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text());root=Path(job['root']);cfg=job['config'];verify='--verify' in sys.argv


def collection(name):
    c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);return c


def material(name,color,roughness=.9):
    m=bpy.data.materials.new(name);m.diffuse_color=color;m.use_nodes=True
    n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=color;n.inputs['Roughness'].default_value=roughness
    return m


def mesh_object(name,v,f,materials,indices,group,translation=(0,0,0)):
    if not len(f):return None
    mesh=bpy.data.meshes.new(name);mesh.vertices.add(len(v));mesh.vertices.foreach_set('co',v.ravel())
    mesh.loops.add(len(f)*3);mesh.loops.foreach_set('vertex_index',f.ravel());mesh.polygons.add(len(f));mesh.polygons.foreach_set('loop_start',np.arange(len(f),dtype=np.int32)*3);mesh.polygons.foreach_set('loop_total',np.full(len(f),3,dtype=np.int32))
    for m in materials:mesh.materials.append(m)
    if indices is not None:mesh.polygons.foreach_set('material_index',indices)
    mesh.update(calc_edges=True);obj=bpy.data.objects.new(name,mesh);group.objects.link(obj);obj.location=translation;return obj


def aim(camera,location,target,scale):
    camera.location=location;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=scale;camera.data.clip_start=.1;camera.data.clip_end=500000


if not verify:
    bpy.ops.wm.read_factory_settings(use_empty=True);s=bpy.context.scene;s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
    s['project_stage']=3;s['origin_utm_m']=job['origin_utm_m'];s['horizontal_crs']='EPSG:32611';s['vertical_datum']='NAVD88';s['z_offset_m']=0;s['vertical_exaggeration']=1
    s['ocean_height_status']='project design reference0 NAVD88 axis, not a measured tidal level';s['data_limits']='River masks are dated hydrographic extent; reach materials, current flow and bridge deck geometry unknown.'
    active=collection('01_Terrain_ACTIVE_static_budget');alternates=collection('02_Terrain_LOD_ALTERNATIVES_hidden');alternates.hide_render=True;alternates.hide_viewport=True
    water_group=collection('03_Hydrography_observed_XY_inferred_Z');sea_group=collection('04_Ocean_separate_display_reference');base_group=collection('05_Display_base_synthetic');controls=collection('06_Coordinate_controls');reference=collection('07_Coastline_source_reference_hidden');reference.hide_render=True
    mats=[material(name,tuple(color)) for name,color in cfg['surface']['colors'].items()]
    for count,t in enumerate(job['tiles']):
        with np.load(root/t['file']) as d:
            for lod in range(3):
                obj=mesh_object(t['id']+f'_LOD{lod}',d[f'v{lod}'],d[f'f{lod}'],mats,d[f'm{lod}'],active if lod==job['active_lods'][t['id']] else alternates,t['blender_object_translation_m'])
                if obj:
                    obj.data.polygons.foreach_set('use_smooth',np.ones(len(obj.data.polygons),dtype=bool))
                    if f'n{lod}' in d.files:obj.data.normals_split_custom_set_from_vertices(d[f'n{lod}'].tolist())
                    obj['tile_id']=t['id'];obj['lod']=lod;obj['data_class']='processed_observed_with_documented_resampling';obj['vertical_datum']='NAVD88';obj['source_file']=t['file'];obj['original_source_spacing_m']='10m city /1m Downtown';obj['vertex_coordinate_frame']='tile local XY and NAVD88 Z'
        if count%200==0:print('BLENDER_TERRAIN_OBJECTS',count,flush=True)
    water_mats={name:material(name,tuple(cfg['surface']['colors']['ocean' if name=='ocean' else 'inland_water']),.28) for name in ['ocean','river_reference','lake_reservoir_reference']}
    for p in job['water_pieces']:
        with np.load(root/p['file']) as d:obj=mesh_object('Water_'+p['id'],d['v'],d['f'],[water_mats[p['water_class']]],None,sea_group if p['water_class']=='ocean' else water_group,p['object_translation_m'])
        if obj:
            obj['parent_source_id']=p['parent_source_id'];obj['surface_mode']=p['surface_mode'];obj['height_source']=p['height_source'];obj['water_height_data_class']=p['data_class'];obj['current_flow_extent_verified']=False
    if job['foundation']:
        with np.load(root/job['foundation']['file']) as d:
            obj=mesh_object('City_display_plinth_NOT_geology',d['v'],d['f'],[material('Display_base',(0.065,.085,.10,1))],None,base_group)
        obj['data_class']='artistic_synthetic';obj['bottom_z_m']=cfg['foundation']['bottom_z_m'];obj['meaning']='display only; not real cliff, geology or bathymetry'
    for i,line in enumerate(job['coastline_reference_lines']):
        curve=bpy.data.curves.new('Original_geographic_coastline','CURVE');curve.dimensions='3D';spline=curve.splines.new('POLY');spline.points.add(len(line)-1)
        for p,xyz in zip(spline.points,line):p.co=(*xyz,1)
        obj=bpy.data.objects.new('Coastline_reference_'+str(i),curve);reference.objects.link(obj);obj['height_status']='source coastline has no tidal datum/height; displayed at design0 only';obj['source_geometry']='Census2025 coastline'
    for p in json.loads((root/job['control_points_file']).read_text()):
        ix,iy=p['tile_ij'];parent=bpy.data.objects.get(f'ControlFrame_{ix}_{iy}')
        if parent is None:
            parent=bpy.data.objects.new(f'ControlFrame_{ix}_{iy}',None);controls.objects.link(parent);parent.location=(ix*cfg['tile_size_m'],iy*cfg['tile_size_m'],0)
        obj=bpy.data.objects.new('CONTROL_'+p['id'],None);controls.objects.link(obj);obj.parent=parent;obj.location=p['tile_local_m'];obj.empty_display_type='PLAIN_AXES';obj.empty_display_size=25;obj['expected_world_m']=p['blender_world_m'];obj['control_id']=p['id'];obj['source_accuracy']='unknown; computational reference, not surveying network'
    cam=bpy.data.objects.new('Geographic_review_camera',bpy.data.cameras.new('Geographic_camera'));s.collection.objects.link(cam);s.camera=cam
    b=job['bounds_local_m'];center=((b[0]+b[2])/2,(b[1]+b[3])/2,300);span=max(b[2]-b[0],b[3]-b[1]);aim(cam,(center[0],center[1],120000),center,span*1.12)
    sun=bpy.data.objects.new('Sun',bpy.data.lights.new('Sun','SUN'));s.collection.objects.link(sun);sun.rotation_euler=(math.radians(27),math.radians(-18),math.radians(-25));sun.data.energy=3
    s.world=bpy.data.worlds.new('World');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.12,.16,.20,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.5
    s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.use_denoising=False;s.cycles.samples=cfg['quality'][job['quality']]['render_samples'];s.render.threads_mode='FIXED';s.render.threads=cfg['build']['threads']
    s.render.image_settings.file_format='PNG';s.render.resolution_percentage=100;s.view_settings.view_transform='Standard';s.render.film_transparent=False
    s['static_selected_triangles']=job['expected_active_triangles'];s['runtime_lod_switching_implemented']=False
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active;space.clip_start=.1;space.clip_end=500000;space.shading.color_type='MATERIAL'
                space.region_3d.view_location=Vector(center);space.region_3d.view_rotation=cam.rotation_euler.to_quaternion();space.region_3d.view_distance=span*.9;space.region_3d.view_perspective='ORTHO'
    bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=job['blend_path'],check_existing=False);print('STAGE03_SAVED_AND_EXITING',flush=True)
else:
    s=bpy.context.scene;bpy.context.view_layer.update();assert Path(bpy.data.filepath)==Path(job['blend_path']);assert s.unit_settings.system=='METRIC' and s.unit_settings.scale_length==1
    assert s['vertical_exaggeration']==1 and s['z_offset_m']==0 and s['vertical_datum']=='NAVD88'
    nonfinite=0;degenerate=0;max_world=0;active_tri=0;terrain_meshes=0;control_errors=[];maximum_edge_xy=0
    for obj in s.objects:
        if obj.type=='MESH':
            v=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',v);v=v.reshape(-1,3);nonfinite+=int((~np.isfinite(v)).sum());max_world=max(max_world,float(np.abs(v+np.array(obj.location)).max()))
            tri=np.empty(len(obj.data.loops),dtype=np.int32);obj.data.loops.foreach_get('vertex_index',tri);tri=tri.reshape(-1,3)
            if len(tri):
                cross=np.cross(v[tri[:,1]].astype(float)-v[tri[:,0]],v[tri[:,2]].astype(float)-v[tri[:,0]]);degenerate+=int((np.linalg.norm(cross,axis=1)<1e-10).sum())
            if obj.name.startswith('la_t_'):
                terrain_meshes+=1;assert v[:,:2].min()>=-.001 and v[:,:2].max()<=cfg['tile_size_m']+.001
                if obj.users_collection[0].name.startswith('01_') and len(tri):
                    edge=np.linalg.norm(v[tri[:,1],:2].astype(float)-v[tri[:,0],:2],axis=1);maximum_edge_xy=max(maximum_edge_xy,float(edge.max()))
            if not any(c.hide_render for c in obj.users_collection):active_tri+=len(tri)
        if obj.name.startswith('CONTROL_'):
            actual=np.array(obj.matrix_world.translation);expected=np.array(obj['expected_world_m']);error=float(np.linalg.norm(actual-expected));control_errors.append({'id':obj['control_id'],'actual_world_m':actual.tolist(),'error_m':error})
    assert nonfinite==0,'Nonfinite vertices';assert degenerate==0,'Degenerate triangles';assert max_world<cfg['validation']['maximum_scene_coordinate_abs_m']
    assert active_tri==job['expected_active_triangles'] and active_tri<=job['visible_triangle_cap']
    assert max(p['error_m'] for p in control_errors)<cfg['validation']['blender_position_tolerance_m']
    cam=s.camera;b=job['bounds_local_m'];cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2;span=max(b[2]-b[0],b[3]-b[1]);width=cfg['quality'][job['quality']]['render_width'];renders=[]
    views=[('top',(cx,cy,120000),(cx,cy,200),span*1.12,1),
           ('side',(cx-60000,cy-85000,30000),(cx,cy,350),span*1.22,.65),
           ('downtown',(4500,-5500,4200),(0,0,90),6000,.75)]
    for label,position,target,scale,ratio in views:
        aim(cam,position,target,scale);s.render.resolution_x=width;s.render.resolution_y=int(width*ratio);path=Path(job['preview_directory'])/(label+'.png');s.render.filepath=str(path);bpy.ops.render.render(write_still=True);renders.append(str(path));print('STAGE03_RENDERED',label,flush=True)
    wire=bpy.data.materials.new('Actual_mesh_wireframe');wire.use_nodes=True;n=wire.node_tree;n.nodes.clear();output=n.nodes.new('ShaderNodeOutputMaterial');em=n.nodes.new('ShaderNodeEmission');mix=n.nodes.new('ShaderNodeMixRGB');mix.blend_type='MIX';mix.inputs[1].default_value=(.025,.045,.06,1);mix.inputs[2].default_value=(.4,.8,.95,1);w=n.nodes.new('ShaderNodeWireframe');w.use_pixel_size=True;w.inputs['Size'].default_value=.7;n.links.new(w.outputs[0],mix.inputs[0]);n.links.new(mix.outputs[0],em.inputs[0]);n.links.new(em.outputs[0],output.inputs[0]);bpy.context.view_layer.material_override=wire
    aim(cam,(0,0,12000),(0,0,90),4700);s.render.resolution_x=width;s.render.resolution_y=width;s.render.filepath=str(Path(job['preview_directory'])/'wireframe.png');bpy.ops.render.render(write_still=True);renders.append(s.render.filepath);bpy.context.view_layer.material_override=None
    result={'status':'passed','reopened_in_new_process':True,'unit_system':'METRIC','meters_per_BU':1,'z_exaggeration':1,'vertical_datum':'NAVD88',
        'mesh_objects_checked':sum(o.type=='MESH' for o in s.objects),'terrain_meshes_checked':terrain_meshes,'nonfinite_vertex_values':nonfinite,'degenerate_triangles':degenerate,
        'maximum_world_coordinate_abs_m':max_world,'active_triangles':active_tri,'visible_triangle_cap':job['visible_triangle_cap'],'maximum_active_terrain_edge_xy_m':maximum_edge_xy,
        'control_positions':control_errors,'maximum_control_position_error_m':max(p['error_m'] for p in control_errors),'rendered_files':renders,
        'seam_validation':'All baked mesh neighbor/LOD combinations checked separately in seams_medium.json; shared vertices preserved on Blender serialization',
        'limits':'No hydraulic/flow survey, bridge-deck geometry or verified bank materials; see water report'}
    Path(job['check_path']).write_text(json.dumps(result,indent=2)+'\n');print('STAGE03_REOPEN_MEASURE_RENDER_PASSED',flush=True)
