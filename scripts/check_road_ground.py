"""Independent before/after terrain occlusion check at the typical intersection."""
from pathlib import Path
import json,numpy as np,shapely
from shapely.strtree import STRtree
from stage02_io import write_json
root=Path(__file__).resolve().parents[1];index=json.loads((root/'data/processed/stage04/mesh_index.json').read_text());m=next(m for m in index['meshes'] if m['tile_id']=='la_t_x-001_y+000' and m['role']=='markings')
with np.load(root/m['file']) as a:tri=a['v'][a['f']].astype(float)
q=tri[:,:,:2].mean(axis=1);near=np.linalg.norm(q-[540.0118476781645,774.891940115951],axis=1)<30;q=q[near];z=tri[near,:,2].mean(axis=1);report={'paint_centroid_samples':len(q)}
for name,path in [('before','work/history/stage04_before_pavement_occlusion_fix/data/processed/stage04/ground/la_t_x-001_y+000.npz'),('after','data/processed/stage04/ground/la_t_x-001_y+000.npz')]:
 with np.load(root/path) as a:v=a['v0'].astype(float);f=a['f0']
 tr=v[f];tree=STRtree(shapely.polygons(tr[:,:,:2]));pairs=tree.query(shapely.points(q),predicate='intersects');d=[]
 for pi,ti in zip(*pairs):
  t=tr[ti];ab=t[1,:2]-t[0,:2];ac=t[2,:2]-t[0,:2];aq=q[pi]-t[0,:2];den=ab[0]*ac[1]-ab[1]*ac[0]
  if abs(den)<1e-10:continue
  u=(aq[0]*ac[1]-aq[1]*ac[0])/den;w=(ab[0]*aq[1]-ab[1]*aq[0])/den;d.append(float(t[0,2]+u*(t[1,2]-t[0,2])+w*(t[2,2]-t[0,2])-z[pi]))
 report[name]={'terrain_hits':len(d),'ground_above_paint_samples':sum(x>.001 for x in d),'maximum_ground_minus_paint_m':max(d) if d else None}
write_json(root/'work/reports/stage04/intersection_ground_occlusion.json',report);print(report)
