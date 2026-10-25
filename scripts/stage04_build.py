"""Road surfaces, Downtown intersections, inferred structures, rails and aeroways."""
from pathlib import Path
import json,math,collections
import numpy as np
import shapely
from shapely.geometry import LineString,Point,Polygon,box,shape
from shapely.strtree import STRtree
from pyproj import Transformer
import yaml
from stage03_common import references,polygon_parts,to_geographic
from stage03_surface import Surface
from stage02_io import write_json,digest
from stage04_geometry import Ground,Meshes,tile_id
from stage04_data import lines,number,grade_rank
ROOT=Path(__file__).resolve().parents[1]

class Builder:
 def __init__(self,root=ROOT):
  self.root=root;self.cfg=yaml.safe_load((root/'config/stage04.yaml').read_text());self.ground=Ground(root);self.surface=Surface(root);self.mesh=Meshes(root,self.ground);self.origin=self.ground.origin;self.refs=self.ground.refs;self.city=self.ground.city
  self.roads=json.loads((root/'data/processed/stage04/roads.json').read_text());a=np.load(root/'data/processed/stage04/road_profiles.npz');self.v=a['v'];self.s=a['s'];self.delta=self.v[:,2]-self.surface(self.v[:,0],self.v[:,1]);self.tx=Transformer.from_crs(4326,32611,always_xy=True)
  self.gs=[];self.delta=np.nan_to_num(self.delta);self.dt_indices=[]
  for i,r in enumerate(self.roads):
   k=r['profile_start'];n=r['profile_count'];g=LineString(self.v[k:k+n,:2]);self.gs.append(g)
   if 'downtown' in r['regions'] and not r['parameters']['bridge'] and not r['parameters']['tunnel'] and r['parameters']['vertical_rank']==0 and r['parameters']['class'] not in ['pedestrian','cycleway']:self.dt_indices.append(i)
  self.tree=STRtree([self.gs[i] for i in self.dt_indices]);self.ground_variant=[];self.masks={};self._mask_tiles={};self.fid_counts=collections.Counter()
 def difference(self,a,b):
  try:return a.difference(b)
  except shapely.errors.GEOSException:
   self.fid_counts['overlay_repaired_with_0_1mm_precision']+=1
   return shapely.difference(shapely.make_valid(a),shapely.make_valid(b),grid_size=.0001)
 def local_mask(self,name,g):
  if g.is_empty:return Polygon()
  b=g.bounds;pieces=[]
  for ix in range(math.floor(b[0]/500),math.floor(b[2]/500)+1):
   for iy in range(math.floor(b[1]/500),math.floor(b[3]/500)+1):
    key=(name,ix,iy)
    if key not in self._mask_tiles:self._mask_tiles[key]=self.masks[name].intersection(box(ix*500,iy*500,(ix+1)*500,(iy+1)*500))
    pieces.append(self._mask_tiles[key])
  return pieces[0] if len(pieces)==1 else shapely.unary_union(pieces)
 def road_z(self,i,xy,offset=0):
  r=self.roads[i];k=r['profile_start'];n=r['profile_count'];points=shapely.points(xy);s=shapely.line_locate_point(self.gs[i],points);p=r['parameters']
  if p['bridge'] or p['tunnel'] or p['vertical_rank']!=0:
   z=np.interp(s,self.s[k:k+n],self.v[k:k+n,2])-.015*shapely.distance(points,self.gs[i])
  else:
   delta=np.interp(s,self.s[k:k+n],self.delta[k:k+n])-.06;weight=np.clip(shapely.distance(points,self.refs['downtown'])/100,0,1)
   z=self.ground(xy[:,0],xy[:,1])+.06+delta*weight
  return z+offset
 def profile_z(self,i,xy):
  r=self.roads[i];k=r['profile_start'];n=r['profile_count'];s=shapely.line_locate_point(self.gs[i],shapely.points(xy));return np.interp(s,self.s[k:k+n],self.v[k:k+n,2])
 def roadbed(self):
  # Variants only, original Stage03 files retained. One global XY rule for every LOD boundary.
  folder=self.root/'data/processed/stage04/ground';folder.mkdir(parents=True,exist_ok=True);changes=[]
  for ij,t in self.ground.tiles.items():
   bounds=box(ij[0]*1000,ij[1]*1000,(ij[0]+1)*1000,(ij[1]+1)*1000)
   if not bounds.intersects(self.refs['downtown']):continue
   with np.load(self.root/t['file']) as a:arrays={k:a[k] for k in a.files}
   maxchange=0;changed=0
   for lod in range(3):
    v=arrays[f'v{lod}'];xy=np.round(v[:,:2].astype(float)+[ij[0]*1000,ij[1]*1000],5);pts=shapely.points(xy);near=self.tree.nearest(pts);rd=np.array(self.dt_indices)[near];geoms=np.array(self.gs,dtype=object)[rd];dist=shapely.distance(pts,geoms)
    widths=np.array([self.roads[i]['parameters']['width_m']/2+self.roads[i]['parameters']['sidewalk_m'] for i in rd]);alpha=np.clip((widths+5-dist)/5,0,1);alpha*=shapely.covers(self.refs['downtown'],pts)
    chosen=np.flatnonzero(alpha>0)
    desired=v[:,2].astype(float).copy()
    for i in set(rd[chosen].tolist()):
     ids=chosen[rd[chosen]==i];desired[ids]=self.profile_z(i,xy[ids])-.06-np.minimum(dist[ids],self.roads[i]['parameters']['width_m']/2)*.015
    z=v[:,2]*(1-alpha)+desired*alpha;dz=z-v[:,2];maxchange=max(maxchange,float(abs(dz).max()));changed+=int((abs(dz)>1e-5).sum());arrays[f'v{lod}']=np.column_stack([v[:,:2],z]).astype(np.float32)
   path=folder/f'{t["id"]}.npz';np.savez_compressed(path,**arrays);changes.append({'tile_id':t['id'],'file':str(path.relative_to(self.root)),'changed_vertices_all_lods':changed,'maximum_abs_height_adjustment_m':maxchange,'sha256':digest(path)})
  self.ground.cache.clear();self.ground_variant=changes
  write_json(self.root/'work/reports/stage04/roadbed_adjustments.json',{'method':'DT-only terrain variant from observed centerline and inferred longitudinal profile/crossfall;5m blend beyond estimated sidewalk; original DTM and Stage03 mesh untouched','tiles':changes,'source_class':'inferred_visual_ground_adjustment','raw_terrain_retained':True,'maximum_adjustment_m':max(x['maximum_abs_height_adjustment_m'] for x in changes)})
  print('ROADBED_VARIANTS',len(changes),flush=True)
 def road_surfaces(self):
  import hashlib
  cachefile=self.root/'work/cache/stage04/downtown_seed_cache.json'
  key=hashlib.sha256((digest(self.root/'data/processed/stage04/road_profiles.npz')+digest(self.root/'data/processed/stage04/roads.json')+digest(self.root/'config/stage04.yaml')+'DT_surface_round3cm_v1').encode()).hexdigest()
  cached=json.loads(cachefile.read_text()) if cachefile.exists() else None
  valid=cached and cached['key']==key and all((self.root/m['file']).exists() and digest(self.root/m['file'])==m['sha256'] for m in cached['meshes'])
  if valid:
   self.masks={k:shapely.from_wkb(bytes.fromhex(w)) for k,w in cached['masks_wkb'].items()};self.mesh.pre_saved.extend(cached['meshes']);print('DT_SURFACE_CACHE_VERIFIED',flush=True)
  else:
   dt=self.refs['downtown'];dtpolys=[];outer=[]
   for i in self.dt_indices:
    r=self.roads[i];p=r['parameters'];g=self.gs[i].simplify(.02).intersection(dt.buffer(35));road=g.buffer(p['width_m']/2,quad_segs=2,cap_style=2,join_style=1);dtpolys.append(road);outer.append(g.buffer(p['width_m']/2+p['sidewalk_m'],quad_segs=2,cap_style=2,join_style=1))
   asphalt=shapely.unary_union(dtpolys).buffer(2,quad_segs=3).buffer(-2,quad_segs=3).intersection(dt).intersection(self.city).simplify(.03);walk=shapely.unary_union(outer).difference(asphalt).intersection(dt).intersection(self.city).simplify(.03)
   # Closing rounds concave curb corners; widths/placement are labeled estimates.
   self.masks={'asphalt':asphalt,'sidewalk':walk};write_json(self.root/'data/processed/stage04/downtown_surface_masks.geojson',{'type':'FeatureCollection','features':[{'type':'Feature','properties':{'id':k,'basis':'inferred variable-width OSM road buffers, unioned once to remove pavement overlap'},'geometry':to_geographic(g,self.origin)} for k,g in self.masks.items()]})
   print('DT_ASPHALT',flush=True);self.mesh.polygon(asphalt,'downtown_road',mat='asphalt',max_segment=4)
   print('DT_SIDEWALK',flush=True);self.mesh.polygon(walk,'downtown_sidewalk',zfun=lambda xy:self.ground(xy[:,0],xy[:,1])+.21,mat='sidewalk',max_segment=4)
   # Curb band is a subset of sidewalk, so a separate same-height top never overlaps it.
   print('DT_CURB',flush=True);curb=asphalt.simplify(.03).buffer(.16,quad_segs=1,join_style=2).difference(asphalt).intersection(walk).simplify(.02);self.mesh.polygon(curb,'downtown_curb',zfun=lambda xy:self.ground(xy[:,0],xy[:,1])+.23,mat='curb',max_segment=4,extrude=.17)
   seeds=self.mesh.save('downtown_seed');self.mesh.pre_saved.extend(seeds);self.mesh.buckets={}
   write_json(cachefile,{'key':key,'meshes':seeds,'masks_wkb':{k:shapely.to_wkb(g).hex() for k,g in self.masks.items()}})
  asphalt=self.masks['asphalt'];walk=self.masks['sidewalk']
  global _WORKER_BUILDER,_ROAD_DATA_KEY
  _WORKER_BUILDER=self;_ROAD_DATA_KEY=digest(self.root/'data/processed/stage04/road_profiles.npz')+digest(self.root/'data/processed/stage04/roads.json')+digest(self.root/'config/stage04.yaml')+digest(self.root/'scripts/stage04_geometry.py')
  import multiprocessing as mp
  step=math.ceil(len(self.roads)/8);jobs=[(j,a,min(a+step,len(self.roads))) for j,a in enumerate(range(0,len(self.roads),step))]
  with mp.get_context('fork').Pool(4) as pool:
   for assets,covered in pool.imap_unordered(_road_worker,jobs):
    self.mesh.pre_saved.extend(assets);self.mesh.feature_coverage.update(covered);print('ROAD_SHARD_COMPLETE',len(assets),'meshes',len(covered),'features',flush=True)
  write_json(self.root/'work/reports/stage04/downtown_surfaces.json',{'asphalt_union_area_m2':asphalt.area,'sidewalk_area_m2':walk.area,'pavement_self_overlap_area_m2':0,'asphalt_sidewalk_overlap_area_m2':asphalt.intersection(walk).area,'method':'set union, difference; rounded inferred curb returns; single drape rule','geometry_source_ids':len(self.dt_indices),'modeling_detail':'overview far; block detail DT; representative intersection markings inferred from local standard and actual node topology'})
 def road_feature(self,i):
  dt=self.refs['downtown'];r=self.roads[i];asphalt=self.masks['asphalt'];walk=self.masks['sidewalk']
  p=r['parameters'];g=self.gs[i];width=p['width_m'];rank=p['vertical_rank'];is_dt='downtown' in r['regions'];zfun=lambda xy,i=i:self.road_z(i,xy)
  poly=g.simplify(.35 if not is_dt else .015).buffer(width/2,quad_segs=1,cap_style=2,join_style=2).intersection(self.city)
  if rank==0 and not p['bridge'] and not p['tunnel']:
   far=poly.difference(dt)
   if not far.is_empty:self.mesh.polygon(far,'full_far',zfun,'cycle' if p['class']=='cycleway' else 'sidewalk' if p['class']=='pedestrian' else 'asphalt',i,max_segment=40)
   if p['class'] not in ['service','parking_aisle','pedestrian','cycleway']:
    ov=g.simplify(3).buffer(width/2,quad_segs=1,cap_style=2,join_style=2).intersection(self.city).difference(dt);self.mesh.polygon(ov,'overview_far',zfun,'asphalt',i,max_segment=120)
   if is_dt and p['class'] in ['pedestrian','cycleway']:
    ped=poly.intersection(dt);ped=self.difference(ped,self.local_mask('asphalt',ped));ped=self.difference(ped,self.local_mask('sidewalk',ped));self.mesh.polygon(ped,'downtown_paths',zfun,'cycle' if p['class']=='cycleway' else 'sidewalk',i,max_segment=4)
   if is_dt:self.mesh.feature_coverage.add(i) # union surface owns geometry; road feature remains editable in profile/index
  else:
   role='tunnel_road' if p['tunnel'] or rank<0 else 'bridge_road'
   self.mesh.polygon(poly,role,zfun,'asphalt',i,max_segment=8 if is_dt else 25,extrude=.65 if role=='bridge_road' else 0)
  if i%10000==0:print('ROAD_GEOMETRY',i,'/',len(self.roads),flush=True)
 def junctions(self):
  graph=json.loads((self.root/'data/processed/stage04/road_graph.json').read_text());observed=[];crossing_evidence=[]
  for row in (self.root/'data/processed/stage04/source_nodes.jsonl').open():
   n=json.loads(row)
   t=n['tags'];x,y=self.tx.transform(n['lon'],n['lat']);point=Point(x-self.origin[0],y-self.origin[1])
   if t.get('highway') in ['traffic_signals','crossing']:crossing_evidence.append(point)
   if t.get('highway')=='traffic_signals' or t.get('crossing')=='traffic_signals' or t.get('crossing:signals')=='yes':observed.append(point)
  # Official signal observations are also accepted as evidence of a signalized junction.
  for path in sorted((self.root/'data/raw/stage04/signals').glob('short_page_*.json')):
   if path.name.endswith('.receipt.json'):continue
   for f in json.loads(path.read_text())['features']:
    g=f.get('geometry')
    if g:
     x,y=self.tx.transform(g['x'],g['y']);point=Point(x-self.origin[0],y-self.origin[1]);observed.append(point);crossing_evidence.append(point)
  otree=STRtree(observed);ctree=STRtree(crossing_evidence);records=[];best=None;ramp_areas=[]
  for nid,n in graph['nodes'].items():
   xy=np.array(n['xyz_m'][:2]);point=Point(xy)
   if not self.refs['downtown'].buffer(-30).covers(point):continue
   arms=[]
   for ei in n['incident_edges']:
    e=graph['edges'][ei];i=e['way_index'];r=self.roads[i];p=r['parameters']
    if p['class'] in ['motorway','trunk','ramp','pedestrian','cycleway','service','parking_aisle'] or p['vertical_rank']!=0:continue
    line=self.gs[i];s=line.project(point);length=line.length
    for direction in [-1,1]:
     ss=np.clip(s+direction*2,0,length);q=np.array(line.interpolate(ss).coords[0]);v=q-xy
     if np.linalg.norm(v)<.1:continue
     v/=np.linalg.norm(v)
     if any(np.dot(v,a['v'])>.97 for a in arms):continue
     arms.append({'i':i,'v':v,'width':p['width_m'],'s':s,'direction':direction})
   if len(arms)<3:continue
   obs=int(otree.nearest(point));dist=point.distance(observed[obs]);signal=dist<25
   crossing_distance=point.distance(crossing_evidence[int(ctree.nearest(point))]);marked=crossing_distance<25
   record={'node_id':nid,'xy_m':xy.tolist(),'arm_count':len(arms),'signal_evidence_distance_m':dist,'signalized_evidence':signal,'placement_status':'crosswalk/stopbar/pole/curb-ramp sizes and offsets inferred, not as-built survey','name':' / '.join(sorted(set(self.roads[a['i']]['name'] or '' for a in arms)))}
   records.append(record)
   record['approximate_marking_evidence_distance_m']=crossing_distance
   record['markings_presence_status']='layout_inferred_not_individual_as_built_verification'
   if marked:
    for a in arms:
     i=a['i'];v=a['v'];normal=np.array([-v[1],v[0]]);w=a['width'];cross_dist=max(z['width']/2 for z in arms)+3.0;center=xy+v*cross_dist;zfun=lambda q,i=i:self.road_z(i,q,.012)
     for side in np.arange(-w/2+.3,w/2-.3,1.0):
      axy=center+normal*side;poly=Polygon([axy-v*1.5-normal*.2,axy+v*1.5-normal*.2,axy+v*1.5+normal*.2,axy-v*1.5+normal*.2]);poly=poly.intersection(self.local_mask('asphalt',poly))
      self.mesh.polygon(poly,'markings',zfun,'white',i,max_segment=2)
     # CA stop line before crosswalk, right-hand traffic inbound half; skip outgoing-only approach.
     p=self.roads[i]['parameters'];incoming=p['oneway'] not in ['yes','1','-1','true'] or (a['direction']==-1 if p['oneway']!='-1' else a['direction']==1)
     if incoming:
      st=center+v*2.3;aa=st+normal*.25;bb=st+normal*(w/2-.3);self.mesh.strip([aa,bb],.45,'markings',zfun,'white',i)
     # A pair of inferred accessibility transitions at either curb end.
     for sign in [-1,1]:
      at=center+normal*sign*(w/2+.4);ramp=Point(at).buffer(.8,quad_segs=1);ramp=ramp.intersection(self.local_mask('sidewalk',ramp));ramp_areas.append(ramp)
      self.mesh.polygon(ramp,'curb_ramp',lambda q:self.ground(q[:,0],q[:,1])+.07+np.clip(shapely.distance(shapely.points(q),self.masks['asphalt']),0,1)*.14,'ramp_tactile',i,max_segment=.6)
     pole=center+normal*(w/2+1.0)+v*2;zz=self.ground(np.array([pole[0]]),np.array([pole[1]]))[0]
     if signal:self.mesh.instance('signal',[*pole,zz+.21],[1,1,1],math.atan2(-v[1],-v[0]),nid)
   if signal and marked and self.refs['historic_core'].covers(point):
    score=point.distance(self.refs['historic_core'].centroid)
    if best is None or score<best[0]:best=(score,record)
  if ramp_areas:
   cut=shapely.unary_union(ramp_areas);walk=self.masks['sidewalk'].difference(cut);curb=self.masks['asphalt'].simplify(.03).buffer(.16,quad_segs=1,join_style=2).difference(self.masks['asphalt']).intersection(walk).simplify(.02)
   self.mesh.buckets={k:v for k,v in self.mesh.buckets.items() if k[0] not in ['downtown_sidewalk','downtown_curb']};self.mesh.pre_saved=[m for m in self.mesh.pre_saved if m['role'] not in ['downtown_sidewalk','downtown_curb']]
   print('DT_SIDEWALK',flush=True);self.mesh.polygon(walk,'downtown_sidewalk',lambda q:self.ground(q[:,0],q[:,1])+.21,'sidewalk',max_segment=4)
   self.mesh.polygon(curb,'downtown_curb',lambda q:self.ground(q[:,0],q[:,1])+.23,'curb',max_segment=4,extrude=.17)
  self.typical=best[1] if best else next(r for r in records if r['signalized_evidence'])
  write_json(self.root/'work/reports/stage04/junctions.json',{'junctions':records,'typical_intersection':self.typical,'local_style_reference':'California MUTCD2026Part3A/B, white same-direction lanes/crosswalks, yellow opposing directions; actual installation geometry remains inferred','signal_instances':sum(x['kind']=='signal' for x in self.mesh.instances)})
  print('DOWNTOWN_JUNCTIONS',len(records),'TYPICAL',self.typical,flush=True)
 def details(self):
  # Select real US101/CA110 crossing from source ref tags near the Four Level Interchange.
  crossings=json.loads((self.root/'work/reports/stage04/crossings.json').read_text());candidates=[]
  for c in crossings:
   tags=[self.roads[c[k]]['tags'].get('ref','') for k in ['a','b']]
   if any('101' in t for t in tags) and any('110' in t for t in tags) and np.linalg.norm(np.array(c['xy_m'])-[-250,2650])<1200:candidates.append(c)
  self.interchange=np.median([c['xy_m'] for c in candidates],axis=0).tolist() if candidates else [-250,2650]
  study=Point(self.interchange).buffer(650).union(self.refs['downtown'])
  for i,r in enumerate(self.roads):
   if not self.gs[i].intersects(study):continue
   p=r['parameters'];g=self.gs[i];w=p['width_m'];rank=p['vertical_rank'];k=r['profile_start'];nn=r['profile_count'];length=g.length
   if p['class'] in ['pedestrian','cycleway','service','parking_aisle'] or rank<0:continue
   # Lane patterns are geometric markings, no thousands of separate Blender objects.
   for boundary in range(1,p['lanes']):
    offset=-w/2+p['shoulder_m']+boundary*(w-2*p['shoulder_m'])/p['lanes'];opp=p['oneway'] not in ['yes','1','-1','true'] and boundary==p['lanes']//2;material='yellow' if opp else 'white';line=g.offset_curve(offset,quad_segs=1)
    for part in lines(line.intersection(study)):
     for s in np.arange(0,part.length,12):
      end=min(s+(12 if opp else 3),part.length)
      if end-s<.05:continue
      from shapely.ops import substring
      seg=substring(part,s,end)
      if seg.geom_type!='LineString':continue
      self.mesh.strip(np.asarray(seg.coords),.12,'markings',lambda xy,i=i:self.road_z(i,xy,.015),material,i)
   # Edge/shoulder lines and repeated guardrails on elevated freeway infrastructure.
   if p['class'] in ['motorway','trunk','ramp'] or p['bridge']:
    for sign in [-1,1]:
     line=g.offset_curve(sign*(w/2-.3),quad_segs=1)
     for part in lines(line.intersection(study)):
      self.mesh.strip(np.asarray(part.coords),.15,'markings',lambda xy,i=i:self.road_z(i,xy,.015),'white',i)
      for s in np.arange(0,part.length,8):
       end=min(s+8,part.length);a=np.array(part.interpolate(s).coords[0]);b=np.array(part.interpolate(end).coords[0]);v=b-a;lengthpiece=np.linalg.norm(v)
       if lengthpiece<.05:continue
       c=(a+b)/2;z=self.road_z(i,c[None,:])[0];self.mesh.instance('guardrail',[*c,z+.75],[lengthpiece,.14,.35],math.atan2(v[1],v[0]),r['id'])
   if p['bridge'] or rank>0:
    # Piersonly if adequate estimated ground clearance; piers are inferred and kept out of lower carriageways.
    for s in np.arange(15,length-10,35):
     q=np.array(g.interpolate(s).coords[0]);pt=Point(q)
     if not study.covers(pt):continue
     z=self.road_z(i,q[None,:])[0]-.65;ground=self.ground(q[:1],q[1:])[0];height=z-ground
     blocked=False
     for c in crossings:
      if c['upper']==i and np.linalg.norm(np.array(c['xy_m'])-q)<max(18,self.roads[c['b'] if c['a']==i else c['a']]['parameters']['width_m']/2+4):blocked=True;break
     if height>2 and not blocked:self.mesh.instance('pier',[*q,ground+height/2],[1.1,1.6,height],0,r['id'])
   # Turn arrows only when a source lane tag supports the lane assignment.
   turn=r['tags'].get('turn:lanes') or r['tags'].get('turn:lanes:forward')
   if turn and 'downtown' in r['regions']:
    for lane,tag in enumerate(turn.split('|')):
     if not any(x in tag for x in ['left','right','through']):continue
     s=max(2,length-22);q=np.array(g.interpolate(s).coords[0]);q2=np.array(g.interpolate(min(length,s+2)).coords[0]);v=q2-q
     if np.linalg.norm(v)<.01:continue
     v/=np.linalg.norm(v);normal=np.array([-v[1],v[0]]);center=q+normal*(-w/2+(lane+.5)*w/max(p['lanes'],len(turn.split('|'))));base=center-v*1.5;arrow_dir=normal if 'left' in tag else -normal if 'right' in tag else v;tip=center+arrow_dir*1.3
     self.mesh.strip([base,tip],.18,'markings',lambda xy,i=i:self.road_z(i,xy,.02),'white',i)
     an=np.array([-arrow_dir[1],arrow_dir[0]]);h=Polygon([tip+arrow_dir*.5,tip-arrow_dir*.25+an*.45,tip-arrow_dir*.25-an*.45]);self.mesh.polygon(h,'markings',lambda xy,i=i:self.road_z(i,xy,.02),'white',i,max_segment=1)
  write_json(self.root/'work/reports/stage04/interchange.json',{'center_local_m':self.interchange,'source_crossing_records':candidates,'study_radius_m':650,'real_location_basis':'intersection of OSM US101 and CA110 ref-tagged ways; not relocated into Downtown','deck_thickness_m':.65,'clearance_design_estimate_m':5.2,'pier_placement':'inferred every35m, excludes known lower crossing corridors; not engineering/as-built','noise_barrier':'only observed OSM noise_barrier geometry; no invented continuous screens'})
 def other(self):
  counts=collections.Counter();features=[]
  for w in json.loads((self.root/'data/processed/stage04/other_transport.json').read_text()):
   tags=w['tags'];ll=np.array(w['lonlat']);x,y=self.tx.transform(ll[:,0],ll[:,1]);xy=np.column_stack([x-self.origin[0],y-self.origin[1]]);line=LineString(xy);clip=line.intersection(self.city);rank,bridge,tunnel=grade_rank(tags);rail=tags.get('railway');aero=tags.get('aeroway');barrier=tags.get('barrier');width=None;status='modeled'
   def zfun(q,rank=rank,bridge=bridge):return self.ground(q[:,0],q[:,1])+.09+rank*(6 if rank>0 else 7)
   fid=-(w['source_id']+10) # external source kept in object index, int face IDs reserved road indices
   if rail in ['rail','light_rail','tram','subway','narrow_gauge','monorail']:
    counts['rail_track_ways']+=1;width=3.6
    self.mesh.polygon(line.buffer(1.8,cap_style=2,quad_segs=1),'rail_corridor',zfun,'rail_ballast',-1,max_segment=20,extrude=.6 if bridge else 0)
    gauge=number(tags.get('gauge'));gauge=gauge/1000 if gauge and gauge>10 else gauge or 1.435
    if not .5<gauge<2:gauge=1.435
    if line.distance(self.refs['downtown'])<1000:
     for off in [-gauge/2,gauge/2]:
      for part in lines(line.offset_curve(off,quad_segs=1).intersection(self.city)):
       self.mesh.strip(np.asarray(part.coords),.07,'rail_detail',lambda q,zfun=zfun:zfun(q)+.12,'rail_steel',-1)
     for s in np.arange(0,line.length,2.4):
      p=np.array(line.interpolate(s).coords[0]);q=np.array(line.interpolate(min(line.length,s+.5)).coords[0]);v=q-p
      if np.linalg.norm(v)<.01:continue
      z=zfun(p[None,:])[0]
      if self.city.covers(Point(p)):self.mesh.instance('sleeper',[*p,z+.04],[.22,gauge+.6,.11],math.atan2(v[1],v[0]),w['id'])
   elif rail=='platform' or tags.get('public_transport')=='platform':
    counts['platforms']+=1
    poly=Polygon(xy) if np.linalg.norm(xy[0]-xy[-1])<.01 and len(xy)>3 else line.buffer(1.5,cap_style=2)
    if not poly.is_valid:poly=shapely.make_valid(poly)
    self.mesh.polygon(poly,'station_platform',lambda q,zfun=zfun:zfun(q)+.4,'platform',-1,max_segment=5,extrude=.35)
    # Compact inferred canopy uses source platform, only Downtown, never a random station footprint.
    if poly.intersects(self.refs['downtown']) and not tunnel and rank>=0:
     c=poly.representative_point();z=zfun(np.array([[c.x,c.y]]))[0];b=poly.minimum_rotated_rectangle;coords=np.asarray(b.exterior.coords);lengths=np.linalg.norm(np.diff(coords,axis=0),axis=1);j=int(np.argmax(lengths));v=coords[j+1]-coords[j];length=lengths[j];width=min(lengths)
     if length>8:self.mesh.instance('canopy',[c.x,c.y,z+3.1],[min(length*.65,70),min(width*.8,5),.18],math.atan2(v[1],v[0]),w['id'])
   elif aero in ['runway','taxiway']:
    counts[aero]+=1;width=number(tags.get('width')) or (45 if aero=='runway' else 18)
    poly=line.buffer(width/2,cap_style=2,quad_segs=1);self.mesh.polygon(poly,'airport_surface',lambda q:self.ground(q[:,0],q[:,1])+.08,'runway',-1,max_segment=25)
    for part in lines(clip):self.mesh.strip(np.asarray(part.coords),.3 if aero=='runway' else .15,'airport_marking',lambda q:self.ground(q[:,0],q[:,1])+.10,'white' if aero=='runway' else 'yellow',-1)
   elif aero=='apron' and len(xy)>3 and np.linalg.norm(xy[0]-xy[-1])<.01:
    poly=shapely.make_valid(Polygon(xy));counts['apron']+=1;self.mesh.polygon(poly,'airport_apron',lambda q:self.ground(q[:,0],q[:,1])+.04,'apron',-1,max_segment=40)
   elif barrier in ['guard_rail','noise_barrier']:
    counts[barrier]+=1
    if line.distance(self.refs['downtown'])<3000:
     for part in lines(clip):
      for s in np.arange(0,part.length,8):
       a=np.array(part.interpolate(s).coords[0]);b=np.array(part.interpolate(min(s+8,part.length)).coords[0]);v=b-a;c=(a+b)/2
       if np.linalg.norm(v)<.01:continue
       z=self.ground(c[:1],c[1:])[0];height=number(tags.get('height')) or (3.0 if barrier=='noise_barrier' else .65);self.mesh.instance('noise_screen' if barrier=='noise_barrier' else 'guardrail',[*c,z+height/2],[np.linalg.norm(v),.2,height],math.atan2(v[1],v[0]),w['id'])
    else:status='source_geometry_retained_far_detail_deferred'
   else:status='reference_only_non_operational_or_unsupported_tag';counts['reference_only']+=1
   features.append({'id':w['id'],'tags':tags,'edit_timestamp':w['edit_timestamp'],'status':status,'inferred_width_m':width if not tags.get('width') else None,'inferred_fields':['elevation','deck_clearance','track_corridor_width','canopy_if_any'],'capture_year':None,'numeric_accuracy_m':None})
  write_json(self.root/'data/processed/stage04/other_transport_inventory.json',features);write_json(self.root/'work/reports/stage04/rail_airport_port.json',{'counts':dict(counts),'rail_status':'OSM rail tracks/corridors with bridge/tunnel/layer estimates, subway geometry occluded underground; no measured tunnel depth','platforms':'source OSM geometry; simple DT canopy inferred, not station architecture','airport':'actual OSM runway/taxiway/apron XY, widths use tags or explicit45m/18m fallback; no invented runway geometry outside coverage','port':'actual OSM road/service/rail geometry inside official Port planning study area, Census marine terminal references; no berth engineering model','official_metro':'107 station records/6 line records acquired separately for comparison; age unknown, not authoritative current service statement','restrictions':'rail vertical offsets not surveyed; crossings with roads require explicit anomaly report'})
 def run(self):
  self.roadbed();self.road_surfaces();self.junctions();self.details();self.other();index=self.mesh.save()
  data={'base_active_lods':self.ground.active,'ground_variants':self.ground_variant,'mesh_index':'data/processed/stage04/mesh_index.json','typical_intersection':self.typical,'interchange_center_m':self.interchange,'triangles_by_role':dict(collections.Counter({role:sum(m['triangles'] for m in index if m['role']==role) for role in set(m['role'] for m in index)})),'ground_barycentric_boundary_fallbacks':self.ground.fallbacks}
  write_json(self.root/'work/reports/stage04/geometry.json',data);print('GEOMETRY_COMPLETE',json.dumps(data['triangles_by_role']),flush=True)
def _road_worker(task):
 j,start,end=task;b=_WORKER_BUILDER;cache=b.root/f'work/cache/stage04/shard{j}_index.json'
 if cache.exists():
  old=json.loads(cache.read_text())
  if old.get('input_key')==_ROAD_DATA_KEY and old.get('job_range')==[start,end] and all((b.root/m['file']).exists() and digest(b.root/m['file'])==m['sha256'] for m in old['meshes']):
   print('ROAD_SHARD_CACHE_VERIFIED',j,flush=True);return old['meshes'],old['feature_indices_with_geometry']
 b.mesh=Meshes(b.root,b.ground)
 for i in range(start,end):
  try:b.road_feature(i)
  except Exception:
   print('FAILED_ROAD_FEATURE',i,b.roads[i]['id'],flush=True);raise
 index=b.mesh.save('shard'+str(j));meta=json.loads(cache.read_text());meta['input_key']=_ROAD_DATA_KEY;meta['job_range']=[start,end];meta['overlay_repairs']=dict(b.fid_counts);write_json(cache,meta)
 return index,sorted(b.mesh.feature_coverage)
if __name__=='__main__':Builder().run()
