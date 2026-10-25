"""Attach the visual spire to its highest source part, not the broad podium center."""
from pathlib import Path
import json,sqlite3,shapely,hashlib
from stage05_geometry import Worker,partitioned_bands
from stage03_common import polygon_parts
from stage05_preserve import sha
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def fix(root=ROOT):
 root=Path(root);report=root/'work/reports/stage05/spire_placement.json'
 if report.exists():print('SUPPORTED_SPIRE_PATCH_ALREADY_EXECUTED',flush=True);return
 ip=root/'data/processed/stage05/mesh_index.json';index=json.load(open(ip));db=sqlite3.connect(root/'data/processed/stage05/buildings.sqlite');uid='lariac6:201700195459';g,astr,owner=db.execute('SELECT geom,attrs,cell FROM buildings WHERE uid=?',(uid,)).fetchone();db.close();g=shapely.from_wkb(g);a=json.loads(astr);band=partitioned_bands(g,a,a['height_m'])[-1][0];poly=max(polygon_parts(band),key=lambda p:p.area);q=poly.representative_point();old=max(polygon_parts(g),key=lambda p:p.area).representative_point();radius=min(.7,q.distance(poly.boundary)*.8);newscript=sha(root/'scripts/stage05_geometry.py');oldsig=hashlib.sha256((index['script_sha256']+index['config_sha256']+index['source_sqlite_sha256']).encode()).hexdigest();newsig=hashlib.sha256((newscript+index['config_sha256']+index['source_sqlite_sha256']).encode()).hexdigest()
 for c in index['cells']:
  assert c['signature']==oldsig
  if c['id']==owner:continue
  for m in c['meshes']:assert sha(root/m['file'])==m['sha256']
  c['signature']=newsig;write_json(root/'data/processed/stage05/meshes'/(c['id']+'.json'),c)
 rebuilt=Worker(root).process(owner);index['cells']=[rebuilt if c['id']==owner else c for c in index['cells']];index['meshes']=[m for c in index['cells'] for m in c['meshes']];index['script_sha256']=newscript;write_json(ip,index);write_json(root/'work/reports/stage05/pending_mesh_updates.json',{'reason':'supported Wilshire spire and explicit flat building normals; geometry source XY remains unchanged','changed_meshes':rebuilt['meshes'],'changed_cells':[rebuilt]});write_json(report,{'status':'executed','id':uid,'source_footprint_moved':False,'architectural_tip_height_m':a['reference']['total_m'],'old_podium_reference_xy_m':list(old.coords[0]),'new_highest_part_reference_xy_m':list(q.coords[0]),'highest_part_area_m2':poly.area,'base_radius_m':radius,'base_circle_within_highest_part':poly.covers(q.buffer(radius)),'real_spire_profile_surveyed':False,'position_and_profile_are_still_marked_visual_approximation':True});print('SUPPORTED_SPIRE_CELL_REBUILT',owner,radius,flush=True)
if __name__=='__main__':fix()
