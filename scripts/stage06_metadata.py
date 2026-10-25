"""Synchronize final research/status text; prove serialized geometry unchanged."""
import bpy,numpy as np,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def signature():
 h=hashlib.sha256();seen=set()
 for ob in sorted(bpy.data.objects,key=lambda o:o.name):
  h.update(ob.name.encode());h.update(np.array([*ob.location,*ob.rotation_euler,*ob.scale,ob.hide_render,ob.hide_viewport],np.float64).tobytes())
  if ob.type!='MESH' or ob.data.as_pointer() in seen:continue
  m=ob.data;seen.add(m.as_pointer());h.update(m.name.encode())
  for owner,field,n,dtype in [(m.vertices,'co',len(m.vertices)*3,np.float32),(m.loops,'vertex_index',len(m.loops),np.int32),(m.polygons,'material_index',len(m.polygons),np.int32),(m.polygons,'use_smooth',len(m.polygons),bool)]:
   a=np.empty(n,dtype);owner.foreach_get(field,a);h.update(a.tobytes())
  for attr in m.attributes:
   if attr.name in ['building_index','module_scale','module_rotation']:
    field='vector' if attr.data_type=='FLOAT_VECTOR' else 'value';n=len(attr.data)*(3 if field=='vector' else 1);a=np.empty(n,np.float32 if field=='vector' else np.int32);attr.data.foreach_get(field,a);h.update(attr.name.encode());h.update(a.tobytes())
  for uv in m.uv_layers:
   a=np.empty(len(uv.data)*2,np.float32);uv.data.foreach_get('uv',a);h.update(a.tobytes())
 return h.hexdigest()
paths=sorted((ROOT/'assets/landmarks/stage06').glob('*.blend'))+sorted((ROOT/'scenes').glob('stage06_context_*.blend'))+[ROOT/'scenes/stage06_massing.blend',ROOT/'scenes/stage06_city_medium.blend'];records=[]
for path in paths:
 bpy.ops.wm.open_mainfile(filepath=str(path));before=signature();ids={o['landmark_id'] for o in bpy.data.objects if o.get('landmark_id')};ids|={o['stable_id'].split(':')[1] for o in bpy.data.objects if str(o.get('stable_id','')).startswith('landmark:')}
 for ident in ids:
  for t in list(bpy.data.texts):
   if t.name.startswith(ident+'_PARAMETERS_AND_SOURCES.json'):
    archive=ROOT/'work/history/stage06_metadata_snapshots'/path.stem/t.name;archive.parent.mkdir(parents=True,exist_ok=True)
    if not archive.exists():archive.write_text(t.as_string())
    bpy.data.texts.remove(t)
  t=bpy.data.texts.new(ident+'_PARAMETERS_AND_SOURCES.json');t.write((ROOT/'data/processed/stage06/cards'/(ident+'.json')).read_text())
 for ob in bpy.data.objects:
  if str(ob.get('stable_id','')).startswith('landmark:'):ob['model_status']='近似完成; final source/difference card synchronized; no claim of surveyed photoreal refinement'
 assert signature()==before;bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True);bpy.ops.wm.open_mainfile(filepath=str(path));after=signature();assert before==after,str(path);records.append({'path':str(path.relative_to(ROOT)),'geometry_transform_visibility_and_source_ID_signature':after,'saved_closed_reopened':True,'before_after_geometry_identical':True});print('FINAL_METADATA_SERIALIZED_GEOMETRY_IDENTICAL',path.name,flush=True)
out=ROOT/'work/reports/stage06/metadata_sync.json';out.write_text(json.dumps({'status':'passed','files':records,'only_text_and_status_properties_changed':True},ensure_ascii=False,indent=2)+'\n')
