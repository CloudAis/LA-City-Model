"""Resolve projection interpolation error in priority decks; retain real layer overlaps."""
from pathlib import Path
import json,math
import numpy as np
import shapely
from shapely.geometry import Point
from stage04_build import Builder
from stage04_geometry import Meshes
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def refine(root=ROOT,source_ids=None):
 b=Builder(root);ip=root/'data/processed/stage04/mesh_index.json';idx=json.loads(ip.read_text());report=json.loads((root/'work/reports/stage04/actual_mesh_crossings.json').read_text());byid={r['id']:i for i,r in enumerate(b.roads)};missing={byid[c[k]] for c in report['crossings'] if c['status']=='mesh_sample_missing' for k,z in [('source_a','mesh_z_a_m'),('source_b','mesh_z_b_m')] if c[z] is None};priority={byid[c[k]] for c in report['crossings'] for k in ['source_a','source_b']};patch=Meshes(root,b.ground)
 if source_ids is not None:priority={byid[k] for k in source_ids};missing=set()
 floor=json.loads((root/'data/processed/stage04/road_floor_index.json').read_text());masks=[]
 for m in floor['meshes']:
  with np.load(root/m['file']) as a:t=a['v'][a['f']].astype(float);t[:,:,:2]+=m['origin_m'][:2];masks.extend(shapely.polygons(t[:,:,:2]))
 mask=shapely.unary_union(masks)
 for i in missing:
  r=b.roads[i];poly=b.gs[i].buffer(r['parameters']['width_m']/2,cap_style=2,quad_segs=2).intersection(mask)
  patch.polygon(poly,'profiled_priority_road',lambda xy,i=i:b.profile_z(i,xy)-.015*shapely.distance(shapely.points(xy),b.gs[i]),'asphalt',i,max_segment=2,extrude=.65)
 if missing:
  new=patch.save('restored_layered_surface');idx['meshes'].extend(new)
  # Above-grade restored surfaces are deliberately not added to the ground-floor fallback.
 changed=0;added=0
 def field(i,xy):return b.profile_z(i,xy)-.015*shapely.distance(shapely.points(xy),b.gs[i])
 def split(i,t,depth):
  probes=np.array([(t[0]+t[1])/2,(t[1]+t[2])/2,(t[2]+t[0])/2,t.mean(axis=0)]);want=field(i,probes[:,:2]);error=float(abs(probes[:,2]-want).max())
  if error<=.035 or depth==5:return [t]
  aa,bb,cc=probes[:3].copy();aa[2]=want[0];bb[2]=want[1];cc[2]=want[2]
  children=[np.array([t[0],aa,cc]),np.array([aa,t[1],bb]),np.array([cc,bb,t[2]]),np.array([aa,bb,cc])]
  return [q for child in children for q in split(i,child,depth+1)]
 for m in idx['meshes']:
  if m['role'] not in ['bridge_road','tunnel_road','profiled_priority_road']:continue
  with np.load(root/m['file']) as a:d={k:a[k] for k in a.files}
  selected=(d['m']==0)&np.isin(d['fid'],list(priority));f=d['f'];world=d['v'][f[selected]].astype(float);world[:,:,:2]+=m['origin_m'][:2];ids=d['fid'][selected];verts=[];owners=[]
  for t,i in zip(world,ids):
   # Source vertices already sample the same field; refine only faces whose interior misses it.
   for tri in split(int(i),t,0):verts.append(tri);owners.append(int(i))
  if not verts:continue
  triangles=np.array(verts);newv=triangles.reshape(-1,3);newv[:,:2]-=m['origin_m'][:2];newv=newv.astype(np.float32);newf=np.arange(len(newv),dtype=np.int32).reshape(-1,3);base=len(d['v']);oldtop=int(selected.sum());keep=~selected
  # Closed bridge undersides follow the refined top rather than spanning the original coarse faces.
  if m['role']=='bridge_road':keep&=~((d['m']==5)&np.isin(d['fid'],list(priority))&(abs(np.cross(d['v'][f[:,1]]-d['v'][f[:,0]],d['v'][f[:,2]]-d['v'][f[:,0]])[:,2])>1e-8))
  vv=[d['v'],newv];ff=[f[keep],newf+base];mm=[d['m'][keep],np.zeros(len(newf),np.uint8)];ii=[d['fid'][keep],np.array(owners,np.int32)]
  if m['role']=='bridge_road':bottom=newv.copy();bottom[:,2]-=.65;vv.append(bottom);ff.append(newf[:,::-1]+base+len(newv));mm.append(np.full(len(newf),5,np.uint8));ii.append(np.array(owners,np.int32))
  d={'v':np.concatenate(vv),'f':np.concatenate(ff),'m':np.concatenate(mm),'fid':np.concatenate(ii)};np.savez_compressed(root/m['file'],**d);m['vertices']=len(d['v']);m['triangles']=len(d['f']);m['sha256']=digest(root/m['file']);changed+=1;added+=len(newf)-oldtop
 for m in idx['meshes']:
  if m['role']=='markings':
   with np.load(root/m['file']) as aa:affected=np.isin(aa['fid'],list(priority)).any()
   if affected:m['paint_draped_to_actual_pavement']=False
 write_json(ip,idx);write_json(root/'work/reports/stage04/deck_sampling.json',{'status':'executed','priority_road_features':len(priority),'restored_layers':[b.roads[i]['id'] for i in missing],'changed_meshes':changed,'additional_top_triangles':added,'adaptive_interior_height_error_target_m':.035,'maximum_subdivision_depth':5,'source_XY_graph_and_profiles_unchanged':True});print('ADAPTIVE_DECK_SURFACE_SAMPLING',changed,added,'restored',len(missing),flush=True)
if __name__=='__main__':refine()
