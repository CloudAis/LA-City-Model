"""Geographic coverage grid; actual data presentation is in stage02_presentation.py."""
import json
import math
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parents[1]/'work/cache/matplotlib'))
os.environ['XDG_CACHE_HOME']=str(Path(__file__).resolve().parents[1]/'work/cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from pyproj import Transformer
from shapely.geometry import shape, mapping, box
from shapely.ops import transform
from shapely.strtree import STRtree

from stage02_io import write_json


def lines(g):
    if g.geom_type in ['LineString','LinearRing']:return [list(g.coords)]
    if g.geom_type=='Polygon':return [list(g.exterior.coords),*[list(r.coords) for r in g.interiors]]
    return [line for p in getattr(g,'geoms',[]) for line in lines(p)]


def prepare(root,cfg,quality):
    base=root/'data/processed/stage02';preview=root/'work/previews/stage02';preview.mkdir(parents=True,exist_ok=True)
    tx=Transformer.from_crs(4326,32611,always_xy=True);inv=Transformer.from_crs(32611,4326,always_xy=True)
    origin=json.loads((root/cfg['origin_file']).read_text())['origin_utm_m']
    scopes={f['properties']['id']:transform(tx.transform,shape(f['geometry'])) for f in json.loads((root/cfg['scope_file']).read_text())['features']}
    city=transform(tx.transform,shape(json.loads((base/'city_boundary_2025.geojson').read_text())['features'][0]['geometry']))
    focus=scopes['downtown']
    names=['roads','water_parks','rail_airport_port','landuse_landcover','landmarks']
    data={n:json.loads((base/(n+'.geojson')).read_text())['features'] for n in names}
    geometries={n:[transform(tx.transform,shape(f['geometry'])) for f in fs] for n,fs in data.items()}
    trees={n:STRtree(gs) for n,gs in geometries.items()}
    minx,miny,maxx,maxy=city.bounds;step=cfg['tile_size_m'];cells=[]
    for ix in range(math.floor((minx-origin[0])/step),math.ceil((maxx-origin[0])/step)):
        for iy in range(math.floor((miny-origin[1])/step),math.ceil((maxy-origin[1])/step)):
            g=box(origin[0]+ix*step,origin[1]+iy*step,origin[0]+(ix+1)*step,origin[1]+(iy+1)*step).intersection(city)
            if g.is_empty or g.area<1:continue
            counts={n:len(tree.query(g,predicate='intersects')) for n,tree in trees.items()}
            cells.append({'type':'Feature','properties':{
                'id':f'coverage_1km_{ix}_{iy}','area_m2':g.area,'counts':counts,
                'boundary':'2025_reference_geometry_verified',
                'roads':'2025_file_complete_real_world_completeness_not_guaranteed',
                'buildings':'not_downloaded','terrain':'not_downloaded','trees':'not_downloaded',
                'landcover':'missing_classified_raster; facility_polygons_partial',
                'transport':'partial_census_inventory','landmarks':'partial_census_names_not_architectural_study',
                'acquisition_date':None},'geometry':mapping(transform(inv.transform,g))})
    write_json(base/'coverage.geojson',{'type':'FeatureCollection','features':cells})
    print('COVERAGE_GRID_PREPARED',len(cells),'clipped 1km cells',flush=True)
    return cells
