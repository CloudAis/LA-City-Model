"""Export true WGS84 footprint/research polygons without moving landmarks."""
import json,math
from pathlib import Path
import numpy as np,shapely
from shapely import affinity
from shapely.geometry import shape,mapping
from pyproj import Transformer
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def build(root=ROOT):
 cfg=json.loads((root/'config/stage06.json').read_text());origin=np.array(cfg['origin_utm_m']);tx=Transformer.from_crs(32611,4326,always_xy=True);footprints=[];regions=[]
 for lm in cfg['landmarks']:
  a=json.loads((root/'data/processed/stage06/cards'/(lm['id']+'.json')).read_text());g=affinity.rotate(shape(a['local_plan']),a['rotation_from_grid_east_degrees'],origin=(0,0));g=affinity.translate(g,xoff=a['origin_city_m'][0]+origin[0],yoff=a['origin_city_m'][1]+origin[1]);remote=lm['id'] in ['griffith_observatory','hollywood_sign','dodger_stadium','memorial_coliseum'];props={'id':'landmark:'+lm['id'],'name':a['name'],'source_uid':a['source_uid'],'region_role':'independent_landmark_region' if remote else 'downtown_landmark','geometry_precision':'source-dependent; work buffers are derived planning windows, not official site boundaries','status':'approximate_complete'}
  def geo(h):return mapping(shapely.transform(h,lambda xy:np.column_stack(tx.transform(xy[:,0],xy[:,1]))))
  footprints.append({'type':'Feature','properties':props,'geometry':geo(g)});regions.append({'type':'Feature','properties':props|{'work_buffer_m':300,'official_administrative_boundary':False},'geometry':geo(g.buffer(300))})
 write_json(root/'data/processed/stage06/landmark_footprints_wgs84.geojson',{'type':'FeatureCollection','features':footprints});write_json(root/'data/processed/stage06/landmark_regions_wgs84.geojson',{'type':'FeatureCollection','features':regions});print('TRUE_WGS84_LANDMARK_FOOTPRINTS_AND_REGIONS_SAVED',len(regions))
if __name__=='__main__':build()
