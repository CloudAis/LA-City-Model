"""Blender revision2 authoring checkpoint: linked unchanged base, locally editable refinements."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage06_blender import *
cfgf=read('config/stage07_final.json');ix=read('data/processed/stage07_final/index.json');scene=bpy.context.scene
def coll(name):
 c=bpy.data.collections.new(name);scene.collection.children.link(c);return c
def arrays(m):
 v=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',v);f=np.empty(len(m.loops),np.int32);m.loops.foreach_get('vertex_index',f);mi=np.empty(len(m.polygons),np.int32);m.polygons.foreach_get('material_index',mi);return v.reshape(-1,3),f.reshape(-1,3),mi
def create_materials():
 mats=[]
 for name,color,rough,metal in ix['materials']:
  c=list(color)
  if name=='concrete':c=[.40,.38,.34,1]
  if name=='paving':c=[.39,.37,.33,1]
  if name=='white':c=[.66,.65,.60,1]
  if name=='brick':c=[.56,.45,.31,1]
  mat=bpy.data.materials.new('LA07R2_'+name);mat.diffuse_color=c;mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=c;bs.inputs['Roughness'].default_value=rough;bs.inputs['Metallic'].default_value=metal;n=mat.node_tree.nodes;l=mat.node_tree.links
  if name in ['concrete','paving','white','limestone','brick','terracotta']:
   tex=n.new('ShaderNodeTexCoord');noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=8;noise.inputs['Detail'].default_value=3;l.new(tex.outputs['Object'],noise.inputs['Vector']);ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=tuple(x*.88 if j<3 else 1 for j,x in enumerate(c));ramp.color_ramp.elements[1].color=tuple(min(1,x*1.05) if j<3 else 1 for j,x in enumerate(c));l.new(noise.outputs['Fac'],ramp.inputs[0]);l.new(ramp.outputs[0],bs.inputs['Base Color']);bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.18;bump.inputs['Distance'].default_value=.006;l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],bs.inputs['Normal'])
   if name=='brick':
    brick=n.new('ShaderNodeTexBrick');brick.inputs['Scale'].default_value=1;brick.inputs['Mortar Size'].default_value=.012;brick.inputs['Brick Width'].default_value=.24;brick.inputs['Row Height'].default_value=.075;brick.inputs['Color1'].default_value=(.60,.46,.29,1);brick.inputs['Color2'].default_value=(.48,.37,.25,1);brick.inputs['Mortar'].default_value=(.54,.50,.42,1);sep=n.new('ShaderNodeSeparateXYZ');l.new(tex.outputs['Object'],sep.inputs[0]);combine=n.new('ShaderNodeCombineXYZ');add=n.new('ShaderNodeMath');add.operation='ADD';l.new(sep.outputs['X'],add.inputs[0]);l.new(sep.outputs['Y'],add.inputs[1]);l.new(add.outputs[0],combine.inputs['X']);l.new(sep.outputs['Z'],combine.inputs['Y']);l.new(combine.outputs[0],brick.inputs['Vector']);l.new(brick.outputs['Color'],bs.inputs['Base Color']);l.new(brick.outputs['Fac'],bump.inputs['Height'])
  if name=='glass':bs.inputs['Roughness'].default_value=.19;bs.inputs['Metallic'].default_value=.48;bs.inputs['Base Color'].default_value=(.055,.11,.14,1)
  if name=='grass':
   noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=26;mix=n.new('ShaderNodeMixRGB');mix.inputs[1].default_value=(.035,.11,.017,1);mix.inputs[2].default_value=(.19,.29,.055,1);l.new(noise.outputs['Fac'],mix.inputs[0]);l.new(mix.outputs[0],bs.inputs['Base Color']);bs.inputs['Roughness'].default_value=.76
  mats.append(mat)
 return mats
def compact_mesh(m,keep,name):
 v,f,mi=arrays(m);selected=f[keep];ids,inv=np.unique(selected,return_inverse=True);ar={'v':v[ids],'f':inv.reshape(-1,3).astype(np.int32),'m':mi[keep]}
 if m.uv_layers:
  uv=np.empty(len(m.loops)*2,np.float32);m.uv_layers.active.data.foreach_get('uv',uv);ar['uv']=uv.reshape(-1,3,2)[keep]
 if m.attributes.get('building_index'):
  fid=np.empty(len(m.polygons),np.int32);m.attributes['building_index'].data.foreach_get('value',fid);ar['fid']=fid[keep]
 return mesh(name,ar,list(m.materials))
def build():
 global scene
 library=root/cfgf['source_scene']
 temp=root/'work/tmp/stage07_link_main_temporary.blend'
 # Append a scene into an untitled main file first. Linking the currently open
 # main file as its own library crashes Blender4.3; the source stays external.
 if bpy.data.filepath:
  assert Path(bpy.data.filepath) in [library,temp]
  # Main-file reads are fast for this100k-object city. Scene Append has a very
  # slow dependency expansion in this Blender build, so save a temporary main
  # file before linking the preserved source. It is removed after final save.
  if Path(bpy.data.filepath)==library:
   bpy.context.preferences.filepaths.save_version=0
   bpy.ops.wm.save_as_mainfile(filepath=str(temp),compress=True)
  print('TEMPORARY_MAIN_SAVED_SOURCE_EXTERNAL',flush=True)
 else:
  temp=None
  with bpy.data.libraries.load(str(library),link=False) as (src,dst):dst.scenes=src.scenes[:1]
  old=scene;scene=dst.scenes[0];bpy.context.window.scene=scene
  if old!=scene:bpy.data.scenes.remove(old)
 selected=set(ix['replaced_source_indices']);original_meshes=list(bpy.data.meshes);names={m.name for m in original_meshes if len(m.polygons)>=1000}
 print('LINK_HEAVY_MESHES_ONLY',len(names),'OF',len(original_meshes),flush=True)
 with bpy.data.libraries.load(str(library),link=True) as (src,dst):dst.meshes=[n for n in src.meshes if n in names]
 linked={m.name:m for m in dst.meshes};relinked=0
 for ob in list(bpy.data.objects):
  if ob.type=='MESH' and ob.data.library is None and ob.data.name in linked:ob.data=linked[ob.data.name];relinked+=1
 bpy.data.batch_remove(ids=[m for m in original_meshes if m.users==0])
 print('UNCHANGED_CITY_MESHES_LINKED',relinked,flush=True)
 changed_bodies=[];removed_points=0
 for ob in list(scene.objects):
  if ob.type!='MESH':continue
  m=ob.data;attr=m.attributes.get('building_index')
  if not attr:continue
  if attr.domain=='FACE' and ob.get('building_lod') is not None:
   fid=np.empty(len(m.polygons),np.int32);attr.data.foreach_get('value',fid);keep=~np.isin(fid,list(selected))
   if keep.all():continue
   ob.data=compact_mesh(m,keep,m.name+'_without_refined_near_buildings');ob['r2_replaced_source_indices']=json.dumps(sorted(set(fid[~keep].tolist())));changed_bodies.append({'object':ob.name,'removed_faces':int((~keep).sum()),'retained_faces':int(keep.sum())})
  elif attr.domain=='POINT' and (ob.get('instance_kind_05') or ob.get('stage07_instances') is not None):
   fid=np.empty(len(m.vertices),np.int32);attr.data.foreach_get('value',fid);keep=~np.isin(fid,list(selected))
   if keep.all():continue
   removed_points+=int((~keep).sum())
   if not keep.any():bpy.data.objects.remove(ob,do_unlink=True);continue
   v=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',v);data=bpy.data.meshes.new(m.name+'_r2_retained_points');data.vertices.add(int(keep.sum()));data.vertices.foreach_set('co',v.reshape(-1,3)[keep].ravel());data.attributes.new('building_index','INT','POINT').data.foreach_set('value',fid[keep])
   for name in ['module_scale','module_rotation']:
    a=np.empty(len(m.vertices)*3,np.float32);m.attributes[name].data.foreach_get('vector',a);data.attributes.new(name,'FLOAT_VECTOR','POINT').data.foreach_set('vector',a.reshape(-1,3)[keep].ravel())
   data.update();ob.data=data
   if ob.get('building_instances') is not None:
    factor=int(ob['instance_triangles_05'])/int(ob['building_instances']);ob['building_instances']=int(keep.sum());ob['instance_triangles_05']=round(factor*keep.sum())
   if ob.get('stage07_instances') is not None:
    factor=int(ob['instance_triangles_07'])/int(ob['stage07_instances']);ob['stage07_instances']=int(keep.sum());ob['instance_triangles_07']=round(factor*keep.sum())
 # Old aggregate stairs are superseded, as are old procedural doorstep surfaces.
 for ob in list(scene.objects):
  if ob.get('stage07_region'):bpy.data.objects.remove(ob,do_unlink=True)
 mats=create_materials();parent=coll('40_STAGE07_R2_REFERENCE_GUIDED_AND_NEUTRAL_BUILDINGS');counts={}
 for b in ix['buildings']:
  group=bpy.data.collections.new('R2_'+str(b['i'])+'_'+(b['name'] or b['profile']));parent.children.link(group);empty=bpy.data.objects.new('R2_Building_'+str(b['i']),None);group.objects.link(empty);empty.location=b['origin_city_m'];empty['stable_id']=b['uid'];empty['source_building_index']=b['i'];empty['profile']=b['profile'];empty['source_height_evidence']=b['height_source'];empty['full_measured_facade_certified']=False
  for rec in b['near']+ [{'name':'far','file':b['far']}]:
   with np.load(root/rec['file']) as a:ar={k:a[k] for k in a.files}
   ob=bpy.data.objects.new('R2_'+str(b['i'])+'_'+rec['name'],mesh('R2_'+str(b['i'])+'_'+rec['name'],ar,mats));group.objects.link(ob);ob.parent=empty;ob['r2_building']=b['i'];ob['r2_lod']='far' if rec['name']=='far' else 'near';ob['r2_component']=rec['name'];ob['r2_origin_city_m']=b['origin_city_m'];ob['source_uid']=b['uid'];ob['evidence']='reference-guided approximation' if b['reference_guided'] else 'source-plan neutral facade; detail positions inferred';ob.hide_render=rec['name']=='far';ob.hide_viewport=ob.hide_render
  counts[str(b['i'])]=sum(r['triangles'] for r in b['near'])
  if b['reference_guided']:
   asset=root/'assets/buildings/stage07_final'/(b['profile']+'.blend');asset.parent.mkdir(parents=True,exist_ok=True);bpy.data.libraries.write(str(asset),set(group.objects),fake_user=True,compress=True)
 # Reconstruct one mapped elevated bridge; all three erroneous85m slivers removed.
 rec=ix['skybridge']
 with np.load(root/rec['file']) as a:ar={k:a[k] for k in a.files}
 ob=bpy.data.objects.new('R2_Mapped_City_Hall_East_skybridge',mesh('R2_skybridge',ar,mats));parent.objects.link(ob);ob.location=rec['origin_city_m'];ob['r2_skybridge']=True;ob['stable_id']=rec['id'];ob['source_min_height_m']=6.;ob['enclosure_height_inferred_m']=3.6;ob['replaces_county_indices']=json.dumps(rec['replaces'])
 ground={t['id']:t for t in ix['ground']};cache={}
 for ob in scene.objects:
  tid=ob.get('tile_id')
  if ob.type!='MESH' or tid not in ground or ob.get('lod') is None or ob.get('traffic_role') or ob.get('instance_kind'):continue
  rec=ground[tid]
  if tid not in cache:
   with np.load(root/rec['file']) as a:ar={k:a[k] for k in a.files}
   oldm=list(ob.data.materials);newm=[]
   for material in oldm:newm.append(mats[6] if material.name.lower()=='built' else material)
   cache[tid]=mesh('R2_'+tid+'_street_constrained_grade',ar,newm,True)
  ob.data=cache[tid];ob['r2_ground_variant']=rec['file']
 public=read('data/processed/stage07_final/public_surface.json');updates={r['object']:r for r in public['road_updates']}
 for ob in scene.objects:
  if ob.type!='MESH' or ob.name not in updates:continue
  rec=updates[ob.name]
  with np.load(root/rec['file']) as a:ar={k:a[k] for k in a.files}
  oldm=list(ob.data.materials);data=mesh('R2_'+ob.name,ar,oldm)
  if 'fid' in ar:
   attr=data.attributes.get('building_index')
   if attr:attr.name='transport_feature_index'
  ob.data=data;ob['r2_ordinary_transport_z_inferred']=True
 surface=coll('41_STAGE07_R2_CONTINUOUS_SIDEWALK_AND_CURB')
 for rec in public['regions']:
  for component in rec['meshes']:
   with np.load(root/component['file']) as a:ar={k:a[k] for k in a.files}
   ob=bpy.data.objects.new('R2_'+rec['region']+'_'+component['name'],mesh('R2_'+rec['region']+'_'+component['name'],ar,mats));surface.objects.link(ob);ob.location=rec['origin_city_m'];ob['r2_public_surface']=rec['region'];ob['source_geometry']='stage04 unioned sidewalk mask minus source building/ramp footprints';ob['grade']='inferred street-constrained NAVD88 grade; not an engineering survey'
 # Fixtures remain at source XY; authoring points are re-elevated by precomputed revision placements.
 placements=read('data/processed/stage07_final/street_positions.json')
 for name,p in placements['objects'].items():
  ob=bpy.data.objects.get(name)
  if not ob:continue
  old=ob.data;data=bpy.data.meshes.new(old.name+'_r2_grade');data.vertices.add(len(p['v']));data.vertices.foreach_set('co',np.array(p['v'],np.float32).ravel())
  for name in ['building_index','module_scale','module_rotation']:
   attr=old.attributes.get(name)
   if not attr:continue
   dest=data.attributes.new(name,attr.data_type,'POINT');size=3 if attr.data_type=='FLOAT_VECTOR' else 1;a=np.empty(len(old.vertices)*size,np.float32 if size==3 else np.int32);attr.data.foreach_get('vector' if size==3 else 'value',a);dest.data.foreach_set('vector' if size==3 else 'value',a)
  data.update();ob.data=data
 leaf=read('data/processed/stage07_final/leaf_asset.json');proto=bpy.data.objects.get('LA07_Module_tree_broadleaf')
 if proto:
  with np.load(root/leaf['file']) as a:ar={k:a[k] for k in a.files}
  proto.data=mesh('R2_original_leaf_and_branch_geometry',ar,mats)
  for ob in scene.objects:
   if ob.get('stage07_kind')=='tree_broadleaf' and ob.get('stage07_instances') is not None:ob['instance_triangles_07']=int(ob['stage07_instances'])*len(proto.data.polygons)
 scene['stage']=7;scene['stage07_revision']='r2_reference_guided_near_streets';scene['stage07_base_library']=cfgf['source_scene'];scene['stage07_source_county_features']=103;scene['stage07_near_buildings']=100;scene['stage07_deduplicated_skybridges']=1;scene['stage07_provenance']='data/processed/stage07_final/index.json; docs/stage07_revision_research.md';scene['all_facades_measured_or_current']=False
 setup_scene(1440,1080,64);scene.cycles.seed=cfgf['seed'];scene.view_settings.exposure=.25;world=scene.world;nodes=world.node_tree.nodes;links=world.node_tree.links;sky=nodes.new('ShaderNodeTexSky');sky.sky_type='NISHITA';sky.sun_elevation=math.radians(40);sky.sun_rotation=math.radians(135);sky.sun_disc=False;links.new(sky.outputs[0],nodes.get('Background').inputs[0]);nodes.get('Background').inputs[1].default_value=.25
 from stage07_final_views import show,aim,views
 budget=[];view=views(root)['historic_street']
 for radius,detail in [(450,140),(450,110),(450,85),(450,65),(450,35),(450,0),(350,35),(250,35),(160,20),(100,0),(60,0)]:
  tri=show(scene,root,view['focus_xy_m'],radius,detail,True);budget.append({'near_detail_radius_m':detail,'load_radius_m':radius,'visible_triangles':tri});print('DEFAULT_BUDGET',radius,detail,tri,flush=True)
  if tri<=cfgf['max_visible_triangles']:break
 assert tri<=cfgf['max_visible_triangles'];scene['stage07_final_default_visible_triangles']=tri;scene['stage07_final_default_detail_radius_m']=detail;aim(scene,views(root)['historic_street']);bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=True,do_recursive=True)
 # Relative library path makes the two .blend files relocatable together.
 for lib in bpy.data.libraries:
  if Path(bpy.path.abspath(lib.filepath))==library:lib.filepath='//'+library.name
 bpy.context.preferences.filepaths.save_version=0
 bpy.ops.wm.save_as_mainfile(filepath=str(root/cfgf['output_scene']),compress=True,relative_remap=False)
 if temp is not None:temp.unlink()
 write('work/reports/stage07_final/build.json',{'status':'saved_requires_independent_reopen','linked_unchanged_mesh_objects':relinked,'source_scene':cfgf['source_scene'],'output_scene':cfgf['output_scene'],'removed_body_meshes':changed_bodies,'removed_old_attached_points':removed_points,'new_buildings':100,'one_mapped_skybridge':True,'per_building_near_triangles':counts,'default_budget_attempts':budget,'default_visible_triangles':tri,'fully_measured_facades':0,'local_editable_refinements':True,'source_library_must_accompany_final_file':True})
def check():
 assert Path(bpy.data.filepath)==root/cfgf['output_scene'];bad=degen=matbad=remaining=pointremaining=0;seen=set();links=[];counts=collections.Counter();selected=set(ix['replaced_source_indices']);bounds={};proxy06=set(json.loads(scene['stage06_replaced_building_indices']))
 for lib in bpy.data.libraries:links.append({'path':bpy.path.abspath(lib.filepath),'exists':Path(bpy.path.abspath(lib.filepath)).exists()})
 assert links and all(x['exists'] for x in links)
 for ob in scene.objects:
  if ob.type!='MESH':continue
  m=ob.data;attr=m.attributes.get('building_index')
  if attr and ob.get('building_lod') is not None:
   ids=np.empty(len(m.polygons),np.int32);attr.data.foreach_get('value',ids);remaining+=int(np.isin(ids,list(selected|proxy06)).sum())
  if attr and attr.domain=='POINT' and (ob.get('instance_kind_05') or ob.get('stage07_instances') is not None):
   ids=np.empty(len(m.vertices),np.int32);attr.data.foreach_get('value',ids);pointremaining+=int(np.isin(ids,list(selected|proxy06)).sum())
  if ob.get('r2_building') is not None and ob.get('r2_lod')=='near':counts[str(ob['r2_building'])]+=len(m.polygons)
  if m.library is not None or m.as_pointer() in seen:continue
  seen.add(m.as_pointer());v,f,mi=arrays(m);bad+=int((~np.isfinite(v)).sum())
  if len(f):degen+=int((np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)<=1e-8).sum());matbad+=int(((mi<0)|(mi>=len(m.materials))).sum())
  if ob.get('r2_building') is not None and len(v):
   key=str(ob['r2_building']);lo,hi=v.min(axis=0),v.max(axis=0)
   if key not in bounds:bounds[key]=[lo.tolist(),hi.tolist()]
   else:bounds[key]=[np.minimum(bounds[key][0],lo).tolist(),np.maximum(bounds[key][1],hi).tolist()]
 assert bad==degen==matbad==remaining==pointremaining==0,(bad,degen,matbad,remaining,pointremaining);assert len(counts)==100 and scene.unit_settings.scale_length==1;assert len([o for o in scene.objects if o.get('stable_id','').startswith('landmark:')])==10
 expected={str(b['i']):sum(r['triangles'] for r in b['near']) for b in ix['buildings']};assert dict(counts)==expected;assert scene['stage07_final_default_visible_triangles']<=1500000
 write('work/reports/stage07_final/blender_check.json',{'status':'passed','saved_model_sha256':hashlib.file_digest(open(bpy.data.filepath,'rb'),'sha256').hexdigest(),'saved_checkpoint_reopened_independently':True,'units_metres_per_blender_unit':1,'nonfinite_vertices':bad,'degenerate_triangles':degen,'invalid_material_indices':matbad,'old_selected_body_faces':remaining,'old_selected_attached_points':pointremaining,'refined_buildings_checked':len(counts),'per_building_triangles':dict(counts),'bounds_local_m':bounds,'libraries':links,'source06_landmarks_retained':10,'default_visible_triangles':scene['stage07_final_default_visible_triangles'],'actual_facade_measurement_accuracy':'not certified; sources and inferences separated'});print('R2_REOPEN_GEOMETRY_CHECK_PASSED',len(counts),flush=True)
def patch_grounded_facades():
 assert Path(bpy.data.filepath)==root/cfgf['output_scene'];mats=[bpy.data.materials['LA07R2_'+r[0]] for r in ix['materials']];byid={b['i']:b for b in ix['buildings']};replace=[]
 for ob in list(scene.objects):
  bi=ob.get('r2_building')
  if bi is None:continue
  if bi==1080188:
   bpy.data.objects.remove(ob,do_unlink=True);continue
  if ob.get('r2_component') in ['far','terrain_foundation_and_inferred_plant']:replace.append(ob)
 for ob in replace:
  b=byid[ob['r2_building']];rec={'file':b['far']} if ob['r2_component']=='far' else next(r for r in b['near'] if r['name']==ob['r2_component'])
  with np.load(root/rec['file']) as a:ar={k:a[k] for k in a.files}
  ob.data=mesh(ob.name+'_grounded',ar,mats)
 b=byid[1080188];empty=bpy.data.objects['R2_Building_1080188'];empty.location=b['origin_city_m'];group=empty.users_collection[0]
 for rec in b['near']+[{'name':'far','file':b['far']}]:
  with np.load(root/rec['file']) as a:ar={k:a[k] for k in a.files}
  ob=bpy.data.objects.new('R2_1080188_'+rec['name'],mesh('R2_1080188_'+rec['name'],ar,mats));group.objects.link(ob);ob.parent=empty;ob['r2_building']=1080188;ob['r2_lod']='far' if rec['name']=='far' else 'near';ob['r2_component']=rec['name'];ob['r2_origin_city_m']=b['origin_city_m'];ob['source_uid']=b['uid'];ob['evidence']='reference-guided17m facade screen and shallow visual vestibule; measured architectural accuracy unknown'
 for b in ix['buildings']:
  if b['reference_guided']:
   group=bpy.data.objects['R2_Building_'+str(b['i'])].users_collection[0];bpy.data.libraries.write(str(root/'assets/buildings/stage07_final'/(b['profile']+'.blend')),set(group.objects),fake_user=True,compress=True)
 from stage07_final_views import show,aim,views
 view=views(root)['historic_street'];detail=scene['stage07_final_default_detail_radius_m'];tri=show(scene,root,view['focus_xy_m'],450,detail,True);assert tri<=cfgf['max_visible_triangles'];scene['stage07_final_default_visible_triangles']=tri;aim(scene,view);bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=True,do_recursive=True);save(cfgf['output_scene']);report=read('work/reports/stage07_final/build.json');report.update(default_visible_triangles=tri,per_building_near_triangles={str(b['i']):sum(r['triangles'] for r in b['near']) for b in ix['buildings']},actual_incremental_ground_and_theatre_patch=True);write('work/reports/stage07_final/build.json',report)
def render_views(draft=False):
 from stage07_final_views import views,show,aim
 setup_scene(640 if draft else cfgf['render']['width'],480 if draft else cfgf['render']['height'],12 if draft else cfgf['render']['samples']);scene.cycles.max_bounces=4;scene.view_settings.exposure=.25;scene.world.node_tree.nodes['Background'].inputs[1].default_value=.25;results={}
 for name,v in views(root).items():
  if args.id!='all' and name not in args.id.split(','):continue
  tri=show(scene,root,v['focus_xy_m'],v.get('radius_m',450),v.get('detail_radius_m',140));aim(scene,v);path='work/previews/stage07_final/'+('draft_' if draft else '')+name+'.png';render(path);results[name]=v|{'actual_triangles_including_shared_instances':tri,'actual_cpu_cycles':True,'output':path}
 write('work/reports/stage07_final/'+('draft_' if draft else 'renders_')+args.id+'.json',{'status':'actual_render_completed','images':results,'saved_scene':bpy.data.filepath,'saved_scene_sha256':hashlib.file_digest(open(bpy.data.filepath,'rb'),'sha256').hexdigest(),'render_parameters':{'engine':scene.render.engine,'device':scene.cycles.device,'samples':scene.cycles.samples,'width':scene.render.resolution_x,'height':scene.render.resolution_y,'seed':scene.cycles.seed,'threads':scene.render.threads,'denoising':scene.cycles.use_denoising}})
if __name__=='__main__':
 if args.mode=='build-final':build()
 elif args.mode=='normalize-library-final':
  for lib in bpy.data.libraries:lib.filepath='//stage07_city_medium.blend'
  save(cfgf['output_scene'])
 elif args.mode=='check-final':check()
 elif args.mode=='patch-grounded-final':patch_grounded_facades()
 elif args.mode=='check-draft-final':check();render_views(True)
 elif args.mode=='draft-final':render_views(True)
 elif args.mode=='render-final':render_views()
 elif args.mode=='check-render-final':check();render_views()
 else:raise RuntimeError('未实现 / NOT IMPLEMENTED '+args.mode)
