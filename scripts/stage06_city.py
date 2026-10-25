"""Native Blender city integration and true geographically extracted inspection neighborhoods."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage06_blender import *
def contexts_build():
 index=read('data/processed/stage06/geometry_index.json');contexts=read('data/processed/stage06/context_index.json')
 for context in contexts['contexts']:
  ident=context['id']
  if args.id not in ['all',ident]:continue
  bpy.ops.wm.read_factory_settings(use_empty=True);s=setup_scene();item=next(i for i in index['landmarks'] if i['id']==ident);card=read(item['card']);mats=[make_material(*m) for m in index['materials']];import_landmark(item,mats);coll=bpy.data.collections.new('True_source_city_context');s.collection.children.link(coll);matcache={}
  for rec in context['meshes']:
   key=json.dumps(rec['materials'])
   if key not in matcache:matcache[key]=[make_material('context_'+rec['category']+'_'+n,c,.8,0) for n,c in rec['materials']]
   with np.load(root/rec['file']) as a:arrays={k:a[k] for k in a.files}
   ob=bpy.data.objects.new(rec['id'],mesh(rec['id'],arrays,matcache[key],rec['category']=='terrain'));coll.objects.link(ob);ob['source_file']=rec['source_file'];ob['context_category']=rec['category'];ob['original_city_origin_m']=context['origin_city_m'];ob['local_coordinate_frame']='same inverse geotransform as selected landmark'
  other=[];center=np.array(context['origin_city_m']);theta=context['rotation_z_radians'];R=np.array([[math.cos(theta),math.sin(theta),0],[-math.sin(theta),math.cos(theta),0],[0,0,1]])
  for neighbor in index['landmarks']:
   if neighbor['id']==ident:continue
   a=read(neighbor['card']);distance=np.linalg.norm(np.array(a['origin_city_m'][:2])-center[:2])
   if distance>context['radius_m']:continue
   ob,c=import_landmark(neighbor,mats);ob.location=R@(np.array(a['origin_city_m'])-center);ob.rotation_euler.z=a['rotation_z_radians']-theta
   for q in c.all_objects:
    if q.get('landmark_lod'):q.hide_render=q['landmark_lod']!='mid';q.hide_viewport=q.hide_render
   other.append(neighbor['id'])
  near=next(a for a in item['assets'] if a['lod']=='near');lo,hi=np.array(near['bounds_local_m']);direction=np.array(card['front_local_direction']);right=np.array([-direction[1],direction[0]]);span=max(250.,(hi[0]-lo[0])*1.8,(hi[1]-lo[1])*1.8,(hi[2]-lo[2])*1.6);target=np.array([0,0,max(6,hi[2]*.36)]);offset=direction*span*1.35+right*span*.60;position=target+np.array([*offset,span*.67])
  if ident=='hollywood_sign':span=155.;target=np.array([0,0,7.]);position=np.array([25.,-240.,-18.])
  if ident in ['dodger_stadium','memorial_coliseum']:position[2]=target[2]+span*1.3
  aim(position,target,span);s['stage']=6;s['stage06_context_landmark']=ident;s['context_true_city_radius_m']=context['radius_m'];s['context_other_refined_landmarks']=other;s['context_uses_same_geographic_transform']=True;s['context_preview_boundary']='finite circular extraction for offline inspection; not runtime streaming';save('scenes/stage06_context_'+ident+'.blend')
def contexts_render():
 ident=args.id;s=bpy.context.scene;assert s['stage06_context_landmark']==ident;setup_scene();render('work/previews/stage06/'+ident+'/environment.png');write('work/reports/stage06/contexts/'+ident+'.json',{'status':'passed','saved_scene_reopened_independently':True,'true_geographic_neighbors':True,'same_transform_as_landmark':True,'source_context_index':'data/processed/stage06/context_index.json','image':'work/previews/stage06/'+ident+'/environment.png','camera_position_local_m':list(s.camera.location),'camera_target_orientation_radians':list(s.camera.rotation_euler),'other_refined_landmarks':list(s['context_other_refined_landmarks'])})
def integrate():
 s=bpy.context.scene;identity=read('data/processed/stage06/landmark_index.json');selected={r['i'] for a in identity['landmarks'] for r in a['replaces']};cells={r['cell'] for a in identity['landmarks'] for r in a['replaces']};changed=[];points_changed=[];retained_verified=0
 for ob in list(s.objects):
  if ob.type!='MESH':continue
  if ob.get('building_cell') in cells and ob.get('building_lod') is not None:
   m=ob.data;fid=np.empty(len(m.polygons),np.int32);m.attributes['building_index'].data.foreach_get('value',fid);keep=~np.isin(fid,list(selected));removed=int((~keep).sum())
   if not removed:continue
   v=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',v);v=v.reshape(-1,3);f=np.empty(len(m.loops),np.int32);m.loops.foreach_get('vertex_index',f);f=f.reshape(-1,3);mi=np.empty(len(m.polygons),np.int32);m.polygons.foreach_get('material_index',mi);newf=f[keep];ids,inv=np.unique(newf,return_inverse=True);arrays={'v':v[ids],'f':inv.reshape(-1,3).astype(np.int32),'m':mi[keep],'fid':fid[keep]}
   if m.uv_layers:
    uv=np.empty(len(m.loops)*2,np.float32);m.uv_layers.active.data.foreach_get('uv',uv);arrays['uv']=uv.reshape(-1,3,2)[keep]
   assert np.array_equal(arrays['v'][arrays['f']],v[newf]);retained_verified+=len(newf);old=m;ob.data=mesh(old.name+'_stage06_proxy_replacement',arrays,list(old.materials));ob['stage06_excluded_proxy_indices']=json.dumps(sorted(set(fid[~keep].tolist())));changed.append({'object':ob.name,'cell':ob['building_cell'],'lod':int(ob['building_lod']),'removed_faces':removed,'removed_building_indices':sorted(set(fid[~keep].tolist())),'retained_faces':len(newf),'retained_triangle_coordinates_exactly_equal':True})
   if old.users==0:bpy.data.meshes.remove(old)
  elif ob.get('instance_kind_05'):
   m=ob.data;fid=np.empty(len(m.vertices),np.int32);m.attributes['building_index'].data.foreach_get('value',fid);keep=~np.isin(fid,list(selected))
   if keep.all():continue
   data=bpy.data.meshes.new(m.name+'_without_landmark_modules');v=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',v);v=v.reshape(-1,3);data.vertices.add(int(keep.sum()));data.vertices.foreach_set('co',v[keep].ravel());data.attributes.new('building_index','INT','POINT').data.foreach_set('value',fid[keep])
   for name in ['module_scale','module_rotation']:
    values=np.empty(len(m.vertices)*3,np.float32);m.attributes[name].data.foreach_get('vector',values);data.attributes.new(name,'FLOAT_VECTOR','POINT').data.foreach_set('vector',values.reshape(-1,3)[keep].ravel())
   data.update();old=m;ob.data=data;oldcount=int(ob['building_instances']);ob['building_instances']=int(keep.sum());prototype=bpy.data.objects['Module_'+ob['instance_kind_05']];ob['instance_triangles_05']=int(keep.sum())*len(prototype.data.polygons);points_changed.append({'object':ob.name,'removed_module_instances':oldcount-int(keep.sum()),'remaining_instances':int(keep.sum())})
   if old.users==0:bpy.data.meshes.remove(old)
 terrain=read('data/processed/stage06/ground_index.json');tmap={t['id']:t for t in terrain['tiles']};terrain_data={};patched=[]
 for ob in s.objects:
  tid=ob.get('tile_id');lod=ob.get('lod')
  if tid not in tmap or lod is None or ob.type!='MESH' or ob.get('traffic_role') or ob.get('instance_kind'):continue
  t=tmap[tid]
  if tid not in terrain_data:
   with np.load(root/t['file']) as d:arrays={k:d[k] for k in d.files}
   terrain_data[tid]=mesh(tid+'_stage06_native_detail_and_recorded_grading',arrays,list(ob.data.materials),True)
  old=ob.data;ob.data=terrain_data[tid];ob['stage06_ground_variant']=t['file'];ob['stage06_terrain_lod_note']='same shared refined patch across static alternate LODs; decimation pending viewer stage';patched.append(ob.name)
  if old.users==0:bpy.data.meshes.remove(old)
 index=read('data/processed/stage06/geometry_index.json');mats=[make_material(*m) for m in index['materials']]
 for item in index['landmarks']:import_landmark(item,mats,True)
 # Retain editable full city. The saved working view displays a bounded static region.
 focus=np.array(read('data/processed/stage06/cards/the_broad.json')['origin_city_m']);objs=list(bpy.data.objects);shows={};bounds_cache={};hidden={o.name for c in bpy.data.collections if c.hide_render for o in c.all_objects}
 for o in objs:
  show=not o.hide_render
  if o.type=='MESH' and o.get('landmark_id'):
   a=read('data/processed/stage06/cards/'+o['landmark_id']+'.json');d=np.linalg.norm(np.array(a['origin_city_m'][:2])-focus[:2]);wanted='near' if d<100 else 'mid' if d<1000 else 'far';show=o['landmark_lod']==wanted and d<1500
  elif o.type=='MESH':
   lohi=o.get('stage05_bounds_m');role=o.get('traffic_role')
   if o.get('instance_kind'):show=False
   else:
    if lohi is not None:lo=np.array(lohi[:3]);hi=np.array(lohi[3:])
    else:
     key=o.data.as_pointer()
     if key not in bounds_cache:
      v=np.empty(len(o.data.vertices)*3,np.float32);o.data.vertices.foreach_get('co',v);v=v.reshape(-1,3);bounds_cache[key]=(v.min(axis=0),v.max(axis=0)) if len(v) else (np.zeros(3),np.zeros(3))
     lo,hi=bounds_cache[key];lo=lo+np.array(o.location);hi=hi+np.array(o.location)
    near=lo[0]<focus[0]+450 and hi[0]>focus[0]-450 and lo[1]<focus[1]+450 and hi[1]>focus[1]-450;lod=o.get('building_lod')
    if lod is not None:show=near and int(lod)==2
    elif o.get('instance_kind_05'):show=False
    elif role:show=near and role in ['overview_far','downtown_road','downtown_sidewalk','bridge_road','tunnel_road','profiled_priority_road','rail_corridor','inferred_retaining_bank']
    elif o.get('tile_id') and o.get('lod') is not None:show=near
    else:show=bool(o.get('stage04_full_view_visible',show)) and near
  if o.name in hidden:show=False
  shows[o.name]=show
 flags=np.array([not shows[o.name] for o in objs],bool);bpy.data.objects.foreach_set('hide_render',flags);bpy.data.objects.foreach_set('hide_viewport',flags);tri=sum(int(o.get('instance_triangles_05',len(o.data.polygons))) for o in objs if o.type=='MESH' and shows[o.name]);assert tri<=1500000,tri
 setup_scene();aim(focus+[420,-420,260],focus+[0,30,30],700);s['stage']=6;s['stage06_checkpoint']='ten independent approximate detailed landmarks integrated with stable source identities';s['stage06_replaced_building_indices']=json.dumps(sorted(selected));s['stage06_saved_default_visible_triangles']=tri;s['stage06_static_focus_city_m']=focus.tolist();s['stage06_model_status']='approximate_complete_with_documented_observation_gaps; not all fine detail verified';s['runtime_lod']='near/mid/far assets and actual individualGLBs available; static Blender choices, no distance switching/streaming';save(cfg['output_checkpoint']);write('work/reports/stage06/integration_build.json',{'status':'saved','source_checkpoint':cfg['source_checkpoint'],'source_proxy_count':len(selected),'affected_body_objects':changed,'affected_module_objects':points_changed,'retained_triangle_coordinates_exactly_equal_count':retained_verified,'patched_ground_objects':patched,'ground_shared_meshes':len(terrain_data),'landmark_roots':10,'default_visible_triangles':tri,'medium_budget':1500000,'full_city_locally_editable':True,'runtime_switching':False})
def main_check():
 s=bpy.context.scene;selected=set(json.loads(s['stage06_replaced_building_indices']));remaining=remainingpoints=bad=degen=0;newtri=0;newverts=0;geo=[];roots=[o for o in s.objects if o.name.startswith('Landmark_') and o.get('stable_id')];assert len(roots)==10
 for o in s.objects:
  if o.type!='MESH':continue
  m=o.data
  if o.get('building_lod') is not None:
   ids=np.empty(len(m.polygons),np.int32);m.attributes['building_index'].data.foreach_get('value',ids);remaining+=int(np.isin(ids,list(selected)).sum())
  if o.get('instance_kind_05'):
   ids=np.empty(len(m.vertices),np.int32);m.attributes['building_index'].data.foreach_get('value',ids);remainingpoints+=int(np.isin(ids,list(selected)).sum())
  if o.get('landmark_id') or o.get('stage06_ground_variant'):
   v=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',v);v=v.reshape(-1,3);f=np.empty(len(m.loops),np.int32);m.loops.foreach_get('vertex_index',f);f=f.reshape(-1,3);bad+=int((~np.isfinite(v)).sum());degen+=int((np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)<=1e-8).sum());newtri+=len(f);newverts+=len(v)
 for o in roots:
  ident=o['stable_id'].split(':')[1];a=read('data/processed/stage06/cards/'+ident+'.json');d=float(np.max(np.abs(np.array(o.location)-a['origin_city_m'])));r=abs(o.rotation_euler.z-a['rotation_z_radians']);assert d<.001 and r<1e-6;lods={}
  for q in o.children:
   if q.get('landmark_lod') and not q.hide_render:lods[q['landmark_lod']]=True
  assert len(lods)<=1;geo.append({'id':ident,'translation_numeric_error_m':d,'rotation_numeric_error_rad':r,'active_static_lods':list(lods),'source_accuracy':'source-dependent/unknown, not this numeric transform error'})
 assert remaining==remainingpoints==bad==degen==0;assert s.unit_settings.scale_length==1 and s.unit_settings.system=='METRIC';hidden={o.name for c in bpy.data.collections if c.hide_render for o in c.all_objects};tri=sum(int(o.get('instance_triangles_05',len(o.data.polygons))) for o in s.objects if o.type=='MESH' and not o.hide_render and o.name not in hidden);assert tri==s['stage06_saved_default_visible_triangles'] and tri<=1500000
 write('work/reports/stage06/main_check.json',{'status':'passed','saved_checkpoint_reopened_in_independent_process':True,'removed_proxy_faces_remaining':remaining,'removed_proxy_module_points_remaining':remainingpoints,'new_geometry_nonfinite':bad,'new_geometry_degenerate':degen,'new_geometry_triangles_including_hidden_lods_and_shared_terrain_objects':newtri,'geographic_roots':geo,'meters_per_unit':1,'actual_default_visible_triangles':tri,'inherited_stage05_unknowns_retained':True});setup_scene();render('work/previews/stage06/city_integration.png')
def glb_check():
 results=[]
 for item in read('data/processed/stage06/geometry_index.json')['landmarks']:
  for a in item['assets']:
   ident=item['id'];lod=a['lod'];path=root/'outputs/stage06/glb'/ident/(lod+'.glb');bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(path));lo,hi=saved_bounds(list(bpy.context.scene.objects),True);expected=np.array(a['bounds_local_m']);delta=float(np.max(np.abs(np.array([lo,hi])-expected)));assert delta<.15,(ident,lod,delta);bad=0
   for ob in bpy.context.scene.objects:
    if ob.type=='MESH':
     v=np.empty(len(ob.data.vertices)*3,np.float32);ob.data.vertices.foreach_get('co',v);bad+=int((~np.isfinite(v)).sum())
   assert bad==0
   with path.open('rb') as f:checksum=hashlib.file_digest(f,'sha256').hexdigest()
   results.append({'id':ident,'lod':lod,'path':str(path.relative_to(root)),'sha256':checksum,'actual_export_reimport':'passed','bounds_numeric_difference_m':delta,'coordinate_orientation':'Blender Z-up restored from glTF Y-up','source_accuracy':'not established by reimport','nonfinite':bad});print('GLB_REIMPORT_CHECK',ident,lod,delta,flush=True)
 write('work/reports/stage06/glb_reimport.json',{'status':'passed','actual_blender_import_count':len(results),'assets':results})
def refresh_landmark():
 """Keep an editable delta from an unaccepted draft before a documented factual correction."""
 ident=args.id;s=bpy.context.scene;massing=Path(bpy.data.filepath).name=='stage06_massing.blend';index=read('data/processed/stage06/'+('massing_index.json' if massing else 'geometry_index.json'));item=next(i for i in index['landmarks'] if i['id']==ident);oldcoll=bpy.data.collections.get('LM_'+ident);oldobjects=set(oldcoll.all_objects);archive=root/'work/history/stage06_before_official_observatory_dimensions';archive.mkdir(parents=True,exist_ok=True)
 bpy.data.libraries.write(str(archive/(('massing_' if massing else 'city_')+ident+'_old_editable_delta.blend')),oldobjects,fake_user=True,compress=True)
 def visible_digest(objects):
  out={}
  for q in objects:
   if q.type!='MESH' or q.hide_render:continue
   v=np.empty(len(q.data.vertices)*3,np.float32);q.data.vertices.foreach_get('co',v);f=np.empty(len(q.data.loops),np.int32);q.data.loops.foreach_get('vertex_index',f);out[q['component']]=hashlib.sha256(v.tobytes()+f.tobytes()).hexdigest()
  return out
 old_default_tri=int(s.get('stage06_saved_default_visible_triangles',0));oldhash=visible_digest(oldobjects);shownlods={q['landmark_lod'] for q in oldobjects if q.type=='MESH' and not q.hide_render};oldmeshes={o.data for o in oldobjects if o.type=='MESH'}
 for ob in list(oldobjects):bpy.data.objects.remove(ob,do_unlink=True)
 for c in list(oldcoll.children):bpy.data.collections.remove(c)
 bpy.data.collections.remove(oldcoll)
 for m in oldmeshes:
  if m.users==0:bpy.data.meshes.remove(m)
 mats=[bpy.data.materials.get('LA06_'+m[0]) or make_material(*m) for m in index['materials']];ob,c=import_landmark(item,mats,True,massing)
 if not massing:
  for q in c.all_objects:
   if q.type=='MESH':q.hide_render=q['landmark_lod'] not in shownlods;q.hide_viewport=q.hide_render
  assert visible_digest(c.all_objects)==oldhash,'This mode requires unchanged saved default visible component geometry';assert s['stage06_saved_default_visible_triangles']==old_default_tri
 save(str(Path(bpy.data.filepath).relative_to(root)));write('work/reports/stage06/'+('massing_' if massing else 'city_')+'official_dimension_correction.json',{'status':'saved','id':ident,'official_source':'https://griffithobservatory.lacity.gov/about/fun-facts/','main_dome_reference_m':77*.3048,'telescope_dome_reference_m':55*.3048,'previous_editable_landmark_delta':str(archive.relative_to(root)),'previous_unaccepted_full_binary_not_archived_byte_for_byte':True,'source_stage05_untouched':True,'default_visible_geometry_unchanged':not massing})
def refresh_landcover():
 t=next(t for t in read('data/processed/stage06/ground_index.json')['tiles'] if t['id']=='la_t_x-007_y+010');done=set();changed=0
 with np.load(root/t['file']) as a:mi=a['m']
 for ob in bpy.context.scene.objects:
  if ob.get('stage06_ground_variant')==t['file'] and ob.data.as_pointer() not in done:
   m=ob.data;assert len(m.polygons)==len(mi);old=np.empty(len(mi),np.int32);m.polygons.foreach_get('material_index',old);changed+=int((old!=mi).sum());m.polygons.foreach_set('material_index',mi);done.add(m.as_pointer());ob['surface_color_override']='inferred dry_slope for source NLCD water-cover conflict; raw class retained in NPZ source_m; not hydrology evidence'
 save(str(Path(bpy.data.filepath).relative_to(root)));write('work/reports/stage06/city_landcover_correction.json',{'status':'saved','unique_meshes':len(done),'changed_face_colors':changed,'geometry_changed':False,'classification':'photo-guided inferred display correction, not observed water geometry'})
if __name__=='__main__':
 if args.mode=='contexts-build':contexts_build()
 elif args.mode=='context-render':contexts_render()
 elif args.mode=='integrate':integrate()
 elif args.mode=='main-check':main_check()
 elif args.mode=='glb-check':glb_check()
 elif args.mode=='refresh-landmark':refresh_landmark()
 elif args.mode=='refresh-landcover':refresh_landcover()
 else:raise RuntimeError('未实现 / NOT IMPLEMENTED: '+args.mode)
