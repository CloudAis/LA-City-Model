"""Observed crossing-island presence; inferred editable refuge dimensions and planting."""
from pathlib import Path
import json,math
import numpy as np
from pyproj import Transformer
from shapely.geometry import Point,LineString
from stage04_geometry import Ground,Meshes
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def build(root=ROOT):
 ground=Ground(root);mesh=Meshes(root,ground);roads=json.loads((root/'data/processed/stage04/roads.json').read_text());a=np.load(root/'data/processed/stage04/road_profiles.npz');v=a['v'];tx=Transformer.from_crs(4326,32611,always_xy=True);nodes={}
 for row in (root/'data/processed/stage04/source_nodes.jsonl').open():
  n=json.loads(row);t=n['tags']
  if t.get('crossing:island')!='yes' and t.get('traffic_calming')!='island':continue
  x,y=tx.transform(n['lon'],n['lat']);xy=np.array([x,y])-ground.origin
  if ground.refs['downtown'].covers(Point(xy)):nodes[n['id']]={'node':n,'xy':xy}
 lookup={}
 for i,r in enumerate(roads):
  p=r['parameters']
  if p['class'] not in ['primary','secondary','tertiary','residential'] or p['oneway'] not in ['no','false'] or p['bridge'] or p['tunnel']:continue
  for node in set(r['node_ids'])&nodes.keys():lookup[node]=i
 records=[]
 for node,d in nodes.items():
  if node not in lookup:continue
  i=lookup[node];r=roads[i];k=r['profile_start'];n=r['profile_count'];g=LineString(v[k:k+n,:2]);q=Point(d['xy']);s=g.project(q);lo=max(0,s-1);hi=min(g.length,s+1);tangent=np.array(g.interpolate(hi).coords[0])-np.array(g.interpolate(lo).coords[0]);tangent/=np.linalg.norm(tangent);fid=-(len(records)+2)
  for sign in [-1,1]:
   aa=d['xy']+tangent*sign*2.4;bb=d['xy']+tangent*sign*4.2;poly=LineString([aa,bb]).buffer(.9,cap_style=1,quad_segs=3)
   mesh.polygon(poly,'refuge_island',lambda xy:ground(xy[:,0],xy[:,1])+.22,'curb',fid,max_segment=.8,extrude=.15)
  records.append({'feature_index':fid,'source_node_id':node,'source_way_id':r['id'],'xy_m':d['xy'].tolist(),'source_tags':d['node']['tags'],'presence':'observed_OSM_crossing_island_tag','footprint':'inferred1.8m wide refuge noses,3m accessible crossing gap; not measured outline','planting':'not inferred from island tag; no unsupported vegetation assigned','data_class':'observed_presence_inferred_geometry','confidence':'presence_medium_geometry_low'})
 new=mesh.save('islands');p=root/'data/processed/stage04/mesh_index.json';old=json.loads(p.read_text());old['meshes']=[m for m in old['meshes'] if m['role']!='refuge_island']+new;old['supplemental_refuge_inventory']='data/processed/stage04/refuge_islands.json';write_json(p,old);write_json(root/'data/processed/stage04/refuge_islands.json',records);print('OBSERVED_ISLAND_PRESENCE_MODELED',len(records),'inferred dimensions',flush=True)
if __name__=='__main__':build()
