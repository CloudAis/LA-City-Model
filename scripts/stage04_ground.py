"""Preserve Stage03 river/water terrain detail; update affected transport only."""
from pathlib import Path
import json,collections
import numpy as np
from stage04_geometry import Ground
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def update(root=ROOT):
 p=root/'work/reports/stage04/geometry.json';geo=json.loads(p.read_text());new=Ground(root);old=Ground(root);old.active=geo['base_active_lods'];old.cache.clear();changed={k for k,v in new.active.items() if old.active[k]!=v};ip=root/'data/processed/stage04/mesh_index.json';idx=json.loads(ip.read_text());count=0;maxdiff=0
 roles={'full_far','overview_far','rail_corridor','rail_detail','airport_surface','airport_apron','airport_marking','station_platform','downtown_paths'}
 for m in idx['meshes']:
  if m['tile_id'] not in changed or m['role'] not in roles:continue
  with np.load(root/m['file']) as a:d={k:a[k] for k in a.files}
  v=d['v'];xy=v[:,:2].astype(float)+np.array(m['origin_m'][:2]);before=old(xy[:,0],xy[:,1]);after=new(xy[:,0],xy[:,1]);delta=after-before
  if not np.isfinite(delta).all():raise ValueError('Unsupported terrain priority adjustment '+m['id'])
  maxdiff=max(maxdiff,float(abs(delta).max()));d['v']=np.column_stack([v[:,:2],v[:,2]+delta]).astype(np.float32);np.savez_compressed(root/m['file'],**d);m['sha256']=digest(root/m['file']);m['height_mesh_priority_preserved']=True;count+=1
  if count%1000==0:print('PRIORITY_GROUND_ADJUSTED',count,flush=True)
 roads=json.loads((root/'data/processed/stage04/roads.json').read_text());byid={r['id']:r for r in roads};instances=0
 for ins in idx['instances']:
  tid=__import__('stage04_geometry').tile_id(int(np.floor(ins['xyz_m'][0]/1000)),int(np.floor(ins['xyz_m'][1]/1000)))
  if tid not in changed or ins['kind']=='pier':continue
  r=byid.get(str(ins.get('source')))
  if ins['kind']=='guardrail' and r and (r['parameters']['bridge'] or r['parameters']['vertical_rank']!=0):continue
  xy=np.array(ins['xyz_m'][:2]);delta=new(xy[:1],xy[1:])[0]-old(xy[:1],xy[1:])[0]
  if np.isfinite(delta):ins['xyz_m'][2]+=float(delta);instances+=1
 # DTM-conforming hydrographic references follow the actual Stage04 roadbed variant.
 water=json.loads((root/'data/processed/stage03/medium/water_index.json').read_text());water_variants=[];variant_tiles={x['tile_id'] for x in geo['ground_variants']}
 for w in water['pieces']:
  if w['tile_id'] not in variant_tiles or w['surface_mode']!='DEM_conforming_hydrographic_reference':continue
  with np.load(root/w['file']) as a:d={k:a[k] for k in a.files}
  v=d['v'];xy=v[:,:2].astype(float)+np.array(w['object_translation_m'][:2]);z=new(xy[:,0],xy[:,1])+.03
  if not np.isfinite(z).all():raise ValueError('Missing hydrographic reference ground')
  delta=float(abs(z-v[:,2]).max())
  if delta<1e-5:continue
  path=root/f'data/processed/stage04/water_variants/{w["id"]}.npz';path.parent.mkdir(parents=True,exist_ok=True);d['v']=np.column_stack([v[:,:2],z]).astype(np.float32);np.savez_compressed(path,**d);water_variants.append({'object_name':'Water_'+w['id'],'file':str(path.relative_to(root)),'sha256':digest(path),'maximum_adjustment_m':delta,'status':'inferred_DEM_conforming_reference_not_measured_water_level'})
 geo['base_active_lods']=new.active;geo['water_variants']=water_variants;geo['terrain_policy']='preserve LOD0 on original river/closeup priorities and every water piece tile; other far terrainLOD2. Original Stage03 meshes retained.';write_json(p,geo);write_json(ip,idx)
 report={'status':'executed','changed_terrain_tiles':len(changed),'adjusted_transport_meshes':count,'maximum_terrain_LOD_height_difference_m':maxdiff,'adjusted_instances':instances,'water_variants':water_variants,'original_stage03_data_unchanged':True,'note':'Actual selected terrain surfaces remain coherent with traffic and hydrographic reference masks; resolution/accuracy is not increased.'};write_json(root/'work/reports/stage04/priority_ground.json',report);print('PRIORITY_GROUND_COHERENCE_COMPLETE',len(changed),count,len(water_variants),flush=True)
if __name__=='__main__':update()
