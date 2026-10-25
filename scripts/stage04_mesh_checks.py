"""Query actual saved triangles at priority crossings; not just the pre-mesh profile."""
from pathlib import Path
import json,math,collections
import numpy as np
from stage04_geometry import Ground,tile_id
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def check(root=ROOT):
 folder=root/'data/processed/stage04';roads=json.loads((folder/'roads.json').read_text());idx=json.loads((folder/'mesh_index.json').read_text());cross=json.loads((root/'work/reports/stage04/crossings.json').read_text());geo=json.loads((root/'work/reports/stage04/geometry.json').read_text());ground=Ground(root);bytile=collections.defaultdict(list);cache={}
 for m in idx['meshes']:
  if m['role'] in ['bridge_road','tunnel_road','full_far','overview_far','downtown_road','profiled_priority_road','rail_corridor']:bytile[m['tile_id']].append(m)
 def hit(xy,fid,only_role=None):
  key=tile_id(math.floor(xy[0]/1000),math.floor(xy[1]/1000));hits=[]
  for m in bytile[key]:
   if only_role and m['role']!=only_role:continue
   if not only_role and m['role']=='rail_corridor':continue
   if m['file'] not in cache:
    with np.load(root/m['file']) as a:cache[m['file']]={k:a[k] for k in ['v','f','m','fid']}
   a=cache[m['file']];p=roads[fid]['parameters'] if fid is not None else None;union_allowed=p is not None and m['role']=='downtown_road' and not p['bridge'] and not p['tunnel'] and p['vertical_rank']==0
   mask=(a['m']==7) if fid is None else (a['m']==0)&((a['fid']==fid)|union_allowed);f=a['f'][mask]
   if not len(f):continue
   v=a['v'].astype(float);q=np.array(xy)-m['origin_m'][:2];t=v[f];low=t[:,:,:2].min(axis=1)-.0001;high=t[:,:,:2].max(axis=1)+.0001;ok=((q>=low)&(q<=high)).all(axis=1);t=t[ok]
   if not len(t):continue
   ab=t[:,1,:2]-t[:,0,:2];ac=t[:,2,:2]-t[:,0,:2];aq=q-t[:,0,:2];den=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0];good=abs(den)>1e-10;t=t[good];ab=ab[good];ac=ac[good];aq=aq[good];den=den[good];u=(aq[:,0]*ac[:,1]-aq[:,1]*ac[:,0])/den;w=(ab[:,0]*aq[:,1]-ab[:,1]*aq[:,0])/den;inside=(u>=-1e-4)&(w>=-1e-4)&(u+w<=1.0001);z=t[:,0,2]+u*(t[:,1,2]-t[:,0,2])+w*(t[:,2,2]-t[:,0,2]);hits.extend(z[inside].tolist())
  return float(np.median(hits)) if hits else None
 selected=[]
 for c in cross:
  if c['upper'] is None:continue
  ra,rb=roads[c['a']],roads[c['b']]
  if any(r['parameters']['class'] in ['pedestrian','cycleway'] for r in [ra,rb]):continue
  xy=np.array(c['xy_m']);near_dt=abs(xy[0])<2100 and abs(xy[1])<2100;near_inter=np.linalg.norm(xy-np.array(geo['interchange_center_m']))<700
  if not (near_dt or near_inter):continue
  za=hit(c['xy_m'],c['a']);zb=hit(c['xy_m'],c['b']);row={'source_a':ra['id'],'source_b':rb['id'],'xy_m':c['xy_m'],'source_constraint_status':c['status'],'mesh_z_a_m':za,'mesh_z_b_m':zb}
  if za is None or zb is None:row['status']='mesh_sample_missing'
  else:
   clearance=(za-zb if c['upper']==c['a'] else zb-za)-.65;row['estimated_mesh_clearance_m']=clearance;row['status']='pass_approximate_clearance' if clearance>=4.5 else 'mesh_clearance_warning';row['clearance_threshold_m']=4.5
  selected.append(row)
 # Actual mesh deck-to-ground difference, with abutments excluded from penetration warnings.
 profile=np.load(folder/'road_profiles.npz');vv=profile['v'];ss=profile['s'];bridges=[]
 for i,r in enumerate(roads):
  if not r['parameters']['bridge']:continue
  if 'downtown' not in r['regions'] and np.linalg.norm(vv[r['profile_start'],:2]-np.array(geo['interchange_center_m']))>1000:continue
  k=r['profile_start'];n=r['profile_count'];s=ss[k:k+n];inside=(s-s[0]>15)&(s[-1]-s>15)
  if not inside.any():continue
  xy=vv[k:k+n,:2][inside];profile_z=vv[k:k+n,2][inside];selection=np.unique(np.linspace(0,len(xy)-1,min(32,len(xy))).astype(int));xy=xy[selection];g=ground(xy[:,0],xy[:,1]);actual=np.array([hit(q,i) if hit(q,i) is not None else np.nan for q in xy]);topgap=actual-g;dz=topgap-.65
  if not np.isfinite(dz).any():status='mesh_sample_missing'
  elif np.nanmin(topgap)<-.05:status='deck_top_burial_warning'
  elif np.nanmin(dz)<-.05:status='slab_terrain_overlap_span_limits_unverified'
  else:status='no_sampled_terrain_intersection'
  bridges.append({'id':r['id'],'samples':len(xy),'minimum_actual_deck_top_minus_display_terrain_m':float(np.nanmin(topgap)) if np.isfinite(topgap).any() else None,'minimum_estimated_underside_minus_display_terrain_m':float(np.nanmin(dz)) if np.isfinite(dz).any() else None,'status':status,'note':'under-slab contact may be abutment/approach support; actual span limits are unmeasured'})
 report={'status':'executed','priority_crossings':len(selected),'actual_mesh_crossing_status':dict(collections.Counter(c['status'] for c in selected)),'crossings':selected,'bridge_ground_status':dict(collections.Counter(b['status'] for b in bridges)),'bridges':bridges,'note':'4.5m is a visual anomaly threshold, not a measured/code-compliant clearance;5.2m profile target remains inference. All warnings retained, no claim all structures are accurate.'}
 # Rail/road crossings use separate mode topology and the actual saved ballast triangles.
 from pyproj import Transformer
 from shapely.geometry import LineString,Point
 from shapely.strtree import STRtree
 from stage04_data import grade_rank
 tx=Transformer.from_crs(4326,32611,always_xy=True);vehicle=[i for i,r in enumerate(roads) if r['parameters']['class'] not in ['pedestrian','cycleway']];rgs=[]
 for i in vehicle:
  r=roads[i];k=r['profile_start'];n=r['profile_count'];rgs.append(LineString(vv[k:k+n,:2]))
 tree=STRtree(rgs);railrows=[]
 for w in json.loads((folder/'other_transport.json').read_text()):
  if w['tags'].get('railway') not in ['rail','light_rail','tram','subway','narrow_gauge','monorail']:continue
  ll=np.array(w['lonlat']);x,y=tx.transform(ll[:,0],ll[:,1]);g=LineString(np.column_stack([x-ground.origin[0],y-ground.origin[1]]));rank,bridge,tunnel=grade_rank(w['tags'])
  for j in tree.query(g,predicate='crosses'):
   i=vehicle[int(j)];r=roads[i];q=g.intersection(rgs[int(j)]);points=[q] if q.geom_type=='Point' else list(getattr(q,'geoms',[]))
   for point in points:
    if point.geom_type!='Point':continue
    xy=[point.x,point.y];shared=bool(set(r['node_ids'])&set(w['node_ids']));rr=r['parameters']['vertical_rank'];row={'road':r['id'],'rail':w['id'],'xy_m':xy,'road_rank':rr,'rail_rank':rank,'source_shared_node':shared}
    if shared and rr==rank:row['status']='source_level_crossing'
    elif rr==rank:row['status']='unresolved_same_rank_nonshared_crossing'
    else:
     zr=hit(xy,i);zt=hit(xy,None,'rail_corridor');row['road_mesh_z_m']=zr;row['rail_mesh_z_m']=zt
     if zr is None or zt is None:row['status']='mesh_sample_missing'
     else:
      diff=zr-zt if rr>rank else zt-zr;row['estimated_mesh_clearance_m']=diff-(.65 if rr>rank else .6);row['status']='pass_approximate_relative_grade' if row['estimated_mesh_clearance_m']>=4.5 else 'rail_road_clearance_warning'
    railrows.append(row)
 report['rail_road_status']=dict(collections.Counter(r['status'] for r in railrows));write_json(root/'work/reports/stage04/rail_road_crossings.json',{'status':'executed','crossing_counts':report['rail_road_status'],'crossings':railrows,'note':'rail-road modes not joined automatically; grade and vertical dimensions remain estimated; warnings are not passed checks'})
 write_json(root/'work/reports/stage04/actual_mesh_crossings.json',report);print('ACTUAL_TRIANGLE_CROSSING_CHECKS',report['actual_mesh_crossing_status'],report['bridge_ground_status'],flush=True);return report
if __name__=='__main__':check()
