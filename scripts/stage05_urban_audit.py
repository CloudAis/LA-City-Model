"""Audit footprint setbacks against the actual inherited inferred pavement mask.

Do not move source buildings or roads to conceal a disagreement. Roof overhangs,
age mismatch and estimated widths can all produce intersections.
"""
from pathlib import Path
import json,gzip,sqlite3,collections,numpy as np,shapely
from shapely.geometry import box
from stage03_common import local_features
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def audit(root=ROOT):
 root=Path(root);index=json.loads((root/'data/processed/stage05/mesh_index.json').read_text());asphalt=next(g for f,g in local_features(root,'data/processed/stage04/downtown_surface_masks.geojson') if f['properties']['id']=='asphalt');db=sqlite3.connect(root/'data/processed/stage05/buildings.sqlite');cells={};warnings=[];distances=[];counts=collections.Counter();entry_sources=collections.Counter()
 for cell in index['cells']:
  if not cell.get('placements'):continue
  if not any(m['visual_level'] for m in cell['meshes']):continue
  with gzip.open(root/cell['placements'],'rt') as f:placements=json.load(f)['placements']
  for r in placements:
   if not r['built'] or not r['visual_level']:continue
   geom,a=db.execute('SELECT geom,attrs FROM buildings WHERE i=?',(r['i'],)).fetchone();g=shapely.from_wkb(geom);a=json.loads(a);bounds=g.bounds;key=tuple(np.floor(np.array([g.centroid.x,g.centroid.y])/250).astype(int))
   if key not in cells:cells[key]=asphalt.intersection(box(key[0]*250-300,key[1]*250-300,(key[0]+1)*250+300,(key[1]+1)*250+300))
   road=cells[key];overlap=g.intersection(road).area;distance=g.distance(road);distances.append(distance);counts['downtown_buildings']+=1
   if overlap>1 and overlap/g.area>.01:
    warnings.append({'id':r['id'],'overlap_area_m2':overlap,'footprint_area_ratio':overlap/g.area,'minimum_height_m':a['minimum_height_m'],'cause':'unresolved roofline proxy / inferred road width / mixed vintage; not automatically a building location error','source_xy_moved':False})
   if r.get('entrance'):entry_sources['tagged_OSM_node' if str(r['entrance']['source']).startswith('osm:node:') else 'inferred']+=1
 write_json(root/'work/reports/stage05/urban_interface_audit.json',{'status':'executed_with_warnings','counts':dict(counts),'source_footprint_to_inferred_asphalt_distance_p00_p50_p95_m':np.percentile(distances,[0,50,95]).tolist(),'building_pavement_overlap_warning_count':len(warnings),'overlaps':warnings,'entry_position_sources':dict(entry_sources),'model_positions_changed_to_hide_conflicts':False,'parking_and_service_space':'source footprints/roads retained; full parking stall/parcel validation and driveway access unresolved','not_an_as_built_setback_certification':True});db.close();print('DOWNTOWN_URBAN_INTERFACE_AUDITED',counts['downtown_buildings'],len(warnings),dict(entry_sources),flush=True)
if __name__=='__main__':audit()
