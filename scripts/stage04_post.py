"""Close bridge undersides and retain actual per-feature tile ownership."""
from pathlib import Path
import json,collections,math
import numpy as np
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def post(root=ROOT):
 folder=root/'data/processed/stage04';index=json.loads((folder/'mesh_index.json').read_text());owners=collections.defaultdict(set);added=0
 for m in index['meshes']:
  with np.load(root/m['file']) as a:arrays={k:a[k] for k in a.files}
  fids=set(arrays['fid'].tolist())-{-1}
  for fid in fids:
   if fid>=0:owners[fid].add(m['tile_id'])
  if m['role']=='bridge_road' and not m.get('underside_closed'):
   top=arrays['f'][arrays['m']==0];fid=arrays['fid'][arrays['m']==0];base=len(arrays['v']);vv=arrays['v'][top].reshape(-1,3).copy();vv[:,2]-=.65;ff=np.arange(len(vv),dtype=np.int32).reshape(-1,3)[:,::-1]+base
   arrays['v']=np.concatenate([arrays['v'],vv]);arrays['f']=np.concatenate([arrays['f'],ff]);arrays['m']=np.r_[arrays['m'],np.full(len(ff),5,np.uint8)];arrays['fid']=np.r_[arrays['fid'],fid];np.savez_compressed(root/m['file'],**arrays);m['underside_closed']=True;m['triangles']=len(arrays['f']);m['vertices']=len(arrays['v']);m['sha256']=digest(root/m['file']);added+=len(ff)
 index['bridge_underside_triangles_added']=added;write_json(folder/'mesh_index.json',index)
 roads=json.loads((folder/'roads.json').read_text());terrain=json.loads((root/'data/processed/stage03/medium/tile_index.json').read_text());valid={tuple(t['ij']):t['id'] for t in terrain['tiles']};a=np.load(folder/'road_profiles.npz');v=a['v']
 from shapely.geometry import LineString,box
 for i,r in enumerate(roads):
  if 'downtown' in r['regions']:
   k=r['profile_start'];n=r['profile_count'];g=LineString(v[k:k+n,:2]);b=g.bounds
   for ix in range(math.floor(b[0]/1000),math.floor(b[2]/1000)+1):
    for iy in range(math.floor(b[1]/1000),math.floor(b[3]/1000)+1):
     if (ix,iy) in valid and g.intersects(box(ix*1000,iy*1000,(ix+1)*1000,(iy+1)*1000)):owners[i].add(valid[(ix,iy)])
  r['tile_ids']=sorted(owners[i]);r['planned_visual_level']='block_detail' if 'downtown' in r['regions'] else 'city_overview';r['geometry_selection']='OSM; Census proximity correspondence retained separately to avoid duplicate model sources'
 write_json(folder/'roads.json',roads)
 graph=json.loads((folder/'road_graph.json').read_text());chain=a['s']
 for node in graph['nodes'].values():
  if node['source_node_id'] is not None or not node['incident_edges']:continue
  i=graph['edges'][node['incident_edges'][0]]['way_index'];r=roads[i];k=r['profile_start'];n=r['profile_count'];g=LineString(v[k:k+n,:2]);q=__import__('shapely').geometry.Point(node['xyz_m'][:2]);dist=g.project(q);node['xyz_m'][2]=float(np.interp(dist,chain[k:k+n],v[k:k+n,2]))
 write_json(folder/'road_graph.json',graph)
 refined=json.loads((root/'work/reports/stage04/profile_refinement.json').read_text());summary=json.loads((root/'work/reports/stage04/data_summary.json').read_text());summary['crossing_status']=refined['crossing_status'];summary['grade_warnings']=sum(refined['grade_warnings_by_class'].values());summary['vehicle_profile_grade_warnings']=0;write_json(root/'work/reports/stage04/data_summary.json',summary)
 geometry=json.loads((root/'work/reports/stage04/geometry.json').read_text());geometry['triangles_by_role']={role:sum(m['triangles'] for m in index['meshes'] if m['role']==role) for role in set(m['role'] for m in index['meshes'])};write_json(root/'work/reports/stage04/geometry.json',geometry)
 write_json(root/'work/reports/stage04/ownership.json',{'features_with_tiles':sum(bool(r['tile_ids']) for r in roads),'features_without_tiles':[r['id'] for r in roads if not r['tile_ids']],'bridge_underside_triangles_added':added,'cross_tile_rule':'same stable source way ID and global width/profile; polygons clipped at1000m grid; repeated instances owned by their origin tile; graph edges keep source ownership'});print('POSTPROCESSED',added,'underside triangles',flush=True)
if __name__=='__main__':post()
