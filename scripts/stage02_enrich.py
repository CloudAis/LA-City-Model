"""Actual building archive + observed DEM normalization. No invented floors or elevations."""
import collections
import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np
import pyogrio
import pyogrio.raw
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
from pyproj import Transformer
import shapely
from shapely.geometry import shape,mapping
from shapely.ops import transform,unary_union
from shapely.strtree import STRtree

from stage02_io import write_json,digest


def read_refs(root):
    t=Transformer.from_crs(4326,32611,always_xy=True)
    refs={f['properties']['id']:transform(t.transform,shape(f['geometry'])) for f in json.loads((root/'data/processed/scopes.geojson').read_text())['features']}
    city=transform(t.transform,shape(json.loads((root/'data/processed/stage02/city_boundary_2025.geojson').read_text())['features'][0]['geometry']))
    return refs,city,json.loads((root/'data/processed/origin.json').read_text())['origin_utm_m']


def terrain(root):
    refs,city,origin=read_refs(root);out=root/'data/processed/stage02';nodata=-9999.
    sources=json.loads((root/'config/stage02_dem_sources.json').read_text())
    results={}
    for key,geometry,res,files in [('downtown_1m',refs['downtown'],1,[root/sources['downtown_1m_file']]),
                                  ('city_10m',city,10,[root/'data/raw/stage02/dem'/('usgs_10m_'+tile+'.tif') for tile in ['n34w119','n35w119']])]:
        bounds=geometry.bounds;width=math.ceil((bounds[2]-bounds[0])/res);height=math.ceil((bounds[3]-bounds[1])/res)
        grid=from_origin(bounds[0],bounds[3],res,res);data=np.full((height,width),nodata,dtype='float32')
        for path in files:
            with rasterio.open(path) as src:
                reproject(rasterio.band(src,1),data,src_transform=src.transform,src_crs=src.crs,
                          src_nodata=src.nodata,dst_transform=grid,dst_crs=32611,dst_nodata=nodata,
                          resampling=Resampling.bilinear,init_dest_nodata=False,num_threads=4)
        path=out/(key+'_dem_navd88_m.tif')
        with rasterio.open(path,'w',driver='GTiff',width=width,height=height,count=1,dtype='float32',
                           crs=32611,transform=grid,nodata=nodata,compress='deflate',tiled=True) as d:
            d.write(data,1);d.update_tags(vertical_datum='NAVD88',vertical_unit='meter',horizontal_unit='meter',
                data_class='processed_observed',resampling='bilinear',source_files=json.dumps([str(p.relative_to(root)) for p in files]))
        from rasterio.features import geometry_mask
        mask=geometry_mask([mapping(geometry)],data.shape,grid,invert=True)
        valid=mask & np.isfinite(data) & (data!=nodata)
        results[key]={'file':str(path.relative_to(root)),'resolution_m':res,'shape':[height,width],
            'valid_fraction_within_scope':float(valid.sum()/mask.sum()),'minimum_m':float(data[valid].min()),
            'maximum_m':float(data[valid].max()),'horizontal_crs':'EPSG:32611','vertical_datum':'NAVD88',
            'height_unit':'m','source_files':[str(p.relative_to(root)) for p in files],
            'acquisition_period':'2023-01-08/2024-01-07' if res==1 else 'mixed_source_acquisition_dates_unknown; not 2025 merely because published in 2025'}
        print('OBSERVED_DEM_NORMALIZED',key,results[key]['valid_fraction_within_scope'],flush=True)
    write_json(root/'work/reports/stage02/terrain.json',results)
    return results


def buildings(root):
    refs,city,origin=read_refs(root);out=root/'data/processed/stage02';gdb=next((root/'work/cache/lariac6').rglob('*.gdb'))
    info=pyogrio.read_info(gdb,layer='LARIAC6_BUILDINGS_2020')
    native=Transformer.from_crs(32611,info['crs'],always_xy=True);to_metric=Transformer.from_crs(info['crs'],32611,always_xy=True)
    to_wgs=Transformer.from_crs(32611,4326,always_xy=True)
    city_native=transform(native.transform,city);shapely.prepare(city_native)
    cols=['CODE','BLD_ID','HEIGHT','ELEV','SOURCE','DATE_','STATUS','OLD_BLD_ID']
    meta,fids,wkb,arrays=pyogrio.raw.read(gdb,layer='LARIAC6_BUILDINGS_2020',columns=cols,bbox=city_native.bounds,return_fids=True,force_2d=True)
    attrs=dict(zip(meta['fields'],arrays));geoms=shapely.from_wkb(wkb);del wkb
    selected=shapely.intersects(city_native,geoms);indices=np.flatnonzero(selected)
    print('BUILDINGS_NATIVE_SAMPLE_AND_SCOPE',{'county_records':info['features'],'bbox_records':len(geoms),'city_intersecting':len(indices),'native_crs':info['crs']},flush=True)
    invalid=~shapely.is_valid(geoms[indices]);repair_count=int(invalid.sum())
    if repair_count:geoms[indices[invalid]]=shapely.make_valid(geoms[indices[invalid]])
    geoms=shapely.transform(geoms[indices],to_metric.transform,interleaved=False);fids=fids[indices]
    attrs={k:v[indices] for k,v in attrs.items()};del arrays,indices,selected
    codes=collections.Counter(str(x) for x in attrs['CODE']);courts=[g for g,c in zip(geoms,attrs['CODE']) if c=='Courtyard']
    ctree=STRtree(courts);dt=[];seen=set();stats=collections.Counter();epochs=collections.Counter();matches=[]
    ground_ds=rasterio.open(out/'city_10m_dem_navd88_m.tif');ground=ground_ds.read(1);ground_grid=ground_ds.transform
    residuals=[];invalid_heights=[];source_counts=collections.Counter()
    corrections=(out/'temporal_corrections.csv').open('w',newline='');cw=csv.writer(corrections)
    cw.writerow(['feature_id','old_building_id','source_status','source_observation_year','event_interval','interpretation'])
    sample_old_path=next(iter(sorted((root/'data/raw/stage02/network').glob('*/la_city_buildings/page_00000000.json'))),None)
    old_ids={f['attributes'].get('BLD_ID'):f['attributes'] for f in json.loads(sample_old_path.read_text())['features']} if sample_old_path else {}
    with gzip.open(out/'buildings.geojsonl.gz','wt',encoding='utf-8',compresslevel=5) as stream:
        for i,(g,code) in enumerate(zip(geoms,attrs['CODE'])):
            if code=='Courtyard':continue
            if g.is_empty or g.area<.01:stats['empty_or_tiny_removed']+=1;continue
            for j in ctree.query(g,predicate='intersects'):
                if g.intersection(courts[j]).area>.01:g=g.difference(courts[j]);stats['courtyards_subtracted']+=1
            if g.is_empty:stats['courtyard_only_removed']+=1;continue
            if not g.is_valid:g=shapely.make_valid(g);stats['post_difference_repaired']+=1
            if g.geom_type not in ['Polygon','MultiPolygon']:stats['non_polygon_quarantined']+=1;continue
            bid=attrs['BLD_ID'][i];uid='lariac6:'+str(bid or ('fid_'+str(fids[i])))
            if uid in seen:uid+=':fid_'+str(fids[i]);stats['repeated_building_id_disambiguated']+=1
            seen.add(uid);point=g.representative_point();regions=['city']
            if g.intersects(refs['downtown']):regions.append('downtown')
            for name in ['historic_core','civic_center']:
                if g.intersects(refs[name]):regions.append(name)
            year=attrs['DATE_'][i];year=int(year) if year and str(year).isdigit() else None;epochs[str(year)]+=1
            raw_height=float(attrs['HEIGHT'][i]);raw_elev=float(attrs['ELEV'][i])
            raw_height=raw_height if math.isfinite(raw_height) else None;raw_elev=raw_elev if math.isfinite(raw_elev) else None
            candidate=raw_height*(1200/3937) if raw_height is not None else None
            if candidate is None:stats['raw_height_missing']+=1
            if candidate is not None and not (0<=candidate<=1000):
                invalid_heights.append({'id':uid,'raw_HEIGHT':raw_height,'candidate_m':candidate});candidate=None;stats['height_anomalies']+=1
            rr,cc=rasterio.transform.rowcol(ground_grid,point.x,point.y)
            z=float(ground[rr,cc]) if 0<=rr<ground.shape[0] and 0<=cc<ground.shape[1] else ground_ds.nodata
            z=z if z!=ground_ds.nodata and math.isfinite(z) else None
            if z is None:stats['ground_elevation_missing']+=1
            if candidate is not None and raw_elev is not None and z is not None and 'downtown' in regions:
                residuals.append((raw_elev-raw_height)*(1200/3937)-z)
            old=attrs['OLD_BLD_ID'][i];status=attrs['STATUS'][i];source=attrs['SOURCE'][i];source_counts[str(source)]+=1
            properties={'id':uid,'feature_type':'building_roofline','source_id':'lariac6_2020_gdb','original_id':int(fids[i]),
                'building_id':bid,'old_building_id':old,'data_vintage':2020,'acquisition_year':year,
                'geometry_source':'LARIAC6 stereo roofline archive','height_source':'LARIAC6 raw HEIGHT; field meaning unresolved',
                'inferred_fields':['height_candidate_m'],'data_class':'processed_observed','evidence_class':'official_geometry_with_explicit_inferred_height_candidate',
                'confidence':{'geometry':'official_stereo_roofline_numeric_accuracy_not_established','height':'candidate_only_not_verified_field_definition'},
                'regions':regions,'tile_id':f'utm11_{math.floor((point.x-origin[0])/250)}_{math.floor((point.y-origin[1])/250)}',
                'visual_level':'closeup_detail' if any(n in regions for n in ['historic_core','civic_center']) else 'block_detail' if 'downtown' in regions else 'city_overview',
                'height_m':None,'height_candidate_m':candidate,'height_candidate_note':'HEIGHT times US survey foot; above-ground interpretation inferred, not confirmed by field dictionary',
                'roof_height_m':None,'min_height_m':None,'levels':None,'ground_elevation_m':z,'ground_elevation_source':'USGS 3DEP city 10m NAVD88',
                'source_HEIGHT':raw_height,'source_ELEV':raw_elev,'source_ELEV_vertical_datum':None,'source_status':status,'source_imagery':source}
            feature={'type':'Feature','properties':properties,'geometry':mapping(transform(to_wgs.transform,g))}
            stream.write(json.dumps(feature,separators=(',',':'),ensure_ascii=False)+'\n');stats['retained']+=1
            if 'downtown' in regions:dt.append(feature)
            if old in old_ids:matches.append({'selected_id':uid,'older_source':'la_city_building_sample_2014','older_BLD_ID':old,
                'current_source_year':year,'reason':'explicit OLD_BLD_ID link, prefer newer county 2020 archive; not duplicate geometry for modeling'})
            if status in ['New','Modified','Demolished','Deleted','Replaced']:
                cw.writerow([uid,old,status,year,'2017–2020 update cycle; exact event date unknown','source change label; not a claim of a 2026 event'])
            if stats['retained']%100000==0:print('BUILDINGS_STANDARDIZED',stats['retained'],flush=True)
    corrections.close();ground_ds.close()
    write_json(out/'downtown_buildings.geojson',{'type':'FeatureCollection','features':dt})
    write_json(out/'building_parts.geojson',{'type':'FeatureCollection','availability':'not_a_separate_part_schema_in_selected_source','features':[]})
    # Keep the explicit missing-data placeholder separate from the actual streamed full-city file.
    write_json(out/'buildings.geojson',{'type':'FeatureCollection','storage':'buildings.geojsonl.gz','feature_count':stats['retained'],
        'availability':'downloaded_and_standardized_in_streaming_format','features':[]})
    write_json(out/'cross_source_building_matches.json',{'status':'matched_by_explicit_prior_ids','matches':matches})
    write_json(out/'building_height_anomalies.json',invalid_heights)
    residual_summary={'count':len(residuals),'median_candidate_base_minus_dem_m':float(np.median(residuals)) if residuals else None,
        'p95_abs_difference_m':float(np.percentile(np.abs(residuals),95)) if residuals else None,
        'meaning':'Diagnostic supports or questions interpretation, not proof of a vertical datum or field definition.'}
    report={'county_source_record_count':info['features'],'source_crs':info['crs'],'source_coordinate_unit':'US survey foot',
        'input_invalid_geometry_repaired':repair_count,'source_code_counts':dict(codes),**dict(stats),
        'downtown_buildings':len(dt),'year_counts':dict(epochs),'source_counts':dict(source_counts),
        'raw_height_missing_rate':stats['raw_height_missing']/max(1,stats['retained']),
        'verified_height_missing_rate':1.0,'height_semantics_status':'field dictionary not found; raw values and inferred candidate retained separately',
        'ground_elevation_missing_rate':stats['ground_elevation_missing']/max(1,stats['retained']),
        'height_candidate_diagnostic':residual_summary,'old_new_id_matches_in_sample':len(matches)}
    write_json(root/'work/reports/stage02/buildings.json',report)
    print('BUILDINGS_CITY_STANDARDIZED',json.dumps(report),flush=True)
    return report
