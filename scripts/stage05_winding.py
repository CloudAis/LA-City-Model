"""Post-float32 roof winding correction; coordinates, materials and IDs unchanged."""
from pathlib import Path
import json,shutil,hashlib,collections
import numpy as np
from stage05_preserve import sha
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def fix(root=ROOT):
 root=Path(root);ip=root/'data/processed/stage05/mesh_index.json';index=json.loads(ip.read_text());archive=root/'work/history/stage05_before_roof_winding';archive.mkdir(parents=True,exist_ok=True);report=root/'work/reports/stage05/roof_winding.json'
 if report.exists():print('ROOF_WINDING_PATCH_ALREADY_EXECUTED',flush=True);return
 shutil.copy2(ip,archive/ip.name);oldscript=index['script_sha256'];newscript=sha(root/'scripts/stage05_geometry.py');dbsha=index['source_sqlite_sha256'];cfgsha=index['config_sha256'];oldsig=hashlib.sha256((oldscript+cfgsha+dbsha).encode()).hexdigest();newsig=hashlib.sha256((newscript+cfgsha+dbsha).encode()).hexdigest();roof=next(i for i,r in enumerate(index['materials']) if r[0]=='roof');changed=[];counts=collections.Counter();details=[]
 for cell in index['cells']:
  assert cell['signature']==oldsig
  n=0
  for m in cell['meshes']:
   path=root/m['file'];assert sha(path)==m['sha256']
   with np.load(path) as d:a={k:d[k].copy() for k in d.files}
   v=a['v'];f=a['f'];normal=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]);flip=(a['m']==roof)&(normal[:,2]<0)
   if flip.any():
    dest=archive/path.relative_to(root);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);before=sha(path);details.append({'file':m['file'],'faces':int(flip.sum()),'feature_indices':np.unique(a['fid'][flip]).tolist(),'absolute_projected_double_area_min_max_m2':[float(abs(normal[flip,2]).min()),float(abs(normal[flip,2]).max())],'sha256_before':before});a['f'][flip]=a['f'][flip][:,[0,2,1]];np.savez_compressed(path,**a);m['sha256']=sha(path);changed.append(dict(m));n+=int(flip.sum())
  cell['signature']=newsig;cell['counts']['float32_roof_faces_reoriented']=n;write_json(root/'data/processed/stage05/meshes'/(cell['id']+'.json'),cell);counts.update(cell['counts'])
 index['script_sha256']=newscript;index['counts']=dict(counts);index['meshes']=[m for c in index['cells'] for m in c['meshes']];index['winding_patch']='work/reports/stage05/roof_winding.json';write_json(ip,index);gp=root/'work/reports/stage05/geometry.json';g=json.load(open(gp));g['counts']=dict(counts);write_json(gp,g);write_json(report,{'status':'executed','changed_meshes':changed,'details':details,'faces_reoriented':counts['float32_roof_faces_reoriented'],'positions_materials_and_feature_ids_changed':False,'old_script_sha256':oldscript,'new_script_sha256':newscript});print('FLOAT32_ROOF_WINDING_CORRECTED',len(changed),counts['float32_roof_faces_reoriented'],flush=True)
if __name__=='__main__':fix()
