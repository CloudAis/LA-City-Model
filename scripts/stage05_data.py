"""Canonical footprints, transparent height interpretation, OSM correspondences and parts."""
from pathlib import Path
import json,sqlite3,math,time,collections,shutil,re,hashlib
import numpy as np,shapely,yaml
from shapely.geometry import Point
from shapely.strtree import STRtree
from pyproj import Transformer
from stage02_dataset import iter_model_buildings
from stage03_common import references,polygon_parts
from stage02_io import write_json
from stage05_preserve import sha
ROOT=Path(__file__).resolve().parents[1]
def number(value):
 if value is None:return None
 s=str(value).strip().lower().replace(',','')
 if any(c in s for c in [';','|','~']):return None
 feet=re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*'\s*([0-9]+(?:\.[0-9]+)?)?\s*\"?",s)
 if feet:return float(feet[1])*.3048+float(feet[2] or 0)*.0254
 m=re.fullmatch(r'(-?[0-9]+(?:\.[0-9]+)?)\s*(m|metres?|meters?|ft|feet|foot)?',s)
 if not m:return None
 return float(m[1])*(.3048 if m[2] in ['ft','feet','foot'] else 1)
def cell(g,visual):
 p=g.centroid;size=125 if visual==2 else 250 if visual==1 else 1000;ix,iy=math.floor(p.x/size),math.floor(p.y/size)
 return f's{size}_x{ix:+05d}_y{iy:+05d}',[ix*size,iy*size,0],size
def import_primary(root=ROOT):
 path=root/'work/cache/stage05/primary.sqlite';receipt=root/'work/reports/stage05/primary_import.json';source=root/'data/processed/stage02/buildings.geojsonl.gz'
 if not path.exists() and Path(str(path)+'.zst').exists():
  import subprocess
  subprocess.run(['zstd','-d','--quiet',str(path)+'.zst','-o',str(path)],check=True)
 if path.exists() and receipt.exists():
  r=json.loads(receipt.read_text());assert r['source_sha256']==sha(source) and r['sqlite_sha256']==sha(path);print('PRIMARY_FOOTPRINT_CACHE_VERIFIED',flush=True);return path
 _,origin,city,refs=references(root);tx=Transformer.from_crs(4326,32611,always_xy=True);pending=Path(str(path)+'.pending');pending.unlink(missing_ok=True);db=sqlite3.connect(pending)
 db.executescript('PRAGMA journal_mode=OFF;PRAGMA synchronous=OFF;CREATE TABLE buildings(i INTEGER PRIMARY KEY,uid TEXT UNIQUE,geom BLOB,attrs TEXT,cell TEXT,cx REAL,cy REAL,height REAL,min_height REAL,visual INTEGER,active INTEGER DEFAULT 1);CREATE VIRTUAL TABLE spatial USING rtree(i,minx,maxx,miny,maxy);CREATE INDEX by_cell ON buildings(cell);');stats=collections.Counter();start=time.monotonic()
 for i,f in enumerate(iter_model_buildings(root),1):
  p=f['properties'];g=shapely.transform(shapely.geometry.shape(f['geometry']),lambda xy:np.column_stack(tx.transform(xy[:,0],xy[:,1]))-origin)
  if not g.is_valid:g=shapely.make_valid(g);stats['projection_geometry_repaired']+=1
  parts=polygon_parts(g);g=shapely.MultiPolygon(parts);visual=2 if any(g.intersects(refs[k]) for k in ['historic_core','civic_center']) else 1 if g.intersects(refs['downtown']) else 0;region=['city']+(['downtown'] if visual else [])+[k for k in ['historic_core','civic_center'] if visual==2 and g.intersects(refs[k])];owner,_,_=cell(g,visual)
  a={k:p.get(k) for k in ['source_id','original_id','acquisition_year','geometry_source','source_HEIGHT','source_ELEV','height_candidate_m','boundary_crossing','source_imagery']};a.update({'id':p['id'],'geometry_role':'observed_stereo_roofline_used_as_footprint_proxy','regions':region,'parts':[],'data_class':'processed_observed_geometry_with_separate_inferred_attributes'});cx,cy=g.centroid.coords[0];cur=db.execute('INSERT INTO buildings VALUES(?,?,?,?,?,?,?,?,?,?,1)',(i,p['id'],shapely.to_wkb(g),json.dumps(a,separators=(',',':')),owner,cx,cy,None,None,visual));x0,y0,x1,y1=g.bounds;db.execute('INSERT INTO spatial VALUES(?,?,?,?,?)',(i,x0,x1,y0,y1));stats['buildings']+=1;stats['holes']+=sum(len(x.interiors) for x in parts);stats['multiple_components']+=len(parts)>1;stats[['city_overview','downtown','closeup'][visual]]+=1
  if i%20000==0:db.commit();print('PRIMARY_FOOTPRINTS_IMPORTED',i,flush=True)
 db.commit();db.close();pending.replace(path);write_json(receipt,{'status':'executed','counts':dict(stats),'seconds':time.monotonic()-start,'source_sha256':sha(source),'sqlite_sha256':sha(path),'raw_data_modified':False,'rooflines_are_not_verified_ground_wall_footprints':True});print('PRIMARY_FOOTPRINT_IMPORT_COMPLETE',dict(stats),flush=True);return path
def classify(tags,height,area):
 b=tags.get('building','');am=tags.get('amenity','');start=number(tags.get('start_date'))
 if b=='tower' and tags.get('building:use')=='office':b='office'
 if am in ['hospital','clinic'] or b=='hospital':return 'hospital_public','explicit_building_or_amenity_tag'
 if am in ['school','college','university','kindergarten'] or b in ['school','university','college','kindergarten']:return 'school_campus','explicit_building_or_amenity_tag'
 if b=='parking' or tags.get('parking')=='multi-storey':return 'parking_structure','explicit_parking_tag'
 if tags.get('building:material') in ['brick','stone'] and (tags.get('heritage') or start and start<1940):return 'historic_masonry','material_plus_explicit_heritage_or_building_age'
 if b in ['warehouse','industrial'] or tags.get('industrial'):return 'industrial_warehouse','explicit_building_or_industrial_tag'
 if b in ['apartments','residential'] and tags.get('shop'):return 'mixed_use_apartment','residential_plus_shop_tag'
 if b in ['apartments','dormitory','residential','terrace','semidetached_house']:return 'multifamily_residential','explicit_residential_building_tag'
 if b in ['house','detached','bungalow','cabin','static_caravan']:return 'detached_house','explicit_house_tag'
 if b in ['garage','garages','shed','outbuilding','carport','roof']:return 'garage_outbuilding','explicit_small_structure_tag'
 if b in ['retail','supermarket','commercial','kiosk'] or tags.get('shop'):return 'commercial_shop','explicit_commercial_or_shop_tag'
 if b in ['office','hotel'] or tags.get('office'):return ('office_highrise' if height>=35 else 'mixed_use_apartment'),'explicit_office_or_hotel_tag_generic_facade_approximation'
 return ('unclassified_tall' if height>=35 else 'unclassified_lowrise'),'unclassified_no_neighborhood_style_assumption'
def reference_overrides(root):
 refs={};p=root/'data/processed/stage05/research/us_bank_property.txt'
 if p.exists() and '1,018 feet' in p.read_text():refs['lariac6:484605841062']={'name':'U.S. Bank Tower','total_m':1018*.3048,'roof_m':1018*.3048,'source':'data/raw/stage05/research/us_bank_property.html','definition':'published overall tower height; rounded feet, roof/top proxy at this stage','quote':'Soaring 1,018 feet high','accuracy_m':None,'lonlat':[-118.25432956,34.05107169]}
 p=root/'data/processed/stage05/research/wilshire_grand_engineer.txt'
 if p.exists() and '1,100-foot' in p.read_text():refs['lariac6:201700195459']={'name':'Wilshire Grand Center','total_m':1100*.3048,'roof_m':None,'source':'data/raw/stage05/research/wilshire_grand_engineer.html','definition':'published overall height, not full-footprint roof-plane height','quote':'the 1,100-foot Wilshire Grand','accuracy_m':None,'spire':True,'lonlat':[-118.26044041,34.05013150]}
 write_json(root/'data/processed/stage05/verified_height_references.json',{'references':refs,'published_heights_are_not_independent_survey_control':True});return refs
def attributes(raw,tags,cfg,reference=None):
 cand=raw.get('height_candidate_m');cand=float(cand) if cand is not None else None;limits=cfg['height']['valid_relative_range_m'];observed=number(tags.get('height'));levels=number(tags.get('building:levels'));pre=observed if observed and limits[0]<=observed<=limits[1] else cand if cand and limits[0]<=cand<=limits[1] else 6.4;kind,basis=classify(tags,pre,0);typ=cfg['types'][kind];method='inferred_type';height=typ['floor_m']*typ['default_levels'];source='config/stage05.yaml';warnings=[]
 if cand and limits[0]<=cand<=limits[1]:height=cand;method='inferred_official_field_interpretation';source='LARIAC HEIGHT times US-survey-foot hypothesis; field definition remains unverified'
 if levels and 0<levels<=110:height=levels*typ['floor_m'];method='inferred_levels';source='OSM building:levels times configured use-specific storey height'
 if observed and limits[0]<=observed<=limits[1]:
  height=observed;method='source_reported_unverified';source='OSM explicit height tag; defined units but not independently measured'
  if tags.get('lacounty:bld_id'):
   method='source_reported_county_import_unverified';source='OSM height with lacounty:bld_id; likely shares county lineage, not an independent height measurement'
  if cand and cand>=80 and observed/cand>cfg['height']['maximum_reference_roof_height_ratio_for_unqualified_osm_total']:
   height=cand;method='inferred_official_field_interpretation';source='roofline candidate retained because unqualified OSM total may include a narrow spire';warnings.append('OSM_height_disagrees_with_roof_candidate; requires individual research')
 if reference:
  if reference['roof_m'] is not None:height=reference['roof_m'];method='verified_published_reference';source=reference['source']
  elif reference.get('spire'):
   # A published architectural tip cannot inflate the entire footprint to the spire height.
   height=cand if cand and 0<cand<reference['total_m'] else height;method='inferred_official_field_interpretation';source='LARIAC roof candidate; published tip is modeled separately and explicitly';warnings.append('spire_position_and_profile_approximate; roof_plane_not_officially_verified')
  raw['name']=reference['name']
 kind,basis=classify(tags,height,0)
 if kind in ['detached_house','garage_outbuilding'] and height>cfg['height'].get('type_review_threshold_m',24):
  raw['original_type_before_height_conflict']=kind;raw['height_type_review_required']=True;warnings.append('height_and_small_structure_type_conflict; source units/height/use require review')
  if method=='inferred_official_field_interpretation':
   raw['rejected_unverified_height_candidate_m']=height;height=cfg['types'][kind]['floor_m']*cfg['types'][kind]['default_levels'];method='inferred_type';source='configured type estimate; anomalous unverified county HEIGHT candidate withheld, actual height unknown';warnings.append('candidate_not_a_verified_building_height; no replacement survey accuracy claimed')
  elif height>=cfg['height'].get('reported_height_type_conflict_reclassify_m',35):kind='unclassified_tall';basis='reported_height_conflicts_with_imported_small_structure_tag; neutral unknown use, height retained'
 typ=cfg['types'][kind];roof=tags.get('roof:shape') or typ['roof'];roof_source='OSM roof:shape' if tags.get('roof:shape') else 'inferred_type_default_not_observed';rh=number(tags.get('roof:height'))
 if roof in ['flat','terrace']:rh=0.
 elif rh is None:rh=min(cfg['geometry']['roof_height_default_m'],height*cfg['geometry']['roof_height_ratio_max'])
 rh=max(0,min(rh or 0,height*.8));minimum=number(tags.get('min_height'))
 if minimum is None:minimum=(number(tags.get('building:min_level')) or 0)*typ['floor_m']
 if minimum<0 or minimum>=height:warnings.append('invalid_min_height_ignored');minimum=0
 imported_ids=str(tags.get('lacounty:bld_id','')).split(';')
 if imported_ids!=[''] and str(raw.get('original_id')) not in imported_ids:warnings.append('OSM_county_id_differs_from_primary; geometry_match_only')
 raw.update({'height_m':float(height),'height_evidence':method,'height_source':source,'height_numeric_accuracy_m':None,'height_inferred':method.startswith('inferred'),'minimum_height_m':float(minimum),'min_height_source':'OSM min_height or min_level' if 'min_height' in tags or 'building:min_level' in tags else 'inferred_default_zero','levels':levels or max(1,int(round((height-rh)/typ['floor_m']))),'levels_source':'OSM building:levels' if levels else 'inferred_from_height_and_type','building_type':kind,'type_basis':basis,'roof_shape':roof,'roof_shape_source':roof_source,'roof_height_m':rh,'roof_height_source':'OSM roof:height' if 'roof:height' in tags else 'inferred_roof_type_ratio','tags':tags,'warnings':warnings,'appearance_evidence':'tagged material/colour where present; grid/doors/equipment otherwise inferred visual modules','reference':reference,'OSM_county_lineage_not_independent':bool(tags.get('lacounty:bld_id'))})
 if tags.get('name') and not raw.get('name'):raw['name']=tags['name']
 return raw
def enrich(root=ROOT):
 primary=import_primary(root);osm=root/'data/processed/stage05/osm_buildings.sqlite';assert osm.exists(),'OSM extraction has not completed';out=root/'data/processed/stage05/buildings.sqlite';report=root/'work/reports/stage05/building_data.json'
 if out.exists() and report.exists():
  r=json.loads(report.read_text());assert sha(out)==r['sqlite_sha256'];print('BUILDING_DATA_CACHE_VERIFIED',r['active_buildings'],flush=True);return out
 cfg=yaml.safe_load((root/'config/stage05.yaml').read_text());_,origin,city,regions=references(root);refs=reference_overrides(root);sdb=sqlite3.connect(osm);pending=Path(str(out)+'.pending');pending.unlink(missing_ok=True);shutil.copy2(primary,pending);db=sqlite3.connect(pending);db.execute('PRAGMA synchronous=OFF');db.execute('PRAGMA journal_mode=OFF');stats=collections.Counter();heights=collections.Counter();types=collections.Counter();matched=set();changes=[]
 # Generic yes-only polygons add no height/type evidence; keep the entire OSM database for unmatched-footprint checks.
 interesting=[]
 for row in sdb.execute('SELECT i,uid,kind,geom,tags FROM features'):
  tags=json.loads(row[4])
  if row[2]=='building' and tags.get('building')=='no':continue
  if row[2]!='building' or any(k in tags for k in ['height','building:levels','roof:shape','roof:height','building:material','name','amenity','shop','office','industrial']) or tags.get('building') not in ['yes',None]:interesting.append((row[0],row[1],row[2],shapely.from_wkb(row[3]),tags))
 geoms=[r[3] for r in interesting];tree=STRtree(geoms);start=time.monotonic();allrows=db.execute('SELECT i,uid,geom,attrs,visual FROM buildings').fetchall();print('OSM_INFORMATIVE_BUILDING_FEATURES',len(interesting),flush=True)
 def finalize(row,tags,match,parts,reference):
  index,uid,g,raw,visual=row;raw=attributes(raw,tags,cfg,reference);raw['osm_match']=match;raw['parts']=parts
  if parts:
   explicit_mins=[p['min_height_m'] for p in parts if p['min_height_m']>0];raw['podium_height_m']=min(explicit_mins) if explicit_mins else min([p['height_m'] for p in parts]+[raw['height_m']]);raw['podium_basis']='explicit part min_height or minimum observed part top; partitioned union avoids overlapping full bodies'
  db.execute('UPDATE buildings SET attrs=?,height=?,min_height=? WHERE i=?',(json.dumps(raw,separators=(',',':')),raw['height_m'],raw['minimum_height_m'],index));heights[raw['height_evidence']]+=1;types[raw['building_type']]+=1
 for index,uid,wkb,astr,visual in allrows:
  g=shapely.from_wkb(wkb);raw=json.loads(astr);best=None;bestscore=0;parts=[];dead=None
  for j in tree.query(g,predicate='intersects'):
   src=interesting[int(j)];other=src[3];inter=g.intersection(other).area
   if inter<=.01:continue
   if src[2]=='part':
    if inter/other.area>=cfg['geometry']['part_min_inside_ratio']:
     h=number(src[4].get('height'));minimum=number(src[4].get('min_height'));pl=number(src[4].get('building:levels'));h=h or (pl*3.5 if pl else None)
     if h and 0<h<420:
      minimum=minimum if minimum is not None else (number(src[4].get('building:min_level')) or 0)*3.5
      if minimum<h:parts.append({'id':src[1],'geometry_wkb_hex':shapely.to_wkb(other.intersection(g)).hex(),'height_m':h,'min_height_m':minimum,'height_source':'OSM explicit part height' if src[4].get('height') else 'inferred_part_levels_times3.5m','tags':src[4]})
   elif src[2]=='removed':
    if inter/g.area>.8:dead=src
   else:
    score=inter/(g.area+other.area-inter)
    if score>bestscore:bestscore=score;best=src
  if dead and bestscore<.2 and uid not in refs:
   db.execute('UPDATE buildings SET active=0 WHERE i=?',(index,));stats['old_footprints_suppressed_explicit_OSM_demolition']+=1;changes.append({'id':uid,'evidence':dead[1],'event':'OSM explicitly marks removed building; capture/demolition date unknown','original_footprint_retained':True});continue
  tags={};match=None
  if bestscore>=cfg['geometry']['match_min_iou']:
   tags=best[4];matched.add(best[0]);match={'id':best[1],'footprint_iou':bestscore,'selection':'primary official roofline retained; OSM tags transferred after overlap threshold'};stats['tag_matches']+=1
  finalize((index,uid,g,raw,visual),tags,match,parts,refs.get(uid));stats['primary_active']+=1;stats['buildings_with_parts']+=bool(parts)
  if index%10000==0:db.commit();print('BUILDINGS_ENRICHED',index,flush=True)
 del allrows
 db.commit();nexti=db.execute('SELECT max(i) FROM buildings').fetchone()[0]+1
 for oi,uid,kind,wkb,tagstring in sdb.execute("SELECT i,uid,kind,geom,tags FROM features WHERE kind='building'"):
  if json.loads(tagstring).get('building')=='no':continue
  if oi in matched:continue
  g=shapely.from_wkb(wkb)
  if not g.intersects(city):continue
  g=g.intersection(city)
  if g.area<cfg['geometry']['add_unmatched_osm_min_area_m2']:continue
  x0,y0,x1,y1=g.bounds;candidates=db.execute('SELECT b.geom FROM spatial s JOIN buildings b ON b.i=s.i WHERE s.minx<=? AND s.maxx>=? AND s.miny<=? AND s.maxy>=? AND b.active=1',(x1,x0,y1,y0)).fetchall();overlap=sum(g.intersection(shapely.from_wkb(r[0])).area for r in candidates)
  if overlap/g.area>cfg['geometry']['add_unmatched_osm_max_overlap_ratio']:stats['OSM_existing_or_conflicting_not_duplicated']+=1;continue
  tags=json.loads(tagstring);visual=2 if any(g.intersects(regions[k]) for k in ['historic_core','civic_center']) else 1 if g.intersects(regions['downtown']) else 0;region=['city']+(['downtown'] if visual else [])+[k for k in ['historic_core','civic_center'] if visual==2 and g.intersects(regions[k])];owner,_,_=cell(g,visual);cx,cy=g.centroid.coords[0];raw={'id':uid,'source_id':'OSM PBF2026-10-20','geometry_source':'OSM selected nonoverlapping additional building footprint','acquisition_year':None,'height_candidate_m':None,'geometry_role':'source_reported_building_polygon','regions':region,'parts':[],'data_class':'processed_observed_geometry_with_separate_inferred_attributes'}
  db.execute('INSERT INTO buildings VALUES(?,?,?,?,?,?,?,?,?,?,1)',(nexti,uid,shapely.to_wkb(g),json.dumps(raw),owner,cx,cy,None,None,visual));db.execute('INSERT INTO spatial VALUES(?,?,?,?,?)',(nexti,x0,x1,y0,y1));finalize((nexti,uid,g,raw,visual),tags,{'id':uid,'footprint_iou':1.0,'selection':'nonoverlapping supplementary source geometry'},[],None);nexti+=1;stats['nonoverlapping_OSM_additions']+=1
  if stats['nonoverlapping_OSM_additions']%1000==0:db.commit();print('ADDITIONAL_BUILDINGS',stats['nonoverlapping_OSM_additions'],flush=True)
 db.commit();active=db.execute('SELECT count(*) FROM buildings WHERE active=1').fetchone()[0];db.execute('CREATE INDEX by_visual ON buildings(visual)');db.close();sdb.close();pending.replace(out);write_json(root/'data/processed/stage05/temporal_corrections.json',{'changes':changes,'mixed_city_dates_not_a_single_capture':True});write_json(report,{'status':'executed','active_buildings':active,'counts':dict(stats),'height_sources':dict(heights),'types':dict(types),'sqlite_sha256':sha(out),'seconds':time.monotonic()-start,'height_randomization_used':False,'source_HEIGHT_definition_verified':False,'source_ELEV_used_as_absolute_height':False,'OSM_match_threshold_iou':cfg['geometry']['match_min_iou'],'original_primary_records_retained':True});print('BUILDING_STANDARD_DATA_COMPLETE',active,dict(heights),flush=True);return out
if __name__=='__main__':
 import sys
 import_primary() if '--primary-only' in sys.argv else enrich()
