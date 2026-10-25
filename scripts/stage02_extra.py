"""Normalize actual official landmarks, park trees and categorical cover rasters."""
import datetime
import json
import math
import shutil
import re
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import reproject,Resampling
from rasterio.transform import from_origin
from pyproj import Transformer
from shapely.geometry import Polygon,MultiPolygon,Point,LineString,MultiLineString,shape,mapping
from shapely.ops import transform,unary_union
from shapely import make_valid
from stage02_enrich import read_refs
from stage02_io import write_json


def esri_geometry(g):
    if 'x' in g:return Point(g['x'],g['y'])
    if 'paths' in g:return MultiLineString(g['paths'])
    rings=g.get('rings',[]);outer=[];holes=[]
    for coords in rings:
        if len(coords)<4:continue
        p=Polygon([(v[0],v[1]) for v in coords])
        (holes if p.exterior.is_ccw else outer).append(p)
    if not outer and holes:
        largest=max(holes,key=lambda p:p.area);outer=[largest];holes.remove(largest)
    result=[]
    for p in outer:
        contained=[h for h in holes if p.covers(h.representative_point())]
        assigned=[h for h in contained if not any(o!=p and o.area<p.area and o.covers(h.representative_point()) for o in outer)]
        result.append(Polygon(p.exterior.coords,[h.exterior.coords for h in assigned]))
    return make_valid(unary_union(result))


def official(root):
    refs,city,origin=read_refs(root);out=root/'data/processed/stage02';tx=Transformer.from_crs(4326,32611,always_xy=True);inv=Transformer.from_crs(32611,4326,always_xy=True)
    result={};outside=[];research=[];independent=[]
    for name,relative in [('official_hcm','landmarks/hcm'),('park_trees','official/city_trees_downtown'),('municipal_boundary','official/city_boundary')]:
        folder=root/'data/raw/stage02'/relative
        rows=[];proof=json.loads((folder/'completeness.json').read_text())
        for page in sorted(folder.glob('page_*.json')):rows+=json.loads(page.read_text()).get('features',[])
        # Split-page parent responses can be incomplete. Select exact ID set once.
        unique={f['attributes'][proof['object_id_field']]:f for f in rows};rows=list(unique.values())
        if len(rows)!=proof['server_count']:raise ValueError('Official feature count mismatch')
        normalized=[]
        for f in rows:
            a=f['attributes'];g0=esri_geometry(f['geometry']);g=transform(tx.transform,g0)
            if g.is_empty:continue
            oid=a[proof['object_id_field']];regions=['city'] if city.intersects(g) else ['outside_city_reference']
            if g.intersects(refs['downtown']):regions.append('downtown')
            p=g.representative_point();props={'id':name+':'+str(oid),'source_id':name,'original_id':oid,
                'data_vintage':None,'acquisition_date':a.get('GPS_Date') if name=='park_trees' else None,
                'geometry_source':name,'height_source':None,'inferred_fields':[],
                'data_class':'processed_observed','evidence_class':'official_data','regions':regions,
                'tile_id':f'utm11_{math.floor((p.x-origin[0])/250)}_{math.floor((p.y-origin[1])/250)}',
                'visual_level':'landmark_detail' if name=='official_hcm' else 'block_detail',
                'confidence':{'geometry':'official_service_numeric_accuracy_unknown','height':'unknown'},
                'raw_attributes':a,'ground_elevation_m':None}
            if name=='official_hcm':
                props.update(feature_type='protected_landmark_reference',name=a.get('NAME'),monument_number=a.get('MNT_NUM'),
                    designation_date_utc=datetime.datetime.fromtimestamp(a['DATE_ACTIVE']/1000,datetime.timezone.utc).date().isoformat() if a.get('DATE_ACTIVE') is not None else None,
                    designation_is_not_construction_date=True)
                research.append({'id':props['id'],'official_name':a.get('NAME'),'monument_number':a.get('MNT_NUM'),
                    'address':a.get('LOCATION'),'location_lon_lat':list(g0.representative_point().coords)[0],
                    'source':'LA Department of City Planning Historic Cultural Monuments',
                    'research_entry':'https://www.arcgis.com/home/item.html?id=72ca744a64ac456cabb1056441616e7b',
                    'planning_entry_from_official_homepage':'https://planning.lacity.gov/preservation-design/historic-landmark-programs',
                    'appearance_photo_license':'not_acquired_or_verified; no images redistributed'})
                if any(s in (a.get('NAME') or '').lower() for s in ['griffith observatory','hollywood sign','watts towers','los angeles memorial coliseum']):
                    region=g.buffer(250)
                    independent.append({'type':'Feature','properties':{'id':'landmark_region_'+str(a.get('MNT_NUM')),'source_landmark_id':props['id'],'name':a['NAME'],
                        'role':'independent_detail_work_window','derivation':'250m metric buffer around official feature; actual location preserved'},'geometry':mapping(transform(inv.transform,region))})
            elif name=='park_trees':
                text=a.get('TREE_HEIGH') or '';m=re.search(r'(\d+)\s*-\s*(\d+)\s*ft',text,re.I)
                interval=[float(m[1])*.3048,float(m[2])*.3048] if m else None
                props.update(feature_type='tree_inventory_point',name=a.get('X_COMMONNA'),species=a.get('Botanical_Name'),
                    tree_height_m=None,tree_height_raw=text,tree_height_interval_m=interval,
                    tree_height_unit='ft explicitly in source range text' if m else None,
                    height_semantics='reported interval only; do not invent exact height or current growth',
                    survey_date_raw=a.get('GPS_Date'),coverage='parks inventory within queried Downtown envelope; not all street trees')
                if a.get('GPS_Date') is not None:
                    props['acquisition_date']=datetime.datetime.fromtimestamp(a['GPS_Date']/1000,datetime.timezone.utc).date().isoformat()
            else:props.update(feature_type='administrative_boundary',name='City GIS published Los Angeles boundary',reference_date=None)
            item={'type':'Feature','properties':props,'geometry':mapping(transform(inv.transform,g))}
            if name=='official_hcm' and 'outside_city_reference' in regions:outside.append(item)
            normalized.append(item)
        write_json(out/(name+'.geojson'),{'type':'FeatureCollection','features':normalized})
        result[name]={'downloaded_count':proof['downloaded_count'],'standardized_count':len(normalized),'validity_rate':sum(shape(f['geometry']).is_valid for f in normalized)/len(normalized) if normalized else None}
    write_json(out/'trees.geojson',json.loads((out/'park_trees.geojson').read_text()))
    write_json(out/'landmark_research_index.json',research)
    write_json(out/'independent_landmark_regions.geojson',{'type':'FeatureCollection','features':independent})
    write_json(out/'outside_city_landmark_references.geojson',{'type':'FeatureCollection','features':outside})
    municipal=unary_union([transform(tx.transform,shape(f['geometry'])) for f in json.loads((out/'municipal_boundary.geojson').read_text())['features']])
    result['administrative_comparison']={'census_2025_area_m2':city.area,'city_gis_area_m2':municipal.area,
        'symmetric_difference_m2':city.symmetric_difference(municipal).area,
        'interpretation':'Independent official sources compared; City GIS capture/reference date unknown. No claim of 2026 annexation or cadastral precision.'}
    write_json(root/'work/reports/stage02/official_layers.json',result)
    return result


def landcover(root):
    refs,city,origin=read_refs(root);out=root/'data/processed/stage02';res=30;bounds=city.bounds
    w=math.ceil((bounds[2]-bounds[0])/res);h=math.ceil((bounds[3]-bounds[1])/res);grid=from_origin(bounds[0],bounds[3],res,res)
    values=np.zeros((h,w),dtype='uint8');source=root/'data/raw/stage02/landcover/nlcd2021_city_30m.tif'
    with rasterio.open(source) as src:
        if src.count!=1 or src.dtypes[0]!='uint8':raise ValueError('NLCD is not categorical single-band bytes')
        reproject(rasterio.band(src,1),values,src_transform=src.transform,src_crs=src.crs,src_nodata=0,
            dst_transform=grid,dst_crs=32611,dst_nodata=0,resampling=Resampling.nearest,num_threads=4)
    allowed={0,11,12,21,22,23,24,31,41,42,43,51,52,71,72,73,74,81,82,90,95}
    if not set(np.unique(values)).issubset(allowed):raise ValueError('Unexpected NLCD category; reject rendered RGB/continuous raster')
    with rasterio.open(out/'landcover_nlcd2021_30m.tif','w',driver='GTiff',height=h,width=w,count=1,
        dtype='uint8',crs=32611,transform=grid,nodata=0,compress='deflate',tiled=True) as d:
        d.write(values,1);d.update_tags(data_class='processed_observed',reference_year='2021',resampling='nearest',vertical_datum='not_applicable')
    from rasterio.features import geometry_mask
    mask=geometry_mask([mapping(city)],values.shape,grid,invert=True)
    codes,counts=np.unique(values[mask],return_counts=True)
    canopy=root/'data/raw/stage02/canopy/downtown_canopy_2023_1m.tif'
    with rasterio.open(canopy) as src:
        ca=src.read(1);profile=src.profile
        if not set(np.unique(ca)).issubset({0,1}):raise ValueError('Unexpected canopy classes')
        with rasterio.open(out/'downtown_canopy_2023_1m.tif','w',**profile) as d:
            d.write(ca,1);d.update_tags(data_class='processed_observed',acquisition='winter 2023',
                class_1='source-selected canopy',class_0='not_selected_or_unclassified; not proof of tree absence',
                quality_warning='source description equates 3.28084 meters with 10 feet; inconsistent. Mask retained as delivered; not authoritative tree-height measurement.')
    result={'nlcd_reference_year':2021,'nlcd_resolution_m':30,'nlcd_classes_inside_city':dict(zip(map(str,codes),map(int,counts))),
        'nlcd_valid_fraction_inside_city':float(np.count_nonzero(values[mask])/mask.sum()),
        'canopy_reference_year':2023,'canopy_resolution_m':1,'canopy_present_pixel_fraction':float((ca==1).mean()),
        'canopy_is_tree_inventory':False,'canopy_source_unit_discrepancy':'3.28084 m != 10 ft; correct 10 international feet is 3.048 m; do not silently correct delivered classifier',
        'canopy_class0_interpretation':'not selected or unclassified; not definitive absence','canopy_coverage_scope':'Downtown only'}
    write_json(root/'work/reports/stage02/landcover_canopy.json',result)
    return result
