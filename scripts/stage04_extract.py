"""Stream a licensed OSM PBF; preserve ways/nodes/tags and original node IDs."""
from pathlib import Path
import json,collections,time
import osmium
import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString,Point,box
from stage03_common import references,to_geographic
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def extract(root=ROOT):
 cfg,o,city,refs=references(root);boundary=city.buffer(100);tx=Transformer.from_crs(4326,32611,always_xy=True)
 bb=__import__('shapely').geometry.shape(to_geographic(boundary,o)).bounds
 target=root/'data/processed/stage04';target.mkdir(parents=True,exist_ok=True)
 source=root/'data/raw/stage04/osm/california-20261021.osm.pbf';reader=osmium.io.Reader(str(source));header=reader.header();meta={k:header.get(k) for k in ['osmosis_replication_timestamp','osmosis_replication_sequence_number','generator']};reader.close()
 counts=collections.Counter();tags_count=collections.Counter();start=time.monotonic()
 ways=open(target/'source_ways.jsonl','w');nodes=open(target/'source_nodes.jsonl','w')
 class Handler(osmium.SimpleHandler):
  def node(self,n):
   if not n.location.valid():return
   lon,lat=n.location.lon,n.location.lat
   if not (bb[0]<=lon<=bb[2] and bb[1]<=lat<=bb[3]):return
   tags=dict(n.tags)
   if not any(k in tags for k in ['highway','railway','public_transport','barrier']):return
   x,y=tx.transform(lon,lat);x-=o[0];y-=o[1]
   if not boundary.covers(Point(x,y)):return
   nodes.write(json.dumps({'id':n.id,'lon':lon,'lat':lat,'tags':tags,'version':n.version,'timestamp':str(n.timestamp)})+'\n');counts['selected_nodes']+=1
  def way(self,w):
   counts['candidate_ways_read']+=1;tags=dict(w.tags)
   if not any(k in tags for k in ['highway','railway','aeroway','barrier','public_transport']):return
   if len(w.nodes)<2:return
   if any(not n.location.valid() for n in w.nodes):counts['missing_node_locations']+=1;return
   xy=np.array([(n.lon,n.lat) for n in w.nodes])
   if xy[:,0].max()<bb[0] or xy[:,0].min()>bb[2] or xy[:,1].max()<bb[1] or xy[:,1].min()>bb[3]:return
   x,y=tx.transform(xy[:,0],xy[:,1]);local=np.column_stack([x-o[0],y-o[1]])
   line=LineString(local)
   if line.length<.01:counts['zero_length']+=1;return
   if not line.intersects(boundary):return
   record={'id':w.id,'node_ids':[n.ref for n in w.nodes],'lonlat':xy.tolist(),'tags':tags,'version':w.version,'timestamp':str(w.timestamp)}
   ways.write(json.dumps(record,separators=(',',':'))+'\n');counts['selected_ways']+=1
   for k in ['highway','railway','aeroway','bridge','tunnel','layer','oneway','lanes','width','barrier']:
    if k in tags:tags_count[k]+=1
 h=Handler();h.apply_file(str(source),locations=True,idx='flex_mem',filters=[osmium.filter.KeyFilter('highway','railway','aeroway','barrier','public_transport')])
 ways.close();nodes.close()
 report={'status':'extracted','pbf':str(source.relative_to(root)),'pbf_sha256':digest(source),'header':meta,'counts':dict(counts),'ways_with_tags':dict(tags_count),'seconds':time.monotonic()-start,'scope':'city polygon +100m context; selected original full ways preserved, final model clips exact administrative boundary','license':'OpenStreetMap contributors / ODbL1.0; derivative transportation database kept separate from Census/DEM','data_capture_year':'mixed/unknown; per-object timestamp is edit date, PBF timestamp is database state, neither is survey date','source_accuracy_m':None}
 write_json(root/'work/reports/stage04/osm_extract.json',report);print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':extract()
