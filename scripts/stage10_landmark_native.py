"""Independent editable PBR assets from actual final GLBs; no external library."""
from pathlib import Path
import sys,json,math
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from stage10_common import *
index=read('work/reports/stage10/landmark_exports.json')['assets'];results=[]
for ident in sorted(set(a['id'] for a in index)):
 bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1;root=bpy.data.objects.new(ident+'_city_aligned_origin',None);scene.collection.objects.link(root);assets=sorted((a for a in index if a['id']==ident),key=lambda a:a['lod']);root['origin_city_m']=assets[0]['origin_city_m'];root['orientation_baked']=True;root['model_status']='reference-guided approximation, see metadata card';counts={};near=[]
 for a in assets:
  before=set(scene.objects);bpy.ops.import_scene.gltf(filepath=str(ROOT/a['path']));new=set(scene.objects)-before;collection=bpy.data.collections.new('LOD'+str(a['lod']));scene.collection.children.link(collection)
  for ob in new:
   for c in list(ob.users_collection):c.objects.unlink(ob)
   collection.objects.link(ob)
   if ob.parent is None:ob.parent=root
   ob.hide_render=a['lod']!=0;ob.hide_viewport=ob.hide_render;ob['runtime_lod']=a['lod']
  counts[str(a['lod'])]=sum(len(o.data.polygons) for o in new if o.type=='MESH')
  if a['lod']==0:near=[o for o in new if o.type=='MESH']
 for mat in bpy.data.materials:
  if mat.use_nodes:
   for node in mat.node_tree.nodes:
    if node.type=='BSDF_PRINCIPLED' and node.inputs['Emission Strength'].default_value>0:mat['stage08_night_emission']=True;mat['night_emission_strength']=node.inputs['Emission Strength'].default_value;node.inputs['Emission Strength'].default_value=0
 for image in bpy.data.images:
  if image.source=='FILE' and not image.packed_file:image.pack()
 bpy.context.view_layer.update();points=np.concatenate([np.array([o.matrix_world@v.co for v in o.data.vertices]) for o in near]);lo,hi=points.min(axis=0),points.max(axis=0);center=(lo+hi)/2;span=max(hi-lo);data=bpy.data.cameras.new('Asset inspection');cam=bpy.data.objects.new('Asset inspection',data);scene.collection.objects.link(cam);cam.location=center+Vector((span*1.1,-span*1.5,span*.7));cam.rotation_euler=(Vector(center)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=38;cam.data.clip_end=max(5000,span*10);scene.camera=cam
 world=bpy.data.worlds.new('Asset studio');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.65,.75,1);world.node_tree.nodes['Background'].inputs[1].default_value=.5;scene.world=world;light=bpy.data.lights.new('Sun','SUN');light.energy=3;sun=bpy.data.objects.new('Sun',light);scene.collection.objects.link(sun);sun.rotation_euler=(.5,-.4,-.5);scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.use_denoising=False;scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene['stage10_landmark_id']=ident;scene['geographic_origin_city_m']=assets[0]['origin_city_m'];scene['orientation']='Already aligned to city grid east/north; source card yaw is baked, not an additional transform.'
 target=DELIVERY/'landmarks'/(ident+'.blend')
 if target.exists():
  assert sha(target)==sha(ROOT/'assets/landmarks/stage06'/target.name),'Preserve modified asset';target.unlink()
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(target),compress=True)
 # Actually close and reopen this standalone asset before accepting it.
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.wm.open_mainfile(filepath=str(target));assert not bpy.data.libraries and bpy.context.scene['stage10_landmark_id']==ident;missing=[i.name for i in bpy.data.images if i.source=='FILE' and not i.packed_file and not Path(bpy.path.abspath(i.filepath)).is_file()];assert not missing
 results.append({'id':ident,'path':str(target.relative_to(ROOT)),'sha256':sha(target),'actual_saved_closed_reopened':True,'independent_libraries':len(bpy.data.libraries),'missing_images':missing,'lod_polygons':counts,'source_runtime_assets':[a['sha256'] for a in assets],'status':'近似完成/部分通过，几何资料盲区继承'});print('INDEPENDENT_FINAL_PBR_ASSET_REOPENED',ident,flush=True)
write('work/reports/stage10/landmark_native.json',{'status':'passed','independent_editable_assets':results,'all_model_fidelity_statuses_remain_approximate':True})
