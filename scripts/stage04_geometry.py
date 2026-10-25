"""Tile-local transportation geometry and exact barycentric draping to selected ground."""
import json,math,collections
from pathlib import Path
import numpy as np
import shapely
from shapely.geometry import Polygon,LineString,Point,box
from shapely.strtree import STRtree
from stage03_common import references,polygon_parts
from stage02_io import write_json,digest
MATERIALS=[('asphalt',[.075,.083,.09,1]),('sidewalk',[.48,.46,.41,1]),('curb',[.65,.64,.59,1]),('white',[.88,.87,.79,1]),('yellow',[.95,.65,.065,1]),('bridge_concrete',[.35,.36,.35,1]),('metal',[.28,.32,.34,1]),('rail_ballast',[.25,.23,.20,1]),('rail_steel',[.42,.45,.47,1]),('sleeper',[.20,.18,.15,1]),('cycle',[.18,.31,.24,1]),('runway',[.105,.115,.12,1]),('apron',[.35,.37,.38,1]),('platform',[.61,.58,.52,1]),('noise_screen',[.46,.43,.37,1]),('median',[.23,.28,.18,1]),('ramp_tactile',[.73,.58,.16,1])]
MAT={v[0]:i for i,v in enumerate(MATERIALS)}

def tile_id(ix,iy):return f'la_t_x{ix:+04d}_y{iy:+04d}'
class Ground:
 def __init__(self,root):
  self.root=Path(root);_,self.origin,self.city,self.refs=references(root)
  self.index=json.loads((self.root/'data/processed/stage03/medium/tile_index.json').read_text());self.tiles={tuple(t['ij']):t for t in self.index['tiles']};self.cache={};self.active={}
  water=json.loads((self.root/'data/processed/stage03/medium/water_index.json').read_text());water_tiles={p['tile_id'] for p in water['pieces']}
  for ij,t in self.tiles.items():
   b=box(ij[0]*1000,ij[1]*1000,ij[0]*1000+1000,ij[1]*1000+1000)
   # Preserve detailed ground in Downtown and the real US101/CA110 interchange study window.
   self.active[t['id']]=0 if b.intersects(self.refs['downtown']) or b.distance(Point(-250,2650))<800 or min(t['active_sampling_steps_m'])<50 or t['id'] in water_tiles else 2
  self.fallbacks=0;self.source_override_files={};self.enable_road_floor=True;self.floor_cache={};fp=self.root/'data/processed/stage04/road_floor_index.json';self.floor_index=json.loads(fp.read_text()) if fp.exists() else None
 def load(self,ij):
  if ij in self.cache:return self.cache[ij]
  t=self.tiles.get(ij)
  if t is None:return None
  lod=self.active[t['id']];p=self.root/t['file'];variant=self.root/f'data/processed/stage04/ground/{t["id"]}.npz'
  with np.load(self.source_override_files.get(ij,variant if variant.exists() else p)) as a:v=a[f'v{lod}'].astype(float);f=a[f'f{lod}'].copy()
  triangles=shapely.polygons(v[f,:2]);tree=STRtree(triangles);out=(v,f,tree,triangles);self.cache[ij]=out;return out
 def __call__(self,x,y):
  x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float);z=np.full(len(x),np.nan);ij=np.floor(np.column_stack([x,y])/1000).astype(int)
  for key in set(map(tuple,ij)):
   ids=np.flatnonzero(np.all(ij==key,axis=1));data=self.load(key)
   if data is None:continue
   v,f,tree,tri=data;xy=np.column_stack([x[ids]-key[0]*1000,y[ids]-key[1]*1000]);pts=shapely.points(xy);pairs=tree.query(pts,predicate='intersects');found={int(a):int(b) for a,b in zip(*pairs)}
   missing=np.array([i for i in range(len(ids)) if i not in found],int)
   if len(missing):
    nn=tree.nearest(pts[missing]);dist=shapely.distance(pts[missing],tri[nn]);self.fallbacks+=int((dist<.02).sum())
    for i,j,d in zip(missing,nn,dist):
     if d<.02:found[int(i)]=int(j)
   if not found:continue
   ii=np.array(list(found));jj=np.array(list(found.values()));a=v[f[jj,0]];b=v[f[jj,1]];c=v[f[jj,2]];q=xy[ii];ab=b[:,:2]-a[:,:2];ac=c[:,:2]-a[:,:2];aq=q-a[:,:2]
   den=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0];u=(aq[:,0]*ac[:,1]-aq[:,1]*ac[:,0])/den;w=(ab[:,0]*aq[:,1]-ab[:,1]*aq[:,0])/den
   z[ids[ii]]=a[:,2]+u*(b[:,2]-a[:,2])+w*(c[:,2]-a[:,2])
  if self.enable_road_floor and self.floor_index and (~np.isfinite(z)).any():
   for key in set(map(tuple,ij[~np.isfinite(z)])):
    ids=np.flatnonzero((~np.isfinite(z))&np.all(ij==key,axis=1));tid=tile_id(*key)
    if key not in self.floor_cache:
     arrays=[]
     for m in self.floor_index['meshes']:
      if m['tile_id']!=tid:continue
      with np.load(self.root/m['file']) as d:arrays.append(d['v'][d['f']].astype(float))
     if arrays:
      t=np.concatenate(arrays);self.floor_cache[key]=(t,STRtree(shapely.polygons(t[:,:,:2])))
     else:self.floor_cache[key]=None
    floor=self.floor_cache[key]
    if floor is None:continue
    triangles,tree=floor;q=np.column_stack([x[ids]-key[0]*1000,y[ids]-key[1]*1000]);pairs=tree.query(shapely.points(q),predicate='intersects')
    for pi,ti in zip(*pairs):
     t=triangles[ti];ab=t[1,:2]-t[0,:2];ac=t[2,:2]-t[0,:2];aq=q[pi]-t[0,:2];den=ab[0]*ac[1]-ab[1]*ac[0]
     if abs(den)<1e-10:continue
     u=(aq[0]*ac[1]-aq[1]*ac[0])/den;w=(ab[0]*aq[1]-ab[1]*aq[0])/den;zz=t[0,2]+u*(t[1,2]-t[0,2])+w*(t[2,2]-t[0,2])-.06;j=ids[pi]
     if not np.isfinite(z[j]) or zz<z[j]:z[j]=zz
  return z

class Meshes:
 def __init__(self,root,ground):self.root=Path(root);self.ground=ground;self.buckets={};self.instances=[];self.omitted=collections.Counter();self.feature_coverage=set();self.seam_edges=collections.defaultdict(list);self.city_tiles={};self.pre_saved=[]
 def add(self,role,ix,iy,v,f,mat='asphalt',feature=-1):
  v=np.asarray(v,float);f=np.asarray(f,int)
  if not len(f):return
  if not np.isfinite(v).all():raise ValueError('Nonfinite mesh '+role)
  key=(role,ix,iy);d=self.buckets.setdefault(key,{'v':[],'f':[],'m':[],'fid':[],'offset':0});n=d['offset'];d['v'].append(v-np.array([ix*1000,iy*1000,0]));d['f'].append(f+n);d['m'].extend([MAT[mat]]*len(f));d['fid'].extend([feature]*len(f));d['offset']+=len(v)
  if feature>=0:self.feature_coverage.add(feature)
 def polygon(self,g,role,zfun=None,mat='asphalt',feature=-1,max_segment=30,extrude=0):
  if g.is_empty:return
  bounds=g.bounds
  for ix in range(math.floor(bounds[0]/1000),math.floor(bounds[2]/1000)+1):
   for iy in range(math.floor(bounds[1]/1000),math.floor(bounds[3]/1000)+1):
    if (ix,iy) not in self.ground.tiles:continue
    tile=box(ix*1000,iy*1000,(ix+1)*1000,(iy+1)*1000)
    if (ix,iy) not in self.city_tiles:self.city_tiles[(ix,iy)]=tile if self.ground.city.covers(tile) else tile.intersection(self.ground.city)
    cut=g.intersection(self.city_tiles[(ix,iy)])
    for p in polygon_parts(cut):
     if p.area<.0001:continue
     p=shapely.segmentize(p,max_segment)
     try:tri=shapely.constrained_delaunay_triangles(p)
     except shapely.errors.GEOSException:
      tri=None
      for precision in [.0001,.001,.01]:
       fixed=shapely.make_valid(shapely.set_precision(p,precision))
       try:
        tri=shapely.constrained_delaunay_triangles(fixed);p=fixed;self.omitted['repaired_CDT_precision_'+str(precision)+'m']+=1;break
       except shapely.errors.GEOSException:continue
      if tri is None:
       if p.area<.01:self.omitted['untriangulable_sub_0_01m2_slivers']+=1;continue
       raise ValueError('Untriangulable significant polygon '+role+' feature='+str(feature)+' area='+str(p.area))
     if tri.is_empty:continue
     xy=np.concatenate([np.asarray(t.exterior.coords)[:3,:2] for t in tri.geoms]);z=self.ground(xy[:,0],xy[:,1])+.06 if zfun is None else zfun(xy)
     good=np.isfinite(z)
     if not good.all():
      # Exact city boundary float quantization can lie <2cm outside ground. Omit only unsupported faces and report.
      f=np.arange(len(xy)).reshape(-1,3);keep=good[f].all(axis=1);self.omitted['outside_supported_ground_faces']+=int((~keep).sum());f=f[keep]
      if not len(f):continue
      z[~good]=0
     else:f=np.arange(len(xy)).reshape(-1,3)
     self.add(role,ix,iy,np.column_stack([xy,z]),f,mat,feature)
     if extrude:
      # Exposed deck sides only. No internal triangle walls.
      for ring in [ring for part in polygon_parts(p) for ring in [part.exterior,*part.interiors]]:
       edge=np.asarray(ring.coords);zz=self.ground(edge[:,0],edge[:,1])+.06 if zfun is None else zfun(edge)
       for a,b,za,zb in zip(edge[:-1],edge[1:],zz[:-1],zz[1:]):
        if not np.isfinite([za,zb]).all():continue
        vv=np.array([[*a,za],[*b,zb],[*b,zb-extrude],[*a,za-extrude]])
        self.add(role,ix,iy,vv,[[0,1,2],[0,2,3]],'bridge_concrete',feature)
 def strip(self,xy,width,role,zfun=None,mat='white',feature=-1):
  g=LineString(np.asarray(xy)[:,:2])
  if g.length<.005:return
  self.polygon(g.buffer(width/2,cap_style=2,join_style=2),role,zfun,mat,feature,max_segment=5)
 def instance(self,kind,xyz,scale,rotation=0,source=None):
  if not np.isfinite(xyz).all():return
  self.instances.append({'kind':kind,'xyz_m':[float(v) for v in xyz],'scale':[float(v) for v in scale],'rotation_z':float(rotation),'source':source,'data_class':'inferred_geometry' if kind not in ['signal'] else 'observed_junction_inferred_pole_placement'})
 def save(self,namespace=''):
  folder=self.root/'data/processed/stage04/meshes';folder=folder/namespace if namespace else folder;folder.mkdir(parents=True,exist_ok=True);index=list(self.pre_saved);removed=0
  for (role,ix,iy),d in sorted(self.buckets.items()):
   v=np.concatenate(d['v']).astype(np.float32);f=np.concatenate(d['f']).astype(np.int32);m=np.array(d['m'],np.uint8);fid=np.array(d['fid'],np.int32)
   cross=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]);good=np.linalg.norm(cross,axis=1)>1e-8;removed+=int((~good).sum());f=f[good];m=m[good];fid=fid[good]
   p=folder/f'{tile_id(ix,iy)}_{role}.npz';np.savez_compressed(p,v=v,f=f,m=m,fid=fid)
   index.append({'id':namespace+'_'+p.stem if namespace else p.stem,'tile_id':tile_id(ix,iy),'origin_m':[ix*1000,iy*1000,0],'role':role,'file':str(p.relative_to(self.root)),'triangles':len(f),'vertices':len(v),'sha256':digest(p),'feature_count':len(set(fid.tolist())-{-1}),'visible_default':role!='full_far'})
  write_json(self.root/('work/cache/stage04/'+namespace+'_index.json' if namespace else 'data/processed/stage04/mesh_index.json'),{'meshes':index,'materials':MATERIALS,'instances':self.instances,'removed_float32_degenerates':removed,'omitted':dict(self.omitted),'feature_indices_with_geometry':sorted(self.feature_coverage),'static_visibility':'far overview main streets + Downtown detail; full service/path/parking assets retained in hidden full_far collection for per-tile loading','runtime_lod_implemented':False})
  return index
