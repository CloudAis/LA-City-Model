"""Source-owned building meshes. Rooflines remain labelled proxies; no random heights.

Every feature belongs to exactly one centroid cell, including cross-cell buildings.
The face building_index attribute resolves to buildings.sqlite.i. Runtime meshes are
separate, mutually exclusive representations, not duplicate active building bodies.
"""
import collections,gzip,json,math,sqlite3,time,hashlib
from pathlib import Path
import numpy as np,shapely,yaml
from shapely.geometry import Polygon,LineString,Point
from shapely.ops import split
from stage03_common import polygon_parts,references
from stage04_geometry import Ground
from stage03_surface import Surface
from stage05_data import cell
from stage05_preserve import sha
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]

def materials(cfg):
 out=[('wall_'+k,v['color']) for k,v in cfg['types'].items()]
 out += [('roof',[.25,.26,.25,1]),('foundation',[.39,.38,.35,1]),('glass',[.10,.19,.24,1]),('frame',[.18,.20,.20,1]),('door',[.19,.17,.14,1]),('metal',[.45,.47,.47,1]),('brick_trim',[.53,.40,.29,1])]
 return out

class Mesh:
 def __init__(self):self.v=[];self.f=[];self.m=[];self.uv=[];self.lookup={};self.removed=0
 def vertex(self,v):
  k=tuple(round(float(x),6) for x in v)
  if k not in self.lookup:self.lookup[k]=len(self.v);self.v.append(k)
  return self.lookup[k]
 def tri(self,xyz,mat,uv=None):
  ids=[self.vertex(x) for x in xyz]
  if len(set(ids))<3:self.removed+=1;return
  self.f.append(ids);self.m.append(mat);self.uv.append(uv if uv is not None else [[0,0]]*3)
 def quad(self,xyz,mat,uv=None):
  ids=[self.vertex(x) for x in xyz]
  for q in [[0,1,2],[0,2,3]]:
   self.f.append([ids[i] for i in q]);self.m.append(mat);self.uv.append([uv[i] for i in q] if uv is not None else [[0,0]]*3)
 def caps(self,p,z,mat,up=True):
  tris=shapely.constrained_delaunay_triangles(p)
  if tris.is_empty:return
  xy=shapely.get_coordinates(tris).reshape(-1,4,2)[:,:3];cross=(xy[:,1,0]-xy[:,0,0])*(xy[:,2,1]-xy[:,0,1])-(xy[:,1,1]-xy[:,0,1])*(xy[:,2,0]-xy[:,0,0]);flip=(cross>0)!=up;xy[flip]=xy[flip][:,[0,2,1]];flat=xy.reshape(-1,2);zz=z(flat) if callable(z) else np.full(len(flat),z);xyz=np.column_stack([flat,zz]).reshape(-1,3,3)
  for q in xyz:self.tri(q,mat)
 def wall(self,a,b,z0a,z0b,z1a,z1b,mat,uv=None):self.quad([[*a,z0a],[*b,z0b],[*b,z1b],[*a,z1a]],mat,uv)

def simplify(g,tol,maxratio):
 h=g.simplify(tol,preserve_topology=True)
 if not h.is_valid or abs(h.area-g.area)>maxratio*g.area or sum(len(p.interiors) for p in polygon_parts(h))!=sum(len(p.interiors) for p in polygon_parts(g)) or len(polygon_parts(h))!=len(polygon_parts(g)):return g
 return h

def roof_sections(p,shape,roof_h):
 """Split at a real geometric ridge so triangulation cannot erase the roof peak."""
 if shape in ['flat','terrace'] or roof_h<=0:return [p],lambda xy:np.ones(len(xy))
 rect=np.asarray(p.minimum_rotated_rectangle.exterior.coords)[:4];axes=np.diff(np.vstack([rect,rect[0]]),axis=0);lens=np.linalg.norm(axes,axis=1);long=axes[np.argmax(lens)];long/=np.linalg.norm(long);short=np.array([-long[1],long[0]]);proj=np.asarray(p.exterior.coords)[:,:2]@short;lo,hi=proj.min(),proj.max();width=max(hi-lo,.01);middle=(lo+hi)/2
 if shape in ['gabled','gable','round','barrel']:
  center=np.asarray(p.centroid.coords[0]);center+=short*(middle-center@short);line=LineString([center-long*100000,center+long*100000]);pieces=polygon_parts(split(p,line));return pieces,lambda xy:np.clip(1-2*abs(xy@short-middle)/width,0,1)
 if shape in ['skillion','lean_to']:return [p],lambda xy:np.clip((xy@short-lo)/width,0,1)
 # Hipped/pyramidal forms use ridge splits in two axes, retaining courtyard holes.
 if shape in ['hipped','pyramidal','pyramid','half-hipped']:
  center=np.asarray(p.centroid.coords[0]);pp=np.asarray(p.exterior.coords)[:,:2]@long;l0,l1=pp.min(),pp.max();midlong=(l0+l1)/2;center+=short*(middle-center@short)+long*(midlong-center@long)
  pieces=[p]
  for direction in [long,short,(long+short)/math.sqrt(2),(long-short)/math.sqrt(2)]:
   line=LineString([center-direction*100000,center+direction*100000]);pieces=[q for a in pieces for q in polygon_parts(split(a,line))]
  return pieces,lambda xy:np.clip(np.minimum(1-2*abs(xy@short-middle)/width,1-2*abs(xy@long-midlong)/max(l1-l0,.01)),0,1)
 return [p],lambda xy:np.ones(len(xy))

def partitioned_bands(g,a,height):
 parts=a.get('parts',[])
 if not parts:return [(g,0.,height)]
 pod=max(0,min(a.get('podium_height_m',height),height));stops=sorted({0.,pod,height,*[max(0,min(height,p[k])) for p in parts for k in ['min_height_m','height_m']]});bands=[]
 for lo,hi in zip(stops[:-1],stops[1:]):
  if hi-lo<.01:continue
  if lo<pod-.001:poly=g
  else:
   selected=[shapely.from_wkb(bytes.fromhex(p['geometry_wkb_hex'])) for p in parts if p['min_height_m']<hi and p['height_m']>lo]
   if not selected:
    highest=max(parts,key=lambda p:p['height_m']);selected=[shapely.from_wkb(bytes.fromhex(highest['geometry_wkb_hex']))]
   poly=shapely.union_all(selected).intersection(g)
  if not poly.is_empty:bands.append((poly,lo,hi))
 return bands or [(g,0.,height)]

def fast_shell(g,a,base,bottom,mat,runtime):
 """Indexed bulk extrusion for overview cells; the same holes and roof ridges survive.

 Avoid per-triangle Python/NumPy allocations across a million small buildings.
 Roof and bottom share the cap triangulation; boundary vertices weld to both.
 """
 out=Mesh();vv=[];ff=[];mm=[];offset=0;stats=collections.Counter();h=a['height_m'];minimum=a['minimum_height_m'];shape='flat' if runtime else a['roof_shape'];rh=0 if runtime else a['roof_height_m'];supported=shape in ['flat','terrace','gabled','gable','round','barrel','skillion','lean_to','hipped','pyramidal','pyramid','half-hipped']
 if not supported:shape='flat';rh=0;stats['unsupported_roof_shape_flat_proxy']+=1
 for p in polygon_parts(shapely.orient_polygons(g)):
  pieces,profile=roof_sections(p,shape,rh);triangles=shapely.get_coordinates(shapely.constrained_delaunay_triangles(shapely.GeometryCollection(pieces))).reshape(-1,4,2)[:,:3]
  if not len(triangles):continue
  xy,inverse=np.unique(np.round(triangles.reshape(-1,2),6),axis=0,return_inverse=True);top=inverse.reshape(-1,3);cross=(xy[top[:,1],0]-xy[top[:,0],0])*(xy[top[:,2],1]-xy[top[:,0],1])-(xy[top[:,1],1]-xy[top[:,0],1])*(xy[top[:,2],0]-xy[top[:,0],0]);neg=cross<0;top[neg]=top[neg][:,[0,2,1]];n=len(xy);roof=base+h-rh+rh*profile(xy);low=base+minimum if minimum else bottom;v=np.vstack([np.column_stack([xy,roof]),np.column_stack([xy,np.full(n,low)]),np.column_stack([xy,np.full(n,base+minimum)])]);faces=[top,top[:,[0,2,1]]+n];mats=[np.full(len(top),mat['roof'],np.uint8),np.full(len(top),mat['foundation'],np.uint8)]
  # Only edges used once in the roof triangulation bound the exterior/courtyards.
  # This avoids geometric nearest-point tests and also includes ridge edge splits.
  edges=np.vstack([top[:,[0,1]],top[:,[1,2]],top[:,[2,0]]]);canonical=np.sort(edges,axis=1);_,idx,counts=np.unique(canonical,axis=0,return_index=True,return_counts=True);boundary=edges[idx[counts==1]];ia=boundary[:,0];ib=boundary[:,1]
  if minimum==0 and not runtime:
   faces.extend([np.column_stack([ia+n,ib+n,ib+2*n]),np.column_stack([ia+n,ib+2*n,ia+2*n])]);mats.extend([np.full(len(ia),mat['foundation'],np.uint8)]*2);b=2*n
  else:b=n
  faces.extend([np.column_stack([ia+b,ib+b,ib]),np.column_stack([ia+b,ib,ia])]);mats.extend([np.full(len(ia),mat['wall_'+a['building_type']],np.uint8)]*2)
  vv.append(v);ff.append(np.vstack(faces)+offset);mm.append(np.concatenate(mats));offset+=len(v)
 out.v=np.vstack(vv) if vv else np.empty((0,3));out.f=np.vstack(ff) if ff else np.empty((0,3),int);out.m=np.concatenate(mm) if mm else np.empty(0,np.uint8);out.uv=[];return out,[],stats

def geometry(g,a,index,base,bottom,visual,mat, runtime=False):
 if (visual==0 or runtime) and not a.get('parts') and not a.get('reference'):return fast_shell(g,a,base,bottom,mat,runtime)
 mesh=Mesh();wallmat=mat['wall_'+a['building_type']];h=a['height_m'];minimum=a['minimum_height_m'];instances=[];stats=collections.Counter();roofshape=a['roof_shape'];rh=a['roof_height_m'];window_count=0
 if runtime:visual=0;roofshape='flat';rh=0
 bands=partitioned_bands(g,a,h)
 if len(bands)>1:
  # Vertical interval unions form one effective shell. No full-height parent prism.
  for j,(poly,lo,hi) in enumerate(bands):
   prev=bands[j-1][0] if j else shapely.GeometryCollection();nxt=bands[j+1][0] if j+1<len(bands) else shapely.GeometryCollection()
   for p in polygon_parts(shapely.orient_polygons(poly)):
    for ring in [p.exterior,*p.interiors]:
     xy=np.asarray(ring.coords)[:,:2]
     for x,y in zip(xy[:-1],xy[1:]):mesh.wall(x,y,bottom if j==0 and minimum==0 else base+max(lo,minimum),bottom if j==0 and minimum==0 else base+max(lo,minimum),base+hi,base+hi,wallmat,[[0,0],[np.linalg.norm(y-x)/2.2,0],[np.linalg.norm(y-x)/2.2,(hi-lo)/max(h/a['levels'],2)],[0,(hi-lo)/max(h/a['levels'],2)]])
   mesh.caps(poly.difference(nxt),base+hi,mat['roof'],True)
   mesh.caps(poly.difference(prev),bottom if j==0 and minimum==0 else base+max(lo,minimum),mat['foundation'],False)
  stats['partitioned_parts']=1
 else:
  for p in polygon_parts(shapely.orient_polygons(g)):
   shapes,profile=roof_sections(p,roofshape,rh);supported=roofshape in ['flat','terrace','gabled','gable','round','barrel','skillion','lean_to','hipped','pyramidal','pyramid','half-hipped']
   if not supported:stats['unsupported_roof_shape_flat_proxy']+=1;rh=0
   parapet_allowance=.7 if visual and roofshape in ['flat','terrace'] and h>2 else 0
   topfun=lambda xy:base+h-parapet_allowance-rh+rh*profile(xy)
   # Include ridge intersections on side boundaries, so roof/wall edges share vertices.
   points=np.concatenate([np.asarray(q.exterior.coords)[:,:2] for q in shapes]);extra=shapely.MultiPoint(points)
   for ring in [p.exterior,*p.interiors]:
    original=np.asarray(ring.coords)[:,:2]
    for aa,bb in zip(original[:-1],original[1:]):
     d=bb-aa;length=np.linalg.norm(d)
     if length<1e-6:continue
     fractions=[0.,1.]
     t=(points-aa)@d/(length*length);on=(t>1e-7)&(t<1-1e-7)&(np.abs((points[:,0]-aa[0])*d[1]-(points[:,1]-aa[1])*d[0])<length*1e-5)
     fractions+=t[on].tolist();fractions=sorted(set(round(float(v),9) for v in fractions))
     for t0,t1 in zip(fractions[:-1],fractions[1:]):
      x=aa+d*t0;y=aa+d*t1;z1,z2=topfun(np.array([x,y]));wallbottom=base+minimum if minimum else bottom;floor=base+minimum;seglen=np.linalg.norm(y-x);storey=max(2,(h-rh)/a['levels']);uv=[[t0*length/2.2,0],[t1*length/2.2,0],[t1*length/2.2,(z2-floor)/storey],[t0*length/2.2,(z1-floor)/storey]]
      if not runtime and minimum==0:mesh.wall(x,y,wallbottom,wallbottom,base,base,mat['foundation'])
      low=wallbottom if runtime else floor
      # Closeup wall openings are geometric recesses with glass and reveals.
      ncol=max(1,int(seglen/2.8));nrow=max(1,min(24,int((min(z1,z2)-low)/storey)));estimated=ncol*nrow
      if visual==2 and window_count+estimated<=180 and seglen>2 and min(z1,z2)-low>2.5:
       direction=(y-x)/seglen;outward=np.array([direction[1],-direction[0]]);depth=.12
       for r in range(nrow):
        zl=low+r*storey;zh=low+(r+1)*storey
        if zh-zl<1:continue
        for c in range(ncol):
         left=x+direction*(seglen*c/ncol);right=x+direction*(seglen*(c+1)/ncol);w=(seglen/ncol)*.58;center=(left+right)/2;wa=center-direction*w/2;wb=center+direction*w/2;wb0=zl+(zh-zl)*.27;wt=zl+(zh-zl)*.78
         mesh.wall(left,wa,zl,zl,zh,zh,wallmat);mesh.wall(wb,right,zl,zl,zh,zh,wallmat);mesh.wall(wa,wb,zl,zl,wb0,wb0,wallmat);mesh.wall(wa,wb,wt,wt,zh,zh,wallmat)
         front=np.array([[*wa,wb0],[*wb,wb0],[*wb,wt],[*wa,wt]]);back=front-np.array([*outward,0])*depth
         mesh.quad(back,mat['glass'])
         for k in range(4):mesh.quad([front[k],front[(k+1)%4],back[(k+1)%4],back[k]],mat['frame'])
         instances.append({'kind':'window_frame','xyz':[*center,(wb0+wt)/2],'scale':[w,.09,wt-wb0],'rotation':math.atan2(direction[1],direction[0]),'fid':index});stats['recessed_windows']+=1;window_count+=1
       if abs(z1-z2)>.00001 or min(z1,z2)>low+nrow*storey+.0001:mesh.wall(x,y,low+nrow*storey,low+nrow*storey,z1,z2,wallmat)
      else:mesh.wall(x,y,low,low,z1,z2,wallmat,uv if visual else None)
   for q in shapes:mesh.caps(q,topfun,mat['roof'])
   mesh.caps(p,base+minimum if minimum else bottom,mat['foundation'],False)
   if visual and roofshape in ['flat','terrace']:
    # Parapets are thin shared modules; inferred, never treated as observed roof equipment.
    for ring in [p.exterior,*p.interiors]:
     xy=np.asarray(ring.coords)[:,:2]
     for x,y in zip(xy[:-1],xy[1:]):
      length=np.linalg.norm(y-x)
      if length>1:instances.append({'kind':'parapet','xyz':[*((x+y)/2),base+h-.35],'scale':[length,.18,.7],'rotation':math.atan2(*(y-x)[::-1]),'fid':index})
    if p.area>80:
     q=p.representative_point();inset=p.buffer(-2)
     if not inset.is_empty and inset.covers(q):
      instances.append({'kind':'hvac','xyz':[q.x,q.y,base+h-.35],'scale':[1.5,1.2,.65],'rotation':0.,'fid':index});stats['inferred_roof_hvac']+=1
 # Wilshire tip is a narrow visual proxy; published total never inflates the body.
 if a.get('reference',{} ) and a['reference'].get('spire'):
  p=max(polygon_parts(bands[-1][0]),key=lambda p:p.area);q=p.representative_point();tip=base+a['reference']['total_m'];z=base+h;radius=min(.7,q.distance(p.boundary)*.8)
  for j in range(8):
   t=j*math.pi/4;u=(j+1)*math.pi/4;mesh.tri([[q.x+radius*math.cos(t),q.y+radius*math.sin(t),z],[q.x+radius*math.cos(u),q.y+radius*math.sin(u),z],[q.x,q.y,tip]],mat['metal'])
  stats['approximate_spires_with_verified_total_height']+=1
 return mesh,instances,stats

class Worker:
 def __init__(self,root):
  self.root=Path(root);self.cfg=yaml.safe_load((self.root/'config/stage05.yaml').read_text());self.mat={n:i for i,(n,c) in enumerate(materials(self.cfg))};self.ground=Ground(self.root);self.surface=None;self.db=sqlite3.connect(self.root/'data/processed/stage05/buildings.sqlite');self.entry_nodes=None;self.sidewalk=None;self.signature=hashlib.sha256((sha(Path(__file__))+sha(self.root/'config/stage05.yaml')+json.loads((self.root/'work/reports/stage05/building_data.json').read_text())['sqlite_sha256']).encode()).hexdigest()
 def entrance(self,g,a,index,base,bottom):
  from shapely.strtree import STRtree
  from stage03_common import local_features
  if self.entry_nodes is None:
   conn=sqlite3.connect(self.root/'data/processed/stage05/osm_buildings.sqlite');self.entry_nodes=[(uid,Point(x,y)) for uid,x,y,t in conn.execute('SELECT uid,x,y,tags FROM nodes') if 'entrance' in json.loads(t)];conn.close();self.entry_tree=STRtree([r[1] for r in self.entry_nodes]);self.sidewalk=shapely.union_all([p for f,g in local_features(self.root,'data/processed/stage04/downtown_surface_masks.geojson') if f['properties']['id']=='sidewalk' for p in polygon_parts(shapely.make_valid(g) if not g.is_valid else g)])
  p=max(polygon_parts(g),key=lambda p:p.area);boundary=p.exterior;near=self.entry_tree.query(p.buffer(1));node=min([self.entry_nodes[int(j)] for j in near],key=lambda r:boundary.distance(r[1]),default=None)
  if node:point=boundary.interpolate(boundary.project(node[1]));source=node[0];method='OSM entrance position projected to primary roofline proxy'
  elif not self.sidewalk.is_empty:
   from shapely.ops import nearest_points
   point=nearest_points(boundary,self.sidewalk)[0];source='stage04 sidewalk inferred from tagged road widths';method='inferred road-facing entry; not observed doorway'
  else:point=boundary.interpolate(boundary.length*.25);source=None;method='inferred boundary fallback'
  d=boundary.project(point);x=np.asarray(boundary.interpolate(max(0,d-.05)).coords[0]);y=np.asarray(boundary.interpolate(min(boundary.length,d+.05)).coords[0]);direction=y-x;direction/=max(np.linalg.norm(direction),1e-6);outward=np.array([direction[1],-direction[0]]);angle=math.atan2(direction[1],direction[0]);cx,cy=point.x,point.y;ins=[{'kind':'entry_door','xyz':[cx,cy,base+1.15],'scale':[1.8,.14,2.3],'rotation':angle,'fid':index},{'kind':'canopy','xyz':[cx+outward[0]*.65,cy+outward[1]*.65,base+2.6],'scale':[2.4,1.5,.12],'rotation':angle,'fid':index}]
  zz=self.ground(np.array([cx+outward[0]*1.1]),np.array([cy+outward[1]*1.1]))[0];rise=base-float(zz) if np.isfinite(zz) else base-bottom;steps=max(0,math.ceil(max(0,rise)/.17));unresolved=steps>8
  if not unresolved:
   for j in range(steps):
    depth=(steps-j)*.28;ins.append({'kind':'step','xyz':[cx+outward[0]*depth/2,cy+outward[1]*depth/2,base-(j+.5)*rise/max(steps,1)],'scale':[2.,depth,max(.04,rise/max(steps,1))],'rotation':angle,'fid':index})
  return ins,{'position_xy_m':[cx,cy],'source':source,'method':method,'rise_m':rise,'steps':steps if not unresolved else None,'connection_unresolved':unresolved,'accessibility_compliance':'unknown; not an engineered accessible route'}
 def process(self,owner):
  folder=self.root/'data/processed/stage05/meshes';folder.mkdir(parents=True,exist_ok=True);receipt=folder/(owner+'.json')
  if receipt.exists():
   r=json.loads(receipt.read_text())
   if r.get('signature')==self.signature and all((self.root/x['file']).exists() and sha(self.root/x['file'])==x['sha256'] for x in r['meshes']):return r
  rows=self.db.execute('SELECT i,uid,geom,attrs,visual FROM buildings WHERE cell=? AND active=1 ORDER BY i',(owner,)).fetchall();v0=[];f0=[];m0=[];ids0=[];uv0=[];v2=[];f2=[];m2=[];ids2=[];instances=[];placement=[];n0=n2=0;counts=collections.Counter();origin=None
  samples=[];shapes=[]
  for index,uid,wkb,astr,visual in rows:
   g=shapely.from_wkb(wkb);a=json.loads(astr);_,origin,size=cell(g,visual);tol=[self.cfg['geometry'][k] for k in ['city_simplify_m','downtown_simplify_m','closeup_simplify_m']][visual];g0=simplify(g,tol,self.cfg['geometry']['maximum_area_change_ratio']);g2=simplify(g,max(.75,tol),.04);start=len(samples)
   for p in polygon_parts(g0):
    ring=shapely.segmentize(p,self.cfg['ground']['sample_boundary_step_m']);samples.extend(shapely.get_coordinates(ring).tolist());samples.append(list(p.representative_point().coords[0]))
   shapes.append((index,uid,g,g0,g2,a,visual,start,len(samples)))
  if not samples:return {'id':owner,'meshes':[],'placements':None,'counts':{}}
  xy=np.asarray(samples);zz=self.ground(xy[:,0],xy[:,1]);fallback=~np.isfinite(zz)
  if fallback.any():
   if self.surface is None:self.surface=Surface(self.root)
   zz[fallback]=self.surface(xy[fallback,0],xy[fallback,1])
  for index,uid,g,g0,g2,a,visual,start,end in shapes:
   z=zz[start:end];valid=z[np.isfinite(z)]
   if len(valid)==0:counts['no_ground_buildings_not_fabricated']+=1;placement.append({'i':index,'id':uid,'built':False,'reason':'no finite ground source'});continue
   base=float(valid.max()+self.cfg['ground']['floor_above_highest_sample_m']);bottom=float(valid.min()-self.cfg['ground']['foundation_embed_m']);relief=float(valid.max()-valid.min());counts['ground_fallback_samples']+=int(fallback[start:end].sum());counts['ground_unresolved_samples']+=int((~np.isfinite(z)).sum())
   h0,ins,st=geometry(g0,a,index,base,bottom,visual,self.mat);h2,_,_=geometry(g2,a,index,base,bottom,0,self.mat,True);counts.update(st);instances.extend(ins);entry=None
   if visual and a['minimum_height_m']==0:
    entry_ins,entry=self.entrance(g0,a,index,base,bottom);instances.extend(entry_ins);counts['inferred_or_tagged_entries']+=1;counts['entrance_connection_unresolved']+=entry['connection_unresolved']
   for mesh,vl,fl,ml,il,ul,n in [(h0,v0,f0,m0,ids0,uv0,n0),(h2,v2,f2,m2,ids2,None,n2)]:
    v=np.asarray(mesh.v,float)-origin;f=np.asarray(mesh.f,np.int32);vl.append(v.astype(np.float32));fl.append(f+n);ml.extend(mesh.m);il.extend([index]*len(f))
    if ul is not None:ul.extend(mesh.uv)
   n0+=len(h0.v);n2+=len(h2.v);counts['buildings']+=1;counts['courtyard_holes']+=sum(len(p.interiors) for p in polygon_parts(g));counts['true_multipart']+=len(polygon_parts(g))>1;counts['hillside_relief_ge2m']+=relief>=2;counts['high_foundation_warning_gt8m']+=base-bottom>8
   placement.append({'i':index,'id':uid,'built':True,'floor_navd88_m':base,'bottom_navd88_m':bottom,'ground_min_max_m':[float(valid.min()),float(valid.max())],'ground_relief_m':relief,'ground_unresolved':int((~np.isfinite(z)).sum()),'ground_fallback_samples':int(fallback[start:end].sum()),'height_m':a['height_m'],'roof_top_navd88_m':base+a['height_m'],'geometry_area_m2':g.area,'model_area_m2':g0.area,'model_hausdorff_m':g.hausdorff_distance(g0),'courtyard_holes':sum(len(p.interiors) for p in polygon_parts(g0)),'components':len(polygon_parts(g0)),'visual_level':visual,'building_type':a['building_type'],'height_evidence':a['height_evidence'],'parts':len(a['parts']),'roof_shape':a['roof_shape'],'name':a.get('name'),'entrance':entry,'active_representation':'one of authoring or runtime, never both','triangles_authoring':len(h0.f),'triangles_runtime':len(h2.f)})
  records=[]
  for lod,vl,fl,ml,il,ul in [(0,v0,f0,m0,ids0,uv0),(2,v2,f2,m2,ids2,None)]:
   if not vl:continue
   v=np.concatenate(vl);f=np.concatenate(fl);mi=np.array(ml,np.uint8);fid=np.array(il,np.int32);normal=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]);area=np.linalg.norm(normal,axis=1);good=area>1e-8;counts['float32_microfaces_quarantined']+=int((~good).sum());flip=(mi==self.mat['roof'])&(normal[:,2]<0);f[flip]=f[flip][:,[0,2,1]];counts['float32_roof_faces_reoriented']+=int(flip.sum());d={'v':v,'f':f[good],'m':mi[good],'fid':fid[good]}
   if lod==0 and any(r[-1]>0 for r in rows):d['uv']=np.asarray(ul,np.float32)[good]
   p=folder/(owner+f'_lod{lod}.npz');np.savez_compressed(p,**d);records.append({'id':p.stem,'file':str(p.relative_to(self.root)),'sha256':sha(p),'lod':lod,'owner':owner,'origin_m':origin,'triangles':int(good.sum()),'vertices':len(v),'bounds_m':[ (v.min(axis=0)+origin).tolist(),(v.max(axis=0)+origin).tolist()],'visual_level':max(r[-1] for r in rows),'feature_count':len(set(fid[good].tolist()))})
  path=folder/(owner+'_placements.json.gz')
  with gzip.open(path,'wt') as f:json.dump({'placements':placement,'instances':instances},f,separators=(',',':'))
  receipt_data={'id':owner,'signature':self.signature,'origin_m':origin,'meshes':records,'placements':str(path.relative_to(self.root)),'placements_sha256':sha(path),'counts':dict(counts)};write_json(receipt,receipt_data)
  # Keep spatial triangle trees bounded; cross-cell queries reload the same immutable source.
  if len(self.ground.cache)>16:self.ground.cache.clear();self.ground.floor_cache.clear()
  return receipt_data

_worker=None
def task(args):
 global _worker
 root,owner=args
 if _worker is None:_worker=Worker(root)
 return _worker.process(owner)

def build(root=ROOT,workers=3):
 from concurrent.futures import ProcessPoolExecutor
 root=Path(root);db=sqlite3.connect(root/'data/processed/stage05/buildings.sqlite');cells=[r[0] for r in db.execute('SELECT DISTINCT cell FROM buildings WHERE active=1 ORDER BY cell')];db.close();start=time.monotonic();records=[];counts=collections.Counter();folder=root/'work/reports/stage05';folder.mkdir(parents=True,exist_ok=True)
 with ProcessPoolExecutor(max_workers=workers) as pool:
  for i,result in enumerate(pool.map(task,[(str(root),c) for c in cells],chunksize=1),1):
   records.append(result);counts.update(result['counts'])
   if i%20==0:print('BUILDING_CELLS_MESHED',i,'/',len(cells),'BUILDINGS',counts['buildings'],flush=True)
 cfg=yaml.safe_load((root/'config/stage05.yaml').read_text());out={'build_version':cfg['build_version'],'coordinate_system':'EPSG32611 minus project origin; meters; source DTM NAVD88','cells':records,'meshes':[m for r in records for m in r['meshes']],'materials':materials(cfg),'counts':dict(counts),'seconds':time.monotonic()-start,'height_randomization_used':False,'source_sqlite_sha256':sha(root/'data/processed/stage05/buildings.sqlite'),'config_sha256':sha(root/'config/stage05.yaml'),'script_sha256':sha(Path(__file__)),'runtime_switching_implemented':False,'ground_rule':'level floor above highest sampled active stage04 ground; explicit plinth embeds below lowest sample; no absolute LARIAC ELEV mixed with NAVD88'};write_json(root/'data/processed/stage05/mesh_index.json',out);write_json(folder/'geometry.json',{'counts':dict(counts),'cells':len(records),'authoring_triangles':sum(m['triangles'] for m in out['meshes'] if m['lod']==0),'runtime_triangles':sum(m['triangles'] for m in out['meshes'] if m['lod']==2),'seconds':out['seconds'],'status':'executed'});print('ALL_BUILDING_GEOMETRY_COMPLETE',dict(counts),flush=True);return out
if __name__=='__main__':build()
