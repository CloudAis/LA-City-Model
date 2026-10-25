"""Real hydrographic masks; water levels and current flow extent are not surveyed here."""
import collections
import json
import math
import numpy as np
import shapely
from shapely.geometry import box,Point
from shapely.strtree import STRtree
from stage03_common import references,local_features,polygon_parts,to_geographic
from stage02_io import write_json,digest
from stage03_terrain import boundary_edges,tile_id


def rules(root,surface):
    cfg=surface.cfg;rows=[]
    for f,g in local_features(root,cfg['water']['polygon_source']):
        p=f['properties'];code=p['raw_attributes']['MTFCC'];marine=code in ['H2051','H2053'];river=code in ['H3010','H3013','H3020']
        coords=shapely.get_coordinates(g.boundary);coords=coords[np.linspace(0,len(coords)-1,min(len(coords),256)).astype(int)]
        zz=surface(coords[:,0],coords[:,1]);zz=zz[np.isfinite(zz)]
        rp=g.representative_point();level=float(np.median(zz)) if len(zz) else None;spread=float(np.percentile(zz,90)-np.percentile(zz,10)) if len(zz) else None
        mode='project_ocean_reference_plane' if marine else 'DEM_conforming_hydrographic_reference' if river or level is None or spread>cfg['water']['maximum_level_fit_spread_m'] else 'DEM_estimated_lake_plane'
        if marine:level=cfg['vertical']['ocean_reference_z_m']
        rows.append({'feature':f,'geometry':g,'rule':{'id':p['id'],'name':p.get('name'),'source_mtfcc':code,
            'canonical_owner_tile_id':tile_id(math.floor(rp.x/cfg['tile_size_m']),math.floor(rp.y/cfg['tile_size_m'])),
            'water_class':'ocean' if marine else 'river_reference' if river else 'lake_reservoir_reference',
            'surface_mode':mode,'surface_height_m':level if mode!='DEM_conforming_hydrographic_reference' else None,
            'level_source':'display level 0 on NAVD88 axis; no measured tide or tidal-datum transform' if marine else 'DEM boundary samples; actual water level unmeasured',
            'vertical_datum_of_coordinate_axis':'NAVD88','shore_sample_count':len(zz),'shore_z_p10_p50_p90_m':np.percentile(zz,[10,50,90]).tolist() if len(zz) else None,
            'height_estimation_class':'inferred' if not marine else 'artistic_synthetic_display_height',
            'plan_geometry_class':'processed_observed','actual_wetted_extent_or_flow_observed':False,
            'warning':'Census hydrographic polygon is a dated geographic extent, not instantaneous flow. DEM conforming mask represents hydrography on ground, not a measured hydraulic surface.'}})
    return rows


def barycentric_z(xy,triangle):
    a,b,c=triangle;v0=b[:2]-a[:2];v1=c[:2]-a[:2];d=xy-a[:2];den=v0[0]*v1[1]-v1[0]*v0[1]
    u=(d[:,0]*v1[1]-v1[0]*d[:,1])/den;v=(v0[0]*d[:,1]-d[:,0]*v0[1])/den
    return a[2]+u*(b[2]-a[2])+v*(c[2]-a[2])


def build(root,quality,index,surface):
    cfg=surface.cfg;parents=rules(root,surface);geoms=[r['geometry'] for r in parents];tree=STRtree(geoms);out=root/f'data/processed/stage03/{quality}/water';out.mkdir(parents=True,exist_ok=True)
    pieces=[];contacts=[];counts=collections.Counter();triangles=0;edge_records={};size=cfg['tile_size_m'];precision_faces_removed=0
    for ti,tile in enumerate(index['tiles']):
        x0,y0,_=tile['blender_object_translation_m'];extent=box(x0,y0,x0+size,y0+size);ids=tree.query(extent,predicate='intersects')
        if not len(ids):continue
        with np.load(root/tile['file']) as data:v=data['v0'].astype(float);faces=data['f0']
        if not len(faces):continue
        v[:,:2]+=[x0,y0];polys=shapely.polygons(v[faces,:2]);mesh_tree=STRtree(polys)
        for ri in ids:
            body=parents[ri];g=body['geometry'].intersection(extent);rule=body['rule'];lookup={};vertices=[];tri=[];maxoffset=0
            for fi in mesh_tree.query(g,predicate='intersects'):
                part=polys[fi].intersection(g)
                for poly in polygon_parts(part):
                    if poly.area<cfg['terrain']['min_triangle_plan_area_m2']:continue
                    for t in shapely.constrained_delaunay_triangles(poly).geoms:
                        if t.area<cfg['terrain']['min_triangle_plan_area_m2']:continue
                        xy=np.asarray(t.exterior.coords)[:3];ground=barycentric_z(xy,v[faces[fi]])
                        z=ground+cfg['water']['display_offset_m'] if rule['surface_mode']=='DEM_conforming_hydrographic_reference' else np.full(3,rule['surface_height_m'])+cfg['water']['display_offset_m']
                        if rule['surface_mode']=='DEM_conforming_hydrographic_reference':maxoffset=max(maxoffset,float(np.max(abs(z-ground))))
                        ids3=[]
                        for p,h in zip(xy,z):
                            key=(round(float(p[0]-x0),6),round(float(p[1]-y0),6),round(float(h),6))
                            if key not in lookup:lookup[key]=len(vertices);vertices.append(key)
                            ids3.append(lookup[key])
                        d1=xy[1]-xy[0];d2=xy[2]-xy[0]
                        if d1[0]*d2[1]-d1[1]*d2[0]<0:ids3[1],ids3[2]=ids3[2],ids3[1]
                        tri.append(ids3)
            if not tri:continue
            uid=rule['id'].split(':')[-1]+'__'+tile['id'];file=out/(uid+'.npz');vv=np.array(vertices,dtype=np.float32);ff=np.array(tri,dtype=np.int32)
            # Overlay slivers may collapse at float32 precision. Merge exact serialized
            # vertices and quarantine zero-area/duplicate faces rather than shipping them.
            old_count=len(ff)
            _,first_vertex,inverse=np.unique(vv[:,:2],axis=0,return_index=True,return_inverse=True)
            canonical=vv[first_vertex]
            if float(np.max(abs(vv[:,2]-canonical[inverse,2])))>.001:raise ValueError('Inconsistent water height at serialized shared XY')
            vv=canonical;ff=inverse[ff].astype(np.int32)
            keep=(ff[:,0]!=ff[:,1])&(ff[:,1]!=ff[:,2])&(ff[:,0]!=ff[:,2]);ff=ff[keep]
            a=vv[ff[:,1],:2].astype(float)-vv[ff[:,0],:2];b=vv[ff[:,2],:2].astype(float)-vv[ff[:,0],:2]
            area=abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])*.5
            ff=ff[area>cfg['terrain']['min_triangle_plan_area_m2']];_,first=np.unique(np.sort(ff,axis=1),axis=0,return_index=True);ff=ff[np.sort(first)]
            precision_faces_removed+=old_count-len(ff)
            if not len(ff):continue
            assert np.isfinite(vv).all();np.savez_compressed(file,v=vv,f=ff)
            border=boundary_edges(vv,ff,size)[0]
            # Axis tolerance may identify a near-perpendicular micrometer edge at
            # the exact shore/tile intersection. It has zero length along the seam.
            edge_records[(rule['id'],*tile['ij'])]={name:a[(a[:,1]-a[:,0])>1e-5] for name,a in border.items()}
            pieces.append({'id':uid,'parent_source_id':rule['id'],'tile_id':tile['id'],'file':str(file.relative_to(root)),
                'sha256':digest(file),'object_translation_m':[x0,y0,0],'water_class':rule['water_class'],'surface_mode':rule['surface_mode'],
                'triangle_count':len(ff),'height_source':rule['level_source'],'data_class':rule['height_estimation_class'],
                'display_offset_m':cfg['water']['display_offset_m'],'canonical_owner_tile':rule['canonical_owner_tile_id']})
            counts[rule['surface_mode']]+=1;triangles+=len(ff)
            if rule['surface_mode']=='DEM_conforming_hydrographic_reference':contacts.append(maxoffset)
        if ti%100==0:print('WATER_TILE_REVIEW',ti,flush=True)
    write_json(root/f'data/processed/stage03/{quality}/water_index.json',{'parents':[r['rule'] for r in parents],'pieces':pieces,
        'ownership':'Canonical source ID independent of chunks; tile children cover clipped observed footprint. Shared ground or global parent plane defines every piece height.'})
    write_json(root/'data/processed/stage03/water_surfaces.geojson',{'type':'FeatureCollection','features':[{'type':'Feature','properties':r['rule'],'geometry':to_geographic(r['geometry'],surface.origin)} for r in parents]})
    # River reach records preserve every native segment. No arbitrary buffered water widths or guessed bridge decks.
    reaches=[];sections=[]
    for f,g in local_features(root,cfg['water']['centerline_source']):
        if not any(s in (f['properties'].get('name') or '') for s in ['Los Angeles Riv','Los Angeles R Chann']):continue
        distances=np.linspace(0,g.length,max(2,math.ceil(g.length/20)+1));pts=[g.interpolate(float(d)) for d in distances];x=np.array([p.x for p in pts]);y=np.array([p.y for p in pts]);z=surface(x,y)
        reaches.append({'type':'Feature','properties':{'id':f['properties']['id'],'name':f['properties'].get('name'),
            'length_m':g.length,'sampled_ground_profile_m':[[float(d),float(h) if np.isfinite(h) else None] for d,h in zip(distances,z)],
            'source':'Census 2025 native hydrographic segment; USGS NAVD88 terrain',
            'bank_material':'unverified_by_reach; not blanket natural or concrete','channel_shape':'DEM-derived ground profile only',
            'bridge_deck_geometry':'not acquired; ground DEM does not determine bridge decks',
            'current_wetted_flow_width_m':None,'flow_extent_status':'not observed; do not use centerline buffer as current flow',
            'fine_source_available':g.intersects(surface.refs['downtown']),'detail_gap':'Engineering cross sections, current flow, bank material and bridge survey needed for detailed channel assets'},'geometry':to_geographic(g,surface.origin)})
        if g.intersects(surface.refs['downtown']):
            h=g.intersection(surface.refs['downtown'])
            for d in np.arange(0,h.length,100):
                p=h.interpolate(float(d));before=h.interpolate(max(0,float(d)-5));after=h.interpolate(min(h.length,float(d)+5));v=np.array([after.x-before.x,after.y-before.y]);length=np.linalg.norm(v)
                if length==0:continue
                perpendicular=np.array([-v[1],v[0]])/length;offsets=np.arange(-80,81,1);xy=np.array([p.x,p.y])+offsets[:,None]*perpendicular;zz=surface(xy[:,0],xy[:,1])
                sections.append({'source_reach_id':f['properties']['id'],'chainage_m':float(d),'center_local_xy_m':[p.x,p.y],
                    'offsets_m':offsets.tolist(),'ground_NAVD88_m':[float(z) if np.isfinite(z) else None for z in zz],
                    'basis':'Downtown 1m DEM with documented100m border blend; terrain cross-section, not surveyed engineering section',
                    'width_meaning':'±80m investigation window, NOT assumed bank/channel/flow width','bank_material':'unknown'})
    write_json(root/'data/processed/stage03/la_river_reaches.geojson',{'type':'FeatureCollection','features':reaches})
    write_json(root/'data/processed/stage03/la_river_terrain_cross_sections.json',sections)
    seam_pairs=0;seam_max=0
    for (parent,ix,iy),border in edge_records.items():
        for name,dx,dy,opposite in [('E',1,0,'W'),('N',0,1,'S')]:
            neighbor=edge_records.get((parent,ix+dx,iy+dy))
            if neighbor is None:continue
            a,b=border[name],neighbor[opposite]
            if a.shape!=b.shape:raise ValueError('Water chunk seam segmentation mismatch')
            error=float(np.max(abs(a-b))) if a.size else 0;seam_max=max(seam_max,error);seam_pairs+=1
            if error>.001:raise ValueError('Water chunk seam position/height mismatch')
    report={'status':'passed_for_geographic_masks_with_explicit_level_and_flow_gaps','parent_count':len(parents),'tile_child_count':len(pieces),'triangles':triangles,
        'surface_mode_child_counts':dict(counts),'river_reach_count':len(reaches),'Downtown_terrain_cross_sections':len(sections),
        'water_neighbor_pair_checks':seam_pairs,'maximum_water_chunk_edge_error_m':seam_max,'serialized_zero_area_or_duplicate_faces_quarantined':precision_faces_removed,
        'maximum_conforming_surface_offset_m':max(contacts,default=None),'conforming_contact_tolerance_m':cfg['water']['display_offset_m']+.001,
        'shoreline_geometry':'actual Census polygons and original coastal line retained; no invented river width',
        'marine_datum_limit':'NAVD88-axis design height 0, not measured MSL/MHW/MLLW; no tidal datum mixing or bathymetry claim',
        'water_level_limit':'Only DEM-consistent small-spread bodies get an estimated plane; others are explicitly conforming geographic reference masks, not physical hydraulic surfaces',
        'river_bank_and_bridge_limit':'No verified reach cross sections/materials/current flow/bridge deck geometry available. Terrain channel and source reaches retained; detailed assets unimplemented pending data.'}
    write_json(root/f'work/reports/stage03/water_{quality}.json',report);print('WATER_BUILD_PASSED',json.dumps(report),flush=True);return pieces
