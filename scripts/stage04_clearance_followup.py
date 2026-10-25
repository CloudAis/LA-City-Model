"""Keep rail, sleepers and inferred supports coherent with the localized road cutting."""
from pathlib import Path
import json,collections
import numpy as np
from stage04_geometry import Ground
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def update(root=ROOT):
 new=Ground(root);old=Ground(root);old.enable_road_floor=False;geo=json.loads((root/'work/reports/stage04/geometry.json').read_text());archive=root/'work/history/stage04_before_clearance_fix/files';cut={v['tile_id'] for v in geo['ground_variants'] if v.get('type')=='profiled_road_cut_in_display_terrain'}
 for ij,t in old.tiles.items():
  if t['id'] not in cut:continue
  p=archive/f'data/processed/stage04/ground/{t["id"]}.npz'
  if not p.exists():p=archive/t['file']
  assert p.exists();old.source_override_files[ij]=p
 ip=root/'data/processed/stage04/mesh_index.json';idx=json.loads(ip.read_text());changed=0;skipped=0
 for m in idx['meshes']:
  if m['tile_id'] not in cut or m['role'] not in ['rail_corridor','rail_detail','station_platform']:continue
  with np.load(root/m['file']) as a:d={k:a[k] for k in a.files}
  v=d['v'];xy=v[:,:2]+np.array(m['origin_m'][:2]);delta=new(xy[:,0],xy[:,1])-old(xy[:,0],xy[:,1]);valid=np.isfinite(delta);skipped+=int((~valid).sum());delta=np.where(valid,delta,0);d['v']=np.column_stack([v[:,:2],v[:,2]+delta]).astype(np.float32);dst=archive/m['file'];dst.parent.mkdir(parents=True,exist_ok=True)
  if not dst.exists():__import__('shutil').copy2(root/m['file'],dst)
  np.savez_compressed(root/m['file'],**d);m['sha256']=digest(root/m['file']);changed+=1
 moved=0
 for ins in idx['instances']:
  if ins['tile_id'] not in cut or ins['kind'] not in ['sleeper','pier']:continue
  xy=np.array(ins['xyz_m'][:2]);zz=new(xy[:1],xy[1:])[0];before=old(xy[:1],xy[1:])[0]
  if not np.isfinite(zz+before):continue
  if ins['kind']=='sleeper':ins['xyz_m'][2]+=float(zz-before)
  else:
   top=ins['xyz_m'][2]+ins['scale'][2]/2;h=top-zz
   if h<=0:continue
   ins['xyz_m'][2]=float((top+zz)/2);ins['scale'][2]=float(h)
  moved+=1
 # Reference water follows the new display ground only where a cutting touches it.
 water=json.loads((root/'data/processed/stage03/medium/water_index.json').read_text());wv={v['object_name']:v for v in geo.get('water_variants',[])}
 for w in water['pieces']:
  if w['tile_id'] not in cut or w['surface_mode']!='DEM_conforming_hydrographic_reference':continue
  with np.load(root/w['file']) as a:d={k:a[k] for k in a.files}
  v=d['v'];xy=v[:,:2]+np.array(w['object_translation_m'][:2]);z=new(xy[:,0],xy[:,1])+.03;valid=np.isfinite(z);z=np.where(valid,z,v[:,2]);path=root/f'data/processed/stage04/water_variants/{w["id"]}.npz';path.parent.mkdir(parents=True,exist_ok=True);d['v']=np.column_stack([v[:,:2],z]).astype(np.float32);np.savez_compressed(path,**d);wv['Water_'+w['id']]={'object_name':'Water_'+w['id'],'file':str(path.relative_to(root)),'sha256':digest(path),'status':'hydrographic_reference_not_measured_water_level'}
 geo['water_variants']=list(wv.values());write_json(root/'work/reports/stage04/geometry.json',geo);write_json(ip,idx);write_json(root/'work/reports/stage04/clearance_followup.json',{'status':'executed','rail_meshes_updated':changed,'instances_updated':moved,'unsupported_boundary_vertices_retained':skipped,'modeled_ground_in_cuttings':'pavement underside reference, not new bare-earth measurement'});print('CLEARANCE_GROUND_RAIL_SUPPORT_UPDATE',changed,moved,skipped,flush=True)
if __name__=='__main__':update()
