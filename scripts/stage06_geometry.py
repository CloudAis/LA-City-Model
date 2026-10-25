"""Original, parameterized architectural reconstructions; all unsupported detail labelled inferred.

Source plan/part profiles are kept; no purchased third-party meshes or photo textures.
Near/mid/far are separate editable geometries, not a claimed runtime switcher.
"""
from pathlib import Path
import collections,json,math
import numpy as np,shapely
from shapely import affinity
from shapely.geometry import Polygon,Point,LineString,box,shape
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
MATERIALS=[('limestone',[.72,.68,.58,1],.65,0),('glass',[.085,.19,.24,1],.22,.30),('silver',[.55,.59,.60,1],.29,.82),('dark_metal',[.095,.12,.13,1],.43,.65),('copper',[.20,.27,.23,1],.48,.65),('terracotta',[.39,.12,.055,1],.76,0),('concrete',[.45,.43,.38,1],.78,0),('white',[.82,.81,.73,1],.6,0),('grass',[.13,.25,.085,1],.86,0),('earth',[.34,.20,.10,1],.9,0),('paving',[.42,.40,.35,1],.84,0),('seat_yellow',[.73,.56,.22,1],.7,0),('seat_orange',[.67,.30,.12,1],.7,0),('seat_blue',[.16,.35,.43,1],.7,0),('seat_red',[.41,.055,.08,1],.7,0),('screen',[.013,.022,.027,1],.45,.05),('clock',[.78,.72,.57,1],.6,0),('brick',[.35,.17,.10,1],.86,0)]
MAT={n:i for i,(n,*_) in enumerate(MATERIALS)}
_native_surface=None
def polys(g):
 if isinstance(g,Polygon):return [g]
 return [p for x in getattr(g,'geoms',[]) for p in polys(x)]
class Mesh:
 def __init__(self):self.v=[];self.f=[];self.m=[]
 def face(self,xyz,mat):
  o=len(self.v);self.v.extend(xyz)
  for j in range(1,len(xyz)-1):self.f.append([o,o+j,o+j+1]);self.m.append(MAT[mat])
 def quad(self,q,mat):self.face(q,mat)
 def box(self,c,d,mat):
  c=np.array(c);d=np.array(d);o=len(self.v);self.v.extend(c+np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]])*d/2)
  for f in [[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]:
   self.f.extend([[o+f[0],o+f[1],o+f[2]],[o+f[0],o+f[2],o+f[3]]]);self.m.extend([MAT[mat]]*2)
 def beam(self,a,b,w,mat):
  a=np.asarray(a,float);b=np.asarray(b,float);d=b-a;n=np.linalg.norm(d)
  if n<1e-7:return
  t=d/n;u=np.cross(t,[0,0,1] if abs(t[2])<.95 else [0,1,0]);u=u/np.linalg.norm(u)*w/2;v=np.cross(t,u);o=len(self.v);self.v.extend([a-u-v,a+u-v,a+u+v,a-u+v,b-u-v,b+u-v,b+u+v,b-u+v])
  for f in [[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]:self.f.extend([[o+f[0],o+f[1],o+f[2]],[o+f[0],o+f[2],o+f[3]]]);self.m.extend([MAT[mat]]*2)
 def extrude(self,g,lo,hi,mat):
  for p in polys(shapely.orient_polygons(g)):
   if p.area<1e-6 or hi-lo<1e-5:continue
   for ring in [p.exterior,*p.interiors]:
    xy=np.asarray(ring.coords)[:,:2]
    for a,b in zip(xy[:-1],xy[1:]):self.quad([[*a,lo],[*b,lo],[*b,hi],[*a,hi]],mat)
   for t in shapely.constrained_delaunay_triangles(p).geoms:
    xy=np.asarray(t.exterior.coords)[:3,:2];cross=(xy[1,0]-xy[0,0])*(xy[2,1]-xy[0,1])-(xy[1,1]-xy[0,1])*(xy[2,0]-xy[0,0]);xy=xy if cross>0 else xy[::-1];self.face([[*a,hi] for a in xy],mat);self.face([[*a,lo] for a in xy[::-1]],mat)
 def loft(self,rings,mat,cap=True):
  n=len(rings[0]);o=len(self.v);self.v.extend(np.asarray(rings).reshape(-1,3))
  for k in range(len(rings)-1):
   for j in range(n):a=o+k*n+j;b=o+k*n+(j+1)%n;c=b+n;d=a+n;self.f.extend([[a,b,c],[a,c,d]]);self.m.extend([MAT[mat]]*2)
  if cap:self.face(list(rings[0])[::-1],mat);self.face(rings[-1],mat)
 def cylinder(self,c,rx,ry,h,mat,n):
  ts=np.arange(n)*2*math.pi/n;x,y,z=c;rings=[np.column_stack([x+rx*np.cos(ts),y+ry*np.sin(ts),np.full(n,z+zz)]) for zz in [0,h]];self.loft(rings,mat)
 def dome(self,c,rx,ry,h,mat,n):
  x,y,z=c;ts=np.arange(n)*2*math.pi/n;rings=[np.column_stack([x+rx*np.cos(ts)*math.cos(a),y+ry*np.sin(ts)*math.cos(a),np.full(n,z+h*math.sin(a))]) for a in np.linspace(0,math.pi/2-.005,max(5,n//4))];self.loft(rings,mat)
 def arrays(self):
  v=np.array(self.v,np.float32).reshape(-1,3);f=np.array(self.f,np.int32).reshape(-1,3);m=np.array(self.m,np.uint8);good=np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)>1e-8;return {'v':v,'f':f[good],'m':m[good]},int((~good).sum())
class Asset:
 def __init__(self,card,lod):self.a=card;self.lod=lod;self.near=lod=='near';self.detail=lod!='far';self.n={'near':64,'mid':32,'far':16}[lod];self.groups=collections.defaultdict(Mesh);self.g=shape(card['local_plan']);self.b=self.g.bounds
 def m(self,name):return self.groups[name]
 def box(self,name,c,d,mat='limestone'):self.m(name).box(c,d,mat)
 def extrude(self,name,g,lo,hi,mat='limestone'):self.m(name).extrude(g,lo,hi,mat)
 def beams(self,name,lines,w,mat):
  for a,b in lines:self.m(name).beam(a,b,w,mat)
 def facade(self,g,z0,z1,style='stone',storey=3.8):
  if not self.detail:return
  for p in polys(shapely.orient_polygons(g)):
   for ring in [p.exterior,*p.interiors]:
    xy=np.asarray(ring.coords)
    for a,b in zip(xy[:-1],xy[1:]):
     d=b-a;length=np.linalg.norm(d)
     if length<1.:continue
     t=d/length;n=np.array([t[1],-t[0]]);cols=max(1,round(length/(2.7 if style=='stone' else 2.1)));rows=max(1,int((z1-z0)/storey));rowh=(z1-z0)/rows
     for row in range(rows):
      za=z0+rowh*(row+.25 if style=='stone' else row+.035);zb=z0+rowh*(row+.81 if style=='stone' else row+.95)
      for col in range(cols):
       x=a+t*length*(col+.2 if style=='stone' else col+.02)/cols+n*.035;y=a+t*length*(col+.8 if style=='stone' else col+.98)/cols+n*.035
       self.m('recessed_glazing').quad([[*x,za],[*y,za],[*y,zb],[*x,zb]],'glass')
       if self.near:
        for aa,bb in [([*x,za],[*y,za]),([*x,zb],[*y,zb]),([*x,za],[*x,zb]),([*y,za],[*y,zb])]:self.m('window_frames_and_reveals').beam(aa,bb,.10 if style=='glass' else .16,'silver' if style=='glass' else 'limestone')
 def arch(self,name,center,width,height,depth,angle,mat='limestone',infill=True):
  # Local arch has horizontal x, vertical z, outward -y. It is an actual open curved band.
  r=width/2;spring=height-r;x,y,z=center;c,s=math.cos(angle),math.sin(angle)
  def point(u,v,w):return [x+c*u-s*v,y+s*u+c*v,z+w]
  mesh=self.m(name);n=max(8,self.n//4);thick=.4
  for k in range(n):
   a=k*math.pi/n;b=(k+1)*math.pi/n;q=[[r*math.cos(a),spring+r*math.sin(a)],[(r+thick)*math.cos(a),spring+(r+thick)*math.sin(a)],[(r+thick)*math.cos(b),spring+(r+thick)*math.sin(b)],[r*math.cos(b),spring+r*math.sin(b)]]
   mesh.quad([point(u,-depth/2,w) for u,w in q],mat);mesh.quad([point(u,depth/2,w) for u,w in q[::-1]],mat)
   for j in range(4):u,w=q[j];v,h=q[(j+1)%4];mesh.quad([point(u,-depth/2,w),point(v,-depth/2,h),point(v,depth/2,h),point(u,depth/2,w)],mat)
  for sign in [-1,1]:mesh.beam(point(sign*(r+thick/2),0,0),point(sign*(r+thick/2),0,spring),thick,mat)
  if infill:
   q=[point(-r,.04,0),point(r,.04,0)]+[point(r*math.cos(a),.04,spring+r*math.sin(a)) for a in np.linspace(0,math.pi,n+1)];self.m(name+'_glazing').face(q,'glass')
 def stairs(self,c,width,rise,depth,angle=0):
  global _native_surface
  if _native_surface is None:
   from stage03_surface import Surface
   _native_surface=Surface(ROOT)
  steps=max(1,min(32,math.ceil(rise/.17)));m=self.m('site_steps_and_landings');c=np.array(c);co,si=math.cos(angle),math.sin(angle);theta=self.a['rotation_z_radians'];R=np.array([[math.cos(theta),-math.sin(theta)],[math.sin(theta),math.cos(theta)]]);origin=np.array(self.a['origin_city_m'])
  for i in range(steps):
   y=(i+.5)*depth/steps;x,y=-si*y,co*y;top=c[2]+rise-i*rise/steps;cityxy=R@np.array([c[0]+x,c[1]+y])+origin[:2];ground=float(_native_surface(cityxy[:1],cityxy[1:])[0])-origin[2];bottom=min(ground-.25,top-.1);tmp=Mesh();tmp.box([0,(i+.5)*depth/steps,(top+bottom)/2],[width,depth/steps,top-bottom],'paving');v=np.array(tmp.v);v[:,:2]=v[:,:2]@np.array([[co,si],[-si,co]]);v[:,0]+=c[0];v[:,1]+=c[1];offset=len(m.v);m.v.extend(v);m.f.extend((np.array(tmp.f)+offset).tolist());m.m.extend(tmp.m)
 def site(self):
  if not self.detail or self.a['id'] in ['hollywood_sign','dodger_stadium','memorial_coliseum']:return
  # A narrow perimeter apron follows the selected plan, not a fictional rectangular parcel.
  outer=self.g.buffer(2,join_style=2);self.extrude('site_perimeter_apron',outer.difference(self.g),-.15,0,'paving')
 def make(self):
  getattr(self,self.a['id'])();self.site();return self.groups
 def us_bank_tower(self):
  h=self.a['height_m'];parts=[(shape(p['geometry']),float(p['tags'].get('height',0))) for p in self.a['parts'] if p['tags'].get('height') and float(p['tags'].get('height',0))>100];stops=[0,195,225,250,280]
  for lo,hi in zip(stops[:-1],stops[1:]):
   gs=[g for g,z in parts if z>lo+.1];g=shapely.union_all(gs).intersection(self.g) if gs else self.g;self.extrude('shaft_tier_'+str(hi),g,lo,hi);self.facade(g,max(lo,5),hi-.25,storey=4.0)
   if self.detail:self.extrude('setback_cornices',g.buffer(.25).difference(g.buffer(-.35)),hi-.7,hi,'white')
  top=max(parts,key=lambda t:t[1])[0];q=top.centroid;r=min(top.bounds[2]-top.bounds[0],top.bounds[3]-top.bounds[1])/2*.93
  for j,(lo,hi,scale) in enumerate([(280,293,1.0),(293,301,.92),(301,h,.82)]):
   g=Point(q.x,q.y).buffer(r*scale,quad_segs=self.n//4);self.extrude('circular_crown_'+str(j),g,lo,hi,'glass' if j==2 else 'limestone');self.facade(g,lo+.4,hi-.2,storey=3.6)
  if self.detail:
   for t in np.linspace(0,2*math.pi,24,endpoint=False):
    x=q.x+r*.86*math.cos(t);y=q.y+r*.86*math.sin(t);self.m('lantern_vertical_fins').beam([x,y,298],[x,y,h],.35,'white')
   self.box('entry_landing',[0,-31,-.15],[15,6,.3],'paving');self.stairs([0,-34,-1.7],15,1.7,4,math.pi)
 def wilshire_grand(self):
  parts=self.a['parts'];tagged=[(shape(p['geometry']),float(p['tags'].get('height',0))) for p in parts];pod=next((shape(p['geometry']) for p in parts if p['tags'].get('building:levels')=='7'),self.g);tower_parts=[shape(p['geometry']) for p in parts if float(p['tags'].get('building:levels',0))>=60 and shape(p['geometry']).area>20];body=shapely.union_all(tower_parts);assert not body.is_empty; crown=body;needle=next((g for g,z in tagged if z>300),body.representative_point().buffer(.5));q=needle.representative_point();roof=self.a['roof_reference_m'];h=self.a['height_m']
  self.extrude('podium_convention_block',pod,0,24.5,'limestone');self.facade(pod,2,23.5,'glass',4.5);self.extrude('glass_tower_shaft',body,24.5,245,'glass');self.facade(body,25,244,'glass',3.4)
  # Variable-height crown uses OSM crown plan; top profile interpolated to secondary roof reference.
  for p in polys(shapely.orient_polygons(crown)):
   xy=np.asarray(shapely.segmentize(p,2 if self.detail else 7).exterior.coords)[:-1];dist=np.linalg.norm(xy-np.array([q.x,q.y]),axis=1);maxdist=max(dist.max(),1);top=245+(roof-245)*np.clip(1-dist/maxdist,0,1)**.65;ring0=np.column_stack([xy,np.full(len(xy),245)]);ring1=np.column_stack([xy,top]);self.m('asymmetric_sail_crown').loft([ring0,ring1],'glass',False)
   for t in shapely.constrained_delaunay_triangles(p).geoms:
    xyroof=np.asarray(t.exterior.coords)[:3];ar=(xyroof[1,0]-xyroof[0,0])*(xyroof[2,1]-xyroof[0,1])-(xyroof[1,1]-xyroof[0,1])*(xyroof[2,0]-xyroof[0,0]);xyroof=xyroof if ar>0 else xyroof[::-1];zz=245+(roof-245)*np.clip(1-np.linalg.norm(xyroof-np.array([q.x,q.y]),axis=1)/maxdist,0,1)**.65;self.m('crown_roof').face(np.column_stack([xyroof,zz]),'silver')
   if self.detail:
    for a,b in zip(ring1,np.roll(ring1,-1,axis=0)):self.m('crown_rim').beam(a,b,.22,'silver')
    for a,b in zip(ring0[::2],ring1[::2]):self.m('crown_mullions').beam(a,b,.12,'silver')
  self.m('spire').loft([[[q.x+.46*math.cos(t),q.y+.46*math.sin(t),245] for t in np.arange(self.n//2)*4*math.pi/self.n],[[q.x+.07*math.cos(t),q.y+.07*math.sin(t),h] for t in np.arange(self.n//2)*4*math.pi/self.n]],'silver')
  if self.detail:
   self.box('roof_lobby_glass',[q.x-9,q.y,251],[13,15,12],'glass');self.canopy_roof('entry_skylight',[-15,-20],42,13,5,3,'glass');self.box('entry_landing',[-20,-43,-.15],[19,6,.3],'paving');self.stairs([-20,-46,-2],19,2,6,math.pi)
 def city_hall(self):
  self.extrude('historic_lower_courtyards',self.g,0,20);self.facade(self.g,4,19.3,storey=3.3)
  parts=[(shape(p['geometry']),float(p['tags'].get('height',0))) for p in self.a['parts']];last=20
  for hi in [46.5,98.5,110,121.6]:
   subset=[g for g,z in parts if z>=hi-.05];g=shapely.union_all(subset).intersection(self.g);self.extrude('tower_tier_'+str(hi),g,last,hi);self.facade(g,last+.5,hi-.6,storey=3.7)
   if self.detail:self.extrude('tier_cornices',g.buffer(.25).difference(g.buffer(-.4)),hi-.8,hi,'white')
   last=hi
  g=next(g for g,z in parts if z>130);rect=np.array(g.minimum_rotated_rectangle.exterior.coords)[:4];center=rect.mean(axis=0);base=np.column_stack([rect,np.full(4,121.6)]);top=np.column_stack([center+(rect-center)*.13,np.full(4,self.a['height_m'])]);self.m('pyramidal_crown').loft([base,top],'limestone')
  if self.detail:
   # Observation colonnade, distinct from the solid main tower.
   pp=next(g for g,z in parts if abs(z-121.6)<.2)
   for p in polys(pp):
    xy=np.asarray(p.minimum_rotated_rectangle.exterior.coords)[:4]
    for a,b in zip(xy,np.roll(xy,-1,axis=0)):
     for t in np.linspace(.08,.92,6):v=a*(1-t)+b*t;self.m('observation_columns').beam([*v,111],[*v,120],.65,'white')
   for y in [-20,-8,4,16]:self.arch('arched_civic_entry',[-43,y,1],6,10,1,-math.pi/2)
   self.box('entry_landing',[-47,-2,-.15],[8,32,.3],'paving');self.stairs([-51,-2,-1.7],32,1.7,6,math.pi/2)
 def curved_shell(self,name,center,width,depth,height,angle,z0=3,lean=4,mat='silver'):
  n=max(6,self.n//2);m=max(5,self.n//4);cx,cy=center;co,si=math.cos(angle),math.sin(angle);mesh=self.m(name);grid=[]
  for j,t in enumerate(np.linspace(0,1,m+1)):
   row=[]
   for i,s in enumerate(np.linspace(-1,1,n+1)):
    x=s*width/2;y=depth*(1-s*s)+lean*t*t;z=z0+t*(height-z0)*(1-.12*s*s);row.append([cx+co*x-si*y,cy+si*x+co*y,z])
   grid.append(row)
  for j in range(m):
   for i in range(n):mesh.quad([grid[j][i],grid[j][i+1],grid[j+1][i+1],grid[j+1][i]],mat)
  if self.near and mat=='silver':
   for j in range(0,m+1,max(1,m//12)):
    for a,b in zip(grid[j][:-1],grid[j][1:]):self.m('steel_panel_seams').beam(a,b,.025,'dark_metal')
   for i in range(0,n+1,max(1,n//10)):
    for j in range(m):self.m('steel_panel_seams').beam(grid[j][i],grid[j+1][i],.018,'dark_metal')
  return grid
 def disney_hall(self):
  self.extrude('source_plan_lower_foyer',self.g,0,4,'concrete');self.box('acoustic_core',[0,7,15.5],[45,78,27],'limestone');self.box('glass_entry_foyer',[0,-42,7],[62,25,14],'glass')
  sails=[([-25,-32],44,8,30,.20,3,8),([19,-35],49,12,35,-.25,3,-5),([-31,7],67,10,36.7,math.pi/2,6,8),([29,12],71,12,36,-math.pi/2,6,-5),([-19,53],44,8,32,math.pi-.2,8,3),([21,53],45,10,33,math.pi+.25,6,7),([-31,-48],27,5,19,.4,1,4),([32,-43],32,7,23,-.7,2,-4),([-25,38],38,7,34,2.3,9,3),([24,39],37,7,35,-2.2,8,-3),([0,-14],45,5,36.7,.08,12,4)]
  for j,(center,w,d,h,a,z,l) in enumerate(sails):self.curved_shell('stainless_sail_%02d'%j,center,w,d,h,a,z,l)
  if self.detail:
   self.facade(box(-30,-54,30,-29),0,13,'glass',4);self.stairs([-2,-65,-1.8],45,1.8,12,math.pi)
   self.box('Grand_Avenue_entry_landing',[49,-20,-.15],[6,16,.3],'paving');self.stairs([52,-20,-1.5],16,1.5,8,-math.pi/2)
   for x in [-24,24]:self.m('entry_handrails').beam([x,-65,0],[x,-53,2],.08,'silver')
 def the_broad(self):
  x0,y0,x1,y1=self.b;w=x1-x0;d=y1-y0;h=self.a['height_m'];self.box('glass_lobby',[0,0,2],[w-3,d-3,4],'glass');self.box('dark_vault',[0,0,(h+4)/2],[w-9,d-9,h-4.7],'concrete')
  if not self.detail:
   self.extrude('veil_far_shell',self.g.buffer(.35).difference(self.g.buffer(-.55)),4,h,'white');self.box('roof_far',[0,0,h-.3],[w,d,.6],'white');return
  for side in range(4):
   length=w if side%2==0 else d;front=side==1
   def pt(u,z,depth=0):
    lift=6*(abs(u)/(length/2))**8;eye=4.0*math.exp(-((u/10)**2+((z-15)/6)**2)) if front else 0;y=-d/2+eye+depth
    if side==0:return [u,y,z]
    if side==1:return [w/2-eye-depth,u,z]
    if side==2:return [-u,d/2-eye-depth,z]
    return [-w/2+eye+depth,-u,z]
   edges=set();step=2.5 if self.near else 3.75;rise=2 if self.near else 3
   # A staggered diamond lattice shares edges continuously; duplicate coplanar
   # beams are excluded. The small horizontal shear creates the observed lean.
   for col,u in enumerate(np.arange(-length/2-10,length/2+10,step)):
    for row,z in enumerate(np.arange(-rise,h+rise,rise)):
     u2=u+(step/2 if row%2 else 0)+.30*(z-h/2);q=[(u2-step/2,z),(u2+.30*rise,z+rise),(u2+step/2,z),(u2-.30*rise,z-rise)]
     for aa,bb in zip(q,q[1:]+q[:1]):
      # Clip each rib in the facade's 2D domain, lifted corners and oculus.
      domain=box(-length/2,.1,length/2,h-.1)
      eye=affinity.scale(Point(0,15).buffer(1,quad_segs=self.n//4),xfact=7.9,yfact=3.5,origin=(0,15)) if front else Polygon()
      cut=LineString([aa,bb]).intersection(domain).difference(eye)
      for line in ([cut] if isinstance(cut,LineString) else getattr(cut,'geoms',[])):
       if not isinstance(line,LineString) or line.length<.05:continue
       a,b=np.array(line.coords)[[0,-1]];mid=(a+b)/2
       if mid[1]<6*(abs(mid[0])/(length/2))**8:continue
       key=tuple(sorted([tuple(np.round(a,5)),tuple(np.round(b,5))]))
       if key in edges:continue
       edges.add(key);self.m('porous_veil_diagonal_ribs').beam(pt(*a),pt(*b),.48 if self.near else .60,'white')
   # Deep window oculus, with a true open ring in the veil.
   if front:
    ts=np.linspace(0,2*math.pi,self.n+1)
    for a,b in zip(ts[:-1],ts[1:]):self.m('concave_oculus_rim').beam(pt(8.0*math.cos(a),15+3.6*math.sin(a)),pt(8.0*math.cos(b),15+3.6*math.sin(b)),.42,'white')
    self.m('oculus_recessed_glass').face([[w/2-4.35,8.0*math.cos(t),15+3.5*math.sin(t)] for t in ts[:-1]],'glass')
  for x in np.arange(x0+1,x1,2.45):
   for y in np.arange(y0+1,y1,3.25):
    # Open daylight grid, not a solid flat roof covering the pores.
    self.m('roof_daylight_grid').beam([x,y,h],[min(x+2.35,x1),min(y+3.15,y1),h],.25,'white')
  self.box('corner_entry_landing',[w/2+1.5,-d/2+7,-.15],[3,9,.3],'paving');self.stairs([w/2+3,-d/2+7,-.5],9,.5,3,-math.pi/2)
 def roof(self,c,w,d,lo,rise):
  x,y=c;self.m('red_tile_roofs').face([[x-w/2,y-d/2,lo],[x+w/2,y-d/2,lo],[x,y-d/2,lo+rise]],'terracotta');self.m('red_tile_roofs').face([[x+w/2,y+d/2,lo],[x-w/2,y+d/2,lo],[x,y+d/2,lo+rise]],'terracotta')
  self.m('red_tile_roofs').quad([[x-w/2,y-d/2,lo],[x,y-d/2,lo+rise],[x,y+d/2,lo+rise],[x-w/2,y+d/2,lo]],'terracotta');self.m('red_tile_roofs').quad([[x,y-d/2,lo+rise],[x+w/2,y-d/2,lo],[x+w/2,y+d/2,lo],[x,y+d/2,lo+rise]],'terracotta')
  if self.near:
   for yy in np.arange(y-d/2,y+d/2,.45):
    for s in [-1,1]:self.m('tile_roof_ribbing').beam([x,yy,lo+rise+.03],[x+s*w/2,yy,lo+.03],.075,'terracotta')
 def canopy_roof(self,name,c,w,d,z,rise,mat='silver',folded=False):
  nx=max(12,self.n//2);ny=max(3,self.n//8);xs=np.linspace(-w/2,w/2,nx+1);ys=np.linspace(-d/2,d/2,ny+1);grid=[]
  for yy in ys:
   row=[]
   for xx in xs:
    zz=z+rise*(math.cos(xx/w*4*math.pi) if folded else 1-(2*xx/w)**2)+.2*(1-(2*yy/d)**2);row.append([c[0]+xx,c[1]+yy,zz])
   grid.append(row)
  for j in range(ny):
   for i in range(nx):self.m(name).quad([grid[j][i],grid[j][i+1],grid[j+1][i+1],grid[j+1][i]],mat)
  if self.near:
   for i in range(0,nx+1,2):
    for j in range(ny):self.m(name+'_roof_seams').beam(grid[j][i],grid[j+1][i],.045,'dark_metal')
 def union_station(self):
  patios=box(-22,30,21,68).union(box(-30,-77,12,-42));self.extrude('source_plan_station_base_with_patios',self.g.difference(patios),0,7.8);self.box('west_waiting_hall',[-57,-3,8.5],[29,116,17]);self.roof([-57,-3],32,118,17,5);self.box('ticket_hall',[-22,25,7.5],[33,82,15]);self.roof([-22,25],36,85,15,5);self.box('east_concourse',[31,10,5],[55,115,10]);self.roof([31,10],58,117,10,3)
  self.box('clock_tower',[-59,-62,16],[10,11,32]);self.box('belfry',[-59,-62,34],[8.5,9.5,4]);self.roof([-59,-62],10,11,36,2.5);self.m('tower_finial').beam([-59,-62,38.5],[-59,-62,self.a['height_m']],.14,'dark_metal')
  if self.detail:
   for y in np.arange(-45,47,13):self.arch('west_hall_arched_windows',[-72,y,2],7.7,12,1,-math.pi/2)
   self.arch('main_station_entry',[-72,-56,0],8.2,16,1.2,-math.pi/2)
   for angle in [0,math.pi/2,math.pi,math.pi*1.5]:
    normal=np.array([math.sin(angle),-math.cos(angle)]);center=np.array([-59,-62])+normal*5.06;u=np.array([math.cos(angle),math.sin(angle)]);m=self.m('clock_faces');ts=np.arange(self.n)*2*math.pi/self.n;m.face([[*(center+u*1.35*math.cos(t)),27+1.35*math.sin(t)] for t in ts],'clock');m.beam([*center,27],[*(center+u*.65),27.5],.08,'dark_metal');m.beam([*center,27],[*center,28.05],.07,'dark_metal')
   for y in [-76,-43,30,67]:self.box('patio_arcade',[-3,y,4],[42,1,8]);self.roof([-3,y],44,3,8,1)
   self.box('entry_landing',[-76,-3,-.15],[8,20,.3],'paving');self.stairs([-80,-3,-1.2],20,1.2,4,math.pi/2)
 def griffith_observatory(self):
  central_top=77*.3048;telescope_top=55*.3048
  self.extrude('cream_art_deco_wings',self.g,0,9.3,'white');self.m('planetarium_drum').cylinder([0,-8,8.7],13,13,4.3,'white',self.n);self.m('central_copper_dome').dome([0,-8,13],13,13,central_top-13,'copper',self.n)
  for x in [-27,27]:self.m('telescope_drum').cylinder([x,6,8],7,7,2.5,'white',self.n);self.m('telescope_copper_dome').dome([x,6,10.5],7,7,telescope_top-10.5,'copper',self.n)
  if self.detail:
   for x in [-27,27]:
    self.m('telescope_slit').quad([[x-.5,6,telescope_top+.05],[x+.5,6,telescope_top+.05],[x+.5,12.8,11.2],[x-.5,12.8,11.2]],'dark_metal')
   for x,y,r,z,h in [(0,-8,13,13,central_top-13),(-27,6,7,10.5,telescope_top-10.5),(27,6,7,10.5,telescope_top-10.5)]:
    for t in np.linspace(0,2*math.pi,16,endpoint=False):
     arc=[[x+r*math.cos(t)*math.cos(a),y+r*math.sin(t)*math.cos(a),z+h*math.sin(a)+.04] for a in np.linspace(0,math.pi/2,16)]
     for a,b in zip(arc[:-1],arc[1:]):self.m('copper_dome_ribs').beam(a,b,.065,'dark_metal')
   for x in np.arange(-29,30,5):
    if abs(x)>8:self.box('northern_tall_windows',[x,20.5,5.1],[1.7,.15,4.4],'glass')
   for x in [-5,-3,-1,1,3,5]:self.box('fluted_entry_pilasters',[x,22.5,5.6],[.40,.7,10.8],'white')
   self.box('entry_canopy',[0,24,11],[13,4,.6],'white');self.box('front_entry_landing',[0,24.5,-.15],[17,4,.3],'paving');self.stairs([0,26,-1.7],17,1.7,7)
   # South terrace and balustrade, foundation extends only below the building envelope.
   self.box('south_terrace',[0,-33,-.5],[70,10,1],'paving')
   for x in np.arange(-35,36,3):self.m('terrace_balustrade').beam([x,-38,0],[x,-38,1],.13,'white')
   self.m('terrace_balustrade').beam([-35,-38,1],[35,-38,1],.17,'white')
 def hollywood_sign(self):
  zroot=self.a['origin_city_m'][2];xyroot=np.array(self.a['origin_city_m'][:2])
  for index,letter in enumerate(self.a['letters']):
   a,b=np.array(letter['xy_m'])-xyroot
   if a[0]>b[0]:a,b=b,a
   tangent=(b-a)/np.linalg.norm(b-a);normal=np.array([tangent[1],-tangent[0]]);w=np.linalg.norm(b-a);h=letter['height_m'];z=letter['baseline_NAVD88_m']-zroot;ch=letter['letter'];t=.23
   if ch=='H':g=box(0,0,t,1).union(box(1-t,0,1,1)).union(box(0,.41,1,.62))
   elif ch=='L':g=box(0,0,t,1).union(box(0,0,1,.22))
   elif ch=='O':g=Polygon([(0,.15),(.15,0),(.85,0),(1,.15),(1,.85),(.85,1),(.15,1),(0,.85)],holes=[[(.25,.23),(.75,.23),(.75,.77),(.25,.77)]])
   elif ch=='D':g=Polygon([(0,0),(.70,0),(1,.22),(1,.78),(.70,1),(0,1)],holes=[[(.24,.22),(.67,.22),(.77,.30),(.77,.70),(.67,.78),(.24,.78)]])
   elif ch=='Y':g=shapely.union_all([LineString([(0.12,1),(.5,.53)]).buffer(.115,cap_style=2),LineString([(.88,1),(.5,.53)]).buffer(.115,cap_style=2),box(.385,0,.615,.55)])
   else:g=shapely.union_all([LineString([(.10,1),(.27,.10),(.5,.64),(.73,.10),(.90,1)]).buffer(.105,join_style=2,cap_style=2)])
   # Mesh in letter x/z plane, extrusion depth along the observed source line normal.
   tmp=Mesh();tmp.extrude(affinity.scale(g,xfact=w,yfact=h,origin=(0,0)),-.15,.15,'white');arrays,_=tmp.arrays();coords=arrays['v'];out=np.column_stack([a[0]+tangent[0]*coords[:,0]+normal[0]*coords[:,2],a[1]+tangent[1]*coords[:,0]+normal[1]*coords[:,2],z+coords[:,1]]);m=self.m('letter_%02d_%s'%(index,ch));o=len(m.v);m.v.extend(out);m.f.extend((arrays['f']+o).tolist());m.m.extend(arrays['m'].tolist())
   if self.detail:
    for frac in ([.15,.5,.85] if self.near else [.22,.78]):
     p=a+tangent*w*frac;rear=p-normal*1.2;self.m('rear_steel_posts').beam([*rear,z-.3],[*rear,z+h-.2],.14,'dark_metal');self.m('rear_diagonal_braces').beam([*(rear-normal*3),z-.5],[*rear,z+h*.70],.11,'dark_metal')
    for level in ([h*.2,h*.5,h*.8] if self.near else [h*.5]):self.m('rear_horizontal_girts').beam([*(a-normal*.3),z+level],[*(b-normal*.3),z+level],.08,'dark_metal')
 def bowl(self,rx,ry,innerx,innery,theta0,theta1,tiers=4,matnames=None):
  rows=18 if self.near else (9 if self.detail else 2);n=self.n*2;ts=np.linspace(theta0,theta1,n+1);mats=matnames or ['seat_yellow','seat_orange','seat_blue','seat_blue'];groups=self.groups
  for tier in range(tiers):
   for row in range(rows):
    t0=(tier+(row/rows))/tiers;t1=(tier+(row+1)/rows)/tiers;r0x=innerx+(rx-innerx)*t0;r1x=innerx+(rx-innerx)*t1;r0y=innery+(ry-innery)*t0;r1y=innery+(ry-innery)*t1;z0=2+t0*31;z1=2+t1*31;mesh=self.m('seating_tier_'+str(tier));mat=mats[tier%len(mats)]
    for j,(a,b) in enumerate(zip(ts[:-1],ts[1:])):
     if self.detail and j%12==0:continue
     mesh.quad([[r0x*math.cos(a),r0y*math.sin(a),z1],[r1x*math.cos(a),r1y*math.sin(a),z1],[r1x*math.cos(b),r1y*math.sin(b),z1],[r0x*math.cos(b),r0y*math.sin(b),z1]],mat);mesh.quad([[r0x*math.cos(a),r0y*math.sin(a),z0],[r0x*math.cos(a),r0y*math.sin(a),z1],[r0x*math.cos(b),r0y*math.sin(b),z1],[r0x*math.cos(b),r0y*math.sin(b),z0]],mat)
   if self.detail:
    for t in np.linspace(theta0,theta1,22):
     x=(innerx+(rx-innerx)*(tier+.3)/tiers)*math.cos(t);y=(innery+(ry-innery)*(tier+.3)/tiers)*math.sin(t);self.m('concourse_piers').beam([x,y,0],[x,y,2+(tier+.3)/tiers*31],1.1,'concrete')
  # Structural ring closure beneath the seating, not a second full-height solid stadium.
  ts=np.linspace(theta0,theta1,max(16,self.n)+1)
  for a,b in zip(ts[:-1],ts[1:]):self.m('outer_concourse_fascia').quad([[rx*math.cos(a),ry*math.sin(a),25],[rx*math.cos(b),ry*math.sin(b),25],[rx*math.cos(b),ry*math.sin(b),33],[rx*math.cos(a),ry*math.sin(a),33]],'concrete')
 def dodger_stadium(self):
  self.bowl(126,118,73,70,math.radians(143),math.radians(397));field=Point(0,0).buffer(1,quad_segs=self.n//4);field=affinity.scale(field,xfact=80,yfact=91,origin=(0,0));self.extrude('playing_field',field,-.15,.03,'grass');home=np.array([0,-55]);b1=np.array([27.432,-27.568]);b2=np.array([0,-.136]);b3=np.array([-27.432,-27.568]);self.extrude('infield_dirt',Polygon([home,b1+[5,4],b2+[0,12],b3+[-5,4]]),.03,.045,'earth')
  for x,y in [home,b1,b2,b3]:self.box('regulation_base_markers',[x,y,.08],[.38,.38,.05],'white')
  for p in [b1,b3]:self.m('foul_lines').beam([*home,.09],[*(home+(p-home)*3.5),.09],.12,'white')
  self.m('pitchers_mound').cylinder([0,-36.56,.04],2.75,2.75,.25,'earth',self.n//2)
  for x in [-66,66]:
   self.box('outfield_pavilion',[x,82,5],[46,30,10],'concrete')
   for row in range(8 if self.detail else 3):self.box('pavilion_seat_rows',[x,70+row*3,4+row*.75],[45,2.8,.65],'seat_blue')
   if self.detail:
    self.canopy_roof('pavilion_wave_canopy',[x,83],48,33,15.5,.7,'white',True)
    # Six-sided scoreboard silhouette, no copied sponsor artwork.
    self.m('hexagonal_scoreboards').face([[x-13,103,20],[x-13,103,30],[x,103,34],[x+13,103,30],[x+13,103,20],[x,103,17]],'screen');self.m('scoreboard_posts').beam([x,103,0],[x,103,23],1.3,'dark_metal')
  if self.detail:
   for t in np.radians([150,190,235,285,330,385]):
    x=126*math.cos(t);y=118*math.sin(t);self.m('floodlight_masts').beam([x,y,15],[x,y,43],.5,'dark_metal');self.box('floodlight_banks',[x,y,43],[10,1.5,3.5],'white')
 def memorial_coliseum(self):
  self.bowl(158,114,100,57,math.radians(27),math.radians(333),4,['seat_red']*4);self.box('football_field',[0,0,.02],[109.728,48.768,.08],'grass')
  if self.detail:
   for x in np.linspace(-54.864,54.864,13):self.m('football_yard_lines').beam([x,-24.384,.09],[x,24.384,.09],.11,'white')
   for y in [-24.384,24.384]:self.m('football_boundary').beam([-54.864,y,.09],[54.864,y,.09],.13,'white')
  self.box('scholarship_club_tower',[0,-96,24],[145,21,32],'glass');self.box('club_roof_deck',[0,-96,40],[149,26,.7],'white')
  if self.detail:
   for z in np.linspace(9,39,8):self.box('club_floor_bands',[0,-96,z],[148,23,.4],'white')
   for x in np.arange(-68,69,7):self.m('club_vertical_mullions').beam([x,-107,9],[x,-107,39],.14,'silver')
  # East peristyle wraps the oval opening. Real arches remain open, including the central portal.
  for j,t in enumerate(np.linspace(-.49,.49,13)):
   x=151*math.cos(t);y=114*math.sin(t);w=7.5 if abs(t)>.05 else 12;h=12 if abs(t)>.05 else 18;self.arch('east_peristyle_arches',[x,y,0],w,h,2.5,math.pi/2+t,'limestone',False)
  self.box('central_peristyle_pylon',[153,0,24],[8,15,12]);self.m('olympic_cauldron_stem').cylinder([153,0,30],2.1,2.1,7,'limestone',self.n//2);self.m('olympic_cauldron_bowl').loft([[[153+2.2*math.cos(t),2.2*math.sin(t),37] for t in np.arange(self.n)*2*math.pi/self.n],[[153+3.7*math.cos(t),3.7*math.sin(t),40] for t in np.arange(self.n)*2*math.pi/self.n]],'dark_metal')
  if self.detail:
   for t in np.linspace(.6,5.68,54):
    x=158*math.cos(t);y=114*math.sin(t);self.arch('outer_arcade',[x,y,0],6.5,9,1,math.atan2(y/114,x/158)+math.pi/2,'concrete',False)
def build(root=ROOT,massing=False):
 cfg=json.loads((root/'config/stage06.json').read_text());records=[];removed=0
 for p in cfg['landmarks']:
  card=json.loads((root/'data/processed/stage06/cards'/(p['id']+'.json')).read_text());lods=['far'] if massing else ['near','mid','far'];assets=[]
  for lod in lods:
   a=Asset(card,lod);groups=a.make();tri=0;bounds=[];objs=[]
   for name,m in groups.items():
    arrays,n=m.arrays();removed+=n
    if not len(arrays['f']):continue
    assert np.isfinite(arrays['v']).all();file=root/'data/processed/stage06'/('massing_meshes' if massing else 'meshes')/p['id']/lod/(name+'.npz');file.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(file,**arrays);tri+=len(arrays['f']);bounds.extend([arrays['v'].min(axis=0),arrays['v'].max(axis=0)]);objs.append({'name':name,'file':str(file.relative_to(root)),'triangles':len(arrays['f']),'sha256':digest(file),'inference':'source plan/part form for primary body; photo-guided inferred detail, see card','smooth_curved':any(k in name for k in ['dome','sail','crown'])})
   bounds=np.array(bounds);assets.append({'lod':lod,'triangles':tri,'objects':objs,'bounds_local_m':[bounds.min(axis=0).tolist(),bounds.max(axis=0).tolist()]})
  records.append({'id':p['id'],'card':'data/processed/stage06/cards/'+p['id']+'.json','assets':assets});print('ORIGINAL_LANDMARK_GEOMETRY',p['id'],[(a['lod'],a['triangles']) for a in assets],flush=True)
 write_json(root/'data/processed/stage06'/('massing_index.json' if massing else 'geometry_index.json'),{'landmarks':records,'materials':MATERIALS,'removed_float32_degenerate_faces':removed,'seed':cfg['seed'],'source_config_sha256':digest(root/'config/stage06.json'),'script_sha256':digest(Path(__file__)),'all_procedural_approximation_marked':True})
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--massing',action='store_true');a=p.parse_args();build(massing=a.massing)
