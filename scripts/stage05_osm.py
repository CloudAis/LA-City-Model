"""Stream licensed OSM building areas (including relations), parts and entrances to SQLite."""
from pathlib import Path
import json,sqlite3,collections,time
import osmium,numpy as np,shapely
from shapely.geometry import Point,shape
from pyproj import Transformer
from stage03_common import references,to_geographic
from stage02_io import write_json
from stage05_preserve import sha
ROOT=Path(__file__).resolve().parents[1]
def extract(root=ROOT):
 output=root/'data/processed/stage05/osm_buildings.sqlite';report=root/'work/reports/stage05/osm_extract.json';pbf=root/'data/raw/stage04/osm/california-20261021.osm.pbf'
 if output.exists() and report.exists():
  d=json.loads(report.read_text());assert sha(output)==d['sqlite_sha256'];print('OSM_BUILDING_CACHE_VERIFIED',d['counts'],flush=True);return
 _,origin,city,refs=references(root);region=city.buffer(50);bbox=shape(to_geographic(region,origin)).bounds;tx=Transformer.from_crs(4326,32611,always_xy=True);wkb=osmium.geom.WKBFactory();pending=Path(str(output)+'.pending');pending.unlink(missing_ok=True);db=sqlite3.connect(pending)
 db.executescript('PRAGMA journal_mode=OFF;PRAGMA synchronous=OFF;CREATE TABLE features(i INTEGER PRIMARY KEY,uid TEXT UNIQUE,kind TEXT,geom BLOB,tags TEXT,edited TEXT,version INTEGER);CREATE VIRTUAL TABLE spatial USING rtree(i,minx,maxx,miny,maxy);CREATE TABLE nodes(uid TEXT PRIMARY KEY,x REAL,y REAL,tags TEXT,edited TEXT);CREATE TABLE relations(uid TEXT PRIMARY KEY,tags TEXT,members TEXT);');counts=collections.Counter();tagcounts=collections.Counter();start=time.monotonic()
 def local(g):return shapely.transform(g,lambda xy:np.column_stack(tx.transform(xy[:,0],xy[:,1]))-origin)
 class Handler(osmium.SimpleHandler):
  def area(self,a):
   tags=dict(a.tags)
   if not any(k in tags for k in ['building','building:part','demolished:building']):return
   rings=iter(a.outer_rings());first=next(rings,None)
   if first is None or not len(first):return
   p=first[0]
   if not p.location.valid() or not(bbox[0]-.01<=p.lon<=bbox[2]+.01 and bbox[1]-.01<=p.lat<=bbox[3]+.01):return
   try:g=local(shapely.from_wkb(wkb.create_multipolygon(a)))
   except Exception:counts['failed_area_geometry']+=1;return
   if not g.intersects(region):return
   if not g.is_valid:g=shapely.make_valid(g);counts['geometry_repaired']+=1
   if g.is_empty or g.area<1:return
   uid=('osm:way:' if a.from_way() else 'osm:relation:')+str(a.orig_id());kind='part' if tags.get('building:part') not in [None,'no'] else 'removed' if 'demolished:building' in tags else 'building';cur=db.execute('INSERT OR IGNORE INTO features(uid,kind,geom,tags,edited,version) VALUES(?,?,?,?,?,?)',(uid,kind,shapely.to_wkb(g),json.dumps(tags,separators=(',',':')),str(a.timestamp),a.version))
   if not cur.rowcount:return
   x0,y0,x1,y1=g.bounds;db.execute('INSERT INTO spatial VALUES(?,?,?,?,?)',(cur.lastrowid,x0,x1,y0,y1));counts[kind]+=1
   for k in ['height','building:levels','min_height','building:min_level','roof:height','roof:shape','building:material','building:colour','name','start_date']:
    if k in tags:tagcounts[k]+=1
   if sum(counts[k] for k in ['building','part','removed'])%5000==0:db.commit();print('OSM_BUILDING_AREAS',dict(counts),flush=True)
  def node(self,n):
   tags=dict(n.tags)
   if not ('entrance' in tags or tags.get('generator:location')=='roof' or tags.get('building') or tags.get('man_made')=='water_tank'):return
   if not n.location.valid():return
   if not(bbox[0]<=n.lon<=bbox[2] and bbox[1]<=n.lat<=bbox[3]):return
   x,y=tx.transform(n.lon,n.lat);x-=origin[0];y-=origin[1]
   if region.covers(Point(x,y)):db.execute('INSERT OR IGNORE INTO nodes VALUES(?,?,?,?,?)',('osm:node:'+str(n.id),x,y,json.dumps(tags),str(n.timestamp)));counts['nodes']+=1
  def relation(self,r):
   tags=dict(r.tags)
   if tags.get('type')=='building':db.execute('INSERT OR IGNORE INTO relations VALUES(?,?,?)',('osm:relation:'+str(r.id),json.dumps(tags),json.dumps([{'type':m.type,'ref':m.ref,'role':m.role} for m in r.members])));counts['building_relations']+=1
 keys=['building','building:part','entrance','roof:shape','building:levels','demolished:building','generator:location','man_made','type']
 Handler().apply_file(str(pbf),locations=True,idx='flex_mem',filters=[osmium.filter.KeyFilter(*keys)]);db.commit();db.close();pending.replace(output)
 reader=osmium.io.Reader(str(pbf));state=reader.header().get('osmosis_replication_timestamp');reader.close();d={'status':'executed','counts':dict(counts),'tag_counts':dict(tagcounts),'seconds':time.monotonic()-start,'sqlite_sha256':sha(output),'pbf_sha256':sha(pbf),'pbf_database_state_utc':state,'acquisition_year':'mixed/unknown; edit time is not capture year','source_crs':'EPSG:4326','working_crs':'EPSG:32611 plus fixed local XY origin','license':'©OpenStreetMap contributors / ODbL1.0','scope':'city +50m; raw PBF remains authoritative geographic input','multipolygons_and_courtyard_rings_preserved':True};write_json(report,d);print('OSM_BUILDING_EXTRACT_COMPLETE',json.dumps(d),flush=True)
if __name__=='__main__':extract()
