"""Single near-street pavement, oriented curb surfaces and unblocked source ramp cuts.

Source XY is retained. Elevations are a labelled street-constrained visual model,
not an as-built or accessibility compliance survey.
"""
import json
import numpy as np,shapely
from shapely import affinity
from shapely.geometry import shape,box,LineString
from shapely.ops import transform
from pyproj import Transformer
from stage07_final_data import Grade,OUT,save,read,Mesh,polys,ROOT
from stage04_clearance import clip_arrays
from stage02_io import write_json,digest

def source_arrays(rec):
 with np.load(ROOT/rec['file']) as a:return {k:a[k].copy() for k in a.files}

def triangle_plan_area(v,f):
 ab=v[f[:,1],:2]-v[f[:,0],:2];ac=v[f[:,2],:2]-v[f[:,0],:2]
 return np.abs(ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0]).sum()/2

def run():
 grade=Grade();cfg=read('config/stage07_final.json');tx=Transformer.from_crs(4326,32611,always_xy=True);features=read('data/processed/stage04/downtown_surface_masks.geojson')['features'];index=read('data/processed/stage04/mesh_index.json');excluded=set(cfg['skybridge']['replaces'])
 def mask(name):
  source=next(f for f in features if f['properties']['id']==name);g=transform(tx.transform,shape(source['geometry']));g=affinity.translate(g,-grade.origin[0],-grade.origin[1]);return shapely.union_all(polys(shapely.make_valid(g)))
 sidewalk=mask('sidewalk');asphalt=mask('asphalt');bs=read('data/processed/stage07/buildings.json');plans=shapely.union_all([shape(b['geometry']) for b in bs if b['i'] not in excluded]);bridge_plans=shapely.union_all([shape(b['geometry']) for b in bs if b['i'] in excluded]);scopes=shapely.union_all([r.buffer(35,join_style=2) for r in grade.regions]);ramp_tris=[];ramp_sources=[]
 for rec in index['meshes']:
  if rec['role']!='curb_ramp':continue
  o=np.array(rec['origin_m']);bbox=box(o[0],o[1],o[0]+1000,o[1]+1000)
  if not bbox.intersects(scopes):continue
  ar=source_arrays(rec);v=ar['v'].astype(float)+o;tris=shapely.polygons(v[ar['f'],:2]);hit=shapely.intersects(tris,scopes)
  if hit.any():ramp_tris.extend(tris[hit]);ramp_sources.append(rec['file'])
 ramps=shapely.union_all(ramp_tris) if ramp_tris else shapely.GeometryCollection()
 # A0.1mm precision model joins serialization cracks only; source ramp XY is untouched.
 ramps=shapely.make_valid(shapely.set_precision(ramps,.0001)) if not ramps.is_empty else ramps
 ramp_parts=polys(ramps);ramp_tree=shapely.STRtree(ramp_parts) if ramp_parts else None;ramp_max=[]
 for p in ramp_parts:
  xy=shapely.get_coordinates(p);ramp_max.append(max(float(shapely.distance(shapely.points(xy),asphalt).max()),.05))
 records=[];checks=[];global_new=[]
 for region in ['historic_core','civic_center']:
  scope=grade.refs[region].buffer(35,join_style=2);cut=shapely.make_valid(sidewalk.intersection(scope).difference(plans.buffer(.03)).difference(ramps));mesh=Mesh();curb=Mesh();area=0
  for original in polys(cut):
   if original.area<.05:continue
   p=shapely.orient_polygons(shapely.segmentize(original,4));area+=p.area
   for tri in shapely.constrained_delaunay_triangles(p).geoms:
    xy=np.array(tri.exterior.coords)[:3];cross=(xy[1,0]-xy[0,0])*(xy[2,1]-xy[0,1])-(xy[1,1]-xy[0,1])*(xy[2,0]-xy[0,0]);xy=xy if cross>0 else xy[::-1];z=grade(xy[:,0],xy[:,1])+.15;mesh.face(np.column_stack([xy,z]),'paving')
   for ring in [p.exterior,*p.interiors]:
    xy=np.array(ring.coords)
    for a,b in zip(xy[:-1],xy[1:]):
     edge=LineString([a,b])
     if edge.distance(scope.boundary)<.02 or edge.distance(plans)<.07 or (not ramps.is_empty and edge.distance(ramps)<.10):continue
     z=grade(np.array([a[0],b[0]]),np.array([a[1],b[1]]));curb.quad([[*a,z[0]],[*b,z[1]],[*b,z[1]+.15],[*a,z[0]+.15]],'concrete')
  origin=np.array([*grade.refs[region].centroid.coords[0],0]);items=[];row={'region':region,'cut_polygon_area_m2':area}
  for name,m in [('paving',mesh),('curb',curb)]:
   ar,removed=m.arrays();ar['v']-=origin.astype(np.float32);corrected=0
   if name=='paving':
    vv=ar['v'];ff=ar['f'];normal=np.cross(vv[ff[:,1]]-vv[ff[:,0]],vv[ff[:,2]]-vv[ff[:,0]]);good=np.abs(normal[:,2])>1e-7;removed+=int((~good).sum());ar['f']=ff[good];ar['m']=ar['m'][good];negative=normal[good,2]<0;corrected=int(negative.sum());ar['f'][negative]=ar['f'][negative][:,[0,2,1]]
   file=save(OUT+'public_surface/'+region+'_'+name+'.npz',ar);items.append({'name':name,'file':file,'triangles':len(ar['f']),'removed_float32_degenerate_faces':removed,'float32_projected_winding_corrected_faces':corrected});world=ar['v'].astype(float)+origin;f=ar['f'];cross=np.cross(world[f[:,1]]-world[f[:,0]],world[f[:,2]]-world[f[:,0]])
   if name=='paving':
    tris=shapely.polygons(world[f,:2]);global_new.extend(tris);ramp_overlap=float(shapely.area(shapely.intersection(tris,ramps)).sum()) if not ramps.is_empty else 0.;down=int((cross[:,2]<=0).sum());plan_area=float(triangle_plan_area(world,f));row.update(paving_triangles=len(f),paving_downward_or_vertical_faces=down,new_paving_ramp_overlap_m2=ramp_overlap,paving_triangle_plan_area_m2=plan_area,paving_area_numeric_difference_m2=plan_area-area);assert down==0 and ramp_overlap<.02 and abs(plan_area-area)<.1,row
   else:
    normal=cross[:,:2]/np.maximum(np.linalg.norm(cross[:,:2],axis=1)[:,None],1e-12);centres=world[f].mean(axis=1)[:,:2]
    # Probe locally: a 3cm probe can cross a narrow exterior gap and enter a
    # separate sidewalk polygon. A 2mm probe resolves the oriented boundary
    # while remaining above float32 coordinate roundoff (under 0.1mm here).
    inside=shapely.covers(cut,shapely.points(centres+normal*.002));wide_inside=shapely.covers(cut,shapely.points(centres+normal*.03));row.update(curb_triangles=len(f),curb_normals_pointing_into_pavement=int(inside.sum()),curb_normal_local_probe_m=.002,wide_probe_adjacent_paving_reentries=int((wide_inside&~inside).sum()));assert not inside.any(),row
    if not ramps.is_empty:
     distance=shapely.distance(shapely.points(centres),ramps);row['minimum_curb_centroid_distance_from_ramp_m']=float(distance.min()) if len(distance) else None;assert not len(distance) or distance.min()>.09,row
  checks.append(row);records.append({'region':region,'scope':shapely.geometry.mapping(scope),'origin_city_m':origin.tolist(),'source_sidewalk_plan_area_m2':area,'meshes':items,'xy_source':'stage04 unioned inferred sidewalk buffers, source ramp cutouts and grounded-building exclusions; no new survey assertion','z_basis':'same street-constrained inferred grade as adjacent terrain and ordinary roads','curb_height_m':.15,'elevated_bridge_does_not_cut_ground_pavement':True})
 road_updates=[];old_overlap=0.;ramp_profiles=[];source_hashes={}
 for rec in index['meshes']:
  if rec['role'] not in ['downtown_road','downtown_sidewalk','downtown_curb','curb_ramp','markings','downtown_paths','refuge_island']:continue
  o=np.array(rec['origin_m']);bbox=box(o[0],o[1],o[0]+1000,o[1]+1000)
  if not bbox.intersects(scopes):continue
  ar=source_arrays(rec);v=ar['v'].astype(float)+o;inside=shapely.covers(scopes,shapely.points(v[:,:2]));footprints=shapely.convex_hull(shapely.polygons(v[ar['f'],:2]));touch=shapely.intersects(footprints,scopes)
  if not inside.any() and not touch.any():continue
  source_hashes[rec['file']]=digest(ROOT/rec['file']);removed=0
  if rec['role']=='downtown_sidewalk':
   result=clip_arrays(ar['v'],ar['f'],ar['m'],ar['fid'],scopes,o[:2]);ar=result if result is not None else ar;vv=ar['v'];ff=ar['f'];cross=np.cross(vv[ff[:,1]]-vv[ff[:,0]],vv[ff[:,2]]-vv[ff[:,0]]);negative=cross[:,2]<0;ar['f'][negative]=ar['f'][negative][:,[0,2,1]];removed=int(touch.sum())
   retained=ar['v'].astype(float)+o;tt=shapely.polygons(retained[ar['f'],:2]);overlap=float(shapely.area(shapely.intersection(tt,scopes)).sum());old_overlap+=overlap;assert overlap<.02,(rec['id'],overlap)
  elif rec['role']=='downtown_curb':
   # Omit touched legacy vertical strips only at the outer35m transition margin.
   keep=~touch;removed=int(touch.sum());ar['f']=ar['f'][keep]
   for key in ['m','fid']:ar[key]=ar[key][keep]
  else:
   ids=np.flatnonzero(inside)
   if not len(ids):continue
   offset=np.full(len(ids),.025 if rec['role']=='markings' else .15 if rec['role'] in ['downtown_paths','refuge_island'] else 0.)
   if rec['role']=='curb_ramp' and ramp_tree is not None:
    xy=v[ids,:2];nearest=ramp_tree.nearest(shapely.points(xy));distance=shapely.distance(shapely.points(xy),asphalt);offset=.15*np.clip(distance/np.array(ramp_max)[nearest],0,1);ramp_profiles.append({'object':rec['id'],'vertices_regraded':len(ids),'minimum_above_street_grade_m':float(offset.min()),'maximum_above_street_grade_m':float(offset.max()),'profile':'0..0.15m normalized source-footprint distance from asphalt; ramp flare/as-built compliance not certified'})
   v[ids,2]=grade(v[ids,0],v[ids,1])+offset;ar['v']=(v-o).astype(np.float32)
  file=save(OUT+'roads/'+rec['id']+'.npz',ar);road_updates.append({'object':rec['id'],'file':file,'source_file':rec['file'],'role':rec['role'],'origin_city_m':rec['origin_m'],'source_xy_plan_preserved_outside_exact_cut':True,'removed_or_clipped_old_surface_faces':removed})
 restored=sidewalk.intersection(bridge_plans).difference(plans.buffer(.03)).intersection(scopes);new_union=shapely.union_all(global_new);restored_area=float(new_union.intersection(restored).area);lost_area=float(restored.difference(new_union.union(ramps)).area);assert lost_area<.05,(restored_area,lost_area)
 report={'status':'passed_geometry_generation_checks','regions':checks,'old_sidewalk_retained_inside_replacement_scope_m2':old_overlap,'ramp_mask_polygon_components':len(ramp_parts),'source_ramp_meshes':ramp_sources,'ramp_profiles':ramp_profiles,'new_paving_excludes_ramps':True,'curb_omits_ramp_openings':True,'skybridge_source_indices_excluded_from_ground_mask':sorted(excluded),'sidewalk_restored_below_skybridge_m2':restored_area,'unrestored_bridge_sidewalk_m2':lost_area,'parameters':{'curb_height_m':.15,'curb_ramp_clearance_m':.10,'ramp_mask_precision_m':.0001,'scope_buffer_m':35,'building_mask_buffer_m':.03,'paving_boundary_segment_max_m':4},'source_mesh_hashes_after_read':source_hashes,'raw_and_previous_stages_modified':False,'limitations':['Street grade and sidewalk widths remain inferred source design, not engineering survey','Original ramp footprint geometry retained with normalized visual slope; no accessibility certification','Touched legacy vertical curbs omitted at outer35m scope boundary; no removal in the accepted work windows','Saved Blender scene and actual visual inspection still required']}
 write_json(ROOT/(OUT+'public_surface.json'),{'regions':records,'road_updates':road_updates,'paving_is_single_surface_not_overlapping_old_sidewalk':True,'source_ramp_cuts_preserved':True,'generation_check':'work/reports/stage07_final/ground_generation_check.json'});write_json(ROOT/'work/reports/stage07_final/ground_generation_check.json',report);print('PUBLIC_SURFACES_GENERATED',[(r['region'],round(r['source_sidewalk_plan_area_m2'])) for r in records],'ROAD_UPDATES',len(road_updates),'OLD_OVERLAP_M2',old_overlap,'BRIDGE_SIDEWALK_RESTORED_M2',restored_area,flush=True)
if __name__=='__main__':run()
