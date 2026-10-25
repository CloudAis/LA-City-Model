"""Blender-only stage05 construction and independent saved-file inspection."""
import bpy,numpy as np,json,gzip,sys,math,argparse,time,collections
from pathlib import Path
from mathutils import Matrix,Vector
p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--mode',required=True,choices=['build','repair','check','render','gn-test']);p.add_argument('--view',default='all');args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(args.root);scene=bpy.context.scene
def write(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def mesh(name,v,f,mats=(),mi=None,fid=None,uv=None):
 m=bpy.data.meshes.new(name);m.vertices.add(len(v));m.vertices.foreach_set('co',np.asarray(v,np.float32).ravel());m.loops.add(len(f)*3);m.loops.foreach_set('vertex_index',np.asarray(f,np.int32).ravel());m.polygons.add(len(f));m.polygons.foreach_set('loop_start',np.arange(len(f),dtype=np.int32)*3);m.polygons.foreach_set('loop_total',np.full(len(f),3,np.int32))
 m.polygons.foreach_set('use_smooth',np.zeros(len(f),bool))
 for mat in mats:m.materials.append(mat)
 if mi is not None:m.polygons.foreach_set('material_index',np.asarray(mi,np.int32))
 if fid is not None:m.attributes.new('building_index','INT','FACE').data.foreach_set('value',np.asarray(fid,np.int32))
 if uv is not None:m.uv_layers.new(name='FacadeUV').data.foreach_set('uv',np.asarray(uv,np.float32).ravel())
 m.update();return m
def mat(name,color):
 m=bpy.data.materials.new('LA05_'+name);m.diffuse_color=color;m.use_nodes=True;b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=color;b.inputs['Roughness'].default_value=.69
 if name=='glass':b.inputs['Metallic'].default_value=.35;b.inputs['Roughness'].default_value=.22
 if name.startswith('wall_'):
  # Meter-derived facade coordinates are authored only on block detail walls.
  nt=m.node_tree;n=nt.nodes;l=nt.links;uv=n.new('ShaderNodeUVMap');uv.uv_map='FacadeUV';sep=n.new('ShaderNodeSeparateXYZ');l.new(uv.outputs['UV'],sep.inputs[0]);tests=[]
  for socket,lo,hi in [(sep.outputs['X'],.18,.82),(sep.outputs['Y'],.26,.80)]:
   fract=n.new('ShaderNodeMath');fract.operation='FRACT';l.new(socket,fract.inputs[0]);a=n.new('ShaderNodeMath');a.operation='GREATER_THAN';a.inputs[1].default_value=lo;l.new(fract.outputs[0],a.inputs[0]);z=n.new('ShaderNodeMath');z.operation='LESS_THAN';z.inputs[1].default_value=hi;l.new(fract.outputs[0],z.inputs[0]);both=n.new('ShaderNodeMath');both.operation='MULTIPLY';l.new(a.outputs[0],both.inputs[0]);l.new(z.outputs[0],both.inputs[1]);tests.append(both.outputs[0])
  both=n.new('ShaderNodeMath');both.operation='MULTIPLY';l.new(tests[0],both.inputs[0]);l.new(tests[1],both.inputs[1]);mix=n.new('ShaderNodeMixRGB');mix.blend_type='MIX';mix.inputs[1].default_value=color;mix.inputs[2].default_value=(.10,.17,.21,1);l.new(both.outputs[0],mix.inputs[0]);l.new(mix.outputs[0],b.inputs['Base Color'])
 return m
def boxes(name,items,mats):
 vv=[];ff=[];mi=[]
 faces=[[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]]
 for c,d,k in items:
  base=len(vv);vv.extend([np.asarray(c)+np.asarray(s)*np.asarray(d)/2 for s in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]);ff.extend([[base+i for i in f] for f in faces]);mi.extend([k]*12)
 return mesh(name,np.asarray(vv),np.asarray(ff),mats,np.array(mi))
def module_library(mats):
 c=bpy.data.collections.new('11_Building_MODULES_library_hidden');scene.collection.children.link(c);c.hide_render=True;c.hide_viewport=True;M={m.name.removeprefix('LA05_'):m for m in mats};frame=M['frame'];glass=M['glass'];metal=M['metal'];concrete=M['foundation'];door=M['door'];roof=M['roof']
 proto={
 'window_frame':([([-.46,0,0],[.08,1,1],0),([.46,0,0],[.08,1,1],0),([0,0,-.46],[.84,1,.08],0),([0,0,.46],[.84,1,.08],0),([0,0,0],[.035,1,.84],0)],[frame]),
 'entry_door':([([-.47,0,0],[.06,1,1],0),([.47,0,0],[.06,1,1],0),([0,0,.47],[.88,1,.06],0),([0,-.1,0],[.88,.4,.92],1),([.25,-.4,0],[.02,.15,.14],0)],[frame,glass]),
 'garage_door':([([0,0,0],[1,.4,1],0)]+[([0,-.3,-.4+i*.1],[1,.1,.015],1) for i in range(9)],[door,metal]),
 'hvac':([([0,0,0],[1,1,.9],0),([-.25,0,.47],[.35,.7,.06],1),([.25,0,.47],[.35,.7,.06],1)],[metal,frame]),
 'rail':([([0,0,.45],[1,.1,.1],0),([-.45,0,0],[.04,.1,1],0),([.45,0,0],[.04,.1,1],0)],[metal]),
 'parapet':([([0,0,0],[1,1,1],0)],[concrete]),'canopy':([([0,0,0],[1,1,1],0)],[metal]),'step':([([0,0,0],[1,1,1],0)],[concrete]),
 'fire_escape':([([0,0,0],[1,1,.08],0),([0,.45,.5],[1,.05,1],0),([-.45,0,.5],[.05,1,1],0),([.45,0,.5],[.05,1,1],0)],[metal]),
 'solar_panel':([([0,0,0],[1,1,.06],0),([0,0,-.07],[1.05,1.05,.05],1)],[glass,metal]),
 'water_tank':([([0,0,0],[1,1,1],0),([-.35,-.35,-.8],[.08,.08,.6],1),([.35,-.35,-.8],[.08,.08,.6],1),([-.35,.35,-.8],[.08,.08,.6],1),([.35,.35,-.8],[.08,.08,.6],1)],[roof,metal])}
 out={}
 for kind,(parts,materials) in proto.items():
  ob=bpy.data.objects.new('Module_'+kind,boxes('Shared_'+kind,parts,materials));c.objects.link(ob);ob['evidence']='procedural approximate template; placement requires separate source or inference record';out[kind]=ob
 path=root/'assets/buildings/stage05_modules.blend';path.parent.mkdir(parents=True,exist_ok=True);bpy.data.libraries.write(str(path),set(out.values()),fake_user=True,compress=True);return out
def instances(name,items,origin,prototype,coll):
 points=np.array([x['xyz'] for x in items],np.float32)-origin;data=bpy.data.meshes.new(name);data.vertices.add(len(points));data.vertices.foreach_set('co',points.ravel());scale=np.array([x['scale'] for x in items],np.float32);rot=np.array([[0,0,x['rotation']] for x in items],np.float32)
 for field,values in [('module_scale',scale),('module_rotation',rot)]:data.attributes.new(field,'FLOAT_VECTOR','POINT').data.foreach_set('vector',values.ravel())
 data.attributes.new('building_index','INT','POINT').data.foreach_set('value',np.array([x['fid'] for x in items],np.int32));data.update();ob=bpy.data.objects.new(name,data);coll.objects.link(ob);ob.location=origin
 tree=bpy.data.node_groups.new(name+'_instancing','GeometryNodeTree');tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry');n=tree.nodes;l=tree.links;inp=n.new('NodeGroupInput');out=n.new('NodeGroupOutput');info=n.new('GeometryNodeObjectInfo');info.inputs['Object'].default_value=prototype;info.inputs['As Instance'].default_value=True;node=n.new('GeometryNodeInstanceOnPoints');l.new(inp.outputs['Geometry'],node.inputs['Points']);l.new(info.outputs['Geometry'],node.inputs['Instance']);l.new(node.outputs['Instances'],out.inputs['Geometry'])
 for attr,sock in [('module_scale','Scale'),('module_rotation','Rotation')]:
  a=n.new('GeometryNodeInputNamedAttribute');a.data_type='FLOAT_VECTOR';a.inputs['Name'].default_value=attr;l.new(a.outputs['Attribute'],node.inputs[sock])
 mod=ob.modifiers.new('Shared editable building modules','NODES');mod.node_group=tree;ob['building_instances']=len(items);ob['instance_kind_05']=prototype.name.removeprefix('Module_');ob['instance_triangles_05']=len(items)*len(prototype.data.polygons);ob['inference']='inferred facade/roof modules; per-point building_index maps evidence in SQLite';return ob
_bounds={}
def bounds(o):
 if o.name in _bounds:return _bounds[o.name]
 if o.get('stage05_bounds_m') is not None:
  a=np.array(o['stage05_bounds_m']);out=(a[:3],a[3:]);_bounds[o.name]=out;return out
 if o.type!='MESH':return np.array([-1e9]*3),np.array([1e9]*3)
 key=o.data.as_pointer()
 if key not in _bounds:
  v=np.empty(len(o.data.vertices)*3,np.float32);o.data.vertices.foreach_get('co',v);v=v.reshape(-1,3);_bounds[key]=(v.min(axis=0),v.max(axis=0)) if len(v) else (np.zeros(3),np.zeros(3))
 a,b=_bounds[key];m=Matrix.LocRotScale(o.location,o.rotation_euler.to_quaternion(),o.scale)
 if o.parent:m=o.parent.matrix_world@m
 vv=np.array([m@Vector((x,y,z)) for x in [a[0],b[0]] for y in [a[1],b[1]] for z in [a[2],b[2]]]);out=(vv.min(axis=0),vv.max(axis=0));_bounds[o.name]=out;return out
def count(shows):return sum(int(o.get('instance_triangles_05',len(o.data.polygons))) for o in scene.objects if o.type=='MESH' and shows.get(o.name,False))
def visible(focus,radius,mode='street',batch=False):
 objects=list(scene.objects);shows={};collection_hidden={o.name for c in bpy.data.collections if c.hide_render for o in c.objects}
 for o in objects:
  role=o.get('traffic_role');lod=o.get('building_lod');module=o.get('instance_kind_05');show=bool(o.get('stage04_full_view_visible',not o.hide_render));lo,hi=bounds(o);near=lo[0]<=focus[0]+radius and hi[0]>=focus[0]-radius and lo[1]<=focus[1]+radius and hi[1]>=focus[1]-radius
  if lod is not None:show=near and ((int(lod)==2) if mode=='city' else ((int(lod)==0) if int(o['visual_level_05']) else (int(lod)==2)))
  elif module:show=near and mode!='city'
  elif o.type=='MESH':show=show and near
  if mode=='city':
   if role:show=near and role in ['overview_far','bridge_road','tunnel_road','downtown_road','rail_corridor','airport_surface','airport_apron','airport_marking','profiled_priority_road','inferred_retaining_bank']
   if o.get('instance_kind'):show=False
  if mode=='downtown' and (role in ['downtown_curb','rail_detail','refuge_island'] or o.get('instance_kind')):show=False
  if mode=='skyline' and o.get('instance_kind'):show=False
  if o.name in collection_hidden:show=False
  shows[o.name]=show
 if batch:
  flags=np.array([not shows[o.name] for o in bpy.data.objects],bool);bpy.data.objects.foreach_set('hide_render',flags);bpy.data.objects.foreach_set('hide_viewport',flags)
 else:
  for o in objects:
   if o.hide_render==shows[o.name]:o.hide_render=not shows[o.name]
 # Only an actual changed RNA setter can refresh visibility during a running render process.
 return shows
def aim(view):
 cam=scene.camera;cam.location=view['position_m'];cam.rotation_euler=(Vector(view['target_m'])-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.clip_start=.1;cam.data.clip_end=500000
 if 'ortho_scale_m' in view:cam.data.type='ORTHO';cam.data.ortho_scale=view['ortho_scale_m']
 else:cam.data.type='PERSP';cam.data.lens=view.get('lens_mm',35);cam.data.sensor_width=36
def build():
 index=json.loads((root/'data/processed/stage05/mesh_index.json').read_text());mats=[mat(n,c) for n,c in index['materials']];protos=module_library(mats);groups={}
 for level in [0,2]:
  c=bpy.data.collections.new('10_Buildings_'+('AUTHORING_editable' if level==0 else 'RUNTIME_simplified_static_alternative'));scene.collection.children.link(c);groups[level]=c
 instcoll=bpy.data.collections.new('12_Building_modules_GN_shared_instances');scene.collection.children.link(instcoll)
 for i,m in enumerate(index['meshes']):
  with np.load(root/m['file']) as a:data=mesh(m['id'],a['v'],a['f'],mats,a['m'],a['fid'],a['uv'] if 'uv' in a else None)
  ob=bpy.data.objects.new(m['id'],data);groups[m['lod']].objects.link(ob);ob.location=m['origin_m'];ob['building_lod']=m['lod'];ob['visual_level_05']=m['visual_level'];ob['stage05_bounds_m']=m['bounds_m'][0]+m['bounds_m'][1];ob['building_cell']=m['owner'];ob['source_file']=m['file'];ob['source_database']='data/processed/stage05/buildings.sqlite; FACE building_index -> i';ob['data_class']='source roofline/footprint geometry; separately recorded reported and inferred heights; procedural facade approximation'
  if i%100==0:print('BUILDING_MESHES_IMPORTED',i,'/',len(index['meshes']),flush=True)
 instance_count=0
 for cell in index['cells']:
  if cell.get('placements') is None:continue
  with gzip.open(root/cell['placements'],'rt') as f:d=json.load(f)
  kinds=collections.defaultdict(list)
  for ins in d['instances']:kinds[ins['kind']].append(ins)
  for kind,items in kinds.items():
   ob=instances(cell['id']+'_'+kind,items,np.array(cell['origin_m']),protos[kind],instcoll);xyz=np.array([x['xyz'] for x in items]);ob['stage05_bounds_m']=(xyz.min(axis=0)-5).tolist()+(xyz.max(axis=0)+5).tolist();instance_count+=len(items)
 print('BUILDING_GN_INSTANCES_IMPORTED',instance_count,flush=True)
 scene['stage']=5;scene['building_source']='county rooflines 1992/2003/2008/2014/2017/2020 + OSM state2026-10-20; not one-date snapshot';scene['building_height_notes']='Published reference / source-reported county import / source-reported other / inferred interpretation / storeys / type are separate fields; no random heights. LARIAC ELEV not mixed with NAVD88.';scene['building_geometry_index']='data/processed/stage05/mesh_index.json';scene['runtime_lod']='static exclusive alternatives only; runtime streaming and GLB not implemented';scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
 scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24;scene.cycles.use_denoising=False;scene.cycles.seed=20261021;scene.render.threads_mode='FIXED';scene.render.threads=4
 view=json.loads((root/'config/stage05_views.json').read_text())['historic_core_street'];focus=view['focus_xy_m'];budget_attempts=[]
 for radius in [600,450,350,250,150,100]:
  shows=visible(focus,radius,'street',True);tri=count(shows);budget_attempts.append({'radius_m':radius,'triangles':tri})
  if tri<=1500000:break
 if tri>1500000:
  # Coarse source traffic tiles can span the focus even for a small radius.
  # Keep their editable geometry but omit dense paint/curb/sleeper display.
  for o in scene.objects:
   if o.get('traffic_role') in ['markings','downtown_curb','rail_detail'] or o.name.startswith('sleeper_'):shows[o.name]=False
  flags=np.array([not shows[o.name] for o in bpy.data.objects],bool);bpy.data.objects.foreach_set('hide_render',flags);bpy.data.objects.foreach_set('hide_viewport',flags);tri=count(shows)
 assert tri<=1500000,'Actual default visibility still exceeds configured budget'
 scene['stage05_default_visible_triangles']=tri;scene['stage05_default_focus_xy_m']=focus;scene['stage05_default_radius_m']=radius;scene['stage05_budget_attempts']=json.dumps(budget_attempts);scene['stage05_shared_module_instances']=instance_count;aim(view)
 text=bpy.data.texts.new('STAGE05_VIEW_PRESETS.py');text.write((root/'scripts/stage05_view_presets.py').read_text());scene.render.resolution_x=1536;scene.render.resolution_y=1152;scene.render.resolution_percentage=100
 for screen in bpy.data.screens:
  for area in screen.areas:
   if area.type=='VIEW_3D':area.spaces.active.clip_end=500000;area.spaces.active.region_3d.view_location=Vector((*focus,100));area.spaces.active.region_3d.view_distance=500
 sys.path.insert(0,str(root/'scripts'));from stage05_regions import organize
 organize(root);scene.view_settings.exposure=1.;bpy.context.preferences.filepaths.save_version=0;path=root/'scenes/stage05_city_medium.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True);write(root/'work/reports/stage05/blender_build.json',{'status':'saved','path':str(path),'default_visible_triangles':tri,'default_radius_m':radius,'budget_attempts':budget_attempts,'module_instances':instance_count,'geometry_nodes_are_shared_instances':True,'runtime_lod_switching':False});print('STAGE05_SAVED_AND_EXIT',path,'DEFAULT_TRIANGLES',tri,flush=True)
def check():
 patchpath=root/'work/reports/stage05/semantic_exclusions.json'
 if patchpath.exists() and not scene.get('stage05_nonbuilding_filter_applied',False):
  # A source semantics correction can arrive while the large scene imports.
  # Replace the affected fourteen block meshes from the validated final NPZs.
  # Save/close this working checkpoint, then inspect in a fresh Blender process.
  patch=json.loads(patchpath.read_text());assert patch['retained_building_triangle_coordinates_verified_identical']
  for rec in patch['affected_meshes']:
   ob=bpy.data.objects[rec['id']];old=ob.data
   with np.load(root/rec['file']) as arrays:ob.data=mesh(rec['id']+'_semantic_filter',arrays['v'],arrays['f'],list(old.materials),arrays['m'],arrays['fid'],arrays['uv'] if 'uv' in arrays else None)
   ob['stage05_bounds_m']=rec['bounds_m'][0]+rec['bounds_m'][1]
   if old.users==0:bpy.data.meshes.remove(old)
  scene['stage05_nonbuilding_filter_applied']=True;scene['stage05_nonbuilding_filter_report']='work/reports/stage05/semantic_exclusions.json';path=root/'scenes/stage05_city_medium.blend';archive=root/'work/history/stage05_before_nonbuilding_filter/stage05_city_medium.blend';archive.parent.mkdir(parents=True,exist_ok=True);assert not archive.exists();path.replace(archive);bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True);write(root/'work/reports/stage05/blender_semantic_repair.json',{'status':'saved','affected_meshes':len(patch['affected_meshes']),'excluded_nonbuilding_ids':len(patch['excluded_nonbuildings']),'archived_unaccepted_checkpoint':str(archive.relative_to(root)),'source_coordinates_of_retained_triangles_unchanged':True});print('SEMANTICALLY_CORRECTED_CHECKPOINT_SAVED',flush=True)
  bpy.ops.wm.read_factory_settings(use_empty=True)
  import subprocess
  command=['/usr/bin/blender','--background','--threads','4','--python-exit-code','1',str(path),'--python',str(Path(__file__).resolve()),'--','--root',str(root),'--mode','check'];p=subprocess.run(command);assert p.returncode==0,'Independent corrected-file check failed';return
 assert Path(bpy.data.filepath)==root/'scenes/stage05_city_medium.blend';seen=set();nonfinite=degen=tri=0;actual_features=set();building_objects=0;mat_bad=0;wrong_roofnormals=0;smooth_building_faces=0;fid_counts=collections.Counter();hidden={o.name for c in bpy.data.collections if c.hide_render for o in c.objects};visible_triangles=0;start=time.monotonic();samples=json.loads((root/'work/reports/stage05/audit_selection.json').read_text());selected=set(x['i'] for x in samples['buildings']);measured={i:{'vertices':[],'normal_counts':collections.Counter(),'materials':set(),'face_count':0} for i in selected}
 for oi,o in enumerate(scene.objects):
  if o.type!='MESH':continue
  m=o.data
  if not o.hide_render and o.name not in hidden:visible_triangles+=int(o.get('instance_triangles_05',len(m.polygons)))
  if m.as_pointer() in seen:continue
  seen.add(m.as_pointer());v=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',v);v=v.reshape(-1,3);nonfinite+=int((~np.isfinite(v)).sum());f=np.empty(len(m.polygons)*3,np.int32)
  if o.get('instance_kind_05'):
   transform_values={}
   for attribute in ['module_scale','module_rotation']:
    values=np.empty(len(m.vertices)*3,np.float32);m.attributes[attribute].data.foreach_get('vector',values);assert np.isfinite(values).all(),o.name+' nonfinite module transform'
    transform_values[attribute]=values.reshape(-1,3)
    if attribute=='module_scale':assert (values>0).all(),o.name+' invalid module dimensions'
   point_ids=np.empty(len(m.vertices),np.int32);m.attributes['building_index'].data.foreach_get('value',point_ids);prototype=bpy.data.objects['Module_'+o['instance_kind_05']];prototype_zmax=max(p.co.z for p in prototype.data.vertices);world_top=v[:,2]+o.location.z+transform_values['module_scale'][:,2]*prototype_zmax
   for index in selected.intersection(np.unique(point_ids).tolist()):
    maximum=float(world_top[point_ids==index].max());measured[index]['module_zmax']=max(measured[index].get('module_zmax',-1e30),maximum)
  if not len(m.polygons):continue
  # All generated source meshes use triangles. Refuse unexpected polygon topology.
  total=np.empty(len(m.polygons),np.int32);m.polygons.foreach_get('loop_total',total)
  if not (total==3).all():
   assert o.get('building_lod') is None,'Unexpected nontriangular building mesh '+o.name
   m.calc_loop_triangles();f=np.array([t.vertices[:] for t in m.loop_triangles],np.int32)
  else:m.loops.foreach_get('vertex_index',f);f=f.reshape(-1,3)
  cross=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]);degen+=int((np.linalg.norm(cross,axis=1)<1e-8).sum());tri+=len(f)
  if o.get('building_lod') is not None:
   smooth=np.empty(len(m.polygons),bool);m.polygons.foreach_get('use_smooth',smooth);smooth_building_faces+=int(smooth.sum())
   building_objects+=1;ids=np.empty(len(f),np.int32);m.attributes['building_index'].data.foreach_get('value',ids);mi=np.empty(len(f),np.int32);m.polygons.foreach_get('material_index',mi);mat_bad+=int(((mi<0)|(mi>=len(m.materials))).sum())
   if int(o['building_lod'])==0:
    unique=np.unique(ids);actual_features.update(unique.tolist());fid_counts.update(unique.tolist());roof_id=next(i for i,t in enumerate(m.materials) if t.name=='LA05_roof');wrong_roofnormals+=int(((mi==roof_id)&(cross[:,2]<-1e-7)).sum())
    for index in selected.intersection(unique.tolist()):
     mask=ids==index;d=measured[index];unique_v,inverse=np.unique(f[mask],return_inverse=True);world_v=v[unique_v]+np.array(o.location);d['vertices'].append(world_v);d['materials'].update(int(x) for x in mi[mask]);d['face_count']+=int(mask.sum());d['normal_counts'].update({'up':int((cross[mask,2]>1e-7).sum()),'down':int((cross[mask,2]<-1e-7).sum()),'wall':int((abs(cross[mask,2])<=1e-7).sum())});sample_path=root/f'work/reports/stage05/audit_meshes/{index}.npz';sample_path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(sample_path,v=world_v,f=inverse.reshape(-1,3),m=mi[mask])
  if oi%10000==0:print('REOPEN_MESHES_INSPECTED',oi,flush=True)
 rows=[]
 for expected in samples['buildings']:
  d=measured[expected['i']];vv=np.concatenate(d['vertices']) if d['vertices'] else np.empty((0,3));rows.append({'i':expected['i'],'id':expected['id'],'actual_face_count':d['face_count'],'actual_bbox_m':[vv.min(axis=0).tolist(),vv.max(axis=0).tolist()] if len(vv) else None,'actual_maximum_z_including_shared_modules':max(float(vv[:,2].max()),d.get('module_zmax',-1e30)) if len(vv) else None,'materials':sorted(d['materials']),'normal_counts':dict(d['normal_counts']),'present_in_exactly_one_authoring_cell':fid_counts[expected['i']]==1,'expected_record':expected})
 report={'status':'passed' if nonfinite==degen==mat_bad==wrong_roofnormals==0 and visible_triangles<=1500000 else 'failed','file_reopened_in_independent_process':True,'opened_path':bpy.data.filepath,'nonfinite_coordinates':nonfinite,'degenerate_triangles':degen,'invalid_material_indices':mat_bad,'downward_building_roof_faces':wrong_roofnormals,'unique_used_meshes':len(seen),'all_stored_unique_triangles':tri,'visible_default_triangles_including_GN_instances':visible_triangles,'building_mesh_objects':building_objects,'unique_authoring_building_ids':len(actual_features),'building_ids_in_multiple_authoring_cells':sum(n>1 for n in fid_counts.values()),'units':'1 Blender unit=1m; NAVD88 ground, relative inferred/reported building heights','unit_scale':scene.unit_settings.scale_length,'samples':rows,'seconds':time.monotonic()-start};write(root/'work/reports/stage05/blender_check.json',report)
 kinds=collections.Counter()
 for ob in scene.objects:
  if ob.get('instance_kind_05'):kinds[ob['instance_kind_05']]+=int(ob['building_instances'])
 write(root/'assets/buildings/stage05_catalog.json',{'library':'assets/buildings/stage05_modules.blend','modules':[{'name':ob.name,'unique_triangles':len(ob.data.polygons),'placed_instances':kinds[ob.name.removeprefix('Module_')],'inference':'own approximate visual template, not surveyed architecture'} for ob in bpy.data.objects if ob.name.startswith('Module_')],'shared_instances_by_kind':dict(kinds),'templates_do_not_establish_observed_presence':True})
 report['smooth_building_faces']=smooth_building_faces
 if smooth_building_faces:report['status']='failed'
 if (root/'work/reports/stage05/region_collections.json').exists():
  sys.path.insert(0,str(root/'scripts'));from stage05_regions import verify
  verify(root)
 write(root/'work/reports/stage05/blender_check.json',report)
 assert report['status']=='passed' and report['building_ids_in_multiple_authoring_cells']==0
 assert scene.unit_settings.scale_length==1 and scene.unit_settings.system=='METRIC'
 print('STAGE05_REOPEN_ACTUAL_GEOMETRY_CHECK_PASSED',len(actual_features),tri,visible_triangles,flush=True)
def render():
 views=json.loads((root/'config/stage05_views.json').read_text());records={};scene.render.image_settings.file_format='PNG';scene.render.resolution_x=1536;scene.render.resolution_y=1152;scene.render.resolution_percentage=100;scene.cycles.device='CPU';scene.cycles.use_denoising=False;scene.render.threads_mode='FIXED';scene.render.threads=4
 for name,view in views.items():
  if args.view not in ['all',name]:continue
  start=time.monotonic();shows=visible(view['focus_xy_m'],view['radius_m'],view['mode']);aim(view);scene.view_settings.exposure=view.get('exposure_stops',0.);scene.cycles.samples=view.get('samples',16);scene.render.filepath=str(root/'work/previews/stage05'/f'{name}.png');print('ACTUAL_RENDER_START',name,'triangles',count(shows),flush=True);bpy.ops.render.render(write_still=True);records[name]={'path':scene.render.filepath,'position_m':view['position_m'],'target_m':view['target_m'],'visible_triangles_including_instances':count(shows),'mode':view['mode'],'exposure_stops':scene.view_settings.exposure,'seconds':time.monotonic()-start};print('ACTUAL_RENDER_DONE',name,flush=True)
 write(root/'work/reports/stage05'/('renders_'+args.view+'.json'),{'status':'executed','renders':records,'actual_cpu_cycles':True,'not_real_time_performance_measurement':True})
def repair():
 queue=root/'work/reports/stage05/pending_mesh_updates.json';patch=json.loads((queue if queue.exists() else root/'work/reports/stage05/roof_winding.json').read_text());nreplaced=0
 for rec in patch['changed_meshes']:
  ob=bpy.data.objects[rec['id']];old=ob.data
  with np.load(root/rec['file']) as arrays:ob.data=mesh(rec['id']+'_float32_roof_normals',arrays['v'],arrays['f'],list(old.materials),arrays['m'],arrays['fid'],arrays['uv'] if 'uv' in arrays else None)
  ob['stage05_bounds_m']=rec['bounds_m'][0]+rec['bounds_m'][1]
  if old.users==0:bpy.data.meshes.remove(old)
  nreplaced+=1
 if patch.get('changed_cells'):
  cellids={c['id'] for c in patch['changed_cells']};coll=bpy.data.collections['12_Building_modules_GN_shared_instances']
  for ob in list(coll.all_objects):
   if any(ob.name.startswith(c+'_') for c in cellids):
    old=ob.data;groups=[m.node_group for m in ob.modifiers if m.type=='NODES'];bpy.data.objects.remove(ob,do_unlink=True)
    if old.users==0:bpy.data.meshes.remove(old)
    for group in groups:
     if group.users==0:bpy.data.node_groups.remove(group)
  for c in patch['changed_cells']:
   with gzip.open(root/c['placements'],'rt') as f:data=json.load(f)
   kinds=collections.defaultdict(list)
   for ins in data['instances']:kinds[ins['kind']].append(ins)
   for kind,items in kinds.items():
    ob=instances(c['id']+'_'+kind,items,np.array(c['origin_m']),bpy.data.objects['Module_'+kind],coll);xyz=np.array([x['xyz'] for x in items]);ob['stage05_bounds_m']=(xyz.min(axis=0)-5).tolist()+(xyz.max(axis=0)+5).tolist()
  shows=visible(scene['stage05_default_focus_xy_m'],float(scene['stage05_default_radius_m']),'street',True);scene['stage05_default_visible_triangles']=count_visible=count(shows);assert count_visible<=1500000;scene['stage05_shared_module_instances']=sum(int(o.get('building_instances',0)) for o in coll.all_objects)
 flat_faces=0
 for ob in scene.objects:
  if ob.type=='MESH' and (ob.get('building_lod') is not None or ob.name.startswith('Module_')):
   ob.data.polygons.foreach_set('use_smooth',np.zeros(len(ob.data.polygons),bool));flat_faces+=len(ob.data.polygons)
 bpy.data.libraries.write(str(root/'assets/buildings/stage05_modules.blend'),{o for o in bpy.data.objects if o.name.startswith('Module_')},fake_user=True,compress=True)
 sys.path.insert(0,str(root/'scripts'));from stage05_regions import organize
 organize(root)
 text=bpy.data.texts.get('STAGE05_VIEW_PRESETS.py');text.clear();text.write((root/'scripts/stage05_view_presets.py').read_text());scene['stage05_float32_roof_winding_corrected']=True;scene.view_settings.exposure=1.;bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(root/'scenes/stage05_city_medium.blend'),compress=True);write(root/'work/reports/stage05/blender_winding_repair.json',{'status':'saved','mesh_replacements':nreplaced,'reason':patch.get('reason','float32 roof winding'),'flat_shaded_building_and_module_faces':flat_faces,'next_required_step':'independent process reopen and actual geometry check'});print('UPDATED_BLOCKS_REPAIRED_SAVED_AND_EXIT',nreplaced,flush=True)
def gn_test():
 bpy.ops.wm.read_factory_settings(use_empty=True);m=mat('frame',[.2,.2,.2,1]);p=bpy.data.objects.new('TestPrototype',boxes('TestUnit',[([0,0,0],[1,1,1],0)],[m]));c=bpy.data.collections.new('HiddenPrototypeLibrary');bpy.context.scene.collection.children.link(c);c.objects.link(p);c.hide_render=True;c.hide_viewport=True;o=instances('TestPoints',[{'xyz':[10,20,30],'scale':[2,3,4],'rotation':math.pi/2,'fid':12},{'xyz':[20,30,40],'scale':[1,1,1],'rotation':0,'fid':13}],np.zeros(3),p,bpy.context.scene.collection);bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();rows=[]
 for ins in dg.object_instances:
  if ins.is_instance:rows.append({'translation':list(ins.matrix_world.translation),'scale':list(ins.matrix_world.to_scale())})
 assert len(rows)==2;assert np.allclose(sorted(r['translation'] for r in rows),[[10,20,30],[20,30,40]])
 assert any(np.allclose(r['scale'],[2,3,4]) for r in rows);write(root/'work/reports/stage05/geometry_nodes_test.json',{'status':'passed','actual_evaluated_instances':rows});print('REAL_GEOMETRY_NODES_INSTANCE_TEST_PASSED',flush=True)
{'build':build,'repair':repair,'check':check,'render':render,'gn-test':gn_test}[args.mode]()
