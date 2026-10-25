"""Idempotent non-road source extraction, independently validated against tags."""
from pathlib import Path
import json,collections
import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString
from stage04_data import classification
from stage03_common import references
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def extract(root=ROOT):
 _,o,city,_=references(root);tx=Transformer.from_crs(4326,32611,always_xy=True);other=[];count=collections.Counter()
 for row in (root/'data/processed/stage04/source_ways.jsonl').open():
  w=json.loads(row);t=w['tags']
  if classification(t) and t.get('area')!='yes':continue
  if not (t.get('railway') or t.get('aeroway') or t.get('public_transport')=='platform' or t.get('barrier') in ['guard_rail','noise_barrier']):continue
  xy=np.array(w['lonlat']);x,y=tx.transform(xy[:,0],xy[:,1]);g=LineString(np.column_stack([x-o[0],y-o[1]]))
  if g.intersection(city).length<.05:continue
  other.append({k:w[k] for k in ['id','node_ids','lonlat','tags'] }|{'id':'osm:way:'+str(w['id']),'source_id':w['id'],'edit_timestamp':w['timestamp']});count[t.get('railway',t.get('aeroway',t.get('barrier','platform')))]+=1
 write_json(root/'data/processed/stage04/other_transport.json',other);print('OTHER_TRANSPORT_VERIFIED',len(other),dict(count),flush=True)
if __name__=='__main__':extract()
