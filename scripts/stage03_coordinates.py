"""Explicit horizontal/vertical transforms and computational control positions."""
import json
import math
import numpy as np
from pyproj import CRS,Transformer,Proj,Geod
from pyproj.transformer import TransformerGroup
from shapely.geometry import shape,Point
from stage03_common import references,load_features
from stage02_io import write_json


def matrix(tx=0,ty=0,tz=0):
    m=np.eye(4);m[:3,3]=[tx,ty,tz];return m.tolist()


def prepare(root,sampler):
    cfg,o,city,refs=references(root);out=root/'data/processed/stage03';reports=root/'work/reports/stage03'
    wgs=Transformer.from_crs(4326,32611,always_xy=True);inv=Transformer.from_crs(32611,4326,always_xy=True);geod=Geod(ellps='WGS84');proj=Proj(32611)
    transforms=[]
    for epsg in [4326,4269,6424,26911,5070]:
        group=TransformerGroup(CRS(epsg),CRS(32611),always_xy=True,allow_ballpark=False)
        chosen=group.transformers[0]
        # Force lazy concatenated operations to resolve at the actual city center.
        source=Transformer.from_crs(32611,epsg,always_xy=True).transform(*o)
        chosen.transform(*source)
        transforms.append({'source_epsg':epsg,'target_epsg':32611,'always_xy':True,'best_available':group.best_available,
            'operation_description':chosen.description,'pipeline':chosen.definition,'reported_operation_accuracy_m':chosen.accuracy,
            'unavailable_operation_count':len(group.unavailable_operations),'source_wkt':CRS(epsg).to_wkt(),
            'source_projjson':CRS(epsg).to_json_dict(),'vertical_transformation':'none; not a 3D height transform'})
    points=[('downtown_origin',*inv.transform(*o),'frozen MappingLA projected centroid, not surveyed monument')]
    monuments=load_features(root,'data/processed/stage02/official_hcm.geojson')
    for needle in ['City Hall','Griffith Observatory','Hollywood Sign','Towers of Simon Rodia','San Pedro Municipal']:
        f=next((f for f in monuments if needle.lower() in (f['properties'].get('name') or '').lower()),None)
        if f:
            p=shape(f['geometry']).representative_point();points.append((f['properties']['id'],p.x,p.y,'official HCM position; numeric source accuracy unknown'))
    for f in load_features(root,'data/processed/stage02/facility_area.geojson'):
        if f['properties'].get('name') in ['Los Angeles International','Van Nuys Arprt']:
            p=shape(f['geometry']).representative_point();points.append((f['properties']['name'],p.x,p.y,'Census facility interior reference, not a surveyed control'))
    boundary=np.asarray(city.exterior.coords if city.geom_type=='Polygon' else max(city.geoms,key=lambda g:g.area).exterior.coords)
    for label,i in [('edge_west',np.argmin(boundary[:,0])),('edge_east',np.argmax(boundary[:,0])),('edge_north',np.argmax(boundary[:,1])),('edge_south',np.argmin(boundary[:,1]))]:
        e,n=boundary[i]+o;lon,lat=inv.transform(e,n);points.append((label,lon,lat,'derived extreme of primary Census polygon; not surveying accuracy evidence'))
    # Independent analytic UTM definition and constructed metric baselines.
    central=wgs.transform(-117,0)
    assert abs(central[0]-500000)<1e-6 and abs(central[1])<1e-6
    rows=[]
    for uid,lon,lat,source in points:
        e,n=wgs.transform(lon,lat);lo,la=inv.transform(e,n);e2,n2=wgs.transform(lo,la)
        z=float(sampler(np.array([e-o[0]]),np.array([n-o[1]]))[0]);f=proj.get_factors(lon,lat)
        lon_n,lat_n,_=geod.fwd(lon,lat,0,10);en,nn=wgs.transform(lon_n,lat_n);v=np.array([en-e,nn-n]);v/=np.linalg.norm(v)
        x,y=e-o[0],n-o[1];ix,iy=math.floor(x/cfg['tile_size_m']),math.floor(y/cfg['tile_size_m'])
        rows.append({'id':uid,'lon_lat':[lon,lat],'utm_m':[e,n],'blender_world_m':[x,y,z],
            'tile_ij':[ix,iy],'tile_local_m':[x-ix*cfg['tile_size_m'],y-iy*cfg['tile_size_m'],z],
            'roundtrip_error_m':math.hypot(e2-e,n2-n),'roundtrip_error_degrees':[lo-lon,la-lat],
            'meridian_convergence_degrees':f.meridian_convergence,'true_north_vector_in_blender_xy':v.tolist(),
            'point_scale':f.meridional_scale,'source_position':source,'source_horizontal_accuracy_m':None,
            'height_status':'sampled DEM NAVD88, not independently surveyed control elevation'})
    pairs=[]
    for row in rows[1:]:
        a=rows[0];az,_,distance=geod.inv(*a['lon_lat'],*row['lon_lat']);grid=math.dist(a['utm_m'],row['utm_m'])
        mid=((a['lon_lat'][0]+row['lon_lat'][0])/2,(a['lon_lat'][1]+row['lon_lat'][1])/2);scale=proj.get_factors(*mid).meridional_scale
        residual=grid-distance*scale
        grid_azimuth=math.degrees(math.atan2(row['utm_m'][0]-a['utm_m'][0],row['utm_m'][1]-a['utm_m'][1]))
        predicted=az-a['meridian_convergence_degrees'];bearing_error=(grid_azimuth-predicted+180)%360-180
        assert abs(bearing_error)<.2,'Bearing relationship unexpectedly inconsistent'
        assert abs(residual)<2,'UTM/geodesic cross-check unexpectedly inconsistent'
        pairs.append({'from':a['id'],'to':row['id'],'geodesic_distance_m':distance,'grid_distance_m':grid,
            'true_azimuth_degrees':az,'midpoint_projection_scale':scale,'grid_minus_scaled_geodesic_m':residual,
            'grid_azimuth_degrees':grid_azimuth,'bearing_error_after_convergence_correction_degrees':bearing_error,
            'interpretation':'Independent ellipsoidal distance comparison; midpoint scale approximate, no known surveyed baseline claimed'})
    baselines=[]
    for dx,dy in [(1000,0),(0,1000),(4000,0),(0,4000)]:
        p=inv.transform(o[0]+dx,o[1]+dy);e,n=wgs.transform(*p);err=math.hypot(e-o[0]-dx,n-o[1]-dy)
        assert err<cfg['validation']['horizontal_roundtrip_tolerance_m']
        baselines.append({'constructed_offset_m':[dx,dy],'known_grid_distance_m':math.hypot(dx,dy),'reconstruction_error_m':err,'basis':'project metric construction; not a measured ground baseline'})
    unit_checks={'10_international_feet_m':10*.3048,'10_US_survey_feet_m':10*1200/3937,'100_inches_m':100*.0254}
    assert abs(unit_checks['10_international_feet_m']-3.048)<1e-12 and abs(unit_checks['100_inches_m']-2.54)<1e-12
    config={'working_crs':CRS(32611).to_json_dict(),'working_wkt':CRS(32611).to_wkt(),
        'reason':'Los Angeles lies in UTM11N; existing WGS84 UTM origin preserved, meters and limited regional distortion, compatible with prepared DEM. Not a local survey frame.',
        'origin_utm_m':o.tolist(),'origin_lon_lat':inv.transform(*o),'axis':{'x':'UTM grid east','y':'UTM grid north','z':'up'},
        'utm_to_blender':matrix(-o[0],-o[1],0),'blender_to_utm':matrix(o[0],o[1],0),
        'vertical_datum':'NAVD88','vertical_unit':'meter','vertical_offset_m':0,'vertical_exaggeration':1,
        'origin_height_meaning':'z_offset=0 convention; original phase01 synthetic origin_height_m is NOT an observed ground altitude',
        'source_horizontal_operations':transforms,'height_mixing_policy':'No LARIAC ELEV or ellipsoidal heights. All ground Z from NAVD88 DEM; ocean 0 is explicitly a design display level, not a tidal datum transformation.',
        'triangle_coordinates':'tile local XY (0..1000m), absolute NAVD88 Z; object translation only to city-relative meters',
        'pixel_transform_files':'See dem_audit.json; GeoTIFF source affine recorded with pixel-center convention.'}
    write_json(out/'coordinate_system.json',config);write_json(out/'control_points.json',rows)
    report={'status':'passed_computational_validation','control_position_count':len(rows),'maximum_roundtrip_error_m':max(r['roundtrip_error_m'] for r in rows),
        'points':rows,'distance_and_bearing_checks':pairs,'known_constructed_baselines':baselines,'unit_checks':unit_checks,
        'analytic_reference':{'lon_lat':[-117,0],'expected_utm_m':[500000,0],'actual_utm_m':central},
        'source_data_accuracy':'unknown numeric horizontal/vertical source accuracy; these controls are reproducible reference positions, not a surveying network',
        'blender_position_check':'pending actual reopen in Blender'}
    assert len(rows)>=10
    write_json(reports/'control_points.json',report);return rows


if __name__=='__main__':
    import argparse
    from pathlib import Path
    from stage03_common import settings
    root=Path(__file__).resolve().parents[1];cfg=settings(root);origin=json.loads((root/cfg['origin_file']).read_text())['origin_utm_m']
    p=argparse.ArgumentParser(description='2D horizontal conversion; height is NAVD88 meters with no datum conversion')
    p.add_argument('--to',choices=['local','geographic'],required=True);p.add_argument('a',type=float);p.add_argument('b',type=float);p.add_argument('--height-navd88-m',type=float,default=0);args=p.parse_args()
    if args.to=='local':
        e,n=Transformer.from_crs(4326,32611,always_xy=True).transform(args.a,args.b);out={'blender_xyz_m':[e-origin[0],n-origin[1],args.height_navd88_m],'utm_en_m':[e,n]}
    else:
        lon,lat=Transformer.from_crs(32611,4326,always_xy=True).transform(args.a+origin[0],args.b+origin[1]);out={'lon_lat':[lon,lat],'NAVD88_height_m':args.height_navd88_m}
    print(json.dumps(out,ensure_ascii=False))
