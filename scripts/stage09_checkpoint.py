"""Actual independent Blender checkpoint from decoded runtime GLBs, in real city coordinates."""
from pathlib import Path
import hashlib,json,sys
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
CHECK='--check' in sys.argv
path=ROOT/'scenes/stage09_runtime_checkpoint.blend'
def sha(p):
 with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
if not CHECK:
 bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
 evidence=json.loads((ROOT/'work/reports/stage09/gltf_validation.json').read_text());assert evidence['status']=='passed'
 imports=[]
 for record in evidence['samples']:
  before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(ROOT/record['decompressed_file']))
  objects=set(bpy.data.objects)-before
  root=bpy.data.objects.new('Geographic_'+record['resource'],None);scene.collection.objects.link(root);root.location=record['origin_city_m'];root['resource_id']=record['resource'];root['runtime_lod']=record['lod'];root['source_sha256']=record['source_sha256']
  for ob in objects:
   if ob.parent is None:ob.parent=root
  imports.append({'resource':record['resource'],'lod':record['lod'],'objects':len(objects),'origin_city_m':record['origin_city_m']})
 for material in bpy.data.materials:
  if material.use_nodes:
   for n in material.node_tree.nodes:
    if n.type=='BSDF_PRINCIPLED':n.inputs['Emission Strength'].default_value=0
 for image in bpy.data.images:
  if image.source=='FILE' and not image.packed_file:
   try:image.pack()
   except RuntimeError:pass
 world=bpy.data.worlds.new('Runtime daylight check');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.67,.75,1);world.node_tree.nodes['Background'].inputs[1].default_value=.6;scene.world=world
 sun_data=bpy.data.lights.new('Solar clear_day','SUN');sun_data.energy=3;sun=bpy.data.objects.new('Solar clear_day',sun_data);scene.collection.objects.link(sun);sun.rotation_euler=(np.deg2rad(90-56.161673),0,np.deg2rad(180-187.049073))
 camera_data=bpy.data.cameras.new('Historic Core saved runtime camera');cam=bpy.data.objects.new('Historic Core saved runtime camera',camera_data);scene.collection.objects.link(cam);scene.camera=cam
 # The checkpoint intentionally imports only two nearby ordinary buildings.
 # Use a repeatable elevated camera showing those actual samples and the road,
 # rather than an authoring street camera aimed at buildings not in this subset.
 view={'position_m':[-650,650,260],'target_m':[-390,940,105],'lens_mm':38};cam.location=view['position_m'];cam.rotation_euler=(Vector(view['target_m'])-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=view['lens_mm'];cam.data.clip_start=.1;cam.data.clip_end=180000
 scene['check_camera']=json.dumps(view)
 scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.use_denoising=False;scene.cycles.seed=20261021;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=960;scene.render.resolution_y=640;scene.render.resolution_percentage=100
 scene.view_settings.view_transform='AgX';scene['stage']=9;scene['full_authoring_scene']='scenes/stage08_city_medium.blend';scene['runtime_catalog']='outputs/stage09/resources/manifest.json';scene['checkpoint_scope']='Actual representative decoded runtime tiles, not the full authoring city. Entire runtime city is in the resource catalog.'
 scene['imports']=json.dumps(imports);bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True)
 print('STAGE09_RUNTIME_CHECKPOINT_SAVED',path,flush=True)
else:
 scene=bpy.context.scene;assert scene['stage']==9 and scene.unit_settings.scale_length==1
 invalid=0;triangles=0
 for ob in scene.objects:
  if ob.type!='MESH':continue
  v=np.empty((len(ob.data.vertices),3),np.float32);ob.data.vertices.foreach_get('co',v.ravel());invalid+=int((~np.isfinite(v)).any(axis=1).sum());ob.data.calc_loop_triangles();triangles+=len(ob.data.loop_triangles)
 assert invalid==0
 report={'status':'passed','actual_independent_reopen':True,'saved_checkpoint_sha256':sha(path),'units_metres_per_blender_unit':scene.unit_settings.scale_length,'nonfinite_vertices':invalid,'triangles':triangles,'objects':len(scene.objects),'imports':json.loads(scene['imports']),'scope':scene['checkpoint_scope'],'camera':json.loads(scene['check_camera'])}
 scene.render.filepath=str(ROOT/'work/previews/stage09/blender_runtime_checkpoint.png');bpy.ops.render.render(write_still=True);report['actual_cpu_cycles_render']=True;report['render_path']='work/previews/stage09/blender_runtime_checkpoint.png'
 (ROOT/'work/reports/stage09/checkpoint.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('STAGE09_RUNTIME_CHECKPOINT_REOPEN_RENDER_PASSED',flush=True)
