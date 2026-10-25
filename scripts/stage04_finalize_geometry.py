"""Remove quantization microfaces and align shared guardrail beam instances in3D."""
from pathlib import Path
import json,math,collections
import numpy as np
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def finalize(root=ROOT):
 p=root/'data/processed/stage04/mesh_index.json';idx=json.loads(p.read_text());removed=0;changed=0
 for m in idx['meshes']:
  assert digest(root/m['file'])==m['sha256']
  with np.load(root/m['file']) as a:d={k:a[k] for k in a.files}
  v=d['v'];f=d['f'];cross=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]);good=(np.linalg.norm(cross,axis=1)>1e-8)&((d['m']==5)|(abs(cross[:,2])>1e-8))
  if not good.all():
   removed+=int((~good).sum());changed+=1
   for k in ['f','m','fid']:d[k]=d[k][good]
   np.savez_compressed(root/m['file'],**d);m['triangles']=len(d['f']);m['sha256']=digest(root/m['file'])
 from stage04_build import Builder
 b=Builder(root);lookup={r['id']:i for i,r in enumerate(b.roads)};pitched=0
 for ins in idx['instances']:
  x,y,z=ins['xyz_m'];ins['tile_id']=__import__('stage04_geometry').tile_id(math.floor(x/1000),math.floor(y/1000));ins['ownership']='origin_tile_shared_prototype'
  if ins['kind']!='guardrail' or ins.get('pitch_adjusted'):continue
  length=ins['scale'][0];angle=ins['rotation_z'];axis=np.array([math.cos(angle),math.sin(angle)]);xy=np.array([x,y]);ends=np.array([xy-axis*length/2,xy+axis*length/2]);i=lookup.get(str(ins.get('source')))
  heights=b.road_z(i,ends)+.75 if i is not None else b.ground(ends[:,0],ends[:,1])+ins['scale'][2]/2
  if not np.isfinite(heights).all():continue
  dz=float(heights[1]-heights[0]);ins['rotation_y']=-math.atan2(dz,length);ins['scale'][0]=math.hypot(length,dz);ins['xyz_m'][2]=float(np.mean(heights));ins['pitch_adjusted']=True;pitched+=1
 idx['final_removed_quantization_microfaces']=removed;write_json(p,idx)
 geo=json.loads((root/'work/reports/stage04/geometry.json').read_text());geo['triangles_by_role']={role:sum(m['triangles'] for m in idx['meshes'] if m['role']==role) for role in set(m['role'] for m in idx['meshes'])};write_json(root/'work/reports/stage04/geometry.json',geo)
 write_json(root/'work/reports/stage04/final_geometry.json',{'status':'executed','removed_quantization_microfaces':removed,'changed_meshes':changed,'guardrail_instances_pitched_to_endpoint_heights':pitched,'source_XY_centerlines_unchanged':True,'guardrail_pose_status':'estimated endpoint heights, not surveyed guardrail engineering'});print('FINAL_GEOMETRY_SANITIZED',removed,'GUARDRAILS_PITCHED',pitched,flush=True)
if __name__=='__main__':finalize()
