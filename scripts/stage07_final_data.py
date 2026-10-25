"""Revision2: source-plan architecture with actual openings and street-constrained urban ground.

Measured source geometry, source reports, reference observations and inferred design
parameters remain separate. These are original editable meshes, not survey drawings.
"""
from pathlib import Path
import collections,json,math,xml.etree.ElementTree as ET
import numpy as np,shapely
from shapely.geometry import shape,box,Polygon,Point,LineString,MultiPoint
from shapely import affinity
from pyproj import Transformer
from stage06_geometry import Mesh,MATERIALS,MAT,polys
from stage07_data import WorkingGround
from stage03_common import references
from stage05_geometry import partitioned_bands
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
OUT='data/processed/stage07_final/'
def read(p):return json.loads((ROOT/p).read_text())
def save(p,arrays):
 p=ROOT/p;p.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(p,**arrays);return str(p.relative_to(ROOT))
class Grade:
 def __init__(self):
  self.ground=WorkingGround(ROOT);self.surface=self.ground.surface;_,self.origin,_,refs=references(ROOT);self.refs=refs;self.regions=[refs[r] for r in ['historic_core','civic_center']];self.extent=shapely.union_all(self.regions).buffer(75);index=read('data/processed/stage04/mesh_index.json');pts=[]
  for r in index['meshes']:
   if r['role'] not in ['downtown_road','profiled_priority_road','downtown_sidewalk']:continue
   o=np.array(r['origin_m']);b=box(o[0],o[1],o[0]+1000,o[1]+1000)
   if not b.intersects(self.extent):continue
   with np.load(ROOT/r['file']) as a:v=a['v'].astype(float)+o
   v=v[shapely.covers(self.extent,shapely.points(v[:,:2]))];pts.append(v)
  p=np.concatenate(pts);cells=np.floor(p[:,:2]/8).astype(int);_,ii=np.unique(cells,axis=0,return_index=True);self.p=p[ii];self.planes=[]
  for g in self.regions:
   c=np.array(g.centroid.coords[0]);near=np.linalg.norm(self.p[:,:2]-c,axis=1)<430;p=self.p[near];coef=np.linalg.lstsq(np.column_stack([p[:,:2]-c,np.ones(len(p))]),p[:,2],rcond=None)[0];self.planes.append((c,p,coef))
 def __call__(self,x,y):
  xy=np.column_stack([x,y]);z=np.empty(len(xy));choose=np.argmin(np.stack([np.linalg.norm(xy-c,axis=1) for c,_,_ in self.planes]),axis=0)
  for j,(c,p,coef) in enumerate(self.planes):
   ids=np.flatnonzero(choose==j)
   for subset in np.array_split(ids,max(1,math.ceil(len(ids)/1200))):
    if not len(subset):continue
    q=xy[subset];dist=np.sum((q[:,None,:]-p[None,:,:2])**2,axis=2);knn=np.argpartition(dist,7,axis=1)[:,:8];d=np.take_along_axis(dist,knn,axis=1);residual=p[:,2]-np.column_stack([p[:,:2]-c,np.ones(len(p))])@coef;w=1/(d+16);plane=np.column_stack([q-c,np.ones(len(q))])@coef;z[subset]=plane+(w*residual[knn]).sum(axis=1)/w.sum(axis=1)
  return z
 def local_height(self,xy):return float(self(np.array([xy[0]]),np.array([xy[1]]))[0])
def make_ground(grade):
 records=[]
 for ij,t in grade.ground.base.tiles.items():
  bbox=box(ij[0]*1000,ij[1]*1000,(ij[0]+1)*1000,(ij[1]+1)*1000)
  if not bbox.intersects(grade.extent):continue
  prior=grade.ground.overrides.get(ij)
  if prior:
   source=prior['file']
   with np.load(ROOT/source) as a:ar={k:a[k].copy() for k in a.files}
  else:
   v,f,_,_=grade.ground.base.load(ij);lod=grade.ground.base.active[t['id']];variant=ROOT/'data/processed/stage04/ground'/(t['id']+'.npz');source=str(variant.relative_to(ROOT)) if variant.exists() else t['file']
   with np.load(ROOT/source) as a:mi=a['m'+str(lod)].copy()
   ar={'v':v.astype(np.float32),'f':f.astype(np.int32),'m':mi}
  v=ar['v'];old=v[:,2].copy();xy=v[:,:2].astype(float)+np.array(ij)*1000;pts=shapely.points(xy);distance=np.minimum.reduce([shapely.distance(pts,g) for g in grade.regions]);w=np.clip(1-distance/50,0,1);z=grade(xy[:,0],xy[:,1]);v[:,2]=old*(1-w)+z*w;ar['v']=v;file=save(OUT+'ground/'+t['id']+'.npz',ar);records.append({'id':t['id'],'ij':list(ij),'file':file,'source_file':source,'boundary_rule':'same globally sampled grade on both neighbors; original unchanged where work-window influence is zero','max_display_z_edit_m':float(abs(v[:,2]-old).max()),'source_xy_and_faces_unchanged':True,'road_cut_holes_preserved':True})
 return records
def oriented_rectangle(a,t,u0,u1,d0,d1):return Polygon([a+t*u0+np.array([t[1],-t[0]])*d0,a+t*u1+np.array([t[1],-t[0]])*d0,a+t*u1+np.array([t[1],-t[0]])*d1,a+t*u0+np.array([t[1],-t[0]])*d1])
class Building:
 def __init__(self,b,grade,cfg):
  self.b=b;self.cfg=cfg;self.g=shapely.orient_polygons(shape(b['geometry']).simplify(.10,preserve_topology=True));self.center=np.array(self.g.centroid.coords[0]);self.g=affinity.translate(self.g,-self.center[0],-self.center[1]);self.profile=cfg['research_profiles'].get(str(b['i']),{}).get('id','neutral');self.h=b['height_m'];self.m=collections.defaultdict(Mesh);self.windows=0;self.doors=[];self.cap_windows=cfg['max_windows_per_building'];self.front=np.array([.782,-.623]);self.entry=None
  if self.profile=='records':self.front=np.array([0.,-1.])
  edges=[]
  for p in polys(self.g):
   a=np.array(p.exterior.coords)
   for aa,bb in zip(a[:-1],a[1:]):
    d=bb-aa;L=np.linalg.norm(d)
    if L>.25:edges.append((aa,bb,d/L,np.array([d[1],-d[0]])/L,L))
  e=max(edges,key=lambda x:x[4]*(max(0,float(np.dot(x[3],self.front)))**8))
  self.front_edge=e
  if self.profile in ['arcade','theatre']:xy=(e[0]+e[1])/2;self.entry=(xy,e[2],e[3])
  elif b['entry']:
   p=Point(np.array(b['entry']['xy_m'])-self.center);long_edges=[e for e in edges if e[4]>=3.0];e=min(long_edges or edges,key=lambda x:LineString([x[0],x[1]]).distance(p));line=LineString([e[0],e[1]]);d=np.clip(line.project(p),1.25,e[4]-1.25) if e[4]>2.5 else e[4]/2;xy=e[0]+e[2]*d;self.entry=(xy,e[2],e[3])
  if self.profile=='theatre':
   # Roofline digitisation splits this street frontage into short zigzags.
   # Locate the tall front lobby part; the17m decorative screen width is an
   # explicit photo-guided inference, not a measured new footprint.
   t,out=self.front_edge[2:4];parts=[affinity.translate(shapely.from_wkb(bytes.fromhex(p['geometry_wkb_hex'])),-self.center[0],-self.center[1]) for p in b['attrs'].get('parts',[]) if p['height_m']>=self.h-.1]
   frontpart=max(parts,key=lambda p:max(shapely.get_coordinates(p)@out));xy=shapely.get_coordinates(frontpart);u=(min(xy@t)+max(xy@t))/2;d=max(shapely.get_coordinates(self.g)@out)+.5;c=t*u+out*d;self.front_edge=(c-t*8.5,c+t*8.5,t,out,17.);self.entry=(c,t,out)
  self.floor=grade.local_height(self.center+(self.entry[0]+self.entry[2]*.6 if self.entry else np.zeros(2)))+.15+(.45 if self.profile=='times' else 0)
  self.grade=grade
 def facade(self,g,z0,z1,rows=None,style='neutral',grand=False):
  if z1-z0<.5:return
  # Use the same topology-preserving tolerance as the entry-edge selection.
  # Roofline digitisation contains centimetre edges, which must not split a door.
  if self.b['i'] in self.cfg.get('facade_edge_cleanup_indices',[]):g=g.simplify(.10,preserve_topology=True)
  wallmat='brick' if self.profile=='alexandria' else 'white' if self.profile in ['times','records'] else 'limestone' if self.profile in ['arcade','theatre'] else 'concrete';rows=rows or max(1,round((z1-z0)/3.7));step=(z1-z0)/rows
  for p in polys(shapely.orient_polygons(g)):
   for ring in [p.exterior,*p.interiors]:
    xy=np.array(ring.coords)
    for a,b in zip(xy[:-1],xy[1:]):
     d=b-a;L=np.linalg.norm(d)
     if L<.02:continue
     t=d/L;out=np.array([t[1],-t[0]]);to=lambda u,depth,z:np.array([*(a+t*u-out*depth),z]);openings=[];doors=[];wins=[];frontness=float(np.dot(out,self.front));isfront=frontness>(.70 if self.profile=='records' else .9) and L>12
     if self.entry and z0<.1:
      ep,_,eo=self.entry;proj=float(np.dot(ep-a,t));normal=abs(np.dot(ep-a,out))
      if self.profile=='arcade' and abs(frontness)>.90 and L>20:proj=L/2;normal=0
      if normal<.3 and 1.05<=proj<=L-1.05:
       width=8 if self.profile=='arcade' else 5 if self.profile=='theatre' else 2.4 if self.profile=='times' else 2.;height=11 if self.profile=='arcade' else 3.2 if self.profile=='theatre' else 3.5 if self.profile=='times' else 2.7;width=min(width,L-1)
       if self.profile=='arcade':
        rr=width/2;spring=height-rr;coords=[(proj-rr,0),(proj+rr,0)]+[(proj+rr*math.cos(u),spring+rr*math.sin(u)) for u in np.linspace(0,math.pi,25)];cut=Polygon(coords)
       else:cut=box(proj-width/2,0,proj+width/2,height)
       openings.append(cut);doors.append((cut,proj,width,height));self.doors.append({'xy_city_m':(a+t*proj+self.center).tolist(),'outward_xy':out.tolist(),'width_m':width,'height_m':height,'floor_navd88_m':self.floor,'source':'mapped vicinity retained where usable; photo/neutral façade position inferred; no field-survey claim'})
     if self.profile=='theatre' and grand and isfront and z1>=15:
      u=L/2;r=4.5;spring=9.2;upper=Polygon([(u-r,4.7),(u+r,4.7)]+[(u+r*math.cos(q),spring+r*math.sin(q)) for q in np.linspace(0,math.pi,25)]);openings.append(upper);self.m['upper_arch_recess'].face([to(x,.24,z) for x,z in np.array(upper.exterior.coords)[:-1]],'screen')
     if self.profile not in ['theatre'] and style!='blank_storage' and L>=2.5:
      cols=max(1,round(L/(3.2 if style!='modern' else 2.6)));cols=min(cols,40)
      for row in range(rows):
       lo=z0+step*(row+.20);hi=z0+step*(row+.80)
       if z0<.1 and row==0:lo=max(.65,lo);hi=max(hi,3.0) if step>3.5 else hi
       for col in range(cols):
        if self.windows>=self.cap_windows:break
        left=(col+.21)*L/cols;right=(col+.79)*L/cols;cut=box(left,lo,right,hi)
        if any(cut.buffer(.15).intersects(q) for q in openings):continue
        openings.append(cut);wins.append((cut,left,right,lo,hi));self.windows+=1
     wall=box(0,z0,L,z1).difference(shapely.union_all(openings)) if openings else box(0,z0,L,z1)
     for poly in polys(wall):
      for tri in shapely.constrained_delaunay_triangles(poly).geoms:
       q=np.array(tri.exterior.coords)[:3];cross=(q[1,0]-q[0,0])*(q[2,1]-q[0,1])-(q[1,1]-q[0,1])*(q[2,0]-q[0,0]);q=q if cross>0 else q[::-1];self.m['structure'].face([to(u,0,z) for u,z in q],wallmat);self.m['structure'].face([to(u,.28,z) for u,z in q[::-1]],wallmat)
     for cut in openings:
      q=np.array(cut.exterior.coords)
      for aa,bb in zip(q[:-1],q[1:]):self.m['structure'].quad([to(aa[0],0,aa[1]),to(bb[0],0,bb[1]),to(bb[0],.28,bb[1]),to(aa[0],.28,aa[1])],'limestone' if wallmat=='brick' else wallmat)
     for cut,left,right,lo,hi in wins:
      self.m['glazing'].quad([to(left,.17,lo),to(right,.17,lo),to(right,.17,hi),to(left,.17,hi)],'glass')
      for aa,bb in [((left,lo),(right,lo)),((left,hi),(right,hi)),((left,lo),(left,hi)),((right,lo),(right,hi)),(((left+right)/2,lo),((left+right)/2,hi))]:self.m['window_frames'].beam(to(aa[0],-.025,aa[1]),to(bb[0],-.025,bb[1]),.045,'dark_metal')
      self.m['window_frames'].beam(to(left-.10,-.08,lo-.055),to(right+.10,-.08,lo-.055),.12,'limestone')
     for cut,u,w,h in doors:
      # Actual façade opening and a recessed dark vestibule, labelled simplified interior.
      recess=.35 if self.profile=='theatre' else 1.5;glass_depth=.15 if self.profile=='theatre' else .65
      self.m['entry_recess'].quad([to(u-w/2,recess,0),to(u+w/2,recess,0),to(u+w/2,recess,h),to(u-w/2,recess,h)],'screen');self.m['entry_recess'].quad([to(u-w/2,0,0),to(u+w/2,0,0),to(u+w/2,recess,0),to(u-w/2,recess,0)],'paving')
      dw=min(w*.82,3.0);dh=min(h-.2,3.1)
      self.m['entry_recess'].quad([to(u-dw/2,glass_depth,0),to(u+dw/2,glass_depth,0),to(u+dw/2,glass_depth,dh),to(u-dw/2,glass_depth,dh)],'glass')
      for x in [u-dw/2,u,u+dw/2]:self.m['entry_details'].beam(to(x,glass_depth-.05,0),to(x,glass_depth-.05,dh),.055,'dark_metal')
      for x in [u-.18,u+.18]:self.m['entry_details'].beam(to(x,glass_depth-.12,1.0),to(x,glass_depth-.12,1.55),.045,'silver')
      if self.profile=='arcade':
       r=w/2;spring=h-r
       for k in range(32):
        v0=k*math.pi/32;v1=(k+1)*math.pi/32;pts=[to(u+rad*math.cos(v),-.13,spring+rad*math.sin(v)) for rad,v in [(r,v0),(r+.45,v0),(r+.45,v1),(r,v1)]];self.m['ornament'].quad(pts,'limestone')
       for side in [-1,1]:self.m['ornament'].beam(to(u+side*(r+.25),-.13,0),to(u+side*(r+.25),-.13,spring),.5,'limestone')
       upper=cut.intersection(box(u-w,4,u+w,h+.1))
       for p in polys(upper):self.m['glazing'].face([to(x,.21,z) for x,z in np.array(p.exterior.coords)[:-1]],'glass')
      if self.profile=='times':
       for x in [u-w/2-.4,u+w/2+.4]:self.m['ornament'].beam(to(x,-.09,0),to(x,-.09,h+.7),.8,'terracotta')
       self.m['ornament'].beam(to(u-w/2-.8,-.09,h+.5),to(u+w/2+.8,-.09,h+.5),1.0,'terracotta')
     if self.profile=='times' and L>4:
      for u in np.arange(1,L,3.0):self.m['ornament'].beam(to(u,-.075,z0+.25),to(u,-.075,z1-.2),.22,'white')
     if self.profile=='records' and isfront and z1-z0>15:
      for u in np.arange(.8,L,1.45):
       aa=to(u,-.4,z0+.4);bb=to(u,-.4,z1-.4);self.m['sun_louvers'].beam(aa,bb,.18,'white')
      for zz in np.arange(z0+1,z1,2.4):self.m['sun_louvers'].beam(to(.3,-.42,zz),to(L-.3,-.42,zz),.18,'limestone')
 def roof(self,g,z):
  for p in polys(g):
   for tri in shapely.constrained_delaunay_triangles(p).geoms:
    q=np.array(tri.exterior.coords)[:3];cross=(q[1,0]-q[0,0])*(q[2,1]-q[0,1])-(q[1,1]-q[0,1])*(q[2,0]-q[0,0]);q=q if cross>0 else q[::-1];self.m['roof'].face([[*v,z] for v in q],'concrete')
  self.m['roof'].extrude(g.buffer(.18).difference(g.buffer(-.20)),z-.12,z+.55,'limestone')
 def special(self):
  if self.profile=='alexandria':
   # Eight-storey original and twelve-storey rear addition are documented;
   # their unmeasured internal split is explicitly inferred.
   a,b,t,out,L=self.front_edge;allxy=shapely.get_coordinates(self.g);pp=allxy@out;threshold=np.quantile(pp,.35);cut=oriented_rectangle(np.zeros(2),t,-200,200,-200,threshold);rear=self.g.intersection(cut);front=self.g.difference(rear)
   self.facade(self.g,0,34.6,8);self.roof(front,34.6)
   if not rear.is_empty:self.facade(rear,34.6,self.h,4);self.roof(rear,self.h)
   for z,thick in [(5.3,.45),(30.9,.22),(33.6,.65)]:self.m['cornices'].extrude(self.g.buffer(thick).difference(self.g.buffer(-.12)),z,z+.35,'limestone')
  elif self.profile=='arcade':
   rect=np.array(self.g.minimum_rotated_rectangle.exterior.coords)[:4];edges=np.roll(rect,-1,axis=0)-rect;t=edges[np.argmax(np.linalg.norm(edges,axis=1))];t=t/np.linalg.norm(t);n=np.array([t[1],-t[0]]);proj=shapely.get_coordinates(self.g)@t;lo,hi=proj.min(),proj.max();middle=self.g.intersection(oriented_rectangle(np.zeros(2),t,lo+24,hi-24,-200,200));towers=self.g.difference(middle)
   self.facade(self.g,0,12.3,3);self.roof(middle,12.3);self.facade(towers,12.3,self.h,9);self.roof(towers,self.h)
   # Photo-observed radio towers, positions inferred on the two real tower plans.
   for p in polys(towers):
    c=np.array(p.representative_point().coords[0]);size=2.7;height=17.
    for corner in [(-1,-1),(-1,1),(1,-1),(1,1)]:self.m['radio_towers'].beam([*(c+np.array(corner)*size/2),self.h+.7],[*(c+np.array(corner)*.18),self.h+height],.07,'dark_metal')
    for z in np.arange(1,height,2.5):
     width=size*(1-z/height);self.m['radio_towers'].beam([c[0]-width/2,c[1]-width/2,self.h+z],[c[0]+width/2,c[1]+width/2,self.h+z+2.0],.055,'dark_metal')
  elif self.profile=='theatre':
   parts=self.b['attrs'].get('parts',[]);used=shapely.GeometryCollection()
   for part in sorted(parts,key=lambda p:p['height_m'],reverse=True):
    g=affinity.translate(shapely.from_wkb(bytes.fromhex(part['geometry_wkb_hex'])),-self.center[0],-self.center[1]).intersection(self.g).difference(used)
    if g.is_empty:continue
    h=min(self.h,part['height_m']);self.facade(g,0,h,2);self.roof(g,h);used=shapely.union_all([used,g])
   rest=self.g.difference(used)
   if not rest.is_empty:self.facade(rest,0,self.h,3);self.roof(rest,self.h)
   # Source roofline heights describe lobby/roof parts, not the five-storey
   # ornamental street elevation. A separate editable reference-guided screen
   # stands0.5m beyond the source roofline; its17m width is inferred explicitly.
   aa,bb,tt,oo,_=self.front_edge;screen=Polygon([aa,bb,bb-oo*.85,aa-oo*.85]);self.facade(screen,0,self.h,5,grand=True);self.roof(screen,self.h)
   a,b,t,out,L=self.front_edge;c=(a+b)/2;to=lambda x,d,z:np.array([*(c+t*x+out*d),z])
   # Recognizable paired fluted columns, arch fan, entablature, marquee and blade.
   for side in [-1,1]:
    for shift in [-.55,.55]:
     x=side*6.5+shift
     for off in [-.16,0,.16]:self.m['ornament'].beam(to(x+off,.32,4.6),to(x+off,.32,16.2),.14,'limestone')
     self.m['ornament'].beam(to(x-.45,.3,16.3),to(x+.45,.3,16.3),.55,'limestone')
   self.m['ornament'].beam(to(-8.5,.3,17),to(8.5,.3,17),.9,'limestone');self.m['ornament'].beam(to(-9,.3,19.3),to(9,.3,19.3),.4,'limestone')
   self.m['marquee'].loft([[to(x,d,z) for x,d in [(-10,0),(10,0),(10,2.6),(-10,2.6)]] for z in [3.8,4.45]],'terracotta')
   self.m['blade'].beam(to(8.4,.7,6),to(8.4,.7,20),1.0,'terracotta')
   for k in range(13):
    a0=k*math.pi/12;self.m['ornament'].beam(to(0,.30,8.8),to(4.2*math.cos(a0),.30,8.8+4.2*math.sin(a0)),.07,'limestone')
  elif self.profile=='records':
   bands=partitioned_bands(shape(self.b['geometry']),self.b['attrs'],self.h)
   for j,(gg,lo,hi) in enumerate(bands):
    gg=affinity.translate(gg,-self.center[0],-self.center[1]);north=gg.intersection(box(-500,0,500,500));south=gg.difference(north)
    if not north.is_empty:self.facade(north,lo,hi,max(1,round((hi-lo)/6)),'modern')
    if not south.is_empty:self.facade(south,lo,hi,max(1,round((hi-lo)/2.4384)),'blank_storage')
    nxt=affinity.translate(bands[j+1][0],-self.center[0],-self.center[1]) if j+1<len(bands) else shapely.GeometryCollection();self.roof(gg.difference(nxt),hi)
   # A separate eight-storey ceramic screen, inspired by selected rear reference.
   a,b,t,out,L=self.front_edge;c=(a+b)/2
   for zz in np.arange(5,26,1.1):
    for u in np.arange(-min(L*.40,14),min(L*.40,14),1.05):
     pt=c+t*u+out*.65;self.m['ceramic_screen'].box([*pt,zz],[.22,.22,.72],'limestone')
  elif self.profile=='times':
   self.facade(self.g,0,26.5,6);e=self.entry or ((self.front_edge[0]+self.front_edge[1])/2,self.front_edge[2],self.front_edge[3]);c,t,out=e;tower=self.g.intersection(oriented_rectangle(c,t,-12,12,-24,0));self.roof(self.g.difference(tower),26.5);self.facade(tower,26.5,self.h,3);self.roof(tower,self.h)
  else:
   bands=partitioned_bands(shape(self.b['geometry']),self.b['attrs'],self.h)
   for j,(gg,lo,hi) in enumerate(bands):
    gg=affinity.translate(gg,-self.center[0],-self.center[1]);self.facade(gg,lo,hi,min(24,max(1,round((hi-lo)/3.7))));nxt=affinity.translate(bands[j+1][0],-self.center[0],-self.center[1]) if j+1<len(bands) else shapely.GeometryCollection();self.roof(gg.difference(nxt),hi)
 def make(self):
  self.special()
  for door in self.doors:
   xy=np.array(door['xy_city_m'])-self.center;out=np.array(door['outward_xy']);t=np.array([-out[1],out[0]]);grade=self.grade.local_height(xy+self.center+out*1.5)+.15;rise=max(0,self.floor-grade);rise=rise if rise>.04 else 0.;n=min(24,math.ceil(rise/.17));width=min(door['width_m']+1,5.0)
   for j in range(n+1):
    top=-rise*j/max(n,1);depth=1.0 if j==0 else .30;dist=.5 if j==0 else 1+(j-.5)*.30;bottom=min(-rise-.2,top-.1);tmp=Mesh();tmp.box([0,dist,(top+bottom)/2],[width,depth,top-bottom],'paving');v=np.array(tmp.v);v[:,:2]=v[:,:2]@np.column_stack([t,out]).T+xy;m=self.m['entry_steps'];o=len(m.v);m.v.extend(v);m.f.extend((np.array(tmp.f)[:,[0,2,1]]+o).tolist());m.m.extend(tmp.m)
   door.update(rise_m=rise,steps=n,step_rise_m=rise/max(n,1),ground_evidence='compare sidewalk grade+0.15, at-grade allowed; not engineering survey')
  files=[]
  for name,m in self.m.items():
   ar,removed=m.arrays()
   if not len(ar['f']):continue
   file=save(OUT+'buildings/'+str(self.b['i'])+'/'+name+'.npz',ar);files.append({'name':name,'file':file,'triangles':len(ar['f']),'degenerate_filtered':removed})
  coarse=Mesh();coarse.extrude(self.g,0,self.h,'concrete');ar,_=coarse.arrays();coarsefile=save(OUT+'buildings/'+str(self.b['i'])+'/far.npz',ar)
  if not self.doors:
   self.b['attrs']['revision2_entry_limitation']='Tiny roofline fragment; an independent ground building/entrance is not established. Source outline retained; no fabricated doorway.'
  return {'entry_limitation':self.b['attrs'].get('revision2_entry_limitation'),'i':self.b['i'],'uid':self.b['uid'],'name':self.b['name'],'region':self.b['region'],'profile':self.profile,'height_input_m':self.h,'height_source':self.b['height_evidence'],'floor_navd88_m':self.floor,'old_floor_navd88_m':self.b['floor_navd88_m'],'origin_city_m':[*self.center,self.floor],'source_geometry':self.b['geometry'],'wall_plan':shapely.geometry.mapping(affinity.translate(self.g,*self.center)),'footprint_hausdorff_m':float(shape(self.b['geometry']).hausdorff_distance(affinity.translate(self.g,*self.center))),'doors':self.doors,'windows':self.windows,'near':files,'far':coarsefile,'source_accuracy':'source roofline/height reports and explicit design approximations; not a measured facade schedule','reference_guided':self.profile!='neutral'}
def run():
 cfg=read('config/stage07_final.json');grade=Grade();ground=make_ground(grade);bs=read('data/processed/stage07/buildings.json');records=[]
 for b in bs:
  if b['i'] in cfg['skybridge']['replaces']:continue
  rec=Building(b,grade,cfg).make();records.append(rec)
  print('NEAR_ARCHITECTURE',b['i'],b['name'],rec['profile'],rec['windows'],sum(a['triangles'] for a in rec['near']),flush=True)
 # Replace three bad county-height slivers by one mapped skybridge volume.
 xml=ET.parse(ROOT/'data/raw/stage07/osm/civic_center.osm').getroot();tx=Transformer.from_crs(4326,32611,always_xy=True);nodes={n.attrib['id']:np.array(tx.transform(float(n.attrib['lon']),float(n.attrib['lat'])))-grade.origin for n in xml.findall('node')};way=next(w for w in xml.findall('way') if w.attrib['id']==cfg['skybridge']['osm_way']);g=Polygon([nodes[n.attrib['ref']] for n in way.findall('nd')]);center=np.array(g.centroid.coords[0]);base=grade.local_height(center)+6;local=affinity.translate(g,-center[0],-center[1]);m=Mesh();m.extrude(local,0,3.6,'glass');m.extrude(local,-.35,0,'concrete');ar,_=m.arrays();bridge={'id':'osm:way:425993596','replaces':cfg['skybridge']['replaces'],'file':save(OUT+'skybridge.npz',ar),'origin_city_m':[*center,base],'mapped_min_height_m':6.0,'enclosure_height_m':3.6,'enclosure_height_evidence':'inferred; no measured top/deck survey','no_ground_door_required':True,'old85m_tower_interpretation_rejected':True}
 write_json(ROOT/(OUT+'index.json'),{'config':'config/stage07_final.json','materials':MATERIALS,'buildings':records,'skybridge':bridge,'ground':ground,'replaced_source_indices':[b['i'] for b in bs],'actual_buildings':len(records),'original_county_features':len(bs),'road_controls':len(grade.p),'terrain_active_lod':grade.ground.base.active,'all_design_inferences_explicit':True});print('NEAR_REVISION_PREPARED',len(records),'BUILDINGS +1SKYBRIDGE',flush=True)
if __name__=='__main__':run()
