"""Local derived-terrain refinement to keep mapped deck tops visible; raw DTM retained."""
from pathlib import Path
import json,collections,math,shutil
import numpy as np
import shapely
from shapely.strtree import STRtree
from stage04_geometry import Ground
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def cut(root=ROOT):
 ip=root/'data/processed/stage04/mesh_index.json';idx=json.loads(ip.read_text());geo=json.loads((root/'work/reports/stage04/geometry.json').read_text());report=json.loads((root/'work/reports/stage04/actual_mesh_crossings.json').read_text());roads=json.loads((root/'data/processed/stage04/roads.json').read_text());lookup={r['id']:r['feature_index'] for r in roads};bad={lookup[b['id']] for b in report['bridges'] if b['minimum_estimated_underside_minus_display_terrain_m']<-.7};ground=Ground(root);rt=[]
 for m in idx['meshes']:
  if m['role']!='bridge_road':continue
  with np.load(root/m['file']) as a:
   keep=(a['m']==0)&np.isin(a['fid'],list(bad));t=a['v'][a['f'][keep]].astype(float)
  if len(t):t[:,:,:2]+=m['origin_m'][:2];rt.append(t)
 road=np.concatenate(rt);rp=shapely.polygons(road[:,:,:2]);tree=STRtree(rp);variant={m['tile_id']:m for m in geo['ground_variants']};archive=root/'work/history/stage04_before_deck_terrain';changes=[]
 def subdivide(t,n,depth=0):
  if depth>=6 or max(np.linalg.norm(t[a,:2]-t[b,:2]) for a,b in [(0,1),(1,2),(2,0)])<=2:return [(t,n)]
  a,b,c=(t[0]+t[1])/2,(t[1]+t[2])/2,(t[2]+t[0])/2;na,nb,nc=(n[0]+n[1])/2,(n[1]+n[2])/2,(n[2]+n[0])/2
  children=[(np.array([t[0],a,c]),np.array([n[0],na,nc])),(np.array([a,t[1],b]),np.array([na,n[1],nb])),(np.array([c,b,t[2]]),np.array([nc,nb,n[2]])),(np.array([a,b,c]),np.array([na,nb,nc]))]
  return [q for tt,nn in children for q in subdivide(tt,nn,depth+1)]
 for ij,tile in ground.tiles.items():
  tid=tile['id'];lod=geo['base_active_lods'][tid];path=root/f'data/processed/stage04/ground/{tid}.npz';source=path if path.exists() else root/tile['file']
  # Fast reject using original geographic tile box, with6m transition support across tile edges.
  box=shapely.box(ij[0]*1000-6,ij[1]*1000-6,(ij[0]+1)*1000+6,(ij[1]+1)*1000+6)
  if not len(tree.query(box)):continue
  with np.load(source) as a:d={k:a[k] for k in a.files}
  v=d[f'v{lod}'];f=d[f'f{lod}'];gt=v[f].astype(float);gt[:,:,:2]+=tile['blender_object_translation_m'][:2];gp=shapely.polygons(gt[:,:,:2]);pairs=tree.query(gp,predicate='dwithin',distance=6);selected=np.zeros(len(f),bool);selected[np.unique(pairs[0])]=True
  if not selected.any():continue
  ns=d.get(f'n{lod}',np.tile([0,0,1],(len(v),1)));pieces=[];mats=[]
  for j in np.flatnonzero(selected):
   q=subdivide(gt[j],ns[f[j]])
   for t,n in q:pieces.append((t,n));mats.append(int(d[f'm{lod}'][j]))
  t=np.array([x[0] for x in pieces]);norm=np.array([x[1] for x in pieces]).reshape(-1,3);xyz=t.reshape(-1,3);points=shapely.points(xyz[:,:2]);near=tree.nearest(points);dist=shapely.distance(points,rp[near]);r=road[near];ab=r[:,1,:2]-r[:,0,:2];ac=r[:,2,:2]-r[:,0,:2];aq=xyz[:,:2]-r[:,0,:2];den=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0];valid=abs(den)>1e-10;den=np.where(valid,den,1);u=(aq[:,0]*ac[:,1]-aq[:,1]*ac[:,0])/den;w=(ab[:,0]*aq[:,1]-ab[:,1]*aq[:,0])/den;u=np.maximum(u,0);w=np.maximum(w,0);total=np.maximum(1,u+w);u/=total;w/=total;cap=r[:,0,2]+u*(r[:,1,2]-r[:,0,2])+w*(r[:,2,2]-r[:,0,2])-.8;weight=np.where(valid,np.clip((6-dist)/4,0,1),0);newz=xyz[:,2]+weight*np.minimum(cap-xyz[:,2],0);delta=newz-xyz[:,2]
  if not (delta<-.01).any():continue
  xyz[:,2]=newz;xyz[:,:2]-=tile['blender_object_translation_m'][:2];norm/=np.maximum(np.linalg.norm(norm,axis=1)[:,None],1e-12);base=len(v);vv=np.concatenate([v,xyz]).astype(np.float32);ff=np.concatenate([f[~selected],np.arange(len(xyz),dtype=np.int32).reshape(-1,3)+base]);mm=np.r_[d[f'm{lod}'][~selected],np.array(mats,np.uint8)];nn=np.concatenate([ns,norm]).astype(np.float32);cross=np.cross(vv[ff[:,1]]-vv[ff[:,0]],vv[ff[:,2]]-vv[ff[:,0]]);good=(np.linalg.norm(cross,axis=1)>1e-8)&(abs(cross[:,2])>1e-8);d[f'v{lod}']=vv;d[f'f{lod}']=ff[good];d[f'm{lod}']=mm[good];d[f'n{lod}']=nn;dst=archive/source.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True)
  if not dst.exists():shutil.copy2(source,dst)
  path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(path,**d);variant[tid]={'tile_id':tid,'file':str(path.relative_to(root)),'sha256':digest(path),'type':'derived_terrain_clearance_adjustment','cut_lod':lod};changes.append({'tile_id':tid,'maximum_lowering_m':float(-delta.min()),'refined_triangles':int(selected.sum()),'new_triangles':len(ff)})
 geo['ground_variants']=list(variant.values());write_json(root/'work/reports/stage04/geometry.json',geo);write_json(root/'work/reports/stage04/deck_terrain_cuts.json',{'status':'executed','source_feature_indices':sorted(bad),'tiles':changes,'method':'derived terrain only: locally subdivide to<=2m and lower covering vertices toward actual deck underside with2–6m transition; never raise lower ground','original_DTM_and_stage03_unchanged':True,'source_precision_not_increased':True,'maximum_subdivision_depth':6,'classification':'inferred_visual_clearance_adjustment_not_surveyed_earthworks'});print('DECK_TOP_TERRAIN_OCCLUSION_REPAIRED',len(bad),len(changes),flush=True)
if __name__=='__main__':cut()
