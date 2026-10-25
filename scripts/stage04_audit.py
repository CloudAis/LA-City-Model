"""Source matching, graph/grade diagnostics and actual tile mesh continuity."""
from pathlib import Path
import json,collections,math
import numpy as np
import shapely
from shapely.geometry import LineString,Point,shape
from shapely.strtree import STRtree
from pyproj import Transformer
from stage03_common import references,local_features,to_geographic
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def audit(root=ROOT):
 folder=root/'data/processed/stage04';roads=json.loads((folder/'roads.json').read_text());a=np.load(folder/'road_profiles.npz');v=a['v'];s=a['s'];_,origin,city,refs=references(root)
 gs=[LineString(v[r['profile_start']:r['profile_start']+r['profile_count'],:2]) for r in roads];tree=STRtree(gs)
 # Compare an independent older source. Proximity is correspondence evidence, never ground-truth survey accuracy.
 census=local_features(root,'data/processed/stage02/roads.geojson');pts=shapely.points(np.array([g.interpolate(.5,normalized=True).coords[0] for _,g in census]));near=tree.nearest(pts);distance=shapely.distance(pts,np.array(gs,dtype=object)[near]);match=[];gaps=[]
 for (f,g),i,d in zip(census,near,distance):
  match.append({'census_id':f['properties'].get('id'),'osm_id':roads[int(i)]['id'],'midpoint_separation_m':float(d),'relationship':'candidate_nearest_geometry_not_automatic_building_or_road_equivalence','same_name':str(f['properties'].get('name','')).lower()==str(roads[int(i)]['name']).lower()})
  if d>40:gaps.append({'type':'Feature','properties':{'id':f['properties'].get('id'),'gap_type':'Census_midpoint_over40m_from_any_OSM_transport_way','separation_m':float(d)},'geometry':to_geographic(g,origin)})
 write_json(folder/'census_osm_correspondence.json',match);write_json(folder/'transport_gaps.geojson',{'type':'FeatureCollection','features':gaps})
 # Original source coordinate samples include every native vertex of100 deterministically selected ways.
 rng=np.random.default_rng(20261021);ids=set(int(x) for x in rng.choice(len(roads),min(100,len(roads)),replace=False));selected={roads[i]['source_id']:i for i in ids};tx=Transformer.from_crs(4326,32611,always_xy=True);sample=[]
 for row in (folder/'source_ways.jsonl').open():
  w=json.loads(row);i=selected.get(w['id'])
  if i is None:continue
  xy=np.array(w['lonlat']);x,y=tx.transform(xy[:,0],xy[:,1]);xy=np.column_stack([x-origin[0],y-origin[1]]);err=shapely.distance(shapely.points(xy),gs[i]);sample.append({'id':roads[i]['id'],'native_vertices':len(xy),'maximum_centerline_projection_error_m':float(err.max())})
 assert len(sample)==len(ids) and max(x['maximum_centerline_projection_error_m'] for x in sample)<.005
 # Mesh tile interfaces: compare actual independently quantized coordinates/height pairs.
 index=json.loads((folder/'mesh_index.json').read_text());seams=collections.defaultdict(list);nonfinite=0;degen=0;roles=collections.Counter();grade_faces=collections.Counter()
 for m in index['meshes']:
  with np.load(root/m['file']) as d:vv=d['v'];ff=d['f'];fid=d['fid'];mat=d['m']
  nonfinite+=int((~np.isfinite(vv)).sum());cross=np.cross(vv[ff[:,1]]-vv[ff[:,0]],vv[ff[:,2]]-vv[ff[:,0]]);degen+=int((np.linalg.norm(cross,axis=1)<1e-8).sum());roles[m['role']]+=len(ff)
  # Retain surface slope warnings in the actual baked mesh; walls are excluded by asphalt material.
  asphalt=(mat==0)&(abs(cross[:,2])>1e-6);slope=np.linalg.norm(cross[:,:2],axis=1)/np.maximum(abs(cross[:,2]),1e-12);grade_faces[m['role']]+=int((asphalt&(slope>.3)).sum())
  if m['role'] not in ['full_far','overview_far','bridge_road','tunnel_road','rail_corridor','airport_surface','profiled_priority_road']:continue
  originxy=np.array(m['origin_m'][:2]);coords=vv[ff];globalxy=coords[:,:,:2]+originxy
  for axis in [0,1]:
   for boundary in [0,1000]:
    for aa,bb in [(0,1),(1,2),(2,0)]:
     keep=(mat!=5)&(abs(coords[:,aa,axis]-boundary)<1e-5)&(abs(coords[:,bb,axis]-boundary)<1e-5)&(np.linalg.norm(coords[:,aa,:2]-coords[:,bb,:2],axis=1)>.001)
     for j in np.flatnonzero(keep):
      p=globalxy[j,aa];q=globalxy[j,bb];ends=sorted([(tuple(np.round(p,3)),float(coords[j,aa,2])),(tuple(np.round(q,3)),float(coords[j,bb,2]))]);key=(m['role'],int(fid[j]),ends[0][0],ends[1][0]);seams[key].append((m['tile_id'],ends[0][1],ends[1][1]))
 pairs=0;maxdz=0;unpaired=[]
 for key,vals in seams.items():
  tiles=set(v[0] for v in vals)
  if len(tiles)>1:
   pairs+=1;maxdz=max(maxdz,max(v[1] for v in vals)-min(v[1] for v in vals),max(v[2] for v in vals)-min(v[2] for v in vals))
  else:
   # Administrative clipping and intentional Downtown detail boundary are not missing neighbors.
   p=np.array(key[2]);q=np.array(key[3]);mid=Point((p+q)/2)
   if city.buffer(-.02).covers(mid) and refs['downtown'].boundary.distance(mid)>.02:unpaired.append({'role':key[0],'feature_index':key[1],'a':list(key[2]),'b':list(key[3]),'tile':vals[0][0]})
 # A shared boundary may be split differently by constrained triangulation; test interval coverage.
 tmatched=0;remaining=[]
 for row in unpaired:
  aa=np.array(row['a']);bb=np.array(row['b']);axis=0 if abs(aa[0]-bb[0])<1e-6 else 1;along=1-axis;lo=min(aa[along],bb[along]);hi=max(aa[along],bb[along]);pieces=[]
  for key,vals in seams.items():
   if key[0]!=row['role'] or key[1]!=row['feature_index']:continue
   if abs(key[2][axis]-aa[axis])>.001 or abs(key[3][axis]-aa[axis])>.001:continue
   if not any(v[0]!=row['tile'] for v in vals):continue
   left=min(key[2][along],key[3][along]);right=max(key[2][along],key[3][along])
   if right>=lo-.001 and left<=hi+.001:pieces.append((left,right))
  covered=lo
  for left,right in sorted(pieces):
   if left>covered+.001:break
   covered=max(covered,right)
  if covered>=hi-.001:tmatched+=1
  else:remaining.append(row)
 unpaired=remaining
 write_json(root/'work/reports/stage04/tile_seams.json',{'matched_edge_segments':pairs,'verified_differently_split_boundary_segments':tmatched,'maximum_z_difference_m':maxdz,'unpaired_interior_segments':len(unpaired),'unpaired':unpaired[:1000],'tolerance_m':.001,'policy':'tile-local float32 with common world profile/ground rule; mixed terrain LOD boundaries inherited from validated Stage03','status':'passed' if maxdz<.001 and not unpaired else 'needs_review'})
 assert nonfinite==0 and degen==0
 refined=json.loads((root/'work/reports/stage04/profile_refinement.json').read_text());summary={'status':'passed_with_documented_gaps','roads':len(roads),'original_native_XY_samples':sample,'maximum_sample_XY_calculation_error_m':max(x['maximum_centerline_projection_error_m'] for x in sample),'source_accuracy_m':None,'census_comparison':{'features':len(census),'midpoint_separation_p50_p95_max_m':np.percentile(distance,[50,95,100]).tolist(),'within25m':int((distance<=25).sum()),'over40m':int((distance>40).sum()),'not_an_accuracy_assessment':True},'source_clearance_status':refined['crossing_status'],'vehicle_profile_grade_warnings':sum(refined['grade_warnings_by_class'].get(k,0) for k in ['motorway','trunk','ramp','primary','secondary','tertiary','residential','service','parking_aisle']),'actual_surface_triangles_over30pct_slope_by_role':dict(grade_faces),'mesh_nonfinite':nonfinite,'mesh_degenerate':degen,'triangles_by_role':dict(roles),'tile_seam_status':'passed' if maxdz<.001 and not unpaired else 'needs_review','unsupported_modeling':'actual deck/tunnel survey, turn restriction relations, current rail service validation and exact lane/curb/entrance installations unavailable'}
 write_json(root/'work/reports/stage04/audit.json',summary);print('AUDIT',json.dumps({k:v for k,v in summary.items() if k!='original_native_XY_samples'}),flush=True);return summary
if __name__=='__main__':audit()
