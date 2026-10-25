"""Check actual building geometries against the active administrative polygon."""
import sqlite3,collections
import numpy as np,shapely
from shapely.geometry import shape
from shapely.ops import transform
from shapely.affinity import translate
from pyproj import Transformer
from stage10_common import *
transformer=Transformer.from_crs(4326,32611,always_xy=True);origin=read('data/processed/origin.json')['origin_utm_m'];city=shapely.union_all([transform(transformer.transform,shape(f['geometry'])) for f in read('data/processed/stage02/city_boundary_2025.geojson')['features']]);city=translate(city,xoff=-origin[0],yoff=-origin[1]);shapely.prepare(city)
conn=sqlite3.connect('file:'+str(ROOT/'data/processed/stage05/buildings.sqlite')+'?mode=ro',uri=True);cursor=conn.execute('select i,geom,cx,cy from buildings where active=1');outside=[];centers=0;crossings=0;count=0
while True:
 rows=cursor.fetchmany(4096)
 if not rows:break
 geometries=shapely.from_wkb([r[1] for r in rows]);intersects=shapely.intersects(city,geometries);covered=shapely.covers(city,geometries);inside_centers=shapely.covers(city,shapely.points([[r[2],r[3]] for r in rows]));count+=len(rows);centers+=int((~inside_centers).sum());crossings+=int((intersects&~covered).sum());outside.extend(r[0] for r,inside in zip(rows,intersects) if not inside)
conn.close();write('work/reports/stage10/administrative_scope_check.json',{'status':'passed' if not outside else 'scope_correction_required','actual_active_building_geometries_checked':count,'nonintersecting_building_ids':outside,'centroids_outside_but_intersecting_boundary_or_source_geometry':centers,'boundary_crossing_geometries':crossings,'policy':'A whole building that intersects the administrative boundary is retained once. Its parts may extend outside; this does not add a neighboring background city. Nonintersecting buildings require correction.','backgrounds_enabled':[]});print('ACTUAL_ADMINISTRATIVE_SCOPE',count,'NONINTERSECTING',len(outside),'CROSSING',crossings,flush=True)
