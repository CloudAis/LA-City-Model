"""Georeferenced inspection cameras, actual fixture points and reproducible leaf geometry."""
import json,math,sqlite3
from pathlib import Path
import numpy as np,shapely
from shapely.geometry import Point,LineString,shape
from stage07_final_data import ROOT,Grade,read,OUT,save,Mesh
from stage02_io import write_json
def run():
 ix=read(OUT+'index.json');grade=Grade();old=read('config/stage07_views.json');cfg=read('config/stage07_final.json');v={};db=sqlite3.connect(ROOT/'data/processed/stage05/buildings.sqlite')
 for region,name in [('historic_core','historic_street'),('civic_center','civic_street')]:
  a=old[region+'_street'];xy=np.array(a['position_m'][:2]);position=[*xy,grade.local_height(xy)+1.85];target=[*a['target_m'][:2],position[2]+8];v[name]={'position_m':position,'target_m':target,'focus_xy_m':xy.tolist(),'radius_m':420,'detail_radius_m':150,'lens_mm':30,'evidence':'existing real geographic street position; camera Z sampled from revision street-constrained grade'}
 for b in ix['buildings']:
  if not b['reference_guided']:continue
  doors=b['doors'];assert doors,(b['i'],'no ground opening');e=doors[0];xy=np.array(e['xy_city_m']);out=np.array(e['outward_xy']);t=np.array([-out[1],out[0]]);candidates=[]
  for d in ([32,25,18,13] if b['profile'] in ['theatre','arcade','alexandria'] else [20,15,10]):
   for side in [-7,7,0,-3,3]:
    cam=xy+out*d+t*side;x,y=cam;rows=db.execute('select b.i,b.geom from buildings b join spatial s on s.i=b.i where active=1 and s.minx<? and s.maxx>? and s.miny<? and s.maxy>?',(x+.25,x-.25,y+.25,y-.25)).fetchall();blocked=[i for i,g in rows if i!=b['i'] and i not in cfg['skybridge']['replaces'] and shapely.from_wkb(g).buffer(.15).covers(Point(cam))]
    if not blocked:candidates.append(cam)
  assert candidates,(b['profile'],'no clear source-footprint camera');cam=candidates[0];z=grade.local_height(cam)+1.8;targetheight=10 if b['profile'] in ['arcade','theatre','alexandria'] else 8
  if b['profile']=='records':
   # The previous close view showed only the documented blank storage wing.
   # Use a real southwest street position and an elevated target to inspect the
   # wing organisation, louvers and ceramic screen together.
   cam=np.array([100.,1775.]);z=grade.local_height(cam)+5.0;xy=np.array(b['origin_city_m'][:2]);targetheight=23
   x,y=cam;rows=db.execute('select b.i,b.geom from buildings b join spatial s on s.i=b.i where active=1 and s.minx<? and s.maxx>? and s.miny<? and s.maxy>?',(x+.25,x-.25,y+.25,y-.25)).fetchall();assert not [i for i,g in rows if i!=b['i'] and shapely.from_wkb(g).buffer(.15).covers(Point(cam))],'Records inspection camera inside source building'
  v[b['profile']+'_facade']={'position_m':[*cam,z],'target_m':[*xy,b['floor_navd88_m']+targetheight],'focus_xy_m':(np.array(b['origin_city_m'][:2])).tolist(),'radius_m':300,'detail_radius_m':155,'lens_mm':30,'target_uid':b['uid'],'evidence':'source-footprint collision checked; reference-guided exterior with unmeasured details explicit'}
 for region in ['historic_core','civic_center']:
  center=np.array(grade.refs[region].centroid.coords[0]);v[region+'_top']={'position_m':[*center,1000],'target_m':[*center,95],'focus_xy_m':center.tolist(),'radius_m':470,'detail_radius_m':180,'ortho_scale_m':620,'evidence':'georeferenced orthographic inspection; footprint and roof organization, no moved buildings'}
 # Preserve the previously failed plaza viewpoint to prove its terrain repair.
 xy=np.array([220.,1660.]);v['civic_plaza']={'position_m':[*xy,grade.local_height(xy)+1.8],'target_m':[102.,1815.,grade.local_height(xy)+9],'focus_xy_m':xy.tolist(),'radius_m':400,'detail_radius_m':160,'lens_mm':28,'evidence':'same XY and bearing as rejected plaza draft; used to assess actual terrain repair'}
 write_json(ROOT/'config/stage07_final_views.json',v)
 source=read('data/processed/stage07/geometry_index.json')['street_instances'];groups={}
 for a in source:groups.setdefault((a['region'],a['kind']),[]).append(a)
 objects={}
 for (region,kind),items in groups.items():
  origin=np.array([-432.3949595,857.11258,0] if region=='historic_core' else [215.43239,1747.54794,0]);coords=[]
  for a in items:
   x,y,z=a['xyz'];coords.append((np.array([x,y,grade.local_height([x,y])+.15])-origin).tolist())
  objects['LA07_'+region+'_street_'+kind]={'v':coords,'source_xy_unchanged':True}
 write_json(ROOT/(OUT+'street_positions.json'),{'objects':objects,'elevation_evidence':'source XY retained; new inferred sidewalk elevation'})
 rng=np.random.default_rng(cfg['seed']);m=Mesh();m.cylinder([0,0,0],.018,.022,.63,'terracotta',20)
 for j in range(24):
  angle=j*2.39996323;end=np.array([.26*math.cos(angle),.26*math.sin(angle),.66+rng.uniform(-.12,.20)]);m.beam([0,0,.35+j*.009],end,.008,'terracotta')
 for j in range(2500):
  while True:
   xyz=rng.uniform([-1,-1,-1],[1,1,1])
   if np.linalg.norm(xyz)<1:break
  c=xyz*np.array([.34,.32,.23])+[0,0,.74];normal=rng.normal(size=3);normal/=np.linalg.norm(normal);u=np.cross(normal,[0,0,1] if abs(normal[2])<.9 else [0,1,0]);u/=np.linalg.norm(u);v0=np.cross(normal,u);q=[c-u*.016,c+v0*.007,c+u*.016,c-v0*.007];m.face(q,'grass');m.face(q[::-1],'grass')
 ar,removed=m.arrays();file=save(OUT+'tree_leaf_asset.npz',ar);write_json(ROOT/(OUT+'leaf_asset.json'),{'file':file,'triangles':len(ar['f']),'leaves':2500,'fixed_seed':cfg['seed'],'species':'generic inferred broadleaf, not a measured species reconstruction'});print('FINAL_VIEW_PRESETS',len(v),'FIXTURE_GROUPS',len(objects),'REAL_LEAF_GEOMETRY',len(ar['f']),flush=True)
if __name__=='__main__':run()
