"""Create a new master; keep every accepted source binary untouched."""
from pathlib import Path
import sys,json,hashlib,collections
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from stage10_common import DELIVERY,write,sha,read
from stage10_scene import apply_view,apply_light
scene=bpy.context.scene;repairs=[];seen=set()
thin={'downtown_road','profiled_priority_road','overview_far','downtown_sidewalk','markings','airport_surface','airport_apron','rail_corridor','downtown_paths'}
for ob in list(scene.objects):
 if ob.type!='MESH' or ob.get('traffic_role') not in thin or ob.data.as_pointer() in seen:continue
 seen.add(ob.data.as_pointer());m=ob.data
 if len(m.loops)!=3*len(m.polygons):continue
 v=np.empty((len(m.vertices),3),np.float32);m.vertices.foreach_get('co',v.ravel());f=np.empty((len(m.polygons),3),np.int32);m.loops.foreach_get('vertex_index',f.ravel());n=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]);flip=n[:,2]<-1e-8
 if not flip.any():continue
 # Only explicitly classified open transport sheets, never bridge slab bottoms.
 if m.library:ob.data=m.copy();m=ob.data
 before=hashlib.sha256(v.tobytes()).hexdigest();f[flip]=f[flip][:,[0,2,1]];m.loops.foreach_set('vertex_index',f.ravel())
 for uv in m.uv_layers:
  a=np.empty((len(m.polygons),3,2),np.float32);uv.data.foreach_get('uv',a.ravel());a[flip]=a[flip][:,[0,2,1]];uv.data.foreach_set('uv',a.ravel())
 m.update();repairs.append({'object':ob.name,'role':ob['traffic_role'],'reversed_triangles':int(flip.sum()),'vertices_unchanged_sha256':before,'repair':'reverse only downward thin surface triangles; per-corner UV reordered with vertices; no source file saved'})
print('MASTER_OPEN_SHEET_NORMAL_FIXES',len(repairs),sum(r['reversed_triangles'] for r in repairs),flush=True)
for image in bpy.data.images:
 if image.source=='FILE' and image.filepath:
  absolute=Path(bpy.path.abspath(image.filepath,library=image.library));
  if absolute.is_relative_to(ROOT/'assets'):image.filepath='//assets/'+str(absolute.relative_to(ROOT/'assets'))
for lib in bpy.data.libraries:lib.filepath='//assets/linked/'+Path(lib.filepath).name
cfg=read('config/stage10.json');terrain=read('data/processed/stage07_final/index.json')['terrain_active_lod'];default=cfg['views']['downtown_skyline'];tri=apply_view(scene,default,terrain);apply_light(scene,read('config/stage08_lighting.json'),'clear_day')
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1;scene['stage']=10;scene['stage10_version']='1.0.0';scene['stage10_default_view']='downtown_skyline';scene['stage10_status']='local_delivery_with_documented_source_and_visual_gaps';scene['stage10_runtime_resources']='tiles/manifest.json';scene['stage10_provenance']='mixed source dates; source/inferred fields separate; full survey fidelity not certified';scene['stage10_normal_repairs']=len(repairs)
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.use_denoising=False;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.cycles.seed=20261021;scene.view_settings.view_transform='AgX'
bookmarks=bpy.data.collections.new('99_FINAL_CHECK_CAMERAS');scene.collection.children.link(bookmarks)
for name,view in cfg['views'].items():
 data=bpy.data.cameras.new('CHECK_'+name);ob=bpy.data.objects.new('CHECK_'+name,data);bookmarks.objects.link(ob);ob.location=view['position_m'];ob.rotation_euler=(__import__('mathutils').Vector(view['target_m'])-ob.location).to_track_quat('-Z','Y').to_euler();data.lens=view.get('lens_mm',35);data.type='ORTHO' if 'ortho_scale_m' in view else 'PERSP'
 if data.type=='ORTHO':data.ortho_scale=view['ortho_scale_m']
 ob['check_view_id']=name;ob['coordinate_units']='city east/north/up metres';ob['lighting_reference']='2025-09-21 America/Los_Angeles; not city data date'
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.shading.type='SOLID';area.spaces.active.shading.color_type='MATERIAL';area.spaces.active.region_3d.view_perspective='CAMERA'
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(DELIVERY/'LA_Master.blend'),compress=True,relative_remap=False)
write('work/reports/stage10/master_build.json',{'status':'saved_requires_clean_reopen','path':'outputs/LA_Delivery/LA_Master.blend','source_sha256':sha(ROOT/'scenes/stage08_city_medium.blend'),'master_sha256':sha(DELIVERY/'LA_Master.blend'),'normal_repairs':repairs,'total_reversed_surface_triangles':sum(r['reversed_triangles'] for r in repairs),'default_triangles':tri,'default_view':default,'linked_dependencies_relative':True,'all_old_checkpoints_preserved':True})
write('outputs/LA_Delivery/config/terrain_active_lod.json',terrain)
print('LA_MASTER_SAVED',flush=True)
