"""Signals require explicit signal evidence, rather than the mere presence of a crossing."""
from pathlib import Path
import json,shutil
from pyproj import Transformer
from shapely.geometry import Point
from shapely.strtree import STRtree
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def verify(root=ROOT):
 o=json.loads((root/'data/processed/origin.json').read_text())['origin_utm_m'];tx=Transformer.from_crs(4326,32611,always_xy=True);points=[]
 for row in (root/'data/processed/stage04/source_nodes.jsonl').open():
  n=json.loads(row);t=n['tags']
  if t.get('highway')=='traffic_signals' or t.get('crossing')=='traffic_signals' or t.get('crossing:signals')=='yes':x,y=tx.transform(n['lon'],n['lat']);points.append(Point(x-o[0],y-o[1]))
 for p in (root/'data/raw/stage04/signals').glob('short_page_*.json'):
  if p.name.endswith('.receipt.json'):continue
  for f in json.loads(p.read_text())['features']:
   if f.get('geometry'):g=f['geometry'];x,y=tx.transform(g['x'],g['y']);points.append(Point(x-o[0],y-o[1]))
 tree=STRtree(points);jp=root/'work/reports/stage04/junctions.json';d=json.loads(jp.read_text());unknown=set()
 for j in d['junctions']:
  p=Point(j['xy_m']);dist=p.distance(points[int(tree.nearest(p))]);previous=j['signalized_evidence'];j['explicit_signal_evidence_distance_m']=dist;j['signalized_evidence']=dist<25;j['signal_presence_status']='observed_nearby_explicit_signal' if dist<25 else 'unverified_no_explicit_nearby_signal';j['markings_presence_status']='layout_inferred_not_individual_as_built_verification'
  if previous and dist>=25:unknown.add(j['node_id'])
 ip=root/'data/processed/stage04/mesh_index.json';idx=json.loads(ip.read_text());before=len(idx['instances']);idx['instances']=[i for i in idx['instances'] if not(i['kind']=='signal' and str(i['source']) in unknown)];d['signal_instances']=sum(i['kind']=='signal' for i in idx['instances']);write_json(ip,idx);write_json(jp,d);write_json(root/'work/reports/stage04/signal_evidence.json',{'status':'executed','junctions_without_explicit_signal_evidence':len(unknown),'unverified_pole_instances_omitted':before-len(idx['instances']),'modeled_signal_instances':d['signal_instances'],'rule':'OSM traffic_signals or explicit crossing signals tag, or official LADOT signal point within25m; ordinary uncontrolled crossing not sufficient','placement_geometry':'still inferred; no measured mast/arm geometry'});print('EXPLICIT_SIGNAL_EVIDENCE_VALIDATED',d['signal_instances'],before-len(idx['instances']),flush=True)
if __name__=='__main__':verify()
