"""Camera locations are georeferenced; no model is moved to improve a composition."""
from pathlib import Path
import json,math,numpy as np
from pyproj import Transformer
from stage03_common import references
from stage04_geometry import Ground
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def prepare(root=ROOT):
 _,origin,city,refs=references(root);ground=Ground(root);tx=Transformer.from_crs(4326,32611,always_xy=True);inv=Transformer.from_crs(32611,4326,always_xy=True)
 def elevation(xy):
  z=ground(np.array([xy[0]]),np.array([xy[1]]))[0]
  if not np.isfinite(z):raise ValueError('Camera ground not covered '+str(xy))
  return float(z)
 views={};b=city.bounds;cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2;scale=max(b[2]-b[0],(b[3]-b[1])*4/3)*1.08
 views['city_top']={'position_m':[cx,cy,120000],'target_m':[cx,cy,0],'ortho_scale_m':scale,'focus_xy_m':[cx,cy],'radius_m':100000,'mode':'city','samples':8,'description':'whole administrative footprint, low-density building alternative, offline review'}
 views['downtown_top']={'position_m':[0,0,10000],'target_m':[0,0,90],'ortho_scale_m':4400*4/3,'focus_xy_m':[0,0],'radius_m':2350,'mode':'downtown','samples':12,'description':'fixed4x4km working window, no relocated geography'}
 target=[-850,1350,170]
 for name,ll,height in [('skyline_northwest',[-118.2625,34.0609],80.),('skyline_northeast',[-118.2365,34.0605],60.),('skyline_south',[-118.2635,34.0305],20.)]:
  xy=np.asarray(tx.transform(*ll))-origin;z=elevation(xy);views[name]={'position_m':[*xy,z+height],'target_m':target,'focus_xy_m':[0,1000],'radius_m':5500,'mode':'skyline','lens_mm':35,'samples':16,'camera_lonlat':ll,'camera_above_sampled_ground_m':height,'description':'georeferenced skyline view; elevated cameras explicitly recorded; repeated small traffic fixtures omitted at this distance'}
 typical=json.loads((root/'work/reports/stage04/geometry.json').read_text())['typical_intersection']['xy_m']
 for name,xy,targetxy in [('historic_core_street',[typical[0]-3,typical[1]-5],[typical[0]-85,typical[1]+90]),('civic_center_street',[220,1660],[102,1815])]:
  z=elevation(xy);tz=elevation(targetxy);views[name]={'position_m':[*xy,z+1.7],'target_m':[*targetxy,tz+14],'focus_xy_m':xy,'radius_m':650,'mode':'street','lens_mm':28,'samples':24,'camera_lonlat':list(inv.transform(xy[0]+origin[0],xy[1]+origin[1])),'camera_above_sampled_ground_m':1.7,'description':'initial closeup block, inferred facade modules; not final stage07 survey-matched architecture'}
 for v in views.values():
  xy=v['position_m'][:2];v.setdefault('camera_lonlat',list(inv.transform(xy[0]+origin[0],xy[1]+origin[1])));v['camera_axis']='X grid east,Y grid north,Z up; meters'
 views['historic_core_street']['exposure_stops']=1.0
 write_json(root/'config/stage05_views.json',views);print('GEOGRAPHIC_CAMERAS_WRITTEN',len(views),flush=True);return views
if __name__=='__main__':prepare()
