"""Quarantine tiny inherited water faces at the Stage04 float32 tolerance; retain raw/Stage03."""
from pathlib import Path
import json
import numpy as np
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def clean(root=ROOT):
 gpath=root/'work/reports/stage04/geometry.json';g=json.loads(gpath.read_text());variants={r['object_name']:r for r in g['water_variants']};changed=[]
 for piece in json.loads((root/'data/processed/stage03/medium/water_index.json').read_text())['pieces']:
  name='Water_'+piece['id']
  with np.load(root/piece['file']) as a:v=a['v'];f=a['f']
  if name in variants:
   with np.load(root/variants[name]['file']) as a:v=a['v']
  cross=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]);bad=np.linalg.norm(cross,axis=1)<1e-8
  if not bad.any():continue
  path=root/'data/processed/stage04/water_variants'/f'{piece["id"]}.npz';path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(path,v=v,f=f[~bad])
  record={'object_name':name,'file':str(path.relative_to(root)),'sha256':digest(path),'status':'inherited_hydrography_tiny_face_quarantine_not_new_water_measurement'};variants[name]=record
  changed.append({'object_name':name,'faces_quarantined':int(bad.sum()),'cross_product_norm_threshold_m2':1e-8,'coordinates_changed':False})
 g['water_variants']=list(variants.values());write_json(gpath,g);write_json(root/'work/reports/stage04/water_microfaces.json',{'status':'executed','changes':changed,'quarantined_faces':sum(x['faces_quarantined'] for x in changed),'original_stage03_and_raw_unchanged':True});print('WATER_MICROFACE_QUARANTINE',sum(x['faces_quarantined'] for x in changed),flush=True)
if __name__=='__main__':clean()
