"""Blender worker: isolated saves, independent reopen audits, real renders and GLBs."""
import argparse,collections,hashlib,json,math,sys,time
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,Matrix
p=argparse.ArgumentParser();p.add_argument('--root',default='/workspace/Base');p.add_argument('--mode',required=True);p.add_argument('--id',default='all');args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(args.root);sys.path.insert(0,str(root/'scripts'))
def read(p):return json.loads((root/p).read_text())
def write(p,a):
 p=root/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
cfg=read('config/stage06.json')
def make_material(n,c,rough,metal):
 mat=bpy.data.materials.new('LA06_'+n);mat.use_nodes=True;mat.diffuse_color=c;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=c;bs.inputs['Roughness'].default_value=rough;bs.inputs['Metallic'].default_value=metal
 if n in ['limestone','concrete','white','paving','terracotta']:
  nodes=mat.node_tree.nodes;links=mat.node_tree.links;noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=5.;noise.inputs['Detail'].default_value=3;bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.13;bump.inputs['Distance'].default_value=.025;links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bs.inputs['Normal'])
 return mat
def mesh(name,arrays,mats,smooth=False):
 v=arrays['v'];f=arrays['f'];data=bpy.data.meshes.new(name);data.vertices.add(len(v));data.vertices.foreach_set('co',v.ravel());data.loops.add(f.size);data.loops.foreach_set('vertex_index',f.ravel());data.polygons.add(len(f));data.polygons.foreach_set('loop_start',np.arange(len(f),dtype=np.int32)*3);data.polygons.foreach_set('loop_total',np.full(len(f),3,np.int32));data.polygons.foreach_set('use_smooth',np.full(len(f),smooth,bool));data.polygons.foreach_set('material_index',arrays['m']);
 for m in mats:data.materials.append(m)
 if 'fid' in arrays:data.attributes.new('building_index','INT','FACE').data.foreach_set('value',arrays['fid'])
 if 'uv' in arrays:data.uv_layers.new(name='FacadeMeters').data.foreach_set('uv',arrays['uv'].reshape(-1))
 data.update();return data
def setup_scene(width=None,height=None,samples=None):
 s=bpy.context.scene;s.unit_settings.system='METRIC';s.unit_settings.scale_length=1.;s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=samples or cfg['render']['samples'];s.cycles.use_denoising=False;s.cycles.seed=cfg['seed'];s.cycles.max_bounces=5;s.render.threads_mode='FIXED';s.render.threads=4;s.render.resolution_x=width or cfg['render']['width'];s.render.resolution_y=height or cfg['render']['height'];s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.film_transparent=False
 world=bpy.data.worlds.new('Landmark_daylight') if not s.world else s.world;s.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.65,.76,1);world.node_tree.nodes['Background'].inputs[1].default_value=.65
 if not any(o.type=='LIGHT' and o.data.type=='SUN' for o in s.objects):
  light=bpy.data.lights.new('Landmark_sun','SUN');light.energy=3.;light.angle=.14;ob=bpy.data.objects.new('Landmark_sun',light);s.collection.objects.link(ob);ob.rotation_euler=(math.radians(24),math.radians(-30),math.radians(-24))
 if not s.camera:
  cam=bpy.data.objects.new('Landmark_camera',bpy.data.cameras.new('Landmark_camera'));s.collection.objects.link(cam);s.camera=cam
 s.view_settings.view_transform='AgX';s.view_settings.exposure=.3;return s
def aim(position,target,scale=None,lens=45):
 c=bpy.context.scene.camera;c.location=position;c.rotation_euler=(Vector(target)-c.location).to_track_quat('-Z','Y').to_euler();c.data.clip_start=.05;c.data.clip_end=100000;c.data.type='ORTHO' if scale else 'PERSP'
 if scale:c.data.ortho_scale=scale
 else:c.data.lens=lens
def import_landmark(item,mats,global_position=False,massing=False):
 card=read(item['card']);coll=bpy.data.collections.new('LM_'+item['id']);bpy.context.scene.collection.children.link(coll);empty=bpy.data.objects.new('Landmark_'+item['id'],None);coll.objects.link(empty);empty['stable_id']='landmark:'+item['id'];empty['source_card']=item['card'];empty['geographic_origin_city_m']=card['origin_city_m'];empty['rotation_from_grid_east_degrees']=card['rotation_from_grid_east_degrees'];empty['model_status']='approximate architectural reconstruction, see card';empty['asset_to_city_matrix']=json.dumps(card['asset_to_city_matrix']);empty['horizontal_crs']='EPSG:32611 local city origin';empty['vertical_datum']='NAVD88 ground; geometric detail inferred';empty['meters_per_unit']=1.
 if global_position:empty.location=card['origin_city_m'];empty.rotation_euler.z=card['rotation_z_radians']
 for lod in item['assets']:
  lc=bpy.data.collections.new(item['id']+'_'+lod['lod']);coll.children.link(lc)
  for rec in lod['objects']:
   with np.load(root/rec['file']) as a:arrays={k:a[k] for k in a.files}
   ob=bpy.data.objects.new(item['id']+'_'+lod['lod']+'_'+rec['name'],mesh(item['id']+'_'+lod['lod']+'_'+rec['name'],arrays,mats,rec['smooth_curved']));lc.objects.link(ob);ob.parent=empty;ob['landmark_id']=item['id'];ob['landmark_lod']=lod['lod'];ob['component']=rec['name'];ob['source_mesh']=rec['file'];ob['evidence']=rec['inference'];ob.hide_render=lod['lod'] not in (['far'] if massing else ['near']);ob.hide_viewport=ob.hide_render
   if lod['lod']=='near' and any(k in rec['name'] for k in ['clock_tower','podium','acoustic_core','club_tower']):
    mod=ob.modifiers.new('Editable edge highlights; approximate','BEVEL');mod.width=.05;mod.segments=2;mod.limit_method='ANGLE';mod.angle_limit=.6
 text=bpy.data.texts.new(item['id']+'_PARAMETERS_AND_SOURCES.json');text.write(json.dumps(card,ensure_ascii=False,indent=2));return empty,coll
def saved_bounds(objects,world=False):
 out=[]
 for o in objects:
  if o.type!='MESH':continue
  v=np.empty(len(o.data.vertices)*3,np.float32);o.data.vertices.foreach_get('co',v);v=v.reshape(-1,3)
  if not len(v):continue
  if world:
   m=o.matrix_world;out.extend([list(m@Vector(p)) for p in [v.min(axis=0),v.max(axis=0)]])
  else:out.extend([v.min(axis=0),v.max(axis=0)])
 out=np.array(out);return out.min(axis=0),out.max(axis=0)
def save(path):
 bpy.context.preferences.filepaths.save_version=0;path=root/path;path.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True);print('SAVED',path,flush=True)
def render(path):
 path=root/path;path.parent.mkdir(parents=True,exist_ok=True);bpy.context.scene.render.filepath=str(path);start=time.monotonic();bpy.ops.render.render(write_still=True);print('ACTUAL_RENDER',path,time.monotonic()-start,flush=True)
def massing_build():
 bpy.ops.wm.read_factory_settings(use_empty=True);s=setup_scene(640,480,6);index=read('data/processed/stage06/massing_index.json');mats=[make_material(*m) for m in index['materials']]
 for item in index['landmarks']:import_landmark(item,mats,True,True)
 s['stage']=6;s['stage06_phase']='massing_before_detail';s['real_geographic_positions']=True;save('scenes/stage06_massing.blend')
def massing_check():
 s=bpy.context.scene;setup_scene(640,480,6);index=read('data/processed/stage06/massing_index.json');rows=[]
 for item in index['landmarks']:
  card=read(item['card']);objects=[o for o in s.objects if o.get('landmark_id')==item['id']];verts=tri=bad=degen=0
  for o in objects:
   m=o.data;v=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',v);v=v.reshape(-1,3);f=np.empty(len(m.polygons)*3,np.int32);m.loops.foreach_get('vertex_index',f);f=f.reshape(-1,3);bad+=int((~np.isfinite(v)).sum());degen+=int((np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)<=1e-8).sum());tri+=len(f);verts+=len(v)
  assert bad==degen==0;lo,hi=np.array(item['assets'][0]['bounds_local_m']);direction=np.array(card['front_local_direction'],float);theta=card['rotation_z_radians'];R=np.array([[math.cos(theta),-math.sin(theta)],[math.sin(theta),math.cos(theta)]]);direction=R@direction;center=np.array(card['origin_city_m']);target=center+np.array([0,0,(lo[2]+hi[2])/2]);span=max(hi[0]-lo[0],hi[1]-lo[1],(hi[2]-lo[2])*4/3)*1.2
  for o in s.objects:
   if o.get('landmark_id'):o.hide_render=o.get('landmark_id')!=item['id']
  aim(target+np.array([*direction*max(span*2,100),0]),target,span);render('work/previews/stage06/massing/'+item['id']+'_front.png');side=np.array([-direction[1],direction[0]]);aim(target+np.array([*side*max(span*2,100),0]),target,span);render('work/previews/stage06/massing/'+item['id']+'_side.png');aim(center+[0,0,1000],center, max(hi[0]-lo[0],(hi[1]-lo[1])*4/3)*1.2);render('work/previews/stage06/massing/'+item['id']+'_top.png');rows.append({'id':item['id'],'nonfinite':bad,'degenerate':degen,'triangles':tri,'bounds_local_m':[lo.tolist(),hi.tolist()],'source_height_reference_m':card['height_m'],'measured_top_m':float(hi[2]),'published_height_definition':card['height_basis'],'geographic_position_m':center.tolist(),'status':'numeric_checks_passed_visual_review_pending'})
 write('work/reports/stage06/massing_check.json',{'status':'numeric_passed_visual_review_pending','independent_reopen':True,'models':rows,'source_accuracy_not_equal_to_computation_error':True})
def assets_build():
 index=read('data/processed/stage06/geometry_index.json');items=[x for x in index['landmarks'] if args.id in ['all',x['id']]]
 for item in items:
  bpy.ops.wm.read_factory_settings(use_empty=True);s=setup_scene();mats=[make_material(*m) for m in index['materials']];empty,coll=import_landmark(item,mats);near=next(a for a in item['assets'] if a['lod']=='near');lo,hi=np.array(near['bounds_local_m']);target=(lo+hi)/2;span=max(hi[0]-lo[0],hi[1]-lo[1],(hi[2]-lo[2])*4/3)*1.2;aim(target+[span,-span,span*.35],target,span);s['stage']=6;s['landmark_id']=item['id'];s['runtime_switching']='not implemented; manually select near/mid/far mutually exclusively';s['model_status']='approximate, with research-specific identifying geometry';save('assets/landmarks/stage06/'+item['id']+'.blend')
def asset_check_render():
 s=bpy.context.scene;setup_scene();ident=args.id;index=read('data/processed/stage06/geometry_index.json');item=next(i for i in index['landmarks'] if i['id']==ident);card=read(item['card']);audit=[]
 for a in item['assets']:
  objs=[o for o in s.objects if o.get('landmark_lod')==a['lod']];tri=bad=deg=badmat=0;points=[]
  for ob in objs:
   m=ob.data;v=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',v);v=v.reshape(-1,3);f=np.empty(len(m.loops),np.int32);m.loops.foreach_get('vertex_index',f);f=f.reshape(-1,3);mi=np.empty(len(m.polygons),np.int32);m.polygons.foreach_get('material_index',mi);bad+=int((~np.isfinite(v)).sum());deg+=int((np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)<=1e-8).sum());badmat+=int(((mi<0)|(mi>=len(m.materials))).sum());tri+=len(f);points.extend([v.min(axis=0),v.max(axis=0)])
  assert bad==deg==badmat==0 and tri==a['triangles'];points=np.array(points);measured=[points.min(axis=0).tolist(),points.max(axis=0).tolist()];assert np.max(np.abs(np.array(measured)-a['bounds_local_m']))<.0001;audit.append({'lod':a['lod'],'triangles':tri,'nonfinite':bad,'degenerate':deg,'invalid_materials':badmat,'bounds_local_m':measured})
 assert s.unit_settings.scale_length==1 and s.unit_settings.system=='METRIC'
 lo,hi=np.array(next(a for a in item['assets'] if a['lod']=='near')['bounds_local_m']);target=(lo+hi)/2;direction=np.array(card['front_local_direction']);span=max(hi[0]-lo[0],hi[1]-lo[1],(hi[2]-lo[2])*4/3)*1.18
 for name,d in [('front',direction),('side',np.array([-direction[1],direction[0]]))]:aim(target+np.array([*(d*max(span*2,100)),0]),target,span);render('work/previews/stage06/'+ident+'/'+name+'.png')
 aim(target+[0,0,1000],target,max(hi[0]-lo[0],(hi[1]-lo[1])*4/3)*1.18);render('work/previews/stage06/'+ident+'/top.png')
 # glTF exporter is actually executed on each selected mutually-exclusive LOD.
 glbs=[]
 for lod in ['near','mid','far']:
  bpy.ops.object.select_all(action='DESELECT')
  for o in s.objects:
   if o.get('landmark_id')==ident:o.hide_viewport=False;o.hide_set(False);o.select_set(o.get('landmark_lod')==lod)
  path=root/'outputs/stage06/glb'/ident/(lod+'.glb');path.parent.mkdir(parents=True,exist_ok=True);bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True,export_extras=True,export_cameras=False,export_lights=False,export_yup=True,export_materials='EXPORT');assert path.exists();glbs.append({'lod':lod,'path':str(path.relative_to(root)),'bytes':path.stat().st_size})
 write('work/reports/stage06/assets/'+ident+'.json',{'status':'passed','saved_file_reopened_in_independent_process':True,'blender_file':str(Path(bpy.data.filepath).relative_to(root)),'meters_per_unit':1,'lods':audit,'glb_exports':glbs,'actual_cpu_renders':['front','side','top'],'model_truth_status':'approximate; numeric implementation check is not survey/appearance certification'})
if __name__=='__main__':
 if args.mode=='massing-build':massing_build()
 elif args.mode=='massing-check':massing_check()
 elif args.mode=='assets-build':assets_build()
 elif args.mode=='asset-check-render':asset_check_render()
 else:raise RuntimeError('未实现 / NOT IMPLEMENTED: '+args.mode)
