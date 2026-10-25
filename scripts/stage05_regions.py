"""Blender region subcollections; prove collection edits preserve geometry bytes."""
import bpy,numpy as np,json,hashlib
from pathlib import Path
def geometry_fingerprint():
 h=hashlib.sha256();objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and (o.get('building_lod') is not None or o.get('instance_kind_05'))]
 for o in sorted(objects,key=lambda o:o.name):
  m=o.data;h.update(o.name.encode());h.update(np.array([*o.location,*o.rotation_euler,*o.scale],np.float64).tobytes());h.update(bytes([o.hide_render,o.hide_viewport]));h.update(json.dumps([x.name for x in m.materials]).encode())
  v=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',v);h.update(v.tobytes());loops=np.empty(len(m.loops),np.int32);m.loops.foreach_get('vertex_index',loops);h.update(loops.tobytes());mi=np.empty(len(m.polygons),np.int32);m.polygons.foreach_get('material_index',mi);h.update(mi.tobytes())
  for name in ['building_index','module_scale','module_rotation']:
   a=m.attributes.get(name)
   if a is not None:
    field='value' if a.data_type=='INT' else 'vector';array=np.empty(len(a.data)*(1 if field=='value' else 3),np.int32 if field=='value' else np.float32);a.data.foreach_get(field,array);h.update(array.tobytes())
  for uv in m.uv_layers:
   array=np.empty(len(uv.data)*2,np.float32);uv.data.foreach_get('uv',array);h.update(array.tobytes())
 return h.hexdigest(),len(objects)
def organize(root):
 before,n=geometry_fingerprint();counts={};parents=[('10_Buildings_AUTHORING_editable','B5_Authoring'),('10_Buildings_RUNTIME_simplified_static_alternative','B5_Runtime'),('12_Building_modules_GN_shared_instances','B5_Modules')]
 for parent_name,prefix in parents:
  parent=bpy.data.collections[parent_name]
  for ob in list(parent.objects):
   owner=ob.get('building_cell',ob.name);region='historic_core' if owner.startswith('s125') and ob.location.y<1300 else 'civic_center' if owner.startswith('s125') else 'downtown' if owner.startswith('s250') else 'city_overview';name=prefix+'_'+region;coll=bpy.data.collections.get(name)
   if coll is None:coll=bpy.data.collections.new(name);parent.children.link(coll)
   coll.objects.link(ob);parent.objects.unlink(ob);ob['building_region_05']=region;counts[name]=counts.get(name,0)+1
 after,n2=geometry_fingerprint();assert before==after and n==n2,'Region organization changed geometry or visibility';path=Path(root)/'work/reports/stage05/region_collections.json';path.write_text(json.dumps({'status':'organized_in_memory_pending_save','geometry_sha256_before':before,'geometry_sha256_after':after,'objects_hashed':n,'objects_moved_by_collection':counts,'geometry_materials_ids_transforms_and_visibility_unchanged':True},indent=2)+'\n');print('REGION_SUBCOLLECTIONS_CREATED_GEOMETRY_HASH_UNCHANGED',n,flush=True)
def verify(root):
 path=Path(root)/'work/reports/stage05/region_collections.json';r=json.loads(path.read_text());digest,n=geometry_fingerprint();assert digest==r['geometry_sha256_after'] and n==r['objects_hashed'];r.update({'status':'passed_after_independent_reopen','reopened_geometry_sha256':digest,'actual_file':bpy.data.filepath});path.write_text(json.dumps(r,indent=2)+'\n');print('REGION_ORGANIZATION_PRESERVED_AFTER_REOPEN',n,flush=True)
