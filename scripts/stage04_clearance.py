"""Repair sunken priority roads from bounded profiles; cut only derived terrain/pavement."""
from pathlib import Path
import json,math,collections,shutil
import numpy as np
import shapely
from shapely.geometry import LineString,Point,box
from stage04_build import Builder
from stage04_geometry import Meshes,tile_id
from stage03_common import polygon_parts
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def tris(p):
 if p.is_empty:return []
 try:return list(shapely.constrained_delaunay_triangles(p).geoms)
 except shapely.errors.GEOSException:return list(shapely.constrained_delaunay_triangles(shapely.make_valid(shapely.set_precision(p,.0001))).geoms)
def clip_arrays(v,f,m,fid,mask,translation,normals=None):
 world=v[:,:2].astype(float)+translation;polys=shapely.polygons(world[f]);touch=shapely.intersects(polys,mask)
 if not touch.any():return None
 vertices=[v.astype(float)];faces=[f[~touch]];materials=[m[~touch]];owners=[fid[~touch]];ns=[normals] if normals is not None else None;offset=len(v)
 for j in np.flatnonzero(touch):
  if polys[j].area<1e-8:continue
  try:cut=polys[j].difference(mask)
  except shapely.errors.GEOSException:
   cut=None
   for precision in [.0001,.001,.01]:
    try:
     aa=shapely.set_precision(shapely.make_valid(polys[j]),precision);bb=shapely.set_precision(shapely.make_valid(mask),precision);cut=shapely.difference(aa,bb,grid_size=precision);break
    except shapely.errors.GEOSException:continue
   if cut is None:raise ValueError('Significant terrain overlay could not be repaired')
  t=v[f[j]].astype(float);a=t[0,:2]+translation;ab=t[1,:2]-t[0,:2];ac=t[2,:2]-t[0,:2];den=ab[0]*ac[1]-ab[1]*ac[0]
  if abs(den)<1e-10:continue
  for part in polygon_parts(cut):
   if part.area<1e-8:continue
   tt=tris(part)
   if not tt:continue
   xy=np.concatenate([np.asarray(q.exterior.coords)[:3,:2] for q in tt]);aq=xy-a;u=(aq[:,0]*ac[1]-aq[:,1]*ac[0])/den;w=(ab[0]*aq[:,1]-ab[1]*aq[:,0])/den;zz=t[0,2]+u*(t[1,2]-t[0,2])+w*(t[2,2]-t[0,2]);vv=np.column_stack([xy-translation,zz]);ff=np.arange(len(vv),dtype=np.int32).reshape(-1,3);vertices.append(vv);faces.append(ff+offset);offset+=len(vv);materials.append(np.full(len(ff),m[j],np.uint8));owners.append(np.full(len(ff),fid[j],np.int32))
   if ns is not None:
    nn=normals[f[j]];new=nn[0]+u[:,None]*(nn[1]-nn[0])+w[:,None]*(nn[2]-nn[0]);new/=np.maximum(np.linalg.norm(new,axis=1)[:,None],1e-12);ns.append(new)
 vv=np.concatenate(vertices).astype(np.float32);ff=np.concatenate(faces).astype(np.int32);mm=np.concatenate(materials);ii=np.concatenate(owners);cross=np.cross(vv[ff[:,1]]-vv[ff[:,0]],vv[ff[:,2]]-vv[ff[:,0]]);good=np.linalg.norm(cross,axis=1)>1e-8
 out={'v':vv,'f':ff[good],'m':mm[good],'fid':ii[good]}
 if ns is not None:
  out['n']=np.concatenate(ns).astype(np.float32)
  down=cross[good,2]<0;out['f'][down]=out['f'][down][:,[0,2,1]]
 return out

def repair(root=ROOT):
 b=Builder(root);old=b.ground;indexpath=root/'data/processed/stage04/mesh_index.json';idx=json.loads(indexpath.read_text());geo=json.loads((root/'work/reports/stage04/geometry.json').read_text());roi=b.refs['downtown'].buffer(150).union(Point(geo['interchange_center_m']).buffer(950));target=set();lookup={r['id']:i for i,r in enumerate(b.roads)}
 for i,r in enumerate(b.roads):
  p=r['parameters']
  if p['vertical_rank']==0 and not p['bridge'] and not p['tunnel'] and p['class'] in ['motorway','trunk','ramp'] and b.gs[i].intersects(roi):target.add(i)
 check=json.loads((root/'work/reports/stage04/actual_mesh_crossings.json').read_text())
 for c in check['crossings']:
  if c['status']!='mesh_clearance_warning':continue
  for key,zkey in [('source_a','mesh_z_a_m'),('source_b','mesh_z_b_m')]:
   i=lookup[c[key]];p=b.roads[i]['parameters']
   if p['vertical_rank']==0 and not p['bridge'] and not p['tunnel']:
    desired=b.profile_z(i,np.array([c['xy_m']]))[0]
    if abs(c[zkey]-desired)>.3:target.add(i)
 polys={};target_positions={}
 for i in sorted(target):
  r=b.roads[i];g=b.gs[i].intersection(roi);p=r['parameters'];polys[i]=g.simplify(.015).buffer(p['width_m']/2,quad_segs=2,cap_style=2,join_style=1).intersection(b.city)
 mask=shapely.unary_union(list(polys.values()));affected={ij:t for ij,t in old.tiles.items() if box(ij[0]*1000,ij[1]*1000,(ij[0]+1)*1000,(ij[1]+1)*1000).intersects(mask)}
 # Keep the pre-cut terrain in memory, and preserve every replaced generated file.
 for ij in affected:old.load(ij)
 archive=root/'work/history/stage04_before_clearance_fix/files'
 def backup(path):
  dst=archive/path.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True)
  if not dst.exists():shutil.copy2(path,dst)
 cuts={ij:mask.intersection(box(ij[0]*1000,ij[1]*1000,(ij[0]+1)*1000,(ij[1]+1)*1000)) for ij in affected};changed_pavement=0
 cutroles={'downtown_road','full_far','overview_far','downtown_paths','downtown_sidewalk','downtown_curb','curb_ramp','refuge_island'}
 for m in idx['meshes']:
  xy=m['origin_m'][:2];ij=(int(xy[0]/1000),int(xy[1]/1000))
  if ij not in affected or m['role'] not in cutroles:continue
  assert digest(root/m['file'])==m['sha256']
  with np.load(root/m['file']) as a:d={k:a[k] for k in a.files}
  result=clip_arrays(d['v'],d['f'],d['m'],d['fid'],cuts[ij],np.array(xy))
  if result:
   backup(root/m['file']);np.savez_compressed(root/m['file'],**result);m['vertices']=len(result['v']);m['triangles']=len(result['f']);m['sha256']=digest(root/m['file']);changed_pavement+=1
 # Road top surfaces use the longitudinal profile, not a coarser triangle bridging over a cutting.
 mesh=Meshes(root,old)
 def height(i,xy):
  z=b.profile_z(i,xy)-.015*shapely.distance(shapely.points(xy),b.gs[i]);weight=np.clip(shapely.distance(shapely.points(xy),roi.boundary)/100,0,1);base=old(xy[:,0],xy[:,1])+.06
  return z*weight+base*(1-weight)
 for i,poly in polys.items():mesh.polygon(poly,'profiled_priority_road',lambda xy,i=i:height(i,xy),'asphalt',i,max_segment=3)
 # Retaining faces bridge the inferred cutting to the retained original display surface.
 road_tree=__import__('shapely').strtree.STRtree([b.gs[i] for i in sorted(target)]);which=np.array(sorted(target))
 for part in polygon_parts(mask):
  for ring in [part.exterior,*part.interiors]:
   line=shapely.segmentize(LineString(ring.coords),4);xy=np.asarray(line.coords);near=which[road_tree.nearest(shapely.points(xy))];low=np.empty(len(xy))
   for i in set(near.tolist()):ids=np.flatnonzero(near==i);low[ids]=height(i,xy[ids])-.04
   high=old(xy[:,0],xy[:,1]);high=np.where(np.isfinite(high),high,low)
   for aa,bb,la,lb,ha,hb in zip(xy[:-1],xy[1:],low[:-1],low[1:],high[:-1],high[1:]):
    if max(abs(ha-la),abs(hb-lb))<.08:continue
    mid=(aa+bb)/2;ix,iy=np.floor(mid/1000).astype(int);vv=np.array([[*aa,la],[*bb,lb],[*bb,hb],[*aa,ha]]);mesh.add('inferred_retaining_bank',int(ix),int(iy),vv,[[0,1,2],[0,2,3]],'bridge_concrete',-1)
 added=mesh.save('clearance_repair');idx['meshes'].extend(added)
 # Cut all actual selected terrain tiles; original source and other hidden LODs remain intact.
 variant_map={x['tile_id']:x for x in geo['ground_variants']};terrain_count=0
 for ij,t in affected.items():
  path=root/f'data/processed/stage04/ground/{t["id"]}.npz';source=path if path.exists() else root/t['file'];backup(source)
  with np.load(source) as a:arrays={k:a[k] for k in a.files}
  lod=geo['base_active_lods'][t['id']];result=clip_arrays(arrays[f'v{lod}'],arrays[f'f{lod}'],arrays[f'm{lod}'],np.full(len(arrays[f'f{lod}']),-1,np.int32),cuts[ij],np.array(t['blender_object_translation_m'][:2]),arrays.get(f'n{lod}'))
  if result:
   for k in ['v','f','m']:arrays[k+str(lod)]=result[k]
   if 'n' in result:arrays['n'+str(lod)]=result['n']
   path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(path,**arrays);variant_map[t['id']]={'tile_id':t['id'],'file':str(path.relative_to(root)),'sha256':digest(path),'type':'profiled_road_cut_in_display_terrain','cut_lod':lod};terrain_count+=1
 for m in idx['meshes']:
  if m['role']=='markings':m['paint_draped_to_actual_pavement']=False
 for ins in idx['instances']:
  i=lookup.get(str(ins.get('source')))
  if ins['kind']=='guardrail' and i in target:
   angle=ins['rotation_z'];horizontal=ins['scale'][0]*math.cos(ins.get('rotation_y',0));axis=np.array([math.cos(angle),math.sin(angle)]);xy=np.array(ins['xyz_m'][:2]);ends=np.array([xy-axis*horizontal/2,xy+axis*horizontal/2]);zz=height(i,ends)+.75;dz=zz[1]-zz[0];ins['xyz_m'][2]=float(np.mean(zz));ins['rotation_y']=-math.atan2(dz,horizontal);ins['scale'][0]=math.hypot(horizontal,dz)
 geo['ground_variants']=list(variant_map.values());geo['triangles_by_role']={role:sum(m['triangles'] for m in idx['meshes'] if m['role']==role) for role in set(m['role'] for m in idx['meshes'])};write_json(root/'work/reports/stage04/geometry.json',geo);write_json(indexpath,idx);write_json(root/'data/processed/stage04/road_floor_index.json',{'meshes':[m for m in added if m['role']=='profiled_priority_road'],'offset_below_pavement_m':.06})
 write_json(root/'work/reports/stage04/clearance_repair.json',{'status':'executed','source_roads_rebuilt':[b.roads[i]['id'] for i in sorted(target)],'cut_terrain_tiles':terrain_count,'changed_original_pavement_meshes':changed_pavement,'real_XY_and_graph_unchanged':True,'height_source':'existing globally grade-bounded road profiles','retaining_faces':'inferred display cutting boundaries/material, not surveyed retaining structures','original_inputs_preserved':True});print('PRIORITY_ROAD_CLEARANCE_GEOMETRY_REPAIRED',len(target),terrain_count,changed_pavement,flush=True)
if __name__=='__main__':repair()
