"""Remove display terrain directly covered by actual Downtown pavement, preserving DTM."""
from pathlib import Path
import json,shutil,collections,multiprocessing as mp
import numpy as np
import shapely
from stage04_clearance import clip_arrays
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def tile(job):
 root,tid,meshes,variant,base,lod=job;root=Path(root);tri=[]
 for m in meshes:
  with np.load(root/m['file']) as a:tri.append(a['v'][a['f']][:,:,:2].astype(float)+m['origin_m'][:2])
 mask=shapely.unary_union(shapely.polygons(np.concatenate(tri)));source=root/(variant['file'] if variant else base['file'])
 archive=root/'work/history/stage04_before_pavement_occlusion_fix'/source.relative_to(root);archive.parent.mkdir(parents=True,exist_ok=True)
 if not archive.exists():shutil.copy2(source,archive)
 with np.load(source) as a:d={k:a[k] for k in a.files}
 before=len(d[f'f{lod}']);r=clip_arrays(d[f'v{lod}'],d[f'f{lod}'],d[f'm{lod}'],np.full(before,-1,np.int32),mask,np.array(base['blender_object_translation_m'][:2]),d.get(f'n{lod}'))
 if r is None:return None
 for k in ['v','f','m','n']:
  if k in r:d[k+str(lod)]=r[k]
 path=root/f'data/processed/stage04/ground/{tid}.npz';path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(path,**d)
 return {'tile_id':tid,'file':str(path.relative_to(root)),'sha256':digest(path),'type':'inferred_display_terrain_hidden_under_actual_pavement','cut_lod':lod,'before_triangles':before,'after_triangles':len(r['f']),'pavement_mask_area_m2':mask.area}
def cut(root=ROOT):
 gp=root/'work/reports/stage04/geometry.json';geo=json.loads(gp.read_text());idx=json.loads((root/'data/processed/stage04/mesh_index.json').read_text());base={t['id']:t for t in json.loads((root/'data/processed/stage03/medium/tile_index.json').read_text())['tiles']};variants={t['tile_id']:t for t in geo['ground_variants']};bytile=collections.defaultdict(list)
 for m in idx['meshes']:
  if m['role']=='downtown_road':bytile[m['tile_id']].append(m)
 archive=root/'work/history/stage04_before_pavement_occlusion_fix'
 for p in [gp,root/'data/processed/stage04/road_floor_index.json']:
  dst=archive/p.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True)
  if not dst.exists():shutil.copy2(p,dst)
 changes=[]
 jobs=[(str(root),tid,ms,variants.get(tid),base[tid],geo['base_active_lods'][tid]) for tid,ms in bytile.items()]
 with mp.get_context('fork').Pool(4) as pool:
  for r in pool.imap_unordered(tile,jobs):
   if r:variants[r['tile_id']]=r;changes.append(r);print('PAVEMENT_GROUND_CUT_TILE',r['tile_id'],flush=True)
 geo['ground_variants']=list(variants.values());write_json(gp,geo)
 floor=root/'data/processed/stage04/road_floor_index.json';d=json.loads(floor.read_text());existing={m['id'] for m in d['meshes']};d['meshes'].extend(m for ms in bytile.values() for m in ms if m['id'] not in existing);write_json(floor,d)
 write_json(root/'work/reports/stage04/pavement_ground_occlusion.json',{'status':'executed','tiles':changes,'method':'clip derived display ground by actual pavement triangle XY union; road surface itself covers the opening','raw_DTM_and_source_terrain_unchanged':True,'source_road_XY_Z_unchanged':True,'reason':'boundary-only pavement triangulation can otherwise let original terrain show through road interiors','ground_query_interface':'road-floor fallback from actual pavement minus0.06m; not a new survey'})
 print('DOWNTOWN_PAVEMENT_GROUND_OCCLUSION_FIXED',len(changes),flush=True)
if __name__=='__main__':cut()
