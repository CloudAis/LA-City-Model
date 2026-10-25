"""Review explicit parts after canonical correspondence; preserve the initial evidence."""
from pathlib import Path
import sqlite3,json,shapely,collections
from shapely.strtree import STRtree
from stage05_data import number
from stage05_preserve import sha
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def refine(root=ROOT):
 report=root/'work/reports/stage05/part_review.json';path=root/'data/processed/stage05/buildings.sqlite'
 if report.exists():
  r=json.loads(report.read_text());assert sha(path)==r['sqlite_sha256'];print('PART_REVIEW_CACHE_VERIFIED',flush=True);return
 db=sqlite3.connect(path);osm=sqlite3.connect(root/'data/processed/stage05/osm_buildings.sqlite');parts=[]
 for uid,wkb,t in osm.execute("SELECT uid,geom,tags FROM features WHERE kind='part'"):
  tags=json.loads(t);h=number(tags.get('height'));levels=number(tags.get('building:levels'));h=h or (levels*3.5 if levels else None)
  if h and 0<h<420:
   minimum=number(tags.get('min_height'));minimum=minimum if minimum is not None else (number(tags.get('building:min_level')) or 0)*3.5
   if minimum<h:parts.append((uid,shapely.from_wkb(wkb),h,minimum,tags))
 tree=STRtree([r[1] for r in parts]);changes=[];stats=collections.Counter()
 for i,uid,wkb,attrs in db.execute("SELECT i,uid,geom,attrs FROM buildings WHERE active=1 AND (uid LIKE 'osm:%' OR attrs NOT LIKE '%\"parts\":[]%')").fetchall():
  a=json.loads(attrs);g=shapely.from_wkb(wkb);items=a['parts']
  if not items and uid.startswith('osm:'):
   for j in tree.query(g,predicate='intersects'):
    puid,pg,h,minimum,tags=parts[int(j)];cut=pg.intersection(g)
    if cut.area/pg.area>=.85:items.append({'id':puid,'geometry_wkb_hex':shapely.to_wkb(cut).hex(),'height_m':h,'min_height_m':minimum,'height_source':'OSM explicit part height' if tags.get('height') else 'inferred_part_levels_times3.5m','tags':tags});stats['additional_parts_attached']+=1
  if not items:continue
  maximum=max(p['height_m'] for p in items);old=a['height_m']
  if maximum>old+.5 and not a.get('reference'):
   highest=max(items,key=lambda p:p['height_m']);inferred=highest['height_source'].startswith('inferred');a.update({'height_m':maximum,'height_evidence':'inferred_part_levels' if inferred else 'source_reported_part_height_unverified','height_source':'maximum part levels times configured3.5m' if inferred else 'maximum of explicit source building-part tops; not a whole-footprint extrusion','height_inferred':inferred});changes.append({'id':uid,'prior_height_m':old,'part_total_m':maximum,'reason':'explicit parts exceed parent envelope; interval-union massing retains stepped volumes'});stats['parent_envelopes_corrected_from_parts']+=1
  mins=[p['min_height_m'] for p in items if p['min_height_m']>0];a['parts']=items;a['podium_height_m']=min(mins) if mins else min([p['height_m'] for p in items]+[a['height_m']]);a['podium_basis']='explicit min heights or minimum part top; inferred allocation, interval unions avoid duplicate full bodies';db.execute('UPDATE buildings SET attrs=?,height=? WHERE i=?',(json.dumps(a,separators=(',',':')),a['height_m'],i));stats['buildings_with_parts']+=1
 db.commit();heights=collections.Counter();types=collections.Counter()
 for a, in db.execute('SELECT attrs FROM buildings WHERE active=1'):
  a=json.loads(a);heights[a['height_evidence']]+=1;types[a['building_type']]+=1
 db.close();osm.close();write_json(report,{'status':'executed','counts':dict(stats),'changes':changes,'sqlite_sha256':sha(path)});p=root/'work/reports/stage05/building_data.json';r=json.loads(p.read_text());r['initial_enrichment_sqlite_sha256']=r['sqlite_sha256'];r['sqlite_sha256']=sha(path);r['height_sources']=dict(heights);r['types']=dict(types);r['part_review']='work/reports/stage05/part_review.json';write_json(p,r);print('PART_REVIEW_COMPLETE',dict(stats),flush=True)
if __name__=='__main__':refine()
