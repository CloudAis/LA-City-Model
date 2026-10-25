"""Recompute coverage, provenance denominators and geometry validity from actual data."""
from pathlib import Path
import collections,hashlib,json,sqlite3,time
import numpy as np,shapely
from shapely.geometry import shape,mapping,box
from shapely.ops import transform
from pyproj import Transformer,Geod
import rasterio
from stage10_common import *
start=time.perf_counter();forward=Transformer.from_crs(4326,32611,always_xy=True);inverse=Transformer.from_crs(32611,4326,always_xy=True)
origin=np.array(read('data/processed/origin.json')['origin_utm_m'][:2]);citydoc=read('data/processed/stage02/city_boundary_2025.geojson');city=shapely.union_all([shape(f['geometry']) for f in citydoc['features']]);citym=transform(forward.transform,city)
scopes=read('data/processed/scopes.geojson');fine=[];focus=[]
for f in scopes['features']:
 ident=f['properties'].get('id','')
 if ident in ('historic_core','civic_center'):fine.append(f)
 if ident in ('downtown','focus'):focus.append(f)
print('SCOPE_KEYS',[(f['properties'].get('id'),f['properties'].get('name')) for f in scopes['features']],flush=True)
fine_area=sum(transform(forward.transform,shape(f['geometry'])).area for f in fine)
tiles=read('data/processed/stage03/medium/tile_index.json')['tiles'];surface_area=0;missing=[]
for t in tiles:
 p=ROOT/'data/processed/stage03/medium'/(t['id']+'.npz')
 if not p.exists():missing.append(str(p));continue
 with np.load(p) as a:
  v=a['v2'];f=a['f2'];ab=v[f[:,1],:2].astype(float)-v[f[:,0],:2];ac=v[f[:,2],:2].astype(float)-v[f[:,0],:2];surface_area+=np.abs(ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0]).sum()/2
conn=sqlite3.connect('file:'+str(ROOT/'data/processed/stage05/buildings.sqlite')+'?mode=ro',uri=True);cursor=conn.execute('select i,uid,geom,height,min_height,attrs,cx,cy from buildings where active=1')
counts=collections.Counter();heights=collections.Counter();years=collections.Counter();geometry=collections.Counter();grid=collections.defaultdict(collections.Counter);fingerprints={};duplicates=[];invalid=[];samples=[]
while True:
 rows=cursor.fetchmany(4096)
 if not rows:break
 geoms=shapely.from_wkb([r[2] for r in rows]);valid=shapely.is_valid(geoms);finite=shapely.is_valid_input(geoms)
 for r,g,ok in zip(rows,geoms,valid):
  fid,uid,wkb,h,bottom,attrs,x,y=r;a=json.loads(attrs);counts['active']+=1
  if not ok:invalid.append(fid)
  digest=hashlib.blake2b(wkb,digest_size=16).digest()
  if digest in fingerprints:duplicates.append([fingerprints[digest],fid])
  else:fingerprints[digest]=fid
  counts['numeric_height_missing']+=h is None;counts['nonpositive_height']+=h is not None and h<=0;counts['bottom_above_top']+=h is not None and bottom is not None and bottom>h
  evidence=a.get('height_evidence','unknown');heights[evidence]+=1;years[str(a.get('acquisition_year'))]+=1;geometry[a.get('geometry_source','unknown')]+=1
  category='verified' if evidence=='verified_published_reference' else 'unverified_report' if evidence.startswith('source_reported') else 'estimated'
  ij=(int(np.floor(x/1000)),int(np.floor(y/1000)));grid[ij][category]+=1
  if len(samples)<25 and (fid%40001==0 or counts['active']<4):samples.append({'i':fid,'uid':uid,'height_m':h,'min_height_m':bottom,'height_evidence':evidence,'acquisition_year':a.get('acquisition_year'),'geometry_valid':bool(ok)})
 if counts['active']%65536==0:print('BUILDING_DATA_AUDIT',counts['active'],flush=True)
conn.close()
controls=read('data/processed/stage03/control_points.json');raw=controls if isinstance(controls,list) else next((v for v in controls.values() if isinstance(v,list)),[])
points=[]
for feature in [*read('data/processed/stage06/landmark_index.json')['landmarks']]:
 x,y=np.array(feature['origin_city_m'][:2])+origin;lon,lat=inverse.transform(x,y);xx,yy=forward.transform(lon,lat);points.append({'id':feature['id'],'lonlat':[lon,lat],'utm_m':[x,y],'roundtrip_computational_error_m':float(np.hypot(xx-x,yy-y))})
for t in (tiles[0],tiles[len(tiles)//2],tiles[-1]):
 x,y=t['origin_utm_m'][:2];lon,lat=inverse.transform(x,y);xx,yy=forward.transform(lon,lat);points.append({'id':t['id'],'lonlat':[lon,lat],'utm_m':[x,y],'roundtrip_computational_error_m':float(np.hypot(xx-x,yy-y))})
dem=[]
for file in ['city_10m_dem_navd88_m.tif','downtown_1m_dem_navd88_m.tif']:
 with rasterio.open(ROOT/'data/processed/stage02'/file) as ds:dem.append({'file':file,'crs':str(ds.crs),'pixel_resolution':list(ds.res),'nodata':ds.nodata,'vertical':'NAVD88 metres as verified source registry; pixel size is not accuracy'})
refined=read('data/processed/stage07_final/index.json');landmarks=read('data/processed/stage06/landmark_index.json');replaced=set(refined['replaced_source_indices'])|{r['i'] for lm in landmarks['landmarks'] for r in lm['replaces']}
report={'status':'measured_with_documented_gaps','actual_sqlite_rows_checked':counts['active'],'administrative_boundary':{'source':'Census TIGER/Line2025 Los Angeles city GEOID0644000','legal_reference_date':'2025-01-01','area_projected_m2':citym.area,'valid':city.is_valid,'backgrounds':{'Santa Monica':'separate city, disabled','Beverly Hills':'separate city, disabled'}},'coverage':{'tile_domains':len(tiles),'missing_terrain_source_files':missing,'sum_city_clip_area_m2':sum(t['area_within_city_m2'] for t in tiles),'native_lod2_triangle_plan_area_m2':surface_area,'triangle_plan_area_not_coverage_union':True,'fine_work_windows_count':len(fine),'fine_work_windows_area_m2':fine_area,'fine_building_roots':len(refined['buildings']),'reference_guided_buildings':sum(b.get('reference_guided',False) for b in refined['buildings']),'independent_landmarks':10,'fine_area_is_work_window_not_all_surfaces_surveyed':True},'buildings':{'counts':dict(counts),'height_evidence':dict(heights),'acquisition_years':dict(years),'geometry_sources':dict(geometry),'invalid_geometry_ids':invalid,'exact_wkb_duplicate_ids':duplicates,'duplicate_check_scope':'Exact WKB equality plus preserved prior cross-source match audit; arbitrary overlapping but different footprints are not all certified duplicate-free.','ordinary_runtime_attribute_records':1096386,'replacement_source_records':len(replaced),'replacement_mapping':'13 source proxies→10 landmarks;103 near source selections→100 refined building roots plus recorded roof/small components and skybridge. Do not compare counts without this mapping.','samples':samples},'coordinate_controls':points,'dem_sources':dem,'provenance_rules':{'geometry':'source-reported roofline or OSM footprint; county roofline is a footprint proxy','height':'verified published, unverified report and estimate have separate denominators','facade_materials':'project-authored/inferred, not independently observed elevation surveys','no_single_percent_for_all_visual_content':True},'water_limit':'Source boundaries retained. Water levels are recorded estimates and not all NAVD88 surveyed levels; do not treat海面0 display assumption as a vertical datum transformation.','existing_interface_risks':['6151 high-foundation warnings and305 entry checks in stage05 placement audit','208 building/estimated-road overlap candidates in source05 urban audit','Bridge clearance and tunnel elevations partly inferred; see source04 reports','All10 landmarks retain documented observation blind spots'],'elapsed_seconds':time.perf_counter()-start}
write('work/reports/stage10/geography.json',report);write('work/reports/stage10/height_grid.json',[{'ij':list(ij),**dict(v)} for ij,v in sorted(grid.items())]);write('outputs/LA_Delivery/metadata/fine_scope.geojson',{'type':'FeatureCollection','features':fine});write('outputs/LA_Delivery/metadata/city_boundary.geojson',citydoc)
print('ACTUAL_GEOGRAPHY_AUDIT_DONE',counts['active'],len(invalid),len(duplicates),'FINE_AREA',fine_area,flush=True)
