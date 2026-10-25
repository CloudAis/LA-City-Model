"""Native DEM detail/recorded grading, frozen source neighbors and transportation context.

Every context mesh is translated/rotated into the landmark's local inspection frame.
It is not an invented arrangement. City checkpoint uses the inverse exact placement.
"""
from pathlib import Path
import collections,json,math
import numpy as np,shapely
from shapely import affinity
from shapely.geometry import shape,box,Point,MultiPoint,Polygon
from stage03_common import references
from stage04_geometry import Ground
from stage03_surface import Surface
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def read(root,p):return json.loads((root/p).read_text())
def save(root,path,a):
 path=root/path;path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(path,**a);return str(path.relative_to(root))
def compact(v,f,m,fid=None):
 ids,inv=np.unique(f,return_inverse=True);out={'v':v[ids].astype(np.float32),'f':inv.reshape(-1,3).astype(np.int32),'m':m.astype(np.int32)}
 if fid is not None:out['fid']=fid
 return out
def terrain(root=ROOT):
 ground=Ground(root);surface=Surface(root);cards=[read(root,'data/processed/stage06/cards/'+p['id']+'.json') for p in read(root,'config/stage06.json')['landmarks']];sites=[];tiles=collections.defaultdict(list)
 for a in cards:
  g=shape(a['local_plan']);g=affinity.rotate(g,math.degrees(a['rotation_z_radians']),origin=(0,0));g=affinity.translate(g,xoff=a['origin_city_m'][0],yoff=a['origin_city_m'][1]);remote=a['id'] in ['griffith_observatory','hollywood_sign','dodger_stadium','memorial_coliseum'];area=g.convex_hull if 'stadium' in a['id'] or 'coliseum' in a['id'] else shapely.union_all([Polygon(p.exterior) for p in (g.geoms if hasattr(g,'geoms') else [g])]);site={'id':a['id'],'plan':area,'extent':area.buffer(260 if remote else 40),'grading':area.buffer(2.7),'z':a['origin_city_m'][2]-.17,'step':10 if remote else 5,'remote':remote};sites.append(site)
  for ij,t in ground.tiles.items():
   if box(ij[0]*1000,ij[1]*1000,(ij[0]+1)*1000,(ij[1]+1)*1000).intersects(site['extent']):tiles[ij].append(site)
 records=[];maxseam=0;maxedit=0
 for ij,ss in tiles.items():
  t=ground.tiles[ij];vold,fold,_,_=ground.load(ij);ab0=vold[fold[:,1],:2]-vold[fold[:,0],:2];ac0=vold[fold[:,2],:2]-vold[fold[:,0],:2];valid2d=np.abs(ab0[:,0]*ac0[:,1]-ab0[:,1]*ac0[:,0])>1e-10;fold=fold[valid2d];oldxy=vold[:,:2];globxy=oldxy+np.array(ij)*1000;points=[oldxy]
  for site in ss:
   b=site['extent'].bounds;x=np.arange(max(math.ceil(b[0]/site['step'])*site['step'],ij[0]*1000+site['step']),min(b[2],(ij[0]+1)*1000),site['step']);y=np.arange(max(math.ceil(b[1]/site['step'])*site['step'],ij[1]*1000+site['step']),min(b[3],(ij[1]+1)*1000),site['step']);xx,yy=np.meshgrid(x,y);xy=np.column_stack([xx.ravel(),yy.ravel()]);xy=xy[shapely.covers(site['extent'],shapely.points(xy))];points.append(xy-np.array(ij)*1000)
  xy=np.unique(np.round(np.vstack(points),6),axis=0)
  # Retain the actual prior ground footprint, including road cuts. A full-tile
  # unconstrained triangulation would refill those holes and bury pavement.
  oldtris=shapely.polygons(vold[fold,:2]);clip=shapely.union_all(oldtris);tris=shapely.delaunay_triangles(MultiPoint(xy));clipped=shapely.intersection(np.array(list(tris.geoms),object),clip);tri=shapely.constrained_delaunay_triangles(clipped);coords=shapely.get_coordinates(tri).reshape(-1,4,2)[:,:3];xy,inv=np.unique(np.round(coords.reshape(-1,2),6),axis=0,return_inverse=True);f=inv.reshape(-1,3).astype(np.int32)
  # Sample barycentric heights from this tile, including exact boundary points.
  tree=shapely.STRtree(oldtris);query=shapely.points(xy);pairs=tree.query_nearest(query,return_distance=True,all_matches=False);(pointids,faceids),distance=pairs;assert distance.max()<.01,(ij,float(distance.max()));base=np.full(len(xy),np.nan);aa=vold[fold[faceids,0]];ab=vold[fold[faceids,1]]-aa;ac=vold[fold[faceids,2]]-aa;aq=xy[pointids]-aa[:,:2];den=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0];u=(aq[:,0]*ac[:,1]-aq[:,1]*ac[:,0])/den;w=(ab[:,0]*aq[:,1]-ab[:,1]*aq[:,0])/den;base[pointids]=aa[:,2]+u*ab[:,2]+w*ac[:,2]
  gx=xy[:,0]+ij[0]*1000;gy=xy[:,1]+ij[1]*1000;native=surface(gx,gy);assert np.isfinite(base).all() and np.isfinite(native).all(),(ij,'nonfinite_base',int((~np.isfinite(base)).sum()),'native',int((~np.isfinite(native)).sum()));z=base.copy();pts=shapely.points(gx,gy)
  for site in ss:
   if site['remote']:
    dist=shapely.distance(pts,site['plan']);w=np.clip((260-dist)/90,0,1);boundary=np.minimum.reduce([xy[:,0],1000-xy[:,0],xy[:,1],1000-xy[:,1]]);w*=np.clip(boundary/70,0,1);z=z*(1-w)+native*w
   if site['id']!='hollywood_sign':
    dist=shapely.distance(pts,site['grading']);w=np.clip(1-dist/9,0,1);z=z*(1-w)+site['z']*w
  boundary=(np.abs(xy[:,0])<1e-5)|(np.abs(xy[:,0]-1000)<1e-5)|(np.abs(xy[:,1])<1e-5)|(np.abs(xy[:,1]-1000)<1e-5);z[boundary]=base[boundary];maxedit=max(maxedit,float(np.max(np.abs(z-base))));v=np.column_stack([xy,z]).astype(np.float32)
  cross=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]);flip=cross[:,2]<0;f[flip]=f[flip][:,[0,2,1]];good=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])[:,2]>1e-8;removed=int((~good).sum());f=f[good];centroid=v[f,:2].mean(axis=1);mi=surface.material_indices(centroid[:,0]+ij[0]*1000,centroid[:,1]+ij[1]*1000);source_m=mi.copy()
  # A source NLCD water-cover island below the Sign conflicts with the licensed
  # dry-hillside reference. Preserve raw class and label this display override.
  if t['id']=='la_t_x-007_y+010':mi[mi==surface.class_index['inland_water']]=surface.class_index['dry_slope']
  seam=float(np.max(abs(v[boundary,2]-base[boundary])));maxseam=max(maxseam,seam);file=save(root,'data/processed/stage06/ground/'+t['id']+'.npz',{'v':v,'f':f,'m':mi,'source_m':source_m});records.append({'id':t['id'],'ij':list(ij),'file':file,'source_file':t['file'],'original_selected_lod':ground.active[t['id']],'origin_city_m':[ij[0]*1000,ij[1]*1000,0],'triangles':len(f),'boundary_vertices':int(boundary.sum()),'max_boundary_numeric_delta_m':seam,'source_resolution_m':{'remote':10,'downtown':1},'sampling_step_m':sorted(set(s['step'] for s in ss)),'sites':[s['id'] for s in ss],'grading_max_difference_from_prior_mesh_m':float(np.max(abs(z-base))),'source_ground_area_m2':clip.area,'result_triangle_plan_area_m2':float(shapely.area(shapely.polygons(v[f,:2])).sum()),'removed_float32_degenerate_faces':removed,'road_cut_holes_preserved':True,'sha256':digest(root/file),'inferred_surface_class_override_faces':int((source_m!=mi).sum())})
  print('LANDMARK_TERRAIN_VARIANT',t['id'],len(f),'seam_delta',seam,flush=True)
 write_json(root/'data/processed/stage06/ground_index.json',{'tiles':records,'materials':[[name,surface.cfg['surface']['colors'][name]] for name in surface.classes],'original_terrain_files_modified':False,'boundary_matching_tolerance_m':.0001,'max_boundary_numeric_delta_m':maxseam,'maximum_height_difference_from_prior_approximation_m':maxedit,'grading_record':'Local selected building footprint+2.7m flattened to inferred floor minus0.17m, 9m transition; stadiums use convex plan field excavation. Sign not flattened. Remote native10m DEM blended over90m, tile edge70m transition. Raw DEM and all stage03/04 files preserved. Not a measured engineering grading plan.','source_resolution_not_improved_by_resampling':True});return records
def build_context(root=ROOT):
 cards=[read(root,'data/processed/stage06/cards/'+p['id']+'.json') for p in read(root,'config/stage06.json')['landmarks']];bidx=read(root,'data/processed/stage05/mesh_index.json');ridx=read(root,'data/processed/stage04/mesh_index.json');tidx=read(root,'data/processed/stage06/ground_index.json');replace={p['i'] for a in cards for p in a['replaces']};roles={'overview_far','downtown_road','bridge_road','tunnel_road','profiled_priority_road','rail_corridor','inferred_retaining_bank','downtown_sidewalk','downtown_curb','airport_surface','airport_apron'};contexts=[]
 for a in cards:
  ident=a['id'];center=np.array(a['origin_city_m']);theta=a['rotation_z_radians'];R=np.array([[math.cos(theta),math.sin(theta),0],[-math.sin(theta),math.cos(theta),0],[0,0,1]]);radius=650 if a['height_m']>100 else 430;meshes=[];counts=collections.Counter()
  def transform(v,origin):return (v+np.array(origin)-center)@R.T
  def add(rec,arrays,category,materials):
   nonlocal meshes
   world=arrays['v'].astype(float)+np.array(rec['origin_m']);fc=world[arrays['f']].mean(axis=1);mask=np.linalg.norm(fc[:,:2]-center[:2],axis=1)<radius
   if category=='buildings':mask &= ~np.isin(arrays['fid'],list(replace))
   if not mask.any():return
   ar=compact(transform(arrays['v'],rec['origin_m']),arrays['f'][mask],arrays['m'][mask],arrays['fid'][mask] if 'fid' in arrays else None);file=save(root,'data/processed/stage06/contexts/'+ident+'/'+category+'_'+str(len(meshes))+'.npz',ar);meshes.append({'id':ident+'_context_'+str(len(meshes)),'file':file,'category':category,'materials':materials,'source_file':rec['file'],'triangles':len(ar['f']),'sha256':digest(root/file)});counts[category]+=len(ar['f'])
  for rec in bidx['meshes']:
   if rec['lod']!=2:continue
   lo,hi=np.array(rec['bounds_m']);nearest=np.maximum(lo[:2]-center[:2],np.maximum(center[:2]-hi[:2],0))
   if np.linalg.norm(nearest)>radius:continue
   with np.load(root/rec['file']) as d:add(rec,{k:d[k] for k in d.files},'buildings',bidx['materials'])
  for rec in ridx['meshes']:
   if rec['role'] not in roles:continue
   origin=np.array(rec['origin_m']);q=np.maximum(origin[:2]-center[:2],np.maximum(center[:2]-(origin[:2]+1000),0))
   if np.linalg.norm(q)>radius:continue
   with np.load(root/rec['file']) as d:add(rec,{k:d[k] for k in d.files},'roads',ridx['materials'])
  variants={tuple(t['ij']):t for t in tidx['tiles']};g=Ground(root)
  for ij,t in g.tiles.items():
   q=np.maximum(np.array(ij)*1000-center[:2],np.maximum(center[:2]-(np.array(ij)*1000+1000),0))
   if np.linalg.norm(q)>radius:continue
   if ij in variants:
    rec=variants[ij];rec=rec|{'origin_m':rec['origin_city_m']}
    with np.load(root/rec['file']) as d:arrays={k:d[k] for k in d.files}
   else:
    v,f,_,_=g.load(ij);rec={'file':t['file'],'origin_m':[ij[0]*1000,ij[1]*1000,0]};lod=g.active[t['id']];variant=root/'data/processed/stage04/ground'/(t['id']+'.npz')
    with np.load(variant if variant.exists() else root/t['file']) as d:mi=d['m'+str(lod)]
    arrays={'v':v,'f':f,'m':mi}
   add(rec,arrays,'terrain',tidx['materials'])
  contexts.append({'id':ident,'radius_m':radius,'origin_city_m':center.tolist(),'rotation_z_radians':theta,'triangles_by_category':dict(counts),'meshes':meshes,'all_selected_landmark_proxies_excluded':sorted(replace),'limitations':'source roofline neighbors and inherited traffic approximations; clipped circular inspection neighborhood, not runtime loading'});print('TRUE_NEIGHBORHOOD_EXTRACTED',ident,dict(counts),flush=True)
 write_json(root/'data/processed/stage06/context_index.json',{'contexts':contexts,'same_geographic_transform_for_landmark_and_neighbors':True})
if __name__=='__main__':terrain();build_context()
