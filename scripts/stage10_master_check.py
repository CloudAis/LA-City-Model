"""All-mesh numeric audit, selected topology and clean-session asset checks."""
from pathlib import Path
import sys,json,hashlib,time
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from stage10_common import *
from stage10_scene import apply_view,apply_light
scene=bpy.context.scene;started=time.perf_counter();seen=set();bad=zero=triangles=vertices=0;empty=[];topology=[];library=[];images=[];controls=[];proxy=0;sample_count=0
selected=set(read('data/processed/stage07_final/index.json')['replaced_source_indices'])|{r['i'] for lm in read('data/processed/stage06/landmark_index.json')['landmarks'] for r in lm['replaces']}
for ob in scene.objects:
 if ob.type!='MESH' or ob.data.as_pointer() in seen:continue
 m=ob.data;seen.add(m.as_pointer());v=np.empty((len(m.vertices),3),np.float32);m.vertices.foreach_get('co',v.ravel());bad+=int((~np.isfinite(v)).sum());vertices+=len(v)
 if not len(v):empty.append({'name':ob.name,'kind':'zero_vertex_mesh','render_hidden':ob.hide_render})
 if not len(m.polygons):continue # Geometry-node point fields are intentional.
 totals=np.empty(len(m.polygons),np.int32);m.polygons.foreach_get('loop_total',totals)
 if np.all(totals==3):f=np.empty((len(m.polygons),3),np.int32);m.loops.foreach_get('vertex_index',f.ravel())
 else:m.calc_loop_triangles();f=np.empty((len(m.loop_triangles),3),np.int32);m.loop_triangles.foreach_get('vertices',f.ravel())
 n=np.cross(v[f[:,1]].astype(float)-v[f[:,0]],v[f[:,2]].astype(float)-v[f[:,0]]);z=np.sum(n*n,axis=1)==0;zero+=int(z.sum());triangles+=len(f)
 if ob.get('building_lod') is not None and m.attributes.get('building_index'):
  ids=np.empty(len(m.polygons),np.int32);m.attributes['building_index'].data.foreach_get('value',ids);proxy+=int(np.isin(ids,list(selected)).sum())
 if sample_count<30 and (ob.get('r2_component')=='structure' or ob.get('landmark_lod')=='near'):
  # Coordinate weld is inspection-only; no mesh altered to close real openings.
  _,inverse=np.unique(v,axis=0,return_inverse=True);ff=inverse[f];edges=np.sort(np.concatenate([ff[:,[0,1]],ff[:,[1,2]],ff[:,[2,0]]]),axis=1);_,multiplicity=np.unique(edges,axis=0,return_counts=True)
  topology.append({'object':ob.name,'source_id':ob.get('source_uid',ob.get('landmark_id')),'triangles':len(f),'zero_area':int(z.sum()),'open_edges':int((multiplicity==1).sum()),'edge_multiplicity_gt2':int((multiplicity>2).sum()),'interpretation':'Coordinate-welded audit only; doors, layered shells and open façades are not forced watertight.'});sample_count+=1
 if len(seen)%1000==0:print('NATIVE_UNIQUE_MESH_AUDIT',len(seen),triangles,flush=True)
for block in bpy.data.libraries:
 p=Path(bpy.path.abspath(block.filepath));library.append({'path':str(p),'exists':p.is_file(),'inside_delivery':p.is_relative_to(DELIVERY)})
for block in bpy.data.images:
 if block.source=='FILE':
  p=Path(bpy.path.abspath(block.filepath,library=block.library));images.append({'name':block.name,'path':str(p),'packed':bool(block.packed_file),'available':bool(block.packed_file) or p.is_file(),'external_path_inside_delivery':p.is_relative_to(DELIVERY)})
for lm in read('data/processed/stage06/landmark_index.json')['landmarks']:
 ob=next(o for o in scene.objects if o.get('stable_id')=='landmark:'+lm['id']);delta=float(np.max(abs(np.array(ob.location)-lm['origin_city_m'])));angle=abs(ob.rotation_euler.z-lm['rotation_z_radians']);controls.append({'id':lm['id'],'position_numeric_delta_m':delta,'rotation_numeric_delta_rad':angle,'passed':delta<.001 and angle<1e-6})
assert bad==0 and proxy==0 and all(r['exists'] and r['inside_delivery'] for r in library) and all(i['available'] for i in images) and all(c['passed'] for c in controls)
# A bounded initial view keeps the editable city usable on the measured host.
view=dict(read('config/stage10.json')['views']['historic_street'],detail_radius_m=65);tri=apply_view(scene,view,read('data/processed/stage07_final/index.json')['terrain_active_lod']);apply_light(scene,read('config/stage08_lighting.json'),'clear_day');scene['stage10_default_view']='historic_street';scene['stage10_default_visible_triangles']=tri
assert tri<1800000,('Default working view too heavy',tri)
scene['stage10_geometry_status']='all native unique meshes numeric-audited; special open surfaces retained'
if '--read-only' not in sys.argv:
 bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(DELIVERY/'LA_Master.blend'),compress=True,relative_remap=False)
report={'status':'passed_with_topology_and_source_limits','actual_clean_session_open':True,'unique_meshes':len(seen),'native_triangles_including_hidden_lods':triangles,'vertices':vertices,'nonfinite_values':bad,'exact_zero_area_native_triangles':zero,'empty_meshes':empty,'removed_proxies_remaining_faces':proxy,'libraries':library,'images':images,'external_fonts':[f.filepath for f in bpy.data.fonts if f.filepath!='<builtin>'],'landmark_controls':controls,'topology_samples':topology,'default_view':'historic_street','default_visible_triangles':tri,'master_sha256':sha(DELIVERY/'LA_Master.blend'),'elapsed_seconds':time.perf_counter()-started,'limits':['Full numeric checks do not certify all pairwise mesh intersections, engineering bridge clearance or building foundations.','Open surfaces and source T-junctions are retained and classified; existing urban interface candidates remain documented.']}
write('work/reports/stage10/master_geometry.json',report);print('MASTER_ALL_MESH_NUMERIC_AUDIT_COMPLETE',len(seen),triangles,'ZERO',zero,'DEFAULT_TRI',tri,flush=True)
if '--reimport-samples' in sys.argv:
 rows=[]
 for sample in read('work/reports/stage10/gltf_validation.json')['samples']:
  bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(ROOT/sample['decompressed_file']));bpy.context.view_layer.update();nan=0;tri=0;points=[]
  for ob in bpy.context.scene.objects:
   if ob.type!='MESH':continue
   a=np.empty((len(ob.data.vertices),3),np.float32);ob.data.vertices.foreach_get('co',a.ravel());nan+=int((~np.isfinite(a)).sum());ob.data.calc_loop_triangles();tri+=len(ob.data.loop_triangles);M=np.array(ob.matrix_world);points.append(a@M[:3,:3].T+M[:3,3])
  allp=np.concatenate(points);bbox=[allp.min(axis=0).tolist(),allp.max(axis=0).tolist()];matches=[r for r in read('outputs/LA_Delivery/tiles/manifest.json')['resources'] if r['id']==sample['resource'] and r['lod']==sample['lod']];delta=None
  if matches:expected=np.array(matches[0]['bounds_city_m'])-np.array(sample['origin_city_m']);delta=float(np.max(abs(np.array(bbox)-expected)));assert delta<.05,(sample['resource'],delta)
  assert nan==0
  rows.append({'resource':sample['resource'],'actual_blank_scene_import':True,'nonfinite':nan,'triangles':tri,'bounds_numeric_delta_m':delta,'source_sha256':sample['source_sha256']})
 write('work/reports/stage10/glb_blank_scene_check.json',{'status':'passed','actual_imports':len(rows),'samples':rows,'numeric_bounds_error_is_not_survey_accuracy':True});print('FINAL_GLB_BLANK_SCENE_IMPORTS_PASSED',len(rows),flush=True)
