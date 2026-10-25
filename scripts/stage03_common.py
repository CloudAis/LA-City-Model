"""Stage03 source-preserving helpers; local meters are not RFC7946 GeoJSON."""
import json
from pathlib import Path
import yaml
import numpy as np
from pyproj import Transformer
from shapely.geometry import shape,mapping
from shapely.ops import transform
from stage02_io import write_json,digest


def settings(root):return yaml.safe_load((Path(root)/'config/stage03.yaml').read_text())


def references(root):
    root=Path(root);cfg=settings(root);o=json.loads((root/cfg['origin_file']).read_text())['origin_utm_m']
    tx=Transformer.from_crs(4326,32611,always_xy=True)
    def local(g):
        return transform(lambda x,y,z=None:(np.asarray(x)-o[0],np.asarray(y)-o[1]),transform(tx.transform,g))
    refs={f['properties']['id']:local(shape(f['geometry'])) for f in json.loads((root/cfg['scope_file']).read_text())['features']}
    city=local(shape(json.loads((root/cfg['city_boundary']).read_text())['features'][0]['geometry']))
    return cfg,np.array(o),city,refs


def load_features(root,relative):return json.loads((Path(root)/relative).read_text())['features']


def local_features(root,relative):
    cfg,o,_,_=references(root);tx=Transformer.from_crs(4326,32611,always_xy=True)
    return [(f,transform(lambda x,y,z=None:(np.asarray(x)-o[0],np.asarray(y)-o[1]),transform(tx.transform,shape(f['geometry'])))) for f in load_features(root,relative)]


def to_geographic(g,origin):
    inv=Transformer.from_crs(32611,4326,always_xy=True)
    return mapping(transform(inv.transform,transform(lambda x,y,z=None:(np.asarray(x)+origin[0],np.asarray(y)+origin[1]),g)))


def polygon_parts(g):
    if g.geom_type=='Polygon':return [g]
    return [p for c in getattr(g,'geoms',[]) for p in polygon_parts(c)]
