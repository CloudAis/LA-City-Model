"""Executed by Blender only. Save/exit and independent reopen/measure/render modes."""
import bpy,numpy as np,json,sys,math,argparse
from pathlib import Path
from mathutils import Vector,Matrix
p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--mode',choices=['build','verify-render','repair-water','repair-views','repair-ground'],required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(a.root)
geo=json.loads((root/'work/reports/stage04/geometry.json').read_text());index=json.loads((root/'data/processed/stage04/mesh_index.json').read_text());scene=bpy.context.scene;blend=root/'scenes/stage04_city_medium.blend'
def write(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def material(name,color):
 m=bpy.data.materials.new('Transport_'+name);m.diffuse_color=color;m.use_nodes=True;b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=color;b.inputs['Roughness'].default_value=.77;return m
def make_mesh(name,v,f,materials,mi=None,fid=None):
 mesh=bpy.data.meshes.new(name);mesh.vertices.add(len(v));mesh.vertices.foreach_set('co',np.asarray(v,np.float32).ravel());mesh.loops.add(len(f)*3);mesh.loops.foreach_set('vertex_index',np.asarray(f,np.int32).ravel());mesh.polygons.add(len(f));mesh.polygons.foreach_set('loop_start',np.arange(len(f),dtype=np.int32)*3);mesh.polygons.foreach_set('loop_total',np.full(len(f),3,np.int32));mesh.update()
 for m in materials:mesh.materials.append(m)
 if mi is not None:mesh.polygons.foreach_set('material_index',mi.astype(np.int32))
 if fid is not None:
  attr=mesh.attributes.new('transport_feature_index','INT','FACE');attr.data.foreach_set('value',fid.astype(np.int32))
 return mesh

def prototype(name,boxes,mats):
 v=[];f=[];mi=[]
 for center,dim,mat in boxes:
  base=len(v);c=np.array(center);d=np.array(dim)/2
  v.extend([c+np.array(s)*d for s in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]])
  faces=[[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]];f.extend([[base+x for x in q] for q in faces]);mi.extend([mat]*12)
 return make_mesh('Reusable_'+name,np.array(v),np.array(f),mats,np.array(mi))

_LOCAL_BOUNDS={}
def world_corners(ob):
 key=ob.data.as_pointer()
 if key not in _LOCAL_BOUNDS:
  v=np.empty(len(ob.data.vertices)*3,np.float32);ob.data.vertices.foreach_get('co',v);v=v.reshape(-1,3)
  lo=v.min(axis=0) if len(v) else np.zeros(3);hi=v.max(axis=0) if len(v) else np.zeros(3)
  _LOCAL_BOUNDS[key]=[Vector((x,y,z)) for x in [lo[0],hi[0]] for y in [lo[1],hi[1]] for z in [lo[2],hi[2]]]
 # Hidden objects may have stale matrix_world/bound_box after reopening. Source mesh
 # vertices and stored transforms remain authoritative without viewport evaluation.
 matrix=Matrix.LocRotScale(ob.location,ob.rotation_euler.to_quaternion(),ob.scale)
 if ob.parent:matrix=ob.parent.matrix_world@matrix
 return [matrix@v for v in _LOCAL_BOUNDS[key]]

def visibility(shows,viewport=False,batch=True):
 objects=list(bpy.data.objects);flags=np.array([not shows.get(o.name,not o.hide_render) for o in objects],dtype=bool)
 if batch:
  bpy.data.objects.foreach_set('hide_render',flags)
  if viewport:bpy.data.objects.foreach_set('hide_viewport',flags)
 else:
  for o,flag in zip(objects,flags):
   if o.hide_render!=bool(flag):o.hide_render=bool(flag)
   if viewport and o.hide_viewport!=bool(flag):o.hide_viewport=bool(flag)

def apply_water_variants():
 for water in geo.get('water_variants',[]):
  ob=bpy.data.objects.get(water['object_name'])
  if ob:
   with np.load(root/water['file']) as d:
    vv=d['v'];ff=d['f'] if 'f' in d.files else None
   if ff is not None:ob.data=make_mesh(ob.name+'_stage04_clean',vv,ff,list(ob.data.materials))
   else:
    assert len(vv)==len(ob.data.vertices);ob.data.vertices.foreach_set('co',vv.ravel());ob.data.update()
   ob['stage04_hydrographic_reference_variant']=water['file']

def save_view_presets():
 scene['stage04_interchange_xy_m']=geo['interchange_center_m']
 text=bpy.data.texts.get('STAGE04_VIEW_PRESETS.py') or bpy.data.texts.new('STAGE04_VIEW_PRESETS.py');text.clear();text.write((root/'scripts/stage04_view_presets.py').read_text())

def build():
 original_members={}
 for cc in bpy.data.collections:
  for oo in cc.objects:original_members.setdefault(oo.name,[]).append(cc)
 active=bpy.data.collections['01_Terrain_ACTIVE_static_budget'];hidden=bpy.data.collections['02_Terrain_LOD_ALTERNATIVES_hidden'];variants={t['tile_id']:root/t['file'] for t in geo['ground_variants']}
 for ob in list(bpy.data.objects):
  tid=ob.get('tile_id');lod=ob.get('lod')
  if tid is None or lod is None:continue
  desired=geo['base_active_lods'][tid];collection=active if int(lod)==desired else hidden
  for coll in original_members.get(ob.name,[]):coll.objects.unlink(ob)
  collection.objects.link(ob);ob.hide_render=False;ob.hide_viewport=False
  if tid in variants:
   with np.load(variants[tid]) as d:
    v=d[f'v{int(lod)}'];f=d[f'f{int(lod)}'];mi=d[f'm{int(lod)}'];nn=d[f'n{int(lod)}'] if f'n{int(lod)}' in d.files else None
   if len(ob.data.vertices)!=len(v) or len(ob.data.polygons)!=len(f):
    mats0=list(ob.data.materials);ob.data=make_mesh(ob.name+'_cut',v,f,mats0,mi)
    if nn is not None and len(nn)==len(v):ob.data.polygons.foreach_set('use_smooth',np.ones(len(f),bool));ob.data.normals_split_custom_set_from_vertices(nn.tolist())
   else:ob.data.vertices.foreach_set('co',v.ravel());ob.data.update()
   ob['stage04_ground_variant']=str(variants[tid].relative_to(root))
 apply_water_variants()
 mats=[material(name,tuple(color)) for name,color in index['materials']];groups={};full_tiles={'la_t_x-001_y+002','la_t_x+000_y+002','la_t_x-001_y+003','la_t_x+000_y+003'}
 for mesh_number,m in enumerate(index['meshes']):
  if mesh_number%2000==0:print('TRAFFIC_MESHES_LOADED',mesh_number,flush=True)
  role=m['role']
  if role not in groups:
   coll=bpy.data.collections.new('08_Traffic_'+role);scene.collection.children.link(coll);coll.hide_render=False;coll.hide_viewport=False;groups[role]=coll
  with np.load(root/m['file']) as d:mesh=make_mesh(m['id'],d['v'],d['f'],mats,d['m'],d['fid'])
  ob=bpy.data.objects.new(m['id'],mesh);groups[role].objects.link(ob);ob.location=m['origin_m'];visible=(m['visible_default'] or role=='full_far' and m['tile_id'] in full_tiles) and not(role=='overview_far' and m['tile_id'] in full_tiles);ob.hide_render=not visible;ob.hide_viewport=not visible;ob['tile_id']=m['tile_id'];ob['traffic_role']=role;ob['source_file']=m['file'];ob['source_index']='data/processed/stage04/roads.json + FACE transport_feature_index';ob['data_class']='observed_XY_inferred_cross_section_and_Z'
  if role in ['bridge_road','tunnel_road']:ob['surveyed_structure_elevation']=False
 grey=material('pole',[.12,.14,.15,1]);black=material('signal_case',[.025,.03,.035,1]);red=material('red_lens',[.7,.035,.025,1]);amber=material('amber_lens',[.20,.12,.025,1]);green=material('green_lens',[.025,.12,.055,1]);concrete=material('structure',[.43,.44,.42,1]);metal=material('guard_steel',[.47,.51,.54,1]);roof=material('canopy',[.36,.40,.42,1]);sleep=material('sleeper',[.25,.22,.19,1])
 proto={
  'signal':prototype('signal',[([0,0,2.6],[.17,.17,5.2],0),([2.3,0,5.1],[4.8,.15,.15],0),([4.5,0,4.5],[.3,.4,1.1],1),([4.67,0,4.82],[.05,.25,.25],2),([4.67,0,4.5],[.05,.25,.25],3),([4.67,0,4.18],[.05,.25,.25],4)],[grey,black,red,amber,green]),
  'guardrail':prototype('guardrail',[([0,0,0],[1,1,1],0),([-.44,0,-1],[.02,1,3],0),([.44,0,-1],[.02,1,3],0)],[metal]),
  'pier':prototype('pier',[([0,0,0],[1,1,1],0)],[concrete]),
  'sleeper':prototype('sleeper',[([0,0,0],[1,1,1],0)],[sleep]),
  'noise_screen':prototype('noise_screen',[([0,0,0],[1,1,1],0)],[concrete]),
  'canopy':prototype('canopy',[([0,0,0],[1,1,1],0),([-.4,-.35,-8],[.025,.03,16],1),([.4,-.35,-8],[.025,.03,16],1),([-.4,.35,-8],[.025,.03,16],1),([.4,.35,-8],[.025,.03,16],1)],[roof,metal])}
 library=root/'assets/street_furniture/stage04_prototypes.blend';library.parent.mkdir(parents=True,exist_ok=True);bpy.data.libraries.write(str(library),set(proto.values()),fake_user=True,compress=True)
 coll=bpy.data.collections.new('09_Traffic_reusable_instances');scene.collection.children.link(coll)
 for i,ins in enumerate(index['instances']):
  if i%20000==0:print('LINKED_INSTANCES',i,flush=True)
  ob=bpy.data.objects.new(f'{ins["kind"]}_{i:06d}',proto[ins['kind']]);coll.objects.link(ob);ob.location=ins['xyz_m'];ob.scale=ins['scale'];ob.rotation_euler=(0,ins.get('rotation_y',0),ins['rotation_z']);ob['data_class']=ins['data_class'];ob['source']=str(ins.get('source'));ob['tile_id']=ins.get('tile_id','');ob['instance_kind']=ins['kind']
 scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.use_denoising=False;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.cycles.samples=16;scene.cycles.seed=20261021
 scene['stage']=4;scene['transport_notes']='OSM real XY/shared-node topology; widths, road profiles, bridge Z and repeated structures include declared inference. 50 source clearance conflicts and191 non-shared crossings require review.';scene['traffic_source']='© OpenStreetMap contributors / ODbL1.0';scene['traffic_index']='data/processed/stage04/mesh_index.json';scene['runtime_lod']='not implemented; full_far assets retained hidden, overview chosen statically'
 collection_hidden={o.name for c in bpy.data.collections if c.hide_render for o in c.objects}
 # Save an actual focus loading preset. The full-city offline preview uses its own visibility.
 focus=geo['typical_intersection']['xy_m'];radius=1000.;reductions=[];cap=1500000
 def bbox_near(ob,x,y,r):
  if ob.type!='MESH':return True
  lo,hi=bounds_cache[ob.name]
  return lo[0]<=x+r and hi[0]>=x-r and lo[1]<=y+r and hi[1]>=y-r
 print('COMPUTING_STATIC_VIEW_BOUNDS',flush=True)
 bpy.context.view_layer.update()
 bounds_cache={}
 for ob in scene.objects:
  if ob.type=='MESH':
   bb=world_corners(ob);bounds_cache[ob.name]=([min(p.x for p in bb),min(p.y for p in bb)],[max(p.x for p in bb),max(p.y for p in bb)])
 shows={}
 for ob in scene.objects:
  full=not ob.hide_render and ob.name not in collection_hidden;ob['stage04_full_view_visible']=full;shows[ob.name]=full and bbox_near(ob,focus[0],focus[1],radius)
 def count_visible():return sum(len(ob.data.polygons) for ob in scene.objects if ob.type=='MESH' and shows[ob.name])
 reductions.append('saved default: static1000m focus loading preset; full editable city retained hidden')
 if count_visible()>cap:
  for ob in scene.objects:
   if ob.name.startswith('sleeper_'):shows[ob.name]=False
  reductions.append('sleeper instances retained hidden in default view')
 for role in ['downtown_curb','markings','rail_detail']:
  if count_visible()<=cap:break
  for ob in scene.objects:
   if ob.get('traffic_role')==role and ob.get('tile_id')!='la_t_x-001_y+000':shows[ob.name]=False
  reductions.append(role+' outside current closeup tile retained hidden')
 if count_visible()>cap:
  for ob in scene.objects:
   if ob.get('traffic_role') in ['markings','downtown_curb','rail_detail'] or ob.name.startswith('sleeper_'):shows[ob.name]=False
  reductions.append('dense detail retained hidden to enforce saved view budget; offline review views restore it')
 visibility(shows,viewport=True)
 print('BATCH_VISIBILITY_SET',len(shows),flush=True)
 scene['stage04_static_visibility_adjustments']=json.dumps(reductions);scene['stage04_static_visible_triangles']=count_visible();scene['stage04_initial_focus_xy_m']=focus;scene['stage04_initial_load_radius_m']=radius
 aim(scene.camera,(focus[0],focus[1],10000),(focus[0],focus[1],90),1800)
 for screen in bpy.data.screens:
  for area in screen.areas:
   if area.type=='VIEW_3D':area.spaces.active.region_3d.view_location=Vector((focus[0],focus[1],90));area.spaces.active.region_3d.view_distance=1100
 save_view_presets()
 bpy.ops.wm.save_as_mainfile(filepath=str(blend));print('STAGE04_SAVED',str(blend),'VISIBLE_TRIANGLES',count_visible(),flush=True)

def aim(cam,pos,target,scale):
 cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=scale;cam.data.clip_end=500000;scene.camera=cam

def verify_render():
 collection_hidden={o.name for c in bpy.data.collections if c.hide_render for o in c.objects}
 assert Path(bpy.data.filepath)==blend;finite=0;degenerate=0;active_tri=0;all_tri=0;meshcount=0;maxabs=0
 # Each unique mesh is measured once, while active triangles count actual visible instances.
 seen=set();bad_meshes=[]
 for ob in scene.objects:
  if ob.type!='MESH':continue
  visible=not ob.hide_render and ob.name not in collection_hidden
  mesh=ob.data
  if mesh.as_pointer() not in seen:
   seen.add(mesh.as_pointer());meshcount+=1;v=np.empty(len(mesh.vertices)*3,np.float32);mesh.vertices.foreach_get('co',v);v=v.reshape(-1,3);finite+=int((~np.isfinite(v)).sum());mesh.calc_loop_triangles();f=np.array([t.vertices[:] for t in mesh.loop_triangles]);all_tri+=len(f)
   if len(f):
    bad=int((np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)<1e-8).sum());degenerate+=bad
    if bad:bad_meshes.append({'object':ob.name,'degenerate':bad,'source_file':ob.get('source_file'),'ground_variant':ob.get('stage04_ground_variant')})
  if visible:active_tri+=len(mesh.loop_triangles)
  if len(mesh.vertices):
   for corner in world_corners(ob):maxabs=max(maxabs,max(abs(float(x)) for x in corner))
 if finite or degenerate:
  write(root/'work/reports/stage04/blender_geometry_failure.json',{'nonfinite':finite,'degenerate':degenerate,'meshes':bad_meshes});print('BLENDER_GEOMETRY_FAILURE',finite,degenerate,bad_meshes,flush=True)
 assert finite==0 and degenerate==0
 assert scene.unit_settings.system=='METRIC' and scene.unit_settings.scale_length==1
 report={'status':'passed_geometry','opened_path':bpy.data.filepath,'finite_coordinate_failures':finite,'degenerate_triangles':degenerate,'unique_meshes':meshcount,'all_stored_triangles':all_tri,'visible_default_triangles':active_tri,'maximum_absolute_world_coordinate_m':maxabs,'units':'1 Blender unit=1 meter;Z NAVD88m with explicitly inferred structures','saved_and_reopened_in_distinct_processes':True,'shared_instance_meshes':len(index['instances']),'static_visibility_adjustments':json.loads(scene.get('stage04_static_visibility_adjustments','[]')),'renders':{}}
 write(root/'work/reports/stage04/blender_check.json',report)
 cam=scene.camera
 if cam is None:
  data=bpy.data.cameras.new('Transport_review_camera');cam=bpy.data.objects.new('Transport_review_camera',data);scene.collection.objects.link(cam)
 scene.render.image_settings.file_format='PNG';scene.render.resolution_percentage=100;scene.render.resolution_x=1536;scene.render.resolution_y=1152
 scene.world.color=(.25,.25,.25);scene.render.film_transparent=False
 folder=root/'work/previews/stage04';folder.mkdir(parents=True,exist_ok=True)
 # Use nearby real terrain/traffic vertices to choose a target elevation.
 def znear(x,y):
  for m in index['meshes']:
   if m['role'] not in ['downtown_road','bridge_road','overview_far']:continue
   ox,oy,_=m['origin_m']
   if ox<=x<=ox+1000 and oy<=y<=oy+1000:
    with np.load(root/m['file']) as a:v=a['v'];dist=np.linalg.norm(v[:,:2]+[ox,oy]-[x,y],axis=1);return float(v[np.argmin(dist),2])
  return 90.
 typical=geo['typical_intersection']['xy_m'];inter=geo['interchange_center_m'];zt=znear(*typical);zi=znear(*inter)
 aspect=scene.render.resolution_x/scene.render.resolution_y
 views=[('city_top',(0,0,120000),(0,0,0),100000,8),('downtown_top',(0,0,10000),(0,0,90),4400*aspect,12),('intersection',(typical[0]-75,typical[1]-100,zt+100),(*typical,zt),150,24),('interchange',(inter[0]-800,inter[1]-1000,zi+900),(*inter,zi),1800,20)]
 # City framing uses the actual terrain bounds rather than shifting any geometry.
 boxes=[ob for ob in scene.objects if ob.get('tile_id') and not ob.get('traffic_role') and not ob.get('instance_kind') and ob.name not in collection_hidden]
 if boxes:
  b=[v for ob in boxes for v in world_corners(ob)];cx=(min(p.x for p in b)+max(p.x for p in b))/2;cy=(min(p.y for p in b)+max(p.y for p in b))/2;span=max((max(p.y for p in b)-min(p.y for p in b))*aspect,max(p.x for p in b)-min(p.x for p in b))*1.08;views[0]=('city_top',(cx,cy,120000),(cx,cy,0),span,8)
 window_bounds={}
 bpy.context.view_layer.update()
 for ob in scene.objects:
  if ob.type=='MESH':
   bb=world_corners(ob);window_bounds[ob.name]=(min(p.x for p in bb),max(p.x for p in bb),min(p.y for p in bb),max(p.y for p in bb))
 def intersects_window(ob,cx,cy,r):
  if ob.type!='MESH':return True
  a,b,c,d=window_bounds[ob.name];return a<=cx+r and b>=cx-r and c<=cy+r and d>=cy-r
 saved_visibility={o.name:o.hide_render for o in scene.objects}
 views.sort(key=lambda item:['intersection','interchange','downtown_top','city_top'].index(item[0]))
 for name,pos,target,scale,samples in views:
  shows={}
  for ob in scene.objects:
   show=bool(ob.get('stage04_full_view_visible',not ob.hide_render));role=ob.get('traffic_role');instance=bool(ob.get('instance_kind'))
   if name=='city_top':
    if role:show=role in ['overview_far','bridge_road','tunnel_road','downtown_road','rail_corridor','airport_surface','airport_apron','airport_marking','profiled_priority_road','inferred_retaining_bank']
    if instance:show=False
   elif name=='downtown_top':
    show=show and intersects_window(ob,0,0,2250)
    if role in ['downtown_curb','rail_detail','refuge_island']:show=False
    if instance:show=False
   else:show=show and intersects_window(ob,target[0],target[1],400 if name=='intersection' else 1100)
   shows[ob.name]=show
  visibility(shows,batch=False)
  render_triangles=sum(len(o.data.polygons) for o in scene.objects if o.type=='MESH' and not o.hide_render and o.name not in collection_hidden)
  aim(cam,pos,target,scale);scene.cycles.samples=samples;scene.render.filepath=str(folder/(name+'.png'));bpy.ops.render.render(write_still=True);report['renders'][name]={'path':str(Path(scene.render.filepath).relative_to(root)),'camera_m':list(pos),'target_m':list(target),'orthographic_scale_m':scale,'samples':samples,'device':'CPU','status':'rendered','visible_render_triangles':render_triangles,'offline_render_not_runtime_benchmark':True};write(root/'work/reports/stage04/blender_check.json',report);print('RENDERED',name,flush=True)
 visibility({name:not hidden for name,hidden in saved_visibility.items()},batch=False)
 report['status']='passed';write(root/'work/reports/stage04/blender_check.json',report)
if a.mode=='build':build()
elif a.mode=='repair-ground':
 for item in geo['ground_variants']:
  lod=geo['base_active_lods'][item['tile_id']];ob=bpy.data.objects[item['tile_id']+f'_LOD{lod}']
  with np.load(root/item['file']) as d:
   ob.data=make_mesh(ob.name+'_stage04_pavement_cut',d[f'v{lod}'],d[f'f{lod}'],list(ob.data.materials),d[f'm{lod}'])
   if f'n{lod}' in d.files:ob.data.polygons.foreach_set('use_smooth',np.ones(len(ob.data.polygons),bool));ob.data.normals_split_custom_set_from_vertices(d[f'n{lod}'].tolist())
  ob['stage04_ground_variant']=item['file']
 collection_hidden={o.name for c in bpy.data.collections if c.hide_render for o in c.objects}
 scene['stage04_static_visible_triangles']=sum(len(o.data.polygons) for o in scene.objects if o.type=='MESH' and not o.hide_render and o.name not in collection_hidden)
 assert scene['stage04_static_visible_triangles']<=1500000
 bpy.ops.wm.save_as_mainfile(filepath=str(blend));print('STAGE04_PAVEMENT_GROUND_REPAIRED_SAVED',flush=True)
elif a.mode=='repair-views':
 save_view_presets();bpy.ops.wm.save_as_mainfile(filepath=str(blend));print('STAGE04_VIEW_PRESETS_SAVED',flush=True)
elif a.mode=='repair-water':
 apply_water_variants();bpy.ops.wm.save_as_mainfile(filepath=str(blend));print('STAGE04_WATER_REPAIRED_SAVED',flush=True)
else:verify_render()
