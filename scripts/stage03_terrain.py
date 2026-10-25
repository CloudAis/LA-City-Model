"""Adaptive tile meshes with common boundary constraints at every baked LOD."""
import bisect
import collections
import json
import math
import time
from pathlib import Path
import numpy as np
import shapely
from shapely.geometry import box,Polygon,Point
from stage03_common import references,polygon_parts,to_geographic,local_features
from stage03_coordinates import matrix
from stage02_io import write_json,digest


def tile_id(ix,iy):return f'la_t_x{ix:+04d}_y{iy:+04d}'


def rectangles(ix,iy,size,profile,refs):
    x0,y0=ix*size,iy*size;tile=box(x0,y0,x0+size,y0+size)
    focus=box(*np.round(refs['downtown'].bounds,4));step=profile['downtown_step_m'] if tile.intersection(focus).area>1 else profile['city_step_m']
    near=[r.bounds for k,r in refs.items() if k in ['historic_core','civic_center']]
    result=[]
    for x in range(x0,x0+size,step):
        for y in range(y0,y0+size,step):
            close=step==profile['downtown_step_m'] and any(x<b[2] and x+step>b[0] and y<b[3] and y+step>b[1] for b in near)
            sub=profile['closeup_step_m'] if close else step
            river=refs.get('river_refinement')
            if river is not None and step>profile['river_step_m'] and river.intersects(box(x,y,x+step,y+step)):sub=min(sub,profile['river_step_m'])
            for xx in range(x,x+step,sub):
                for yy in range(y,y+step,sub):result.append((xx,yy,sub))
    return result


def breakpoints(cells):
    horizontal=collections.defaultdict(set);vertical=collections.defaultdict(set)
    for rects in cells.values():
        for x,y,s in rects:
            for xx,yy in [(x,y),(x+s,y),(x+s,y+s),(x,y+s)]:horizontal[yy].add(xx);vertical[xx].add(yy)
    return {k:sorted(v) for k,v in horizontal.items()},{k:sorted(v) for k,v in vertical.items()}


def constrained_mesh(rects,city,xy0,size,sampler,breaks,finest_edges=None):
    horizontal,vertical=breaks;vertices=[];lookup={};faces=[];dropped=0;eps=sampler.cfg['terrain']['min_triangle_plan_area_m2']
    def add(p):
        key=(round(float(p[0]),6),round(float(p[1]),6))
        if key not in lookup:lookup[key]=len(vertices);vertices.append(key)
        return lookup[key]
    def edge(a,b):
        if abs(a[1]-b[1])<1e-8:
            position=a[1];v=horizontal.get(round(position),[]) if abs(position-round(position))<1e-6 else []
            if finest_edges is not None and (abs(position-xy0[1])<1e-6 or abs(position-xy0[1]-size)<1e-6):v=finest_edges[0].get(round(position),v)
            lo,hi=sorted((a[0],b[0]));middle=[(x,position) for x in v[bisect.bisect_right(v,lo+1e-7):bisect.bisect_left(v,hi-1e-7)]]
            if b[0]<a[0]:middle.reverse()
        elif abs(a[0]-b[0])<1e-8:
            position=a[0];v=vertical.get(round(position),[]) if abs(position-round(position))<1e-6 else []
            if finest_edges is not None and (abs(position-xy0[0])<1e-6 or abs(position-xy0[0]-size)<1e-6):v=finest_edges[1].get(round(position),v)
            lo,hi=sorted((a[1],b[1]));middle=[(position,y) for y in v[bisect.bisect_right(v,lo+1e-7):bisect.bisect_left(v,hi-1e-7)]]
            if b[1]<a[1]:middle.reverse()
        else:middle=[]
        return [a,*middle]
    def ring(coords):
        coords=list(coords);out=[]
        for a,b in zip(coords[:-1],coords[1:]):out+=edge(a,b)
        return out
    for x,y,s in rects:
        cell=box(x,y,x+s,y+s)
        if city.covers(cell):
            corners=[(x,y),(x+s,y),(x+s,y+s),(x,y+s),(x,y)];points=ring(corners);ids=[add(p) for p in points]
            if len(ids)==4:faces.extend([(ids[0],ids[1],ids[2]),(ids[0],ids[2],ids[3])])
            else:
                center=add((x+s*.5,y+s*.5));faces.extend((center,ids[i],ids[(i+1)%len(ids)]) for i in range(len(ids)))
        elif city.intersects(cell):
            for part in polygon_parts(city.intersection(cell)):
                if part.area<eps:continue
                polygon=Polygon(ring(part.exterior.coords),[ring(r.coords) for r in part.interiors])
                for t in shapely.constrained_delaunay_triangles(polygon).geoms:
                    if t.area<eps:dropped+=1;continue
                    points=np.asarray(t.exterior.coords)[:3];a,b,c=[add(p) for p in points]
                    d1=points[1]-points[0];d2=points[2]-points[0]
                    if d1[0]*d2[1]-d1[1]*d2[0]<0:b,c=c,b
                    faces.append((a,b,c))
    xy=np.asarray(vertices,dtype=float).reshape(-1,2);tri=np.asarray(faces,dtype=np.int32).reshape(-1,3)
    if not len(tri):return np.empty((0,3),dtype=np.float32),tri,np.empty(0,dtype=np.int32),{'dropped_small_boundary_triangles':dropped,'nodata_faces_omitted':0}
    z=sampler(xy[:,0],xy[:,1]);valid=np.isfinite(z[tri]).all(axis=1);omitted=int((~valid).sum());tri=tri[valid]
    used=np.unique(tri);remap=np.full(len(xy),-1,dtype=np.int32);remap[used]=np.arange(len(used));tri=remap[tri];xy=xy[used];z=z[used]
    centers=xy[tri].mean(axis=1);materials=sampler.material_indices(centers[:,0],centers[:,1])
    v=np.column_stack([xy[:,0]-xy0[0],xy[:,1]-xy0[1],z]).astype(np.float32)
    return v,tri,materials,{'dropped_small_boundary_triangles':dropped,'nodata_faces_omitted':omitted}


def boundary_edges(v,tri,size):
    if not len(tri):return {k:np.empty((0,4)) for k in ['W','E','S','N']},np.empty((0,2),dtype=np.int32)
    e=np.sort(np.vstack([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]),axis=1);edges,count=np.unique(e,axis=0,return_counts=True)
    if (count>2).any():raise ValueError('Non-manifold terrain triangles')
    single=edges[count==1];a,b=v[single[:,0]],v[single[:,1]];out={};on_outer=np.zeros(len(single),bool)
    for name,axis,target in [('W',0,0),('E',0,size),('S',1,0),('N',1,size)]:
        mask=(abs(a[:,axis]-target)<1e-5)&(abs(b[:,axis]-target)<1e-5);on_outer|=mask;other=1-axis
        p=np.column_stack([a[mask,other],b[mask,other],a[mask,2],b[mask,2]]).astype(float)
        rev=p[:,0]>p[:,1];p[rev]=p[rev][:,[1,0,3,2]];p=p[np.lexsort((p[:,1],p[:,0]))];out[name]=p
    return out,single[~on_outer]


def build(root,quality,version,sampler):
    cfg,o,city,refs=references(root);profile=cfg['quality'][quality];size=cfg['tile_size_m'];shapely.prepare(city)
    from shapely.ops import unary_union
    refs['river_refinement']=unary_union([g for f,g in local_features(root,cfg['water']['polygon_source']) if f['properties']['raw_attributes']['MTFCC']=='H3010'])
    shapely.prepare(refs['river_refinement'])
    base=root/f'data/processed/stage03/{quality}';base.mkdir(parents=True,exist_ok=True);bounds=city.bounds;tiles={};cells={};start=time.monotonic()
    for ix in range(math.floor(bounds[0]/size),math.ceil(bounds[2]/size)):
        for iy in range(math.floor(bounds[1]/size),math.ceil(bounds[3]/size)):
            region=city.intersection(box(ix*size,iy*size,(ix+1)*size,(iy+1)*size))
            if region.area<1:continue
            tiles[(ix,iy)]={'geometry':region};cells[(ix,iy)]=rectangles(ix,iy,size,profile,refs)
    finest=breakpoints(cells)
    # Include coarse LOD perimeter corners too (e.g. 250m does not divide a 40m interior).
    for ix,iy in tiles:
        for step in cfg['terrain']['baked_lod_steps_m']:
            for y in [iy*size,(iy+1)*size]:finest[0][y]=sorted(set(finest[0].get(y,[]))|set(range(ix*size,(ix+1)*size+1,step)))
            for x in [ix*size,(ix+1)*size]:finest[1][x]=sorted(set(finest[1].get(x,[]))|set(range(iy*size,(iy+1)*size+1,step)))
    entries=[];edges={};count_tri=collections.Counter();total_material=collections.Counter();slivers=0;omitted=0
    for number,((ix,iy),tile) in enumerate(tiles.items(),1):
        uid=tile_id(ix,iy);xy0=(ix*size,iy*size);arrays={};lods=[];bounds_z=[];omitted_here=[]
        for lod,step in enumerate([None,*cfg['terrain']['baked_lod_steps_m']]):
            rects=cells[(ix,iy)] if step is None else [(x,y,step) for x in range(xy0[0],xy0[0]+size,step) for y in range(xy0[1],xy0[1]+size,step)]
            current=finest if step is None else breakpoints({(ix,iy):rects})
            v,f,m,info=constrained_mesh(rects,city,xy0,size,sampler,current,finest if step is not None else None)
            omitted_here.append(info['nodata_faces_omitted'])
            border,internal=boundary_edges(v,f,size);edges[(ix,iy,lod)]=border
            if len(internal):
                mid=(v[internal[:,0],:2].astype(float)+v[internal[:,1],:2].astype(float))*.5+xy0
                d=shapely.distance(shapely.points(mid),city.boundary);unexpected=int((d>0.002).sum())
                if unexpected:raise ValueError(f'Terrain interior unpaired edges / possible crack: {uid} LOD{lod} {unexpected}')
            arrays.update({f'v{lod}':v,f'f{lod}':f,f'm{lod}':m});count_tri[f'LOD{lod}']+=len(f);slivers+=info['dropped_small_boundary_triangles'];omitted+=info['nodata_faces_omitted']
            if len(v):bounds_z.extend([float(v[:,2].min()),float(v[:,2].max())])
            lods.append({'id':f'LOD{lod}','triangles':len(f),'vertices':len(v),'interior_step_m':step or 'adaptive',
                'shared_tile_boundary':'exact finest common sampling retained at every LOD','runtime_switching':'not implemented; geometry available'})
            if lod==0:total_material.update({sampler.classes[k]:int(n) for k,n in zip(*np.unique(m,return_counts=True))})
        path=base/(uid+'.npz');np.savez_compressed(path,**arrays)
        zmin=min(bounds_z) if bounds_z else None;zmax=max(bounds_z) if bounds_z else None
        entry={'id':uid,'ij':[ix,iy],'geographic_extent':to_geographic(box(xy0[0],xy0[1],xy0[0]+size,xy0[1]+size),o),
            'city_clip_geometry':to_geographic(tile['geometry'],o),'area_within_city_m2':tile['geometry'].area,
            'origin_utm_m':[float(o[0]+xy0[0]),float(o[1]+xy0[1]),0],
            'blender_object_translation_m':[*xy0,0],'tile_local_to_utm':matrix(o[0]+xy0[0],o[1]+xy0[1],0),
            'tile_local_to_blender':matrix(*xy0,0),'blender_to_tile_local':matrix(-xy0[0],-xy0[1],0),
            'bounds_tile_local_m':[[0,0,zmin],[size,size,zmax]],'horizontal_crs':'EPSG:32611','vertical_datum':'NAVD88',
            'height_offset_m':0,'exaggeration':1,'source_resolution_m':{'city':10,'downtown':1},
            'active_sampling_steps_m':sorted({r[2] for r in cells[(ix,iy)]}),'data_coverage':'all retained mesh vertices finite; original NoData and repairs separately archived',
            'original_nodata_faces_omitted_by_lod':omitted_here,'available_lods':lods,'build_version':version,
            'file':str(path.relative_to(root)),'sha256':digest(path),'neighbors':{}}
        for name,dx,dy in [('W',-1,0),('E',1,0),('S',0,-1),('N',0,1)]:
            if (ix+dx,iy+dy) in tiles:entry['neighbors'][name]=tile_id(ix+dx,iy+dy)
        entries.append(entry)
        if number%100==0:print('TERRAIN_TILES_WRITTEN',number,'/',len(tiles),flush=True)
    seams=[];maximum=0
    for ix,iy in tiles:
        for direction,dx,dy,other in [('E',1,0,'W'),('N',0,1,'S')]:
            if (ix+dx,iy+dy) not in tiles:continue
            baseline=edges[(ix,iy,0)][direction]
            for a_lod in range(3):
                a=edges[(ix,iy,a_lod)][direction]
                if a.shape!=baseline.shape or not np.allclose(a,baseline,atol=cfg['validation']['seam_height_tolerance_m'],rtol=0):raise ValueError('Within-tile LOD edge mismatch')
                for b_lod in range(3):
                    b=edges[(ix+dx,iy+dy,b_lod)][other]
                    if a.shape!=b.shape:raise ValueError(f'Shared edge segmentation mismatch {ix} {iy} {direction} LOD{a_lod}/{b_lod}: {a.shape} vs {b.shape}')
                    delta=float(np.max(abs(a-b))) if a.size else 0;maximum=max(maximum,delta)
                    if delta>cfg['validation']['seam_height_tolerance_m']:raise ValueError('Shared edge coordinate/Z mismatch')
            seams.append({'a':tile_id(ix,iy),'b':tile_id(ix+dx,iy+dy),'direction':direction,'shared_segments':len(baseline),'all_9_lod_combinations_passed':True})
    index={'tile_size_m':size,'quality':quality,'origin_utm_m':o.tolist(),'working_crs':'EPSG:32611','vertical_datum':'NAVD88','build_version':version,
        'cross_tile_ownership':'Terrain cell domain is half-open [xmin,xmax)×[ymin,ymax); shared edges duplicated geometrically with identical samples; triangles have no overlapping area.',
        'cross_tile_water_objects':'Source-ID canonical record; tile child pieces clipped to exact grid; parent global water-height rule used for all children.',
        'tile_count':len(entries),'tiles':entries}
    write_json(base/'tile_index.json',index);write_json(base/'tile_index.geojson',{'type':'FeatureCollection','features':[{'type':'Feature','properties':{k:e[k] for k in ['id','ij','area_within_city_m2','active_sampling_steps_m','build_version','neighbors']},'geometry':e['city_clip_geometry']} for e in entries]})
    report={'status':'passed','tile_count':len(entries),'neighbor_pair_count':len(seams),'mixed_lod_pair_checks':len(seams)*9,
        'maximum_shared_edge_coordinate_or_height_error_m':maximum,'unpaired_interior_edges':0,'nonmanifold_edges':0,
        'pairs':seams,'all_lods_share_finest_perimeter':True}
    write_json(root/f'work/reports/stage03/seams_{quality}.json',report)
    stats={'tiles':len(entries),'triangles':dict(count_tri),'active_material_triangle_counts':dict(total_material),
        'small_boundary_sliver_triangles_omitted':slivers,'nodata_faces_omitted':omitted,'build_seconds':time.monotonic()-start,
        'quality':quality,'terrain_z_exaggeration':1,'source_precision_improved_by_resampling':False}
    write_json(root/f'work/reports/stage03/terrain_{quality}.json',stats)
    write_json(root/'data/processed/stage03/height_repairs.json',[{'local_xy_m':list(k),**v,'data_class':'inferred'} for k,v in sampler.repairs.items()])
    print('TERRAIN_BUILD_PASSED',json.dumps(stats),flush=True);return index,stats
