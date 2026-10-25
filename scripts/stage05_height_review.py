"""Resolve typed-height contradictions conservatively; retain raw evidence.

Anomalous undefined county-field candidates become explicit type estimates.
Reported heights remain reported; tall small-structure tags become unknown use.
Only affected cells are regenerated. Other mesh bytes are verified and reused.
"""
from pathlib import Path
import json,sqlite3,collections,hashlib,shutil,concurrent.futures
import numpy as np,yaml
from stage05_data import attributes
from stage05_geometry import task
from stage05_preserve import sha
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def review(root=ROOT):
 root=Path(root);out=root/'work/reports/stage05/height_type_review.json'
 if out.exists():print('HEIGHT_TYPE_REVIEW_ALREADY_EXECUTED',flush=True);return
 ip=root/'data/processed/stage05/mesh_index.json';index=json.load(open(ip));cfg=yaml.safe_load((root/'config/stage05.yaml').read_text());dbpath=root/'data/processed/stage05/buildings.sqlite';before=sha(dbpath);db=sqlite3.connect(dbpath);rows=db.execute("SELECT i,uid,geom,attrs,cell FROM buildings WHERE active=1 AND height>? AND json_extract(attrs,'$.building_type') IN ('detached_house','garage_outbuilding')",(cfg['height']['type_review_threshold_m'],)).fetchall();changes=[];cells=set();changed_ids=[]
 for i,uid,wkb,astr,cell in rows:
  old=json.loads(astr);new=attributes(dict(old),old['tags'],cfg,old.get('reference'));keys=['height_m','minimum_height_m','building_type','roof_shape','roof_height_m','levels'];geometry_changed=any(old[k]!=new[k] for k in keys)
  if old['height_evidence']!='inferred_official_field_interpretation':assert old['height_m']==new['height_m'],'Never cap a reported height solely by type'
  if geometry_changed:cells.add(cell);changed_ids.append(i)
  db.execute('UPDATE buildings SET attrs=?,height=?,min_height=? WHERE i=?',(json.dumps(new,separators=(',',':')),new['height_m'],new['minimum_height_m'],i));changes.append({'i':i,'id':uid,'cell':cell,'old_height_m':old['height_m'],'new_height_m':new['height_m'],'old_type':old['building_type'],'new_type':new['building_type'],'old_height_evidence':old['height_evidence'],'new_height_evidence':new['height_evidence'],'geometry_changed':geometry_changed,'old_attrs':old,'new_attrs':new})
 db.commit();hc=collections.Counter();tc=collections.Counter()
 for a, in db.execute('SELECT attrs FROM buildings WHERE active=1'):
  a=json.loads(a);hc[a['height_evidence']]+=1;tc[a['building_type']]+=1
 db.close();after=sha(dbpath);oldcfg=index['config_sha256'];newcfg=sha(root/'config/stage05.yaml');script=index['script_sha256'];oldsig=hashlib.sha256((script+oldcfg+before).encode()).hexdigest();newsig=hashlib.sha256((script+newcfg+after).encode()).hexdigest();archive=root/'work/history/stage05_before_height_type_review';archive.mkdir(parents=True,exist_ok=True);shutil.copy2(ip,archive/ip.name)
 for cell in index['cells']:
  assert cell['signature']==oldsig
  if cell['id'] in cells:
   for m in cell['meshes']:
    p=root/m['file'];dst=archive/p.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
  else:
   for m in cell['meshes']:assert sha(root/m['file'])==m['sha256']
   cell['signature']=newsig;cell['metadata_only_typology_reuse']='work/reports/stage05/height_type_review.json';write_json(root/'data/processed/stage05/meshes'/(cell['id']+'.json'),cell)
 bdpath=root/'work/reports/stage05/building_data.json';bd=json.load(open(bdpath));bd.update({'sqlite_sha256':after,'height_sources':dict(hc),'types':dict(tc),'height_type_review':'work/reports/stage05/height_type_review.json'});write_json(bdpath,bd);prpath=root/'work/reports/stage05/part_review.json';pr=json.load(open(prpath));pr['sqlite_sha256']=after;write_json(prpath,pr)
 updated={}
 with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
  for result in pool.map(task,[(str(root),c) for c in sorted(cells)]):updated[result['id']]=result;print('HEIGHT_REVIEW_CELL_REBUILT',result['id'],flush=True)
 newcells=[updated.get(c['id'],c) for c in index['cells']];counts=collections.Counter()
 for cell in newcells:counts.update(cell['counts'])
 index.update({'cells':newcells,'meshes':[m for c in newcells for m in c['meshes']],'counts':dict(counts),'source_sqlite_sha256':after,'config_sha256':newcfg,'height_type_review':'work/reports/stage05/height_type_review.json'});write_json(ip,index);gp=root/'work/reports/stage05/geometry.json';g=json.load(open(gp));g.update({'counts':dict(counts),'authoring_triangles':sum(m['triangles'] for m in index['meshes'] if m['lod']==0),'runtime_triangles':sum(m['triangles'] for m in index['meshes'] if m['lod']==2)});write_json(gp,g);models=[m for c in updated.values() for m in c['meshes']];write_json(root/'work/reports/stage05/pending_mesh_updates.json',{'reason':'height/type contradiction review; three anomalous undefined candidates withheld, reported numeric heights retained','changed_meshes':models,'changed_cells':list(updated.values())});write_json(out,{'status':'executed','reviewed_features':len(rows),'geometry_changed_ids':changed_ids,'affected_cells':sorted(cells),'unaffected_mesh_hashes_verified':True,'source_geometry_WKB_changed':False,'sqlite_sha256_before':before,'sqlite_sha256_after':after,'rejected_candidate_count':sum(c['old_height_m']!=c['new_height_m'] for c in changes),'reported_height_values_capped':False,'changes':changes,'contextual_imagery':'three bounded Esri World Imagery exports, research only; capture dates unknown; lowrise context does not measure height/storeys','classification_estimate_not_actual_survey_height':True});print('HEIGHT_TYPE_REVIEW_COMPLETE',len(rows),len(changed_ids),len(cells),flush=True)
if __name__=='__main__':review()
