"""Rebuild two actual Historic Core buildings from preserved editable arrays."""
from pathlib import Path
import argparse,hashlib,json,os,struct,sys
import numpy as np
BASE=Path(__file__).resolve().parents[1];LOCAL=(BASE/'LA_Master.blend').exists();ROOT=BASE if LOCAL else BASE/'outputs/LA_Delivery'
if LOCAL:from glb_writer import GLB
else:from stage09_glb import GLB
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',default='config/sample.json');parser.add_argument('--output');args=parser.parse_args();cfg=json.loads((ROOT/args.config).read_text());idx=json.loads((ROOT/'sample_inputs/index.json').read_text());origin=np.array(idx['origin_city_m']);writer=GLB('Historic_Core_two_building_sample');included=[]
for row in idx['objects']:
 if not cfg['include_window_frames'] and any(s in row['name'] for s in ('window_frames','frame_and_sill')):continue
 with np.load(ROOT/row['file']) as z:a={k:z[k] for k in z.files}
 v=np.asarray(a['v'],float)+np.array(row['origin_city_m'])-origin;faces=a['f'];mi=a['m'];fid=int(row['id'].split(':')[1]);included.append(row['name'])
 for slot in np.unique(mi):
  mask=mi==slot;source=dict(idx['materials'][row['materials'][int(slot)]]);source['roughness']=min(1,max(.02,source['roughness']*cfg['roughness_multiplier']));maps={}
  for role,file in source.get('maps',{}).items():
   p=ROOT/file
   if not p.exists() and '/assets/' in str(file):p=ROOT/'assets'/str(file).split('/assets/',1)[1]
   target=ROOT/'tiles/textures'/(sha(p)[:14]+'.png');assert target.is_file(),target
   maps[role]=str(target)
  output=ROOT/(args.output or cfg['output']);output.parent.mkdir(parents=True,exist_ok=True);source['maps']={role:os.path.relpath(file,output.parent).replace(os.sep,'/') for role,file in maps.items()}
  uv=a.get('uv');uv=uv[mask].copy() if uv is not None and maps else None
  if uv is not None:
   tile=source.get('tile_m',[1,1]);tile=np.array(tile if len(tile)==2 else [tile[0],tile[0]]);uv/=tile;uv[...,1]=1-uv[...,1]
  writer.add(v,faces[mask],np.full(mask.sum(),fid,np.int32),source,uv=uv)
writer.save(output);result={'status':'actual_rebuild_completed','output':str(output.relative_to(ROOT)),'sha256':sha(output),'triangles':writer.triangles,'origin_city_m':origin.tolist(),'source_feature_ids':sorted(writer.feature_ids),'seed':cfg['seed'],'included_components':included,'config':cfg,'source_class':'actual source08 arrays with recorded inferred façades; not fresh surveyed data','units':'metres; glTF(x,z,-y); origin stored separately'};output.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','output','sha256','triangles','source_feature_ids']},ensure_ascii=False),flush=True)
