"""Blender stage07: shared near-street assets, independent reopen audit and actual renders."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage06_blender import *
cfg7=read('config/stage07.json');s=bpy.context.scene
def collection(name,parent=None):
 c=bpy.data.collections.new(name);(parent.children if parent else s.collection.children).link(c);return c
def instances(name,items,origin,prototype,coll):
 xyz=np.array([q['xyz'] for q in items],np.float32)-np.asarray(origin,np.float32);data=bpy.data.meshes.new(name);data.vertices.add(len(xyz));data.vertices.foreach_set('co',xyz.ravel())
 for field,values in [('module_scale',[q['scale'] for q in items]),('module_rotation',[[0,0,q['rotation']] for q in items])]:data.attributes.new(field,'FLOAT_VECTOR','POINT').data.foreach_set('vector',np.asarray(values,np.float32).ravel())
 data.attributes.new('building_index','INT','POINT').data.foreach_set('value',np.array([q['fid'] for q in items],np.int32));data.update();ob=bpy.data.objects.new(name,data);coll.objects.link(ob);ob.location=origin
 tree=bpy.data.node_groups.new(name+'_shared_instances','GeometryNodeTree');tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry');n=tree.nodes;l=tree.links;inp=n.new('NodeGroupInput');out=n.new('NodeGroupOutput');info=n.new('GeometryNodeObjectInfo');info.inputs['Object'].default_value=prototype;info.inputs['As Instance'].default_value=True;node=n.new('GeometryNodeInstanceOnPoints');l.new(inp.outputs['Geometry'],node.inputs['Points']);l.new(info.outputs['Geometry'],node.inputs['Instance']);l.new(node.outputs['Instances'],out.inputs['Geometry'])
 for attr,sock in [('module_scale','Scale'),('module_rotation','Rotation')]:a=n.new('GeometryNodeInputNamedAttribute');a.data_type='FLOAT_VECTOR';a.inputs['Name'].default_value=attr;l.new(a.outputs['Attribute'],node.inputs[sock])
 mod=ob.modifiers.new('Editable shared near-street instances','NODES');mod.node_group=tree;ob['stage07_kind']=prototype['stage07_kind'];ob['instance_triangles_07']=len(items)*len(prototype.data.polygons);ob['stage07_instances']=len(items);ob['stage07_bounds_m']=(xyz.min(axis=0)+origin-10).tolist()+(xyz.max(axis=0)+origin+10).tolist();ob['data_class']='OSM point position or inherited inferred aperture; per-point provenance in module_placements/street_features.json';return ob
def array_mesh(m):
 v=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',v);f=np.empty(len(m.loops),np.int32);m.loops.foreach_get('vertex_index',f);mi=np.empty(len(m.polygons),np.int32);m.polygons.foreach_get('material_index',mi);return v.reshape(-1,3),f.reshape(-1,3),mi
def paving_material():
 mat=bpy.data.materials.new('LA07_metre_concrete_paving_inferred');mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;bs=n.get('Principled BSDF');bs.inputs['Roughness'].default_value=.82;geo=n.new('ShaderNodeNewGeometry');sep=n.new('ShaderNodeSeparateXYZ');l.new(geo.outputs['Position'],sep.inputs[0]);tests=[]
 for axis in ['X','Y']:
  div=n.new('ShaderNodeMath');div.operation='DIVIDE';div.inputs[1].default_value=cfg7['paving']['tile_m'];l.new(sep.outputs[axis],div.inputs[0]);mod=n.new('ShaderNodeMath');mod.operation='PINGPONG';mod.inputs[1].default_value=.5;l.new(div.outputs[0],mod.inputs[0]);lt=n.new('ShaderNodeMath');lt.operation='LESS_THAN';lt.inputs[1].default_value=cfg7['paving']['joint_m']/cfg7['paving']['tile_m'];l.new(mod.outputs[0],lt.inputs[0]);tests.append(lt)
 add=n.new('ShaderNodeMath');add.operation='MAXIMUM';l.new(tests[0].outputs[0],add.inputs[0]);l.new(tests[1].outputs[0],add.inputs[1]);mix=n.new('ShaderNodeMixRGB');mix.inputs[1].default_value=(.43,.405,.36,1);mix.inputs[2].default_value=(.25,.24,.22,1);l.new(add.outputs[0],mix.inputs[0]);l.new(mix.outputs[0],bs.inputs['Base Color']);bump=n.new('ShaderNodeBump');bump.invert=True;bump.inputs['Strength'].default_value=.4;bump.inputs['Distance'].default_value=cfg7['paving']['bump_m'];l.new(add.outputs[0],bump.inputs['Height']);l.new(bump.outputs['Normal'],bs.inputs['Normal']);mat['evidence']='inferred neutral .6m paving; not observed slab layout';return mat
def build():
 assert Path(bpy.data.filepath)==root/cfg7['source_scene'];bs=read('data/processed/stage07/buildings.json');bmap={b['i']:b for b in bs};ids=list(bmap);delta={i:b['floor_delta_m'] for i,b in bmap.items()};cells={b['cell'] for b in bs};changed=[];modules_changed=[]
 for ob in list(s.objects):
  if ob.type!='MESH':continue
  m=ob.data
  if ob.get('building_cell') in cells and ob.get('building_lod') is not None:
   fid=np.empty(len(m.polygons),np.int32);m.attributes['building_index'].data.foreach_get('value',fid);v,f,mi=array_mesh(m);oldv=v.copy();touched=False
   for i,d in delta.items():
    if not d or not np.any(fid==i):continue
    vi=np.unique(f[fid==i]);others=np.unique(f[fid!=i]);assert not np.intersect1d(vi,others).size,'Shared vertex across unrelated buildings';v[vi,2]+=d;touched=True
   if touched:
    unchanged=~np.isin(fid,[i for i,d in delta.items() if d]);assert np.array_equal(v[f[unchanged]],oldv[f[unchanged]]);m.vertices.foreach_set('co',v.ravel());m.update();ob['stage07_visual_floor_adjustment']='per-building inferred Z shift only; source XY/height unchanged';changed.append({'object':ob.name,'untouched_triangles_exact':int(unchanged.sum()),'xy_exactly_unchanged':bool(np.array_equal(v[:,:2],oldv[:,:2]))})
  elif ob.get('instance_kind_05'):
   fid=np.empty(len(m.vertices),np.int32);m.attributes['building_index'].data.foreach_get('value',fid)
   if not np.isin(fid,ids).any():continue
   kind=ob['instance_kind_05'];keep=~np.isin(fid,ids) if kind in ['window_frame','entry_door','canopy','step'] else np.ones(len(fid),bool);v=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',v);v=v.reshape(-1,3)
   for i,d in delta.items():
    if d:v[fid==i,2]+=d
   data=bpy.data.meshes.new(m.name+'_stage07');data.vertices.add(int(keep.sum()));data.vertices.foreach_set('co',v[keep].ravel());data.attributes.new('building_index','INT','POINT').data.foreach_set('value',fid[keep])
   for name in ['module_scale','module_rotation']:
    a=np.empty(len(fid)*3,np.float32);m.attributes[name].data.foreach_get('vector',a);data.attributes.new(name,'FLOAT_VECTOR','POINT').data.foreach_set('vector',a.reshape(-1,3)[keep].ravel())
   data.update();ob.data=data;ob['building_instances']=int(keep.sum());ob['instance_triangles_05']=int(keep.sum())*len(bpy.data.objects['Module_'+kind].data.polygons);modules_changed.append({'object':ob.name,'removed':int((~keep).sum())})
   if m.users==0:bpy.data.meshes.remove(m)
 index=read('data/processed/stage07/geometry_index.json');mats=[make_material('stage07_'+n,c,r,me) for n,c,r,me in index['materials']];library=collection('31_STAGE07_MODULE_LIBRARY_hidden');library.hide_render=True;library.hide_viewport=True;protos={}
 for rec in index['modules']:
  with np.load(root/rec['file']) as a:ar={k:a[k] for k in a.files}
  ob=bpy.data.objects.new('LA07_Module_'+rec['kind'],mesh('LA07_Shared_'+rec['kind'],ar,mats));library.objects.link(ob);ob['stage07_kind']=rec['kind'];ob['evidence']=rec['shape_evidence'];protos[rec['kind']]=ob
 libpath=root/'assets/street_furniture/stage07_modules.blend';bpy.data.libraries.write(str(libpath),set(protos.values()),fake_user=True,compress=True)
 parent=collection('30_STAGE07_NEAR_STREETS_editable');regions={r:collection('LA07_'+r,parent) for r in cfg7['regions']};items=read('data/processed/stage07/module_placements.json')['instances']+index['street_instances'];buckets=collections.defaultdict(list)
 for a in items:buckets[(a['region'],a['kind'],bmap[a['fid']]['cell'] if a['fid'] in bmap else 'street')].append(a)
 for (region,kind,cell),items in buckets.items():
  origin=[-432.3949595,857.11258,0] if region=='historic_core' else [215.43239,1747.54794,0];instances('LA07_'+region+'_'+cell+'_'+kind,items,origin,protos[kind],regions[region])
 for rec in index['site_meshes']:
  with np.load(root/rec['file']) as a:ar={k:a[k] for k in a.files}
  ob=bpy.data.objects.new('LA07_'+rec['id'],mesh('LA07_'+rec['id'],ar,mats));regions[rec['region']].objects.link(ob);ob.location=rec['origin_city_m'];ob['stage07_region']=rec['region'];ob['evidence']='inferred solid steps, landings and handrails; no compliance certification'
 groundmap={t['id']:t for t in read('data/processed/stage07/ground_index.json')['tiles']};cache={}
 for ob in s.objects:
  tid=ob.get('tile_id')
  if tid not in groundmap or ob.type!='MESH' or ob.get('lod') is None or ob.get('traffic_role') or ob.get('instance_kind'):continue
  rec=groundmap[tid]
  if tid not in cache:
   with np.load(root/rec['file']) as a:ar={k:a[k] for k in a.files}
   cache[tid]=mesh(tid+'_stage07_recorded_grade',ar,list(ob.data.materials),True)
  old=ob.data;ob.data=cache[tid];ob['stage07_ground_variant']=rec['file']
  if old.users==0:bpy.data.meshes.remove(old)
 pave=paving_material();rects=[(-607.3949595,657.11258,-257.3949595,1057.11258),(40.43239,1547.54794,390.43239,1947.54794)];paving=[]
 for ob in s.objects:
  if ob.type!='MESH' or ob.get('traffic_role') not in ['downtown_sidewalk','downtown_curb']:continue
  v,f,mi=array_mesh(ob.data);p=v[f].mean(axis=1)+np.array(ob.location);mask=np.zeros(len(f),bool)
  for x0,y0,x1,y1 in rects:mask|=(p[:,0]>=x0)&(p[:,0]<=x1)&(p[:,1]>=y0)&(p[:,1]<=y1)
  if not mask.any():continue
  slot=len(ob.data.materials);ob.data.materials.append(pave);mi[mask]=slot;ob.data.polygons.foreach_set('material_index',mi);ob['stage07_paving_material_only']=True;paving.append({'object':ob.name,'faces':int(mask.sum()),'geometry_unchanged':True})
 s['stage']=7;s['stage07_status']='approximate near-street refinement; source-specific and generic details distinguished';s['stage07_regions']=cfg7['regions'];s['stage07_buildings']=len(bs);s['stage07_inference_ledger']='data/processed/stage07/buildings.json';s['stage07_main_source_scene']=cfg7['source_scene'];setup_scene(cfg7['closeup_render']['width'],cfg7['closeup_render']['height'],cfg7['closeup_render']['samples']);s.cycles.seed=cfg7['seed'];s.view_settings.exposure=.8
 from stage07_views import set_visibility,aim_view,views
 budget=[]
 for radius in [250,180,120,80]:
  tri=set_visibility(s,root,[-462.988,769.892],radius,True);budget.append({'radius_m':radius,'triangles':tri})
  if tri<=cfg7['static_visible_triangle_limit']:break
 assert tri<=cfg7['static_visible_triangle_limit'];s['stage07_default_visible_triangles']=tri;s['stage07_default_radius_m']=radius;aim_view(s,views(root)['historic_core_street']);text=bpy.data.texts.new('STAGE07_SOURCE_AND_INFERENCE.json');text.write(json.dumps({'config':cfg7,'buildings':bs,'street_features':'data/processed/stage07/street_features.json'},ensure_ascii=False));save(cfg7['output_scene']);write('work/reports/stage07/blender_build.json',{'status':'saved_requires_independent_reopen','body_changes':changed,'old_module_changes':modules_changed,'paving':paving,'shared_module_types':len(protos),'budget_attempts':budget,'actual_saved_default_triangles':tri,'raw_source_scene_modified':False})
def check():
 assert Path(bpy.data.filepath)==root/cfg7['output_scene'];bs=read('data/processed/stage07/buildings.json');ids=[b['i'] for b in bs];bmap={b['i']:b for b in bs};cells={b['cell'] for b in bs};excluded=set(json.loads(s['stage06_replaced_building_indices']));bad=degen=materialbad=remaining=points=0;seen=set();body_checks=[];counts=collections.Counter();instance_rows=[];newtris=0;samples={}
 for ob in s.objects:
  if ob.type!='MESH':continue
  m=ob.data;attribute=m.attributes.get('building_index')
  if ob.get('building_lod') is not None:
   fid=np.empty(len(m.polygons),np.int32);attribute.data.foreach_get('value',fid);remaining+=int(np.isin(fid,list(excluded)).sum())
   if ob.get('building_cell') in cells:
    v,f,mi=array_mesh(m)
    with np.load(root/ob['source_file']) as a:sv=a['v'];sf=a['f'];si=a['fid'];keep=~np.isin(si,list(excluded));sf=sf[keep];si=si[keep];expected=sv[sf].copy()
    for i,b in bmap.items():
     if b['floor_delta_m']:expected[si==i,:,2]+=b['floor_delta_m']
    assert len(f)==len(sf) and np.array_equal(fid,si);xyerr=float(np.max(abs(v[f][:,:,:2]-expected[:,:,:2]))) if len(f) else 0.;zerr=float(np.max(abs(v[f][:,:,2]-expected[:,:,2]))) if len(f) else 0.;assert xyerr==0 and zerr<.0001;(body_checks.append({'object':ob.name,'lod':int(ob['building_lod']),'source_xy_error_m':xyerr,'expected_z_error_m':zerr,'source_heights_and_holes_preserved':True}))
    if int(ob['building_lod'])==0:
     for i in set(fid.tolist())&set(ids):
      mask=fid==i;vv=v[np.unique(f[mask])]+np.array(ob.location);b=bmap[i];matnames=[m.materials[j].name for j in np.unique(mi[mask])];samples[str(i)]={'uid':b['uid'],'name':b['name'],'region':b['region'],'type':b['building_type'],'actual_bounds_city_m':[vv.min(axis=0).tolist(),vv.max(axis=0).tolist()],'height_input_m':b['height_m'],'height_source':b['height_evidence'],'visual_floor_delta_m':b['floor_delta_m'],'source_triangle_xy_unchanged':True,'source_height_geometry_preserved':True,'source_courtyard_holes':b['old_placement']['courtyard_holes'],'materials':matnames,'entry':b['entry'],'exterior_authenticity':'generic detailed modules; full facade evidence incomplete'}
  if ob.get('instance_kind_05'):
   fid=np.empty(len(m.vertices),np.int32);attribute.data.foreach_get('value',fid);points+=int(np.isin(fid,list(excluded)).sum())
   if ob['instance_kind_05'] in ['window_frame','entry_door','canopy','step']:assert not np.isin(fid,ids).any(),'old near-detail duplicates'
  if ob.get('stage07_kind') and ob.name.startswith('LA07_') and not ob.name.startswith('LA07_Module_'):
   counts[ob['stage07_kind']]+=int(ob.get('stage07_instances',0));instance_rows.append({'object':ob.name,'points':len(m.vertices),'prototype_triangles_times_points':int(ob['instance_triangles_07'])})
  if m.as_pointer() in seen:continue
  seen.add(m.as_pointer())
  if ob.get('building_cell') in cells or ob.get('stage07_kind') or ob.get('stage07_region') or ob.get('stage07_ground_variant'):
   v,f,mi=array_mesh(m);bad+=int((~np.isfinite(v)).sum());degen+=int((np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)<=1e-8).sum());materialbad+=int(((mi<0)|(mi>=len(m.materials))).sum());newtris+=len(f)
 roots=[o for o in s.objects if o.name.startswith('Landmark_') and o.get('stable_id')];assert len(roots)==10 and any(o['stable_id']=='landmark:city_hall' for o in roots);assert bad==degen==materialbad==remaining==points==0;assert s.unit_settings.scale_length==1
 expected=collections.defaultdict(list);geo=read('data/processed/stage07/geometry_index.json')
 for a in read('data/processed/stage07/module_placements.json')['instances']+geo['street_instances']:
  cell=bmap[a['fid']]['cell'] if a['fid'] in bmap else 'street';expected['LA07_'+a['region']+'_'+cell+'_'+a['kind']].append(a)
 pointchecks=[]
 for name,items in expected.items():
  ob=bpy.data.objects[name];m=ob.data;v=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',v);world=v.reshape(-1,3)+np.array(ob.location);target=np.array([a['xyz'] for a in items]);err=float(np.max(abs(world-target)));assert err<.0002 and len(m.vertices)==len(items);fid=np.empty(len(items),np.int32);m.attributes['building_index'].data.foreach_get('value',fid);assert np.array_equal(fid,np.array([a['fid'] for a in items]));pointchecks.append({'object':name,'points':len(items),'max_serialized_world_point_error_m':err})
 write('work/reports/stage07/point_placement_check.json',{'status':'passed','objects':pointchecks,'source_xy_not_randomized':True,'inferred_shapes_and_doorway_positions_not_survey_certified':True})
 from stage07_views import count_visible
 tri=count_visible(s);assert tri==s['stage07_default_visible_triangles'] and tri<=1500000;assert len(samples)==103;write('work/reports/stage07/building_audit.json',{'status':'passed_numeric_appearance_approximate','actual_saved_authoring_buildings_checked':len(samples),'buildings':samples});write('work/reports/stage07/blender_check.json',{'status':'passed','saved_file_reopened_in_independent_process':True,'path':str(Path(bpy.data.filepath).relative_to(root)),'nonfinite_coordinates':bad,'degenerate_triangles':degen,'invalid_material_indices':materialbad,'old_stage06_proxy_faces':remaining,'old_stage06_proxy_module_points':points,'source_body_checks':body_checks,'near_buildings':len(bs),'shared_instance_counts':dict(counts),'instance_objects':instance_rows,'new_and_affected_stored_triangles_checked':newtris,'default_visible_triangles':tri,'meters_per_unit':1,'landmark_roots_preserved':len(roots),'architectural_and_source_accuracy_certified':False});print('STAGE07_INDEPENDENT_REOPEN_CHECK_PASSED',tri,dict(counts),flush=True)
def renders():
 from stage07_views import views,set_visibility,aim_view
 setup_scene(cfg7['closeup_render']['width'],cfg7['closeup_render']['height'],cfg7['closeup_render']['samples']);s.cycles.seed=cfg7['seed'];s.cycles.max_bounces=4;records={}
 for name,v in views(root).items():
  if args.id not in ['all',name]:continue
  tri=set_visibility(s,root,v['focus_xy_m'],v['radius_m'],False);aim_view(s,v);s.view_settings.exposure=v.get('exposure',.9);render('work/previews/stage07/'+name+'.png');records[name]=v|{'actual_visible_triangles_including_shared_instances':tri,'actual_cpu_cycles':True,'output':'work/previews/stage07/'+name+'.png'}
 write('work/reports/stage07/renders_'+args.id+'.json',{'status':'executed','renders':records,'actual_saved_scene_opened':bpy.data.filepath,'offline_inspection_not_runtime_fps':True})
 if args.id!='all' and (root/'work/reports/stage07/renders_all.json').exists():
  allr=read('work/reports/stage07/renders_all.json');allr['renders'].update(records);allr['targeted_rerenders_applied']=True;write('work/reports/stage07/renders_all.json',allr)
def patch():
 assert Path(bpy.data.filepath)==root/cfg7['output_scene'];index=read('data/processed/stage07/geometry_index.json');done=[]
 for rec in index['modules']:
  ob=bpy.data.objects['LA07_Module_'+rec['kind']];old=ob.data
  with np.load(root/rec['file']) as a:ar={k:a[k] for k in a.files}
  ob.data=mesh(old.name+'_reviewed',ar,list(old.materials))
  if old.users==0:bpy.data.meshes.remove(old)
 bpy.data.libraries.write(str(root/'assets/street_furniture/stage07_modules.blend'),{bpy.data.objects['LA07_Module_'+rec['kind']] for rec in index['modules']},fake_user=True,compress=True)
 for ob in list(s.objects):
  if ob.get('stage07_instances') is not None:
   data=ob.data;bpy.data.objects.remove(ob,do_unlink=True)
   if data.users==0:bpy.data.meshes.remove(data)
 bs=read('data/processed/stage07/buildings.json');bmap={b['i']:b for b in bs};buckets=collections.defaultdict(list)
 for a in read('data/processed/stage07/module_placements.json')['instances']+index['street_instances']:buckets[(a['region'],a['kind'],bmap[a['fid']]['cell'] if a['fid'] in bmap else 'street')].append(a)
 for (region,kind,cell),items in buckets.items():
  origin=[-432.3949595,857.11258,0] if region=='historic_core' else [215.43239,1747.54794,0];instances('LA07_'+region+'_'+cell+'_'+kind,items,origin,bpy.data.objects['LA07_Module_'+kind],bpy.data.collections['LA07_'+region])
 for rec in index['site_meshes']:
  ob=bpy.data.objects['LA07_'+rec['id']];old=ob.data
  with np.load(root/rec['file']) as a:ar={k:a[k] for k in a.files}
  ob.data=mesh(old.name+'_upward_stair_normals',ar,list(old.materials));done.append(ob.name)
  if old.users==0:bpy.data.meshes.remove(old)
 from stage07_views import set_visibility
 tri=set_visibility(s,root,[-462.988,769.892],float(s['stage07_default_radius_m']),True);s['stage07_default_visible_triangles']=tri;assert tri<=1500000;save(cfg7['output_scene']);write('work/reports/stage07/stair_normal_correction.json',{'status':'saved_requires_reopen','objects':done,'reason':'Correct solid stair winding; remove inferred window frames crossing doors, move opaque door glazing in front of uncut source wall; refresh negative street-point ID namespace','default_visible_triangles':tri,'source_body_and_stage06_unchanged':True})
def library_check():
 bpy.ops.wm.read_factory_settings(use_empty=True);setup_scene(1200,900,24);index=read('data/processed/stage07/geometry_index.json');path=root/'assets/street_furniture/stage07_modules.blend'
 with bpy.data.libraries.load(str(path),link=False) as (src,dst):dst.objects=[n for n in src.objects if n.startswith('LA07_Module_')]
 for j,o in enumerate(dst.objects):
  s=bpy.context.scene;s.collection.objects.link(o);o.location=((j%4)*6,(j//4)*8,0);o.hide_render=False;o.hide_viewport=False
  if 'window_' in o['stage07_kind']:o.scale=(2.2,.09,2.5);o.location.z=2
  elif o['stage07_kind']=='entry_glazed_double':o.scale=(1.8,.14,2.3);o.location.z=1.15
  elif o['stage07_kind']=='canopy_brackets':o.scale=(2.5,1.6,.18);o.location.z=2.8
  elif o['stage07_kind'].startswith('tree'):o.scale=(6,6,6)
 aim([32,-32,25],[8,8,2],38);render('work/previews/stage07/module_library.png');write('work/reports/stage07/library_check.json',{'status':'passed','actual_library_reopened':str(path.relative_to(root)),'objects':len(dst.objects),'module_names':[o['stage07_kind'] for o in dst.objects],'actual_inspection_render':'work/previews/stage07/module_library.png','gallery_layout_is_not_geographic_city_layout':True})
def diagnose():
 from stage07_views import views,set_visibility,bounds
 view=views(root)['civic_center_street'];set_visibility(s,root,view['focus_xy_m'],view['radius_m']);q=np.array(view['position_m']);hits=[]
 for ob in s.objects:
  if ob.type!='MESH' or ob.hide_render or ob.get('stage07_instances') or ob.get('building_instances') or ob.parent:continue
  lo,hi=bounds(ob)
  if not (lo[0]<=q[0]<=hi[0] and lo[1]<=q[1]<=hi[1]):continue
  v,f,mi=array_mesh(ob.data)
  if not len(f):continue
  vv=v[f]+np.array(ob.location);a=vv[:,0];ab=vv[:,1]-a;ac=vv[:,2]-a;aq=q[:2]-a[:,:2];den=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0];valid=abs(den)>1e-8;idx=np.flatnonzero(valid);u=(aq[valid,0]*ac[valid,1]-aq[valid,1]*ac[valid,0])/den[valid];w=(ab[valid,0]*aq[valid,1]-ab[valid,1]*aq[valid,0])/den[valid];ok=(u>=-1e-6)&(w>=-1e-6)&(u+w<=1.000001)
  for j,uu,ww in zip(idx[ok],u[ok],w[ok]):hits.append({'object':ob.name,'z':float(a[j,2]+uu*ab[j,2]+ww*ac[j,2]),'material':ob.data.materials[int(mi[j])].name,'properties':{k:str(v) for k,v in ob.items()}})
 write('work/reports/stage07/civic_camera_surface_diagnostic.json',{'camera':q.tolist(),'surfaces_at_camera_xy':hits});print('CIVIC_CAMERA_SURFACE_HITS',[(h['object'],h['z'],h['material']) for h in hits],flush=True)
if __name__=='__main__':
 if args.mode=='build7':build()
 elif args.mode=='check7':check()
 elif args.mode=='render7':renders()
 elif args.mode=='patch7':patch()
 elif args.mode=='library7':library_check()
 elif args.mode=='check-render7':check();renders()
 elif args.mode=='diagnose7':diagnose()
 else:raise RuntimeError('未实现 / NOT IMPLEMENTED '+args.mode)
