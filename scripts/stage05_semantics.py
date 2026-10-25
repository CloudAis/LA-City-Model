"""Exclude explicit non-building areas without moving or fabricating structures.

This corrective pass preserves every original row, records previous generated
bytes, and proves unchanged coordinates/materials for all retained features.
"""
from pathlib import Path
import sqlite3,json,gzip,collections,hashlib,shutil
import numpy as np,shapely
from stage02_io import write_json
from stage03_common import polygon_parts
from stage05_preserve import sha
ROOT=Path(__file__).resolve().parents[1]
def fix(root=ROOT):
 root=Path(root);path=root/'data/processed/stage05/buildings.sqlite';db=sqlite3.connect(path);rows=db.execute("SELECT i,uid,geom,attrs FROM buildings WHERE active=1 AND json_extract(attrs,'$.tags.building')='no'").fetchall();report=root/'work/reports/stage05/semantic_exclusions.json'
 if not rows:db.close();print('NO_ACTIVE_EXPLICIT_NONBUILDING_POLYGONS',flush=True);return
 before=sha(path);changes={};ids={r[0] for r in rows};archive=root/'work/history/stage05_before_nonbuilding_filter';archive.mkdir(parents=True,exist_ok=True)
 for i,uid,g,astr in rows:
  a=json.loads(astr);changes[i]={'id':uid,'original_attrs':a,'original_geometry_wkb_hex':bytes(g).hex(),'reason':'explicit OSM building=no; area is not a building, not a demolition date assertion'};a['exclusion_reason']=changes[i]['reason'];db.execute('UPDATE buildings SET active=0,attrs=? WHERE i=?',(json.dumps(a,separators=(',',':')),i))
 db.commit();height=collections.Counter();types=collections.Counter()
 for a, in db.execute('SELECT attrs FROM buildings WHERE active=1'):
  a=json.loads(a);height[a['height_evidence']]+=1;types[a['building_type']]+=1
 active=db.execute('SELECT count(*) FROM buildings WHERE active=1').fetchone()[0];db.close();after=sha(path);indexpath=root/'data/processed/stage05/mesh_index.json';index=json.load(open(indexpath));configsha=sha(root/'config/stage05.yaml');scriptsha=sha(root/'scripts/stage05_geometry.py');oldsig=hashlib.sha256((scriptsha+configsha+before).encode()).hexdigest();newsig=hashlib.sha256((scriptsha+configsha+after).encode()).hexdigest();meshes=[];affected=[];excluded_placements=[]
 for cell in index['cells']:
  assert cell['signature']==oldsig
  placementpath=root/cell['placements']
  with gzip.open(placementpath,'rt') as f:p=json.load(f)
  excluded=[r for r in p['placements'] if r['i'] in ids]
  if excluded:
   dst=archive/placementpath.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(placementpath,dst);excluded_placements.extend(excluded);p['placements']=[r for r in p['placements'] if r['i'] not in ids];p['instances']=[r for r in p['instances'] if r['fid'] not in ids]
   with gzip.open(placementpath,'wt') as f:json.dump(p,f,separators=(',',':'))
   cell['placements_sha256']=sha(placementpath);cell['counts']['buildings']-=len(excluded)
   for r in excluded:
    for key,amount in [('courtyard_holes',r['courtyard_holes']),('true_multipart',r['components']>1),('hillside_relief_ge2m',r['ground_relief_m']>=2),('high_foundation_warning_gt8m',r['floor_navd88_m']-r['bottom_navd88_m']>8),('ground_fallback_samples',r['ground_fallback_samples']),('ground_unresolved_samples',r['ground_unresolved'])]:cell['counts'][key]-=amount
   for m in cell['meshes']:
    meshpath=root/m['file'];assert sha(meshpath)==m['sha256'];dst=archive/meshpath.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(meshpath,dst)
    with np.load(meshpath) as d:arrays={k:d[k].copy() for k in d.files}
    keep=~np.isin(arrays['fid'],list(ids));old_v=arrays['v'];old_f=arrays['f'][keep];used,inverse=np.unique(old_f,return_inverse=True);arrays['v']=old_v[used];arrays['f']=inverse.reshape(-1,3).astype(np.int32)
    for k in ['m','fid','uv']:
     if k in arrays:arrays[k]=arrays[k][keep]
    assert np.array_equal(arrays['v'][arrays['f']],old_v[old_f]),'Retained source coordinates changed';np.savez_compressed(meshpath,**arrays);m.update({'sha256':sha(meshpath),'triangles':len(arrays['f']),'vertices':len(arrays['v']),'bounds_m':[(arrays['v'].min(axis=0)+m['origin_m']).tolist(),(arrays['v'].max(axis=0)+m['origin_m']).tolist()],'feature_count':len(np.unique(arrays['fid']))});affected.append(dict(m))
  cell['signature']=newsig;cell['semantic_patch']='work/reports/stage05/semantic_exclusions.json';write_json(root/'data/processed/stage05/meshes'/(cell['id']+'.json'),cell);meshes.extend(cell['meshes'])
 counts=collections.Counter()
 for c in index['cells']:counts.update(c['counts'])
 index.update({'meshes':meshes,'source_sqlite_sha256':after,'counts':dict(counts),'semantic_patch':'work/reports/stage05/semantic_exclusions.json'});write_json(indexpath,index);geompath=root/'work/reports/stage05/geometry.json';geometry=json.load(open(geompath));geometry.update({'counts':dict(counts),'authoring_triangles':sum(m['triangles'] for m in meshes if m['lod']==0),'runtime_triangles':sum(m['triangles'] for m in meshes if m['lod']==2),'semantic_patch':'work/reports/stage05/semantic_exclusions.json'});write_json(geompath,geometry)
 bdpath=root/'work/reports/stage05/building_data.json';bd=json.load(open(bdpath));bd.update({'sqlite_sha256':after,'active_buildings':active,'height_sources':dict(height),'types':dict(types)});bd['counts']['initial_nonoverlapping_OSM_additions']=bd['counts']['nonoverlapping_OSM_additions'];bd['counts']['nonoverlapping_OSM_additions']-=len(ids);bd['counts']['explicit_OSM_nonbuilding_areas_excluded']=len(ids);write_json(bdpath,bd);prpath=root/'work/reports/stage05/part_review.json';pr=json.load(open(prpath));pr['sqlite_sha256']=after;write_json(prpath,pr);write_json(report,{'status':'executed','sqlite_sha256_before':before,'sqlite_sha256_after':after,'excluded_nonbuildings':changes,'excluded_prior_placements':excluded_placements,'affected_meshes':affected,'retained_building_triangle_coordinates_verified_identical':True,'apply_on_next_blender_reopen':True,'all_original_rows_retained':True});print('EXPLICIT_NONBUILDING_AREAS_EXCLUDED',len(ids),active,flush=True)
if __name__=='__main__':fix()
