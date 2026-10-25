"""Observed vectors only. Unknown height, elevation and road grade stay null."""
import collections
import hashlib
import io
import json
import math
import re
import zipfile
from pathlib import Path

import shapefile
from pyproj import CRS, Transformer
from shapely import make_valid, normalize
from shapely.geometry import shape, mapping, box
from shapely.ops import transform, unary_union

from stage02_io import write_json


def polygon_parts(g):
    if g.geom_type=='Polygon':return [g]
    return [p for a in getattr(g,'geoms',[]) for p in polygon_parts(a)]


def length_m(value, numeric_unit=None):
    """No field-name guessing. Bare numbers require a documented unit."""
    if value is None:return None
    text=str(value).strip().lower()
    try:
        m=re.fullmatch(r'([-+]?\d+(?:\.\d+)?)\s*(m|meters?|metres?|ft|feet|foot|us-ft|in)?',text)
        if m:
            v=float(m[1]);u=m[2] or numeric_unit
            factor={'m':1,'meter':1,'meters':1,'metre':1,'metres':1,'ft':.3048,'feet':.3048,'foot':.3048,'us-ft':1200/3937,'in':.0254}.get(u)
            return v*factor if factor is not None and math.isfinite(v) else None
        m=re.fullmatch(r'(\d+(?:\.\d+)?)\s*\x27\s*(\d+(?:\.\d+)?)?\s*\x22?',text)
        if m:return float(m[1])*.3048+float(m[2] or 0)*.0254
    except (ValueError,OverflowError):pass
    return None


def reader(path):
    z=zipfile.ZipFile(path)
    if z.testzip() is not None:raise ValueError('ZIP CRC error')
    base=next(n[:-4] for n in z.namelist() if n.endswith('.shp'))
    r=shapefile.Reader(shp=io.BytesIO(z.read(base+'.shp')),shx=io.BytesIO(z.read(base+'.shx')),dbf=io.BytesIO(z.read(base+'.dbf')))
    return r,CRS.from_wkt(z.read(base+'.prj').decode())


def clean_census(root, cfg):
    out=root/'data/processed/stage02';out.mkdir(parents=True,exist_ok=True)
    origin=json.loads((root/cfg['origin_file']).read_text())['origin_utm_m']
    original=json.loads((root/cfg['scope_file']).read_text())
    project=Transformer.from_crs(4326,32611,always_xy=True)
    wgs=Transformer.from_crs(32611,4326,always_xy=True)
    refs={f['properties']['id']:transform(project.transform,shape(f['geometry'])) for f in original['features']}
    focus=refs['downtown'];near=[refs['historic_core'],refs['civic_center']]
    def standard(kind,source,oid,g,attributes,vintage=2025):
        c=g.representative_point()
        regions=['city']
        if g.intersects(focus):regions.append('downtown')
        for name in ['historic_core','civic_center']:
            if g.intersects(refs[name]):regions.append(name)
        level='closeup_detail' if any(g.intersects(n) for n in near) else 'block_detail' if 'downtown' in regions else 'city_overview'
        return {'type':'Feature','properties':{
            'id':source+':'+str(oid),'feature_type':kind,'source_id':source,'original_id':str(oid),
            'data_vintage':vintage,'acquisition_date':None,'geometry_source':source,'height_source':None,
            'inferred_fields':[],'data_class':'processed_observed','evidence_class':'official_data',
            'confidence':{'geometry':'source_dependent','height':'unknown','basis':'Published Census geometry; no numeric survey accuracy established'},
            'regions':regions,'tile_id':f"utm11_{math.floor((c.x-origin[0])/250)}_{math.floor((c.y-origin[1])/250)}",
            'visual_level':level,**attributes},'geometry':mapping(transform(wgs.transform,g))}
    places,pcrs=reader(root/'data/raw/stage02/census/ca_places_2025.zip')
    ptx=Transformer.from_crs(pcrs,32611,always_xy=True)
    cities=[];city=None
    for sr in places.iterShapeRecords():
        a=sr.record.as_dict()
        if a['GEOID'] not in ['0644000','0670000','0606308']:continue
        raw=transform(ptx.transform,shape(sr.shape.__geo_interface__))
        g=unary_union(polygon_parts(make_valid(raw)))
        if g.is_empty or not g.is_valid:raise ValueError('Invalid city boundary')
        f=standard('administrative_boundary','census_places_2025',a['GEOID'],g,{
            'name':a['NAME'],'role':'primary_city' if a['GEOID']=='0644000' else 'independent_background_disabled',
            'raw_attributes':a,'area_m2':g.area,'numeric_accuracy_m':None})
        cities.append(f)
        if a['GEOID']=='0644000':city=g
    if city is None:raise ValueError('LA city GEOID not found')
    if not city.covers(focus):raise ValueError('Downtown work window not covered by new city boundary')
    write_json(out/'administrative_boundaries.geojson',{'type':'FeatureCollection','features':cities})
    write_json(out/'city_boundary_2025.geojson',{'type':'FeatureCollection','features':[f for f in cities if f['properties']['original_id']=='0644000']})
    old=refs['city']
    diff={'old_source':'Census 2020 cartographic 1:500,000','new_source':'Census TIGER/Line 2025 full-resolution',
          'old_projected_area_m2':old.area,'new_projected_area_m2':city.area,
          'symmetric_difference_m2':old.symmetric_difference(city).area,
          'interpretation':'Resolution, water clipping and vintage differ; this is NOT proof of annexation or land-use change.'}
    write_json(out/'boundary_comparison.json',diff)
    roads,rcrs=reader(root/'data/raw/stage02/census/la_roads_2025.zip')
    rtx=Transformer.from_crs(rcrs,32611,always_xy=True)
    # Validate a real small downtown sample before reading the full county file.
    fields={f[0] for f in roads.fields[1:]}
    if not {'LINEARID','MTFCC','FULLNAME'}.issubset(fields):raise ValueError('Unexpected TIGER road fields')
    sample_bounds=transform(Transformer.from_crs(32611,rcrs,always_xy=True).transform,refs['historic_core']).bounds
    sample=[]
    for sr in roads.iterShapeRecords(bbox=sample_bounds):
        g=transform(rtx.transform,shape(sr.shape.__geo_interface__))
        if g.intersects(refs['historic_core']):sample.append(sr.record.as_dict())
    if not sample:raise ValueError('Real downtown road sample returned zero features')
    write_json(root/'work/reports/stage02/census_sample.json',{'status':'passed','sample_feature_count':len(sample),
        'fields':sorted(fields),'source_horizontal_crs':rcrs.to_string(),'source_horizontal_unit':'degree',
        'working_crs':'EPSG:32611','working_unit':'m','vertical_datum':None,
        'missing_fields':['oneway','lanes','bridge','tunnel','level','elevation'],
        'first_records':sample[:5],'note':'MTFCC is the source road taxonomy, not a measured lane/grade inventory.'})
    values=[];downtown=[];seen=set();stats=collections.Counter();quarantine=[]
    for index,sr in enumerate(roads.iterShapeRecords()):
        stats['county_records_read']+=1
        g=transform(rtx.transform,shape(sr.shape.__geo_interface__))
        if not g.intersects(city):continue
        stats['city_intersecting_source_features']+=1
        if not g.is_valid:
            stats['invalid_input']+=1;g=make_valid(g)
        else:stats['valid_input']+=1
        g=g.intersection(city)
        if g.is_empty or g.geom_type not in ['LineString','MultiLineString']:
            quarantine.append({'index':index,'reason':'empty_or_non_linear_after_clipping'});continue
        a=sr.record.as_dict();key=(a['LINEARID'],hashlib.sha256(normalize(g).wkb).hexdigest())
        if key in seen:stats['duplicate_removed']+=1;continue
        seen.add(key)
        f=standard('road_centerline','census_roads_2025',a['LINEARID'],g,{
            'name':a['FULLNAME'],'road_class_source':a['MTFCC'],'route_type_source':a['RTTYP'],
            'oneway':None,'lanes':None,'bridge':None,'tunnel':None,'layer':None,
            'ground_elevation_m':None,'length_m':g.length,'raw_attributes':a,
            'topology_rule':'Do not infer connectivity from 2D intersections; grade is unknown.'})
        values.append(f)
        if g.intersects(focus):
            df={**f,'geometry':mapping(transform(wgs.transform,g.intersection(focus)))};downtown.append(df)
    if stats['county_records_read']!=roads.numRecords:raise ValueError('County source record count mismatch')
    ids=[f['properties']['id'] for f in values]
    if len(ids)!=len(set(ids)):raise ValueError('LINEARID not unique; preserve segmented source IDs before continuing')
    write_json(out/'roads.geojson',{'type':'FeatureCollection','features':values})
    write_json(out/'downtown_roads.geojson',{'type':'FeatureCollection','features':downtown})
    write_json(out/'quarantine.json',quarantine)
    other_stats={};groups={'water_parks':[],'rail_airport_port':[],'landuse_landcover':[],'landmarks':[]}
    inputs=[('la_area_water_2025.zip','HYDROID','water_area'),('la_linear_water_2025.zip','LINEARID','waterway'),
            ('ca_area_landmarks_2025.zip','AREAID','facility_area'),('ca_point_landmarks_2025.zip','POINTID','named_facility_point'),
            ('us_rails_2025.zip','LINEARID','railway'),('us_coastline_2025.zip',None,'coastline')]
    for filename,id_field,kind in inputs:
        path=root/'data/raw/stage02/census'/filename
        if not path.exists():continue
        rr,crs=reader(path);tx=Transformer.from_crs(crs,32611,always_xy=True)
        fields={f[0] for f in rr.fields[1:]}
        if id_field is not None and id_field not in fields:raise ValueError('Missing source ID field in '+filename+': '+str(fields))
        count=collections.Counter();keep=[];seen_other=set()
        for record_index,sr in enumerate(rr.iterShapeRecords()):
            count['source_records_read']+=1
            source_geometry=shape(sr.shape.__geo_interface__)
            raw=transform(tx.transform,source_geometry)
            if not raw.intersects(city):continue
            if not raw.is_valid:count['invalid_input']+=1;raw=make_valid(raw)
            else:count['valid_input']+=1
            g=raw.intersection(city)
            if g.is_empty or (kind in ['water_area','facility_area'] and g.area<.01):continue
            if kind in ['waterway','railway','coastline'] and g.geom_type not in ['LineString','MultiLineString']:continue
            a=sr.record.as_dict();mtfcc=a.get('MTFCC')
            oid=a[id_field] if id_field else 'geometry_sha256_'+hashlib.sha256(normalize(source_geometry).wkb).hexdigest()
            key=(oid,hashlib.sha256(normalize(g).wkb).hexdigest())
            if key in seen_other:count['duplicate_removed']+=1;continue
            seen_other.add(key)
            source='census_'+filename.removesuffix('.zip')
            f=standard(kind,source,oid,g,{'name':a.get('FULLNAME') or a.get('NAME') or None,'class_source':mtfcc,
                       'raw_attributes':a,'height_m':None,'ground_elevation_m':None,
                       'coverage_warning':'Census feature inventory; not a complete current land-cover, station or protected-landmark register.'})
            if id_field is None:
                f['properties'].update({'original_id':None,'original_record_index':record_index,
                    'id_basis':'SHA256 normalized original NAD83 geometry; source coastline has only NAME/MTFCC, no stable native ID'})
            keep.append(f)
            if kind in ['water_area','waterway','coastline']:groups['water_parks'].append(f)
            if kind=='railway' or (mtfcc or '').startswith('K245') or mtfcc=='K2460':groups['rail_airport_port'].append(f)
            if kind=='facility_area':
                groups['landuse_landcover'].append(f)
                if (mtfcc or '').startswith('K218'):groups['water_parks'].append(f)
            if a.get('FULLNAME') and kind in ['facility_area','named_facility_point']:groups['landmarks'].append(f)
        if count['source_records_read']!=rr.numRecords:raise ValueError('Source record count mismatch: '+filename)
        write_json(out/(kind+'.geojson'),{'type':'FeatureCollection','features':keep})
        other_stats[kind]={'source_records_expected':rr.numRecords,**dict(count),'retained_count':len(keep),
                           'validity_rate_after':sum(shape(f['geometry']).is_valid for f in keep)/len(keep) if keep else None,
                           'source_crs':crs.to_string()}
        print('CENSUS_LAYER_CLEAN_OK',kind,len(keep),flush=True)
    for name,features in groups.items():
        write_json(out/(name+'.geojson'),{'type':'FeatureCollection','coverage':'partial_inventory_not_exhaustive','features':features})
    # Explicitly unavailable, not a fabricated zero-building city.
    for name in ['buildings','building_parts','trees']:
        if not (out/(name+'.geojson')).exists():
            write_json(out/(name+'.geojson'),{'type':'FeatureCollection','availability':'not_downloaded_yet','features':[]})
    report={'status':'passed_for_acquired_census_vectors','source_records_expected':roads.numRecords,
        **dict(stats),'duplicate_removed':stats['duplicate_removed'],'quarantined_count':len(quarantine),
        'roads_city_count':len(values),'roads_downtown_count':len(downtown),
        'road_validity_rate_before':stats['valid_input']/max(1,stats['city_intersecting_source_features']),
        'road_validity_rate_after':sum(shape(f['geometry']).is_valid for f in values)/max(1,len(values)),
        'road_direction_missing_rate':1.0,'road_lanes_missing_rate':1.0,'road_grade_missing_rate':1.0,
        'building_observed_count':None,'building_downloaded_count':0,'building_height_missing_rate':None,
        'building_height_statistic_status':'unavailable: no downloaded buildings; denominator is zero, not 0% missing',
        'terrain_available':False,'cross_source_building_matching':'not_executed_no_building_sources_downloaded',
        'other_layers':other_stats,'group_feature_counts':{name:len(features) for name,features in groups.items()},
        'horizontal_source_crs':rcrs.to_string(),'vertical_crs':None,'working_crs':'EPSG:32611',
        'boundary_comparison':diff}
    write_json(root/'work/reports/stage02/statistics.json',report)
    if not (out/'cross_source_building_matches.json').exists():
        write_json(out/'cross_source_building_matches.json',{'status':'not_executed_no_building_sources','matches':[],
            'planned_policy':'Compare footprint overlap and source dates; retain parent/part relation; never merge solely by centroid.'})
    print('CENSUS_CLEAN_OK',json.dumps({k:report[k] for k in ['source_records_expected','roads_city_count','roads_downtown_count']}),flush=True)
    return report
