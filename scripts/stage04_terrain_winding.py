"""Orient all derived terrain top faces upward, agreeing with their custom normals."""
from pathlib import Path
import json,shutil
import numpy as np
from stage02_io import digest,write_json
ROOT=Path(__file__).resolve().parents[1]
def correct(root=ROOT):
 gp=root/'work/reports/stage04/geometry.json';g=json.loads(gp.read_text());changes=[]
 for item in g['ground_variants']:
  path=root/item['file']
  with np.load(path) as a:d={k:a[k] for k in a.files}
  count=0
  for lod in range(3):
   v=d[f'v{lod}'];f=d[f'f{lod}'];cross=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]);down=cross[:,2]<0;count+=int(down.sum());f[down]=f[down][:,[0,2,1]];d[f'f{lod}']=f
  if count:
   backup=root/'work/history/stage04_before_winding_fix'/item['file'];backup.parent.mkdir(parents=True,exist_ok=True)
   if not backup.exists():shutil.copy2(path,backup)
   np.savez_compressed(path,**d);item['sha256']=digest(path);changes.append({'tile_id':item['tile_id'],'faces_reoriented':count})
 write_json(gp,g);write_json(root/'work/reports/stage04/terrain_winding.json',{'status':'executed','changes':changes,'faces_reoriented':sum(x['faces_reoriented'] for x in changes),'downward_top_faces_remaining':0,'coordinates_and_elevations_changed':False,'original_stage03_and_raw_unchanged':True});print('TERRAIN_TOP_WINDING_CORRECTED',sum(x['faces_reoriented'] for x in changes),flush=True)
if __name__=='__main__':correct()
