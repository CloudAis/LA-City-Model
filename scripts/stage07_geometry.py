"""Near-street modules and recorded visual grading, preserving source XY and raw DEM."""
from pathlib import Path
import collections,json,math
import numpy as np,shapely
from shapely.geometry import shape,box
from stage06_geometry import Mesh,MATERIALS
from stage07_data import WorkingGround
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def save(root,path,arrays):
 p=root/path;p.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(p,**arrays);return path
def modules():
 out={}
 for kind in ['window_metal_reveal','window_masonry_reveal']:
  m=Mesh();material='silver' if 'metal' in kind else 'limestone'
  for x in [-.475,.475]:m.box([x,.35,0],[.05,2.,1.],'dark_metal')
  for z in [-.475,.475]:m.box([0,.35,z],[.9,2.,.05],'dark_metal')
  for x in [-.48,.48]:m.box([x,-.5,0],[.07,.6,1.08],material)
  m.box([0,-.7,-.49],[1.1,1.25,.07],material);m.box([0,-.5,.49],[1.06,.6,.07],material);m.box([0,-.25,0],[.025,.8,.9],'dark_metal');out[kind]=m
 m=Mesh()
 for x in [-.48,0,.48]:m.box([x,0,0],[.025,1,1],'dark_metal')
 for z in [-.49,.49]:m.box([0,0,z],[1,1,.025],'dark_metal')
 for x in [-.245,.245]:
  m.box([x,-.4,0],[.46,.1,.96],'glass');m.box([x+(.11 if x<0 else -.11),-.65,-.015],[.015,.6,.16],'silver')
 out['entry_glazed_double']=m;m=Mesh();m.box([0,0,0],[1,1,1],'dark_metal')
 for x in [-.4,.4]:m.beam([x,-.42,-.04],[x,.35,-2.5],.04,'silver')
 out['canopy_brackets']=m
 m=Mesh();m.beam([-.5,0,.9],[.5,0,.9],.045,'dark_metal')
 for x in [-.45,.45]:m.beam([x,0,0],[x,0,.9],.04,'dark_metal')
 out['handrail']=m
 m=Mesh();m.cylinder([0,0,0],.022,.022,.62,'terracotta',12)
 for a in [0,2.1,4.2]:m.beam([0,0,.4],[.16*math.cos(a),.16*math.sin(a),.7],.018,'terracotta')
 for x,y,z,r in [(0,0,.64,.32),(-.12,0,.57,.20),(.15,.05,.60,.21),(0,.12,.78,.21)]:
  m.dome([x,y,z],r,r,.24,'grass',16);m.dome([x,y,z],r,r,-.16,'grass',16)
 out['tree_broadleaf']=m;m=Mesh();m.cylinder([0,0,0],.018,.014,.87,'terracotta',12)
 for a in np.linspace(0,2*math.pi,14,endpoint=False):
  pts=[[0,0,.88],[.19*math.cos(a),.19*math.sin(a),.96],[.33*math.cos(a),.33*math.sin(a),.79]]
  for p,q in zip(pts,pts[1:]):
   m.beam(p,q,.013,'grass');d=np.array(q)-p
   for t in [.2,.4,.6,.8]:
    c=np.array(p)+t*d;side=np.array([-math.sin(a),math.cos(a),-.22])*.06;m.face([c-side,c+d*.23,c+side],'grass');m.face([c+side,c+d*.23,c-side],'grass')
 out['tree_palm']=m
 m=Mesh();m.cylinder([0,0,0],.10,.10,.22,'dark_metal',16);m.cylinder([0,0,.2],.065,.065,6.25,'dark_metal',12);m.beam([0,0,6.4],[1.25,0,6.65],.07,'dark_metal');m.box([1.2,0,6.6],[.5,.27,.12],'silver');m.box([1.2,0,6.53],[.4,.22,.015],'white');out['street_lamp']=m
 m=Mesh()
 for x in [-.65,.65]:m.box([x,0,.24],[.07,.55,.48],'dark_metal')
 for y in [-.22,-.11,0,.11,.22]:m.box([0,y,.48],[1.65,.085,.05],'terracotta')
 for z in [.65,.78,.91]:m.box([0,.25,z],[1.65,.06,.095],'terracotta')
 for x in [-.72,.72]:m.beam([x,-.24,.7],[x,.25,.7],.045,'dark_metal')
 out['bench']=m;m=Mesh();m.cylinder([0,0,0],.28,.28,.78,'dark_metal',20);m.cylinder([0,0,.78],.32,.32,.08,'silver',20);out['waste_bin']=m
 m=Mesh();m.cylinder([0,0,0],.16,.16,.12,'dark_metal',16);m.cylinder([0,0,.12],.12,.12,.62,'seat_yellow',16);m.dome([0,0,.74],.13,.13,.12,'seat_yellow',16)
 for x in [-.19,.19]:m.box([x,0,.58],[.17,.16,.16],'seat_yellow')
 out['hydrant']=m;m=Mesh();m.cylinder([0,0,0],.075,.075,.88,'dark_metal',16);m.cylinder([0,0,.7],.078,.078,.06,'white',16);m.dome([0,0,.88],.075,.075,.06,'dark_metal',16);out['bollard']=m
 return out
def terrain(root,buildings,ground,cfg):
 changes=[b for b in buildings if b['floor_delta_m']];records=[]
 for ij,t in ground.base.tiles.items():
  tilebox=box(ij[0]*1000,ij[1]*1000,(ij[0]+1)*1000,(ij[1]+1)*1000);sites=[b for b in changes if shape(b['geometry']).buffer(8).intersects(tilebox)]
  if not sites:continue
  prior=ground.overrides.get(ij)
  if prior:
   src=prior['file']
   with np.load(root/src) as a:ar={k:a[k].copy() for k in a.files}
  else:
   v,f,_,_=ground.base.load(ij);lod=ground.base.active[t['id']];variant=root/'data/processed/stage04/ground'/(t['id']+'.npz');src=str(variant.relative_to(root)) if variant.exists() else t['file']
   with np.load(root/src) as a:mi=a['m'+str(lod)]
   ar={'v':v.copy().astype(np.float32),'f':f.copy().astype(np.int32),'m':mi.copy()}
  v=ar['v'].copy();xy=v[:,:2].astype(float);base=v[:,2].copy();z=base.astype(float);pts=shapely.points(xy+np.array(ij)*1000);boundary=(xy[:,0]<1e-5)|(xy[:,0]>1000-1e-5)|(xy[:,1]<1e-5)|(xy[:,1]>1000-1e-5)
  for b in sites:
   d=shapely.distance(pts,shape(b['geometry']).buffer(cfg['grading']['footprint_buffer_m']));w=np.clip(1-d/cfg['grading']['transition_m'],0,1);w[boundary]=0;z=z*(1-w)+(b['floor_navd88_m']-.18)*w
  v[:,2]=z;ar['v']=v;assert np.array_equal(v[boundary,2],base[boundary]);file=save(root,'data/processed/stage07/ground/'+t['id']+'.npz',ar);records.append({'id':t['id'],'ij':list(ij),'file':file,'source_file':src,'origin_city_m':[ij[0]*1000,ij[1]*1000,0],'boundary_delta_m':float(np.max(abs(v[boundary,2]-base[boundary]))) if boundary.any() else 0.,'max_visual_z_edit_m':float(np.max(abs(v[:,2]-base))),'xy_and_faces_unchanged':True,'raw_dem_modified':False,'inferred_sites':[b['uid'] for b in sites],'sha256':digest(root/file)})
 write_json(root/'data/processed/stage07/ground_index.json',{'tiles':records,'status':'boundary_preserved_inferred_visual_grading','new_original_resolution_claim':False});ground.overrides.update({tuple(t['ij']):t for t in records});ground.cache.clear();return records
def build(root=ROOT):
 cfg=json.loads((root/'config/stage07.json').read_text());bs=json.loads((root/'data/processed/stage07/buildings.json').read_text());ground=WorkingGround(root);terrain(root,bs,ground,cfg);index={'materials':MATERIALS,'terrain_active_lod':ground.base.active,'modules':[],'site_meshes':[],'street_instances':[]};audit=[]
 for kind,m in modules().items():
  a,removed=m.arrays();file=save(root,'assets/street_furniture/stage07/meshes/'+kind+'.npz',a);index['modules'].append({'kind':kind,'file':file,'triangles':len(a['f']),'degenerate_filtered':removed,'shape_evidence':'original inferred template; not a source-measured manufacturer component'})
 groups=collections.defaultdict(Mesh)
 for b in bs:
  e=b['entry']
  if not e or e['unresolved']:continue
  m=groups[b['region']];xy=np.array(e['xy_m']);out=np.array(e['outward_xy']);t=np.array([-out[1],out[0]]);floor=b['floor_navd88_m'];n=e['steps'];width=cfg['entry']['width_m'];landing=1.0;run=n*cfg['entry']['tread_m'];rise=max(0,e['rise_m']);bottom=min(floor-.2,e['walk_navd88_m']-.25)
  def oriented_box(dist,depth,top):
   tmp=Mesh();tmp.box([0,dist,(top+bottom)/2],[width,depth,top-bottom],'paving');v=np.array(tmp.v);v[:,:2]=v[:,:2]@np.column_stack([t,out]).T+xy;o=len(m.v);m.v.extend(v);m.f.extend((np.array(tmp.f)[:,[0,2,1]]+o).tolist());m.m.extend(tmp.m)
  oriented_box(landing/2,landing,floor)
  for j in range(n):oriented_box(landing+(j+.5)*.30,.30,floor-(j+1)*rise/max(n,1))
  if n>=3:
   for side in [-1,1]:
    start=xy+t*side*(width/2-.08)+out*.12;end=xy+t*side*(width/2-.08)+out*(landing+run);a=np.array([*start,floor+.9]);c=np.array([*end,floor-rise+.9]);m.beam(a,c,.045,'dark_metal')
    for w in np.linspace(0,1,max(2,math.ceil((landing+run)/1.2))):p=a*(1-w)+c*w;m.beam(p-[0,0,.9],p,.045,'dark_metal')
  audit.append({'uid':b['uid'],'steps':n,'rise_m':rise,'step_rise_m':rise/max(n,1),'solid_foundation_bottom_m':bottom,'landing_m':landing,'run_m':run,'engineering_or_accessibility_certified':False})
 for region,m in groups.items():
  a,removed=m.arrays();origin=np.array([-432.3949595,857.11258,0] if region=='historic_core' else [215.43239,1747.54794,0]);a['v']-=origin.astype(np.float32);file=save(root,'data/processed/stage07/site_meshes/'+region+'.npz',a);index['site_meshes'].append({'id':region+'_stairs_railings','region':region,'file':file,'origin_city_m':origin.tolist(),'triangles':len(a['f']),'degenerate_filtered':removed})
 features=json.loads((root/'data/processed/stage07/street_features.json').read_text())['features'];plans=[shape(b['geometry']) for b in bs];inside=[]
 for a in features:
  xy=a['xyz_m'][:2]
  if any(p.contains(shapely.Point(xy)) for p in plans):inside.append(a['id']);continue
  z=float(ground(np.array([xy[0]]),np.array([xy[1]]))[0]);h=a['height_m'] if a['kind'].startswith('tree') else 1.;rotation=(int(a['original_id'])%360)*math.pi/180;index['street_instances'].append({'kind':a['kind'],'xyz':[*xy,z+.04],'scale':[h,h,h],'rotation':rotation,'fid':-(int(a['original_id'])%(2**30))-1,'region':a['region'],'stable_source_id':a['id'],'source':a['position_evidence']+'; orientation and fixture geometry inferred'})
 write_json(root/'data/processed/stage07/geometry_index.json',index);write_json(root/'work/reports/stage07/site_geometry.json',{'status':'numeric_geometry_prepared_pending_blender_review','entries_built':audit,'skipped_source_points_inside_source_buildings':inside,'street_instances':len(index['street_instances']),'source_point_xy_not_moved':True});print('STAGE07_GEOMETRY_PREPARED',len(index['modules']),'MODULES',len(audit),'ENTRIES',len(index['street_instances']),'STREET_INSTANCES',flush=True)
if __name__=='__main__':build()
