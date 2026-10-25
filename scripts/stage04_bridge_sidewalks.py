"""A separately mapped sidewalk bridge follows its parallel same-layer vehicle deck."""
from pathlib import Path
import json,math,collections
import numpy as np
import shapely
from shapely.strtree import STRtree
from stage04_build import Builder
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def align(root=ROOT):
 b=Builder(root);idxpath=root/'data/processed/stage04/mesh_index.json';idx=json.loads(idxpath.read_text());qa=json.loads((root/'work/reports/stage04/actual_mesh_crossings.json').read_text());byid={r['id']:i for i,r in enumerate(b.roads)};target={byid[x['id']] for x in qa['bridges'] if x['status']=='deck_top_burial_warning' and b.roads[byid[x['id']]]['tags'].get('footway')=='sidewalk'};veh=[i for i,r in enumerate(b.roads) if r['parameters']['bridge'] and not r['parameters']['tunnel'] and r['parameters']['class'] not in ['pedestrian','cycleway']];tree=STRtree([b.gs[i] for i in veh]);relations={};records=[]
 for i in target:
  g=b.gs[i];s=g.length/2;u=np.array(g.interpolate(min(g.length,s+2)).coords[0])-np.array(g.interpolate(max(0,s-2)).coords[0]);u/=np.linalg.norm(u);candidates=[]
  for j in tree.query(g,predicate='dwithin',distance=15):
   vi=veh[int(j)]
   if b.roads[vi]['parameters']['vertical_rank']!=b.roads[i]['parameters']['vertical_rank']:continue
   vg=b.gs[vi];ss=vg.project(g.interpolate(s));vv=np.array(vg.interpolate(min(vg.length,ss+2)).coords[0])-np.array(vg.interpolate(max(0,ss-2)).coords[0]);length=np.linalg.norm(vv)
   if length and abs(float(np.dot(vv/length,u)))>.7:candidates.append(vi)
  if candidates:relations[i]=set(candidates)
 for i,candidates in relations.items():
  rt=[]
  for m in idx['meshes']:
   if m['role']!='bridge_road':continue
   with np.load(root/m['file']) as a:keep=(a['m']==0)&np.isin(a['fid'],list(candidates));t=a['v'][a['f'][keep]].astype(float)
   if len(t):t[:,:,:2]+=m['origin_m'][:2];rt.append(t)
  if not rt:continue
  rt=np.concatenate(rt);polys=shapely.polygons(rt[:,:,:2]);st=STRtree(polys);moved=0;maxmove=0
  for m in idx['meshes']:
   if m['role']!='bridge_road':continue
   with np.load(root/m['file']) as a:d={k:a[k] for k in a.files}
   face=d['fid']==i
   if not face.any():continue
   ids=np.unique(d['f'][face].ravel());xy=d['v'][ids,:2].astype(float)+m['origin_m'][:2];pts=shapely.points(xy);near=st.nearest(pts);dist=shapely.distance(pts,polys[near]);t=rt[near];ab=t[:,1,:2]-t[:,0,:2];ac=t[:,2,:2]-t[:,0,:2];aq=xy-t[:,0,:2];den=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0];valid=(abs(den)>1e-10)&(dist<=15);den=np.where(valid,den,1);u=np.maximum(0,(aq[:,0]*ac[:,1]-aq[:,1]*ac[:,0])/den);w=np.maximum(0,(ab[:,0]*aq[:,1]-ab[:,1]*aq[:,0])/den);total=np.maximum(1,u+w);u/=total;w/=total;desired=t[:,0,2]+u*(t[:,1,2]-t[:,0,2])+w*(t[:,2,2]-t[:,0,2])+.15;before=b.profile_z(i,xy)-.015*shapely.distance(pts,b.gs[i]);delta=np.where(valid,desired-before,0);d['v'][ids,2]+=delta.astype(np.float32);np.savez_compressed(root/m['file'],**d);m['sha256']=digest(root/m['file']);moved+=len(ids);maxmove=max(maxmove,float(abs(delta).max()))
  records.append({'sidewalk':b.roads[i]['id'],'vehicle_decks':[b.roads[j]['id'] for j in sorted(candidates)],'vertices_aligned':moved,'maximum_height_adjustment_m':maxmove,'crossfall_and_offset_status':'inferred15cm sidewalk rise above same-layer parallel vehicle deck; presence/XY fromOSM'})
 write_json(idxpath,idx);write_json(root/'work/reports/stage04/bridge_sidewalks.json',{'status':'executed','relations':records,'raw_geography_unchanged':True});print('BRIDGE_SIDEWALKS_ALIGNED',len(records),flush=True)
if __name__=='__main__':align()
