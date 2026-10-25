"""Observed plan-geometry and bare-earth DEM checkpoint, without height extrusion."""
import json
import sys
from pathlib import Path
import bpy

job=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())
reopen='--verify' in sys.argv
if not reopen:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s=bpy.context.scene;s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
    s['purpose']='Stage02 georeferenced DATA REVIEW; actual roofline plans over observed DEM. No height extrusion.'
    s['origin_utm_m']=job['origin_utm_m'];s['terrain_observed']=bool(job.get('terrain_grid'));s['buildings_observed']=bool(job.get('building_lines'))
    s['vertical_datum']=job.get('vertical_datum','unknown')
    for name,geometry,color,width in [('Road_Centerlines',job['road_lines'],(.7,.8,.9),2),
                                      ('Water_Observations',job['water_lines'],(.1,.65,.75),4),
                                      ('Closeup_Work_Windows',job['closeup_lines'],(.95,.65,.12),5),
                                      ('Building_Roofline_Plans',job.get('building_lines',[]),(.08,.6,.9),1.4)]:
        collection=bpy.data.collections.new(name);s.collection.children.link(collection)
        material=bpy.data.materials.new(name);material.use_nodes=True
        tree=material.node_tree;tree.nodes.clear();emit=tree.nodes.new('ShaderNodeEmission');emit.inputs[0].default_value=(*color,1)
        output=tree.nodes.new('ShaderNodeOutputMaterial');tree.links.new(emit.outputs[0],output.inputs[0])
        for index,line in enumerate(geometry):
            if len(line)<2:continue
            curve=bpy.data.curves.new(f'{name}_{index}','CURVE');curve.dimensions='3D';curve.bevel_depth=width;curve.bevel_resolution=0
            spline=curve.splines.new('POLY');spline.points.add(len(line)-1)
            heights=job['road_z'][index] if name=='Road_Centerlines' and job.get('road_z') else job['building_z'][index] if name=='Building_Roofline_Plans' else [150]*len(line)
            for point,(x,y),z in zip(spline.points,line,heights):point.co=(x,y,z,1)
            obj=bpy.data.objects.new(curve.name,curve);collection.objects.link(obj);curve.materials.append(material)
            obj['horizontal_data_class']='processed_observed' if name!='Closeup_Work_Windows' else 'project_defined_work_extent'
            obj['z_status']='DEM ground plus display offset; NOT measured building roof or road bridge deck';obj['stroke_width_status']='visual_symbol_NOT_measured_road_width'
            if name=='Road_Centerlines':obj['feature_id']=job['road_feature_ids'][index]
            if name=='Building_Roofline_Plans':obj['feature_id']=job['building_feature_ids'][index]
    if job.get('terrain_grid'):
        grid=job['terrain_grid'];nx=len(grid[0]);ny=len(grid)
        vertices=[(job['terrain_grid_x'][x],job['terrain_grid_y'][y],grid[y][x]) for y in range(ny) for x in range(nx)]
        faces=[(y*nx+x,(y+1)*nx+x,(y+1)*nx+x+1,y*nx+x+1) for y in range(ny-1) for x in range(nx-1)]
        mesh=bpy.data.meshes.new('Observed bare-earth review mesh');mesh.from_pydata(vertices,[],faces);mesh.update()
        o=bpy.data.objects.new('Terrain / observed NAVD88 / preview decimation only',mesh);s.collection.objects.link(o)
        o['data_class']='processed_observed';o['vertical_datum']='NAVD88';o['preview_grid']='101x101 samples, not stage03 terrain deliverable';o['no_vertical_exaggeration']=True
        m=bpy.data.materials.new('Terrain review grey');m.diffuse_color=(.16,.2,.23,1);o.data.materials.append(m)
        light=bpy.data.objects.new('Review sunlight',bpy.data.lights.new('Sun','SUN'));s.collection.objects.link(light);light.rotation_euler=(.5,-.3,-.4);light.data.energy=2
    camera=bpy.data.objects.new('Data review camera',bpy.data.cameras.new('Orthographic'))
    s.collection.objects.link(camera);camera.location=(0,0,6000);camera.data.type='ORTHO';camera.data.ortho_scale=4500;s.camera=camera
    camera.data.clip_start=1;camera.data.clip_end=10000
    s.world=bpy.data.worlds.new('Dark map');s.world.color=(.01,.02,.035)
    s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.use_denoising=False;s.cycles.samples=4
    size={'low':768,'medium':1024,'high':1600}[job['quality']]
    s.render.resolution_x=size;s.render.resolution_y=size;s.render.resolution_percentage=100
    s.render.image_settings.file_format='PNG';s.render.filepath=job['render_path']
    bpy.ops.wm.save_as_mainfile(filepath=job['blend_path'],check_existing=False)
    print('STAGE02_CHECKPOINT_SAVED',flush=True)
else:
    s=bpy.context.scene
    assert Path(bpy.data.filepath)==Path(job['blend_path'])
    assert s.unit_settings.system=='METRIC' and s.unit_settings.scale_length==1
    assert len(bpy.data.collections['Road_Centerlines'].objects)==len(job['road_lines'])
    assert len(bpy.data.collections['Building_Roofline_Plans'].objects)==len(job['building_lines'])
    terrain=next(o for o in s.objects if o.name.startswith('Terrain / observed'))
    assert max(abs(v.co.z-z) for v,z in zip(terrain.data.vertices,[z for row in job['terrain_grid'] for z in row]))<.001
    bpy.ops.render.render(write_still=True)
    Path(job['check_path']).write_text(json.dumps({'status':'passed_for_observed_data_review',
        'reopened':True,'meters':True,'road_curves':len(job['road_lines']),
        'building_curve_count':len(job['building_lines']),'building_overlay_complete':True,'terrain_overlay_complete':True,
        'z_values':'observed NAVD88 terrain; vector display offsets explicitly marked','roof_heights_modeled':False,
        'render_path':job['render_path']},indent=2)+'\n')
    print('STAGE02_CHECKPOINT_REOPEN_RENDER_OK',flush=True)
