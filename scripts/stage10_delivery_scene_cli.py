"""Portable inspection/render and selected landmark/near-building GLB export."""
from pathlib import Path
import sys,json,argparse
import bpy
BASE=Path(__file__).resolve().parents[1]
scene_root=Path(bpy.data.filepath).resolve().parent if bpy.data.filepath else BASE
ROOT=scene_root if (scene_root/'LA_Master.blend').exists() else BASE if (BASE/'LA_Master.blend').exists() else BASE/'outputs/LA_Delivery'
sys.path.insert(0,str(ROOT/'scripts'))
from scene_tools import apply_view,apply_light
p=argparse.ArgumentParser();p.add_argument('--view',default='historic_street');p.add_argument('--light',default='clear_day');p.add_argument('--render');p.add_argument('--export-id');p.add_argument('--output',default='tiles/rebuild/selected.glb');p.add_argument('--check-resources',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);cfg=json.loads((ROOT/'config/stage10.json').read_text());terrain=json.loads((ROOT/'config/terrain_active_lod.json').read_text());lights=json.loads((ROOT/'config/history/stage08_lighting.json').read_text());scene=bpy.context.scene
if a.check_resources:
 rows=[{'path':bpy.path.abspath(lib.filepath),'exists':Path(bpy.path.abspath(lib.filepath)).is_file(),'inside_delivery':Path(bpy.path.abspath(lib.filepath)).is_relative_to(ROOT)} for lib in bpy.data.libraries];missing=[image.filepath for image in bpy.data.images if image.source=='FILE' and not image.packed_file and not Path(bpy.path.abspath(image.filepath,library=image.library)).is_file()];assert all(r['exists'] and r['inside_delivery'] for r in rows) and not missing and scene.unit_settings.scale_length==1
 (ROOT/'metadata/resource_paths_smoke.json').write_text(json.dumps({'status':'passed','actual_clean_session_master':bpy.data.filepath,'actual_root':str(ROOT),'libraries':rows,'missing_images':missing,'unit_scale_m':1.0,'external_fonts':[f.filepath for f in bpy.data.fonts if f.filepath!='<builtin>']},indent=2)+'\n')
if a.view not in cfg['views'] or a.light not in lights['presets']:raise RuntimeError('Unknown actual view or lighting preset')
apply_view(scene,cfg['views'][a.view],terrain);apply_light(scene,lights,a.light)
if a.export_id:
 roots=[o for o in scene.objects if o.get('stable_id')==a.export_id or o.get('source_uid')==a.export_id]
 if not roots:raise RuntimeError('No actual model with this stable ID')
 root=next((o for o in roots if o.type=='EMPTY'),roots[0]);wanted=[root,*root.children_recursive] if root.type=='EMPTY' else roots
 for o in scene.objects:o.select_set(False)
 count=0
 for o in wanted:
  if o.type=='MESH' and (o.get('landmark_lod') not in (None,'near') or o.get('r2_lod')=='far'):continue
  o.hide_render=False;o.hide_viewport=False;o.hide_set(False);o.select_set(True);count+=1
 if not count:raise RuntimeError('No exportable actual components')
 output=ROOT/a.output;output.parent.mkdir(parents=True,exist_ok=True);bpy.context.view_layer.objects.active=root;bpy.ops.export_scene.gltf(filepath=str(output),export_format='GLB',use_selection=True,export_yup=True,export_materials='EXPORT',export_extras=True)
 print('ACTUAL_SELECTED_GLB_EXPORTED',a.export_id,output,count,flush=True)
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(output));finite=True;triangles=0
 for ob in bpy.context.scene.objects:
  if ob.type=='MESH':
   import numpy as np
   v=np.empty(len(ob.data.vertices)*3,np.float32);ob.data.vertices.foreach_get('co',v);finite=finite and bool(np.isfinite(v).all());ob.data.calc_loop_triangles();triangles+=len(ob.data.loop_triangles)
 assert finite and triangles>0
 output.with_suffix('.check.json').write_text(json.dumps({'status':'passed','actual_export_then_blank_import':True,'id':a.export_id,'nonfinite':not finite,'triangles':triangles},indent=2)+'\n')
if a.render:
 scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.use_denoising=False;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.filepath=str(ROOT/a.render);Path(scene.render.filepath).parent.mkdir(parents=True,exist_ok=True);bpy.ops.render.render(write_still=True)
print('ACTUAL_DELIVERY_VIEW_READY',a.view,a.light,flush=True)
