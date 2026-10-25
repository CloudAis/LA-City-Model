"""Geographic base plinth and Blender jobs, with measured visible geometry budgets."""
import json
import math
import numpy as np
import shapely
from shapely.geometry import box
from stage03_common import references,polygon_parts,local_features
from stage02_io import write_json,digest


def prepare_normals(root,quality,surface):
    """Source-gradient shading normals use one world-coordinate rule across tiles/LODs."""
    p=root/f'data/processed/stage03/{quality}/tile_index.json';index=json.loads(p.read_text());fallback=0
    for tile in index['tiles']:
        with np.load(root/tile['file']) as d:arrays={k:d[k] for k in d.files}
        dx,dy,_=tile['blender_object_translation_m']
        for lod in range(3):
            v=arrays[f'v{lod}'];x=v[:,0].astype(float)+dx;y=v[:,1].astype(float)+dy
            gx=(surface(x+1,y)-surface(x-1,y))*.5;gy=(surface(x,y+1)-surface(x,y-1))*.5
            normal=np.column_stack([-gx,-gy,np.ones(len(v))]);bad=~np.isfinite(normal).all(axis=1);fallback+=int(bad.sum());normal[bad]=[0,0,1]
            normal/=np.linalg.norm(normal,axis=1)[:,None];arrays[f'n{lod}']=normal.astype(np.float32)
        np.savez_compressed(root/tile['file'],**arrays);tile['sha256']=digest(root/tile['file'])
    write_json(p,index);write_json(root/f'work/reports/stage03/normals_{quality}.json',{'status':'generated_from_common_DEM_gradient',
        'step_m':1,'fallback_up_normals':fallback,'basis':'same sampled height function at worldXY±1m for every tile and LOD; smoothing affects lighting only, not vertex positions or claimed data resolution',
        'original_terrain_vertex_positions_changed':False})
    print('WORLD_CONSISTENT_NORMALS_GENERATED',len(index['tiles']),flush=True)


def foundation(root,surface):
    cfg=surface.cfg;bottom=cfg['foundation']['bottom_z_m'];vertices=[];faces=[]
    for p in polygon_parts(surface.city):
        for ring in [p.exterior,*p.interiors]:
            source=np.asarray(ring.coords);xy=[]
            for a,b in zip(source[:-1],source[1:]):
                for t in np.arange(max(1,math.ceil(np.linalg.norm(b-a)/100)))/max(1,math.ceil(np.linalg.norm(b-a)/100)):xy.append(a+(b-a)*t)
            xy=np.array(xy);z=surface(xy[:,0],xy[:,1]);marine=shapely.covers(surface.marine,shapely.points(xy));z=np.where(marine,cfg['vertical']['ocean_reference_z_m'],z)
            if not np.isfinite(z).all():raise ValueError('Cannot invent missing ground for foundation upper edge')
            start=len(vertices);n=len(xy);vertices+=np.column_stack([xy,z]).tolist()+np.column_stack([xy,np.full(n,bottom)]).tolist()
            for i in range(n):
                j=(i+1)%n;faces.extend([(start+i,start+j,start+n+j),(start+i,start+n+j,start+n+i)])
        for t in shapely.constrained_delaunay_triangles(p).geoms:
            points=np.asarray(t.exterior.coords)[:3];start=len(vertices);vertices.extend(np.column_stack([points,np.full(3,bottom)]).tolist());faces.append((start+2,start+1,start))
    file=root/'data/processed/stage03/foundation.npz';np.savez_compressed(file,v=np.asarray(vertices,dtype=np.float32),f=np.asarray(faces,dtype=np.int32))
    record={'file':str(file.relative_to(root)),'sha256':digest(file),'vertices':len(vertices),'triangles':len(faces),
        'data_class':'artistic_synthetic','bottom_z_m':bottom,'meaning':'Display plinth follows administrative footprint, not real geology, bathymetry or a cliff at the city limit',
        'upper_edge':'original DEM on land, explicit ocean design level on marine boundary; no terrain height scaling'}
    write_json(root/'work/reports/stage03/foundation.json',record);return record


def job(root,region,quality,index,water,base):
    cfg,o,city,refs=references(root);project=json.loads(json.dumps(__import__('yaml').safe_load((root/'config/project.yaml').read_text())))
    if region=='calibration':region='city'
    window=city if region=='city' else refs[region]
    tiles=[t for t in index['tiles'] if window.intersects(box(t['blender_object_translation_m'][0],t['blender_object_translation_m'][1],t['blender_object_translation_m'][0]+cfg['tile_size_m'],t['blender_object_translation_m'][1]+cfg['tile_size_m']))]
    water=[p for p in water if p['tile_id'] in {t['id'] for t in tiles}]
    water_tri=sum(p['triangle_count'] for p in water);base_tri=base['triangles'] if region=='city' else 0
    cap=project['quality'][quality]['visible_triangles_max'];active={t['id']:0 for t in tiles};tri=sum(t['available_lods'][0]['triangles'] for t in tiles)+water_tri+base_tri
    # Static selection for this checkpoint. Runtime distance switching is a later stage.
    for t in sorted(tiles,key=lambda t:math.hypot(t['blender_object_translation_m'][0]+500,t['blender_object_translation_m'][1]+500),reverse=True):
        if tri<=cap:break
        if min(t['active_sampling_steps_m'])<cfg['quality'][quality]['city_step_m']:continue
        saving=t['available_lods'][0]['triangles']-t['available_lods'][1]['triangles']
        if saving>0:active[t['id']]=1;tri-=saving
    if tri>cap:raise ValueError(f'Static scene budget cannot be met without discarding priority detail: {tri}>{cap}')
    key=f'stage03_{region}_{quality}';folder=root/f'work/previews/stage03/{key}';folder.mkdir(parents=True,exist_ok=True)
    coast=[]
    for f,g in local_features(root,cfg['water']['coastline_source']):
        parts=list(g.geoms) if hasattr(g,'geoms') else [g]
        for line in parts:
            xy=np.asarray(line.coords)[:,:2];z=np.full(len(xy),cfg['vertical']['ocean_reference_z_m']);coast.append(np.column_stack([xy,z]).tolist())
    result={'root':str(root),'region':region,'quality':quality,'config':cfg,'tiles':tiles,'active_lods':active,'water_pieces':water,
        'foundation':base if region=='city' else None,'control_points_file':'data/processed/stage03/control_points.json',
        'coordinate_system_file':'data/processed/stage03/coordinate_system.json','coastline_reference_lines':coast,
        'blend_path':str(root/f'scenes/{key}.blend'),'preview_directory':str(folder),'check_path':str(root/f'work/reports/stage03/{key}_blender.json'),
        'origin_utm_m':o.tolist(),'bounds_local_m':list(window.bounds),'expected_active_triangles':tri,'visible_triangle_cap':cap,
        'static_lod_selection':'manual build-time budget choice; all nine mixed-LOD neighbor combinations verified, not a runtime viewer',
        'build_version':index['build_version']}
    write_json(root/f'work/reports/stage03/{key}_job.json',result);return result
