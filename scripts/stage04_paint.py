"""Clip every paint triangle to actual pavement triangles; exact8mm surface offset."""
from pathlib import Path
import json,collections,math,multiprocessing as mp
import numpy as np
import shapely
from shapely.strtree import STRtree
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
FULL_TILES={'la_t_x-001_y+002','la_t_x+000_y+002','la_t_x-001_y+003','la_t_x+000_y+003'}
def process(mark):
 root,mark=mark;index=_PAINT_INDEX;road_params=_PAINT_PARAMS;root=Path(root);p=root/mark['file']
 if mark.get('paint_draped_to_actual_pavement'):return mark,{'cached':True}
 with np.load(p) as a:old={k:a[k] for k in a.files}
 pavement=[]
 for m in index:
  if m['tile_id']!=mark['tile_id']:continue
  role=m['role']
  if role not in ['bridge_road','tunnel_road','downtown_road','full_far','overview_far','profiled_priority_road']:continue
  if role=='overview_far' and m['tile_id'] in FULL_TILES:continue
  if role=='full_far' and m['tile_id'] not in FULL_TILES:continue
  with np.load(root/m['file']) as a:
   keep=a['m']==0;f=a['f'][keep];tri=a['v'][f].astype(float);fid=a['fid'][keep]
  if len(f):pavement.append((m,tri,fid))
 verts=[];faces=[];mats=[];fids=[];offset=0;input_area=0;covered_area=0;dt_tree=None;dt_tri=None;missing=[]
 for fid in sorted(set(old['fid'].tolist())):
  eligible=[];parameter=road_params[fid] if fid>=0 else {};ground=not parameter.get('bridge') and not parameter.get('tunnel') and parameter.get('vertical_rank',0)==0
  for m,tri,ids in pavement:
   if m['role']=='downtown_road' and ground:eligible.append(tri)
   else:
    sel=tri[ids==fid]
    if len(sel):eligible.append(sel)
  paint_idx=np.flatnonzero(old['fid']==fid);paint3=old['v'][old['f'][paint_idx]].astype(float);paint=shapely.polygons(paint3[:,:,:2]);input_area+=float(shapely.area(paint).sum())
  if not eligible:missing.append(int(fid));continue
  top=np.concatenate(eligible);polys=shapely.polygons(top[:,:,:2]);tree=STRtree(polys);pairs=tree.query(paint,predicate='intersects')
  if not pairs.size:missing.append(int(fid));continue
  try:parts=shapely.intersection(paint[pairs[0]],polys[pairs[1]])
  except shapely.errors.GEOSException:parts=shapely.intersection(paint[pairs[0]],polys[pairs[1]],grid_size=.0001)
  for geom,pi,ti in zip(parts,pairs[0],pairs[1]):
   if geom.is_empty or geom.area<1e-8:continue
   pieces=[geom] if geom.geom_type=='Polygon' else [g for g in getattr(geom,'geoms',[]) if g.geom_type=='Polygon']
   for piece in pieces:
    xy=np.asarray(piece.exterior.coords)[:-1,:2]
    if len(xy)<3:continue
    t=top[ti];ab=t[1,:2]-t[0,:2];ac=t[2,:2]-t[0,:2];den=ab[0]*ac[1]-ab[1]*ac[0]
    if abs(den)<1e-9:continue
    aq=xy-t[0,:2];u=(aq[:,0]*ac[1]-aq[:,1]*ac[0])/den;w=(ab[0]*aq[:,1]-ab[1]*aq[:,0])/den;z=t[0,2]+u*(t[1,2]-t[0,2])+w*(t[2,2]-t[0,2])+.008
    ff=np.array([[0,j,j+1] for j in range(1,len(xy)-1)],np.int32);vv=np.column_stack([xy,z]).astype(np.float32);nn=np.cross(vv[ff[:,1]]-vv[ff[:,0]],vv[ff[:,2]]-vv[ff[:,0]]);good=(np.linalg.norm(nn,axis=1)>1e-8)&(abs(nn[:,2])>1e-8);ff=ff[good]
    if not len(ff):continue
    verts.append(vv);faces.append(ff+offset);offset+=len(vv);mats.extend([int(old['m'][paint_idx[pi]])]*len(ff));fids.extend([int(fid)]*len(ff));covered_area+=piece.area
 if verts:
  v=np.concatenate(verts);f=np.concatenate(faces);np.savez_compressed(p,v=v,f=f,m=np.array(mats,np.uint8),fid=np.array(fids,np.int32));mark['vertices']=len(v);mark['triangles']=len(f);mark['sha256']=digest(p)
 else:raise ValueError('No supported paint triangles '+str(p))
 mark['paint_draped_to_actual_pavement']=True
 return mark,{'file':mark['file'],'input_plan_area_m2':input_area,'covered_plan_area_m2':covered_area,'source_features_without_backing_pavement':missing,'offset_m':.008,'method':'convex intersection of source paint triangles with actual saved asphalt triangles; triangulated within each backing plane; no terrain-only drape'}
def run(root=ROOT):
 global _PAINT_INDEX,_PAINT_PARAMS
 path=root/'data/processed/stage04/mesh_index.json';d=json.loads(path.read_text());roads=json.loads((root/'data/processed/stage04/roads.json').read_text());params=[r['parameters'] for r in roads];_PAINT_INDEX=d['meshes'];_PAINT_PARAMS=params;marks=[m for m in d['meshes'] if m['role']=='markings'];report=[];updated={}
 with mp.get_context('fork').Pool(4) as pool:
  for m,r in pool.imap_unordered(process,[(str(root),m) for m in marks]):updated[m['id']]=m;report.append(r)
 d['meshes']=[updated.get(m['id'],m) for m in d['meshes']];write_json(path,d);write_json(root/'work/reports/stage04/paint_drape.json',{'status':'executed','meshes':report,'offset_m':.008,'method':'actual backing asphalt triangles, not merely DEM elevation','total_input_area_m2':sum(x.get('input_plan_area_m2',0) for x in report),'total_supported_area_m2':sum(x.get('covered_plan_area_m2',0) for x in report)});print('ACTUAL_PAVEMENT_PAINT_DRAPE_COMPLETE',len(marks),flush=True)
if __name__=='__main__':run()
