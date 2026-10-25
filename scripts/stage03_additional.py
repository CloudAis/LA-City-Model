"""Selected City General Plan uses are separate from observed NLCD land cover."""
import datetime
import json
import collections
import numpy as np
from shapely.geometry import mapping
from shapely.ops import transform
from pyproj import Transformer
from stage02_extra import esri_geometry
from stage03_common import references,to_geographic,polygon_parts
from stage02_io import write_json,digest


def prepare(root):
    folder=root/'data/raw/stage03/landuse_selected';out=root/'data/processed/stage03';cfg,o,city,refs=references(root)
    if not (folder/'completeness.json').exists():
        write_json(out/'selected_plan_landuse.geojson',{'type':'FeatureCollection','availability':'not_acquired_use_existing_Census_facilities_only','features':[]});return
    proof=json.loads((folder/'completeness.json').read_text());fs=[]
    for p in sorted(folder.glob('page_*.json')):
        if not p.name.endswith('.receipt.json'):fs+=json.loads(p.read_text()).get('features',[])
    assert len(fs)==proof['server_count'] and len({f['attributes']['OBJECTID'] for f in fs})==len(fs)
    tx=Transformer.from_crs(4326,32611,always_xy=True);rows=[];categories=collections.Counter();repairs=0
    from shapely.ops import unary_union
    for f in fs:
        a=f['attributes'];g=esri_geometry(f['geometry']);g=transform(tx.transform,g);g=transform(lambda x,y,z=None:(np.asarray(x)-o[0],np.asarray(y)-o[1]),g).intersection(city)
        g=unary_union(polygon_parts(g))
        if g.is_empty:continue
        label=a.get('GPLU_Legend') or '';category='airport' if 'airport' in label.lower() else 'port' if 'port' in label.lower() else 'industrial' if 'industr' in label.lower() else None
        if not category:continue
        categories[category]+=1
        rows.append({'type':'Feature','properties':{'id':'city_gplu:'+str(a['OBJECTID']),'source_id':'LA_City_Planning_General_Plan_Land_Use',
            'original_id':a['OBJECTID'],'class':category,'source_label':label,'geometry_source':'official General Plan Land Use polygons',
            'evidence_class':'official_planning_designation_not_observed_current_use','inferred_fields':[],
            'data_class':'processed_observed','acquisition_year':None,'raw_attributes':a,
            'effective_plan_date':datetime.datetime.fromtimestamp(a['ADOPTDATE']/1000,datetime.timezone.utc).date().isoformat() if a.get('ADOPTDATE') else None,
            'geometry_accuracy_m':None,'warning':'Planning designation can differ from actual industrial/warehouse/port ground use; not a current parcel-use census.'},'geometry':to_geographic(g,o)})
    port_folder=root/'data/raw/stage03/port_plan_verified'
    port_proof=None
    if (port_folder/'completeness.json').exists():
        port_proof=json.loads((port_folder/'completeness.json').read_text());port_rows=[]
        for page in sorted(port_folder.glob('page_*.json')):
            if not page.name.endswith('.receipt.json'):port_rows+=json.loads(page.read_text()).get('features',[])
        assert len(port_rows)==port_proof['server_count']
        for f in port_rows:
            a=f['attributes']
            if a['NAME_ALF']!='Port of Los Angeles':continue
            g=transform(tx.transform,esri_geometry(f['geometry']));g=transform(lambda x,y,z=None:(np.asarray(x)-o[0],np.asarray(y)-o[1]),g).intersection(city)
            rows.append({'type':'Feature','properties':{'id':'city_cpa:'+str(a['OBJECTID']),'class':'port','source_label':a['NAME_ALF'],
                'evidence_class':'official_community_plan_area_not_terminal_parcel_boundary','geometry_accuracy_m':None,
                'acquisition_year':None,'raw_attributes':a,'warning':'Port planning domain includes water; marine mask takes priority. Porter Ranch and airport matches excluded by exact official name.'},'geometry':to_geographic(g,o)});categories['port']+=1
    write_json(out/'selected_plan_landuse.geojson',{'type':'FeatureCollection','features':rows})
    metadata=json.loads((folder/'layer.json').read_text())
    write_json(root/'work/reports/stage03/additional_sources.json',{'source':'City of Los Angeles City Planning General Plan Land Use',
        'original_page':'https://maps.lacity.org/lahub/rest/services/City_Planning_Department/MapServer/7',
        'query_predicate':"UPPER(GPLU_Legend) LIKE '%INDUSTR%' OR UPPER(GPLU_Legend) LIKE '%PORT%' OR UPPER(GPLU_Legend) LIKE '%AIRPORT%'",
        'completeness':proof,'port_plan_completeness':port_proof,'port_plan_original_page':'https://services5.arcgis.com/7nsPwEMP38bSkCjy/arcgis/rest/services/Community_Plan_Areas/FeatureServer/0',
        'standardized_features':len(rows),'classes':dict(categories),'actual_observation_year':None,
        'date_meaning':'ADOPTDATE/UPDATE_ are plan adoption/update fields, not image capture or current-use survey dates',
        'source_horizontal_crs':metadata.get('extent',{}).get('spatialReference'),'source_extent':metadata.get('extent'),
        'vertical_datum':'not applicable to 2D planning polygons','geometry_accuracy_m':None,
        'terms':metadata.get('copyrightText'),'redistribution':'not established; original City GIS disclaimer applies',
        'raw_files':[{'path':str(p.relative_to(root)),'sha256':digest(p)} for p in [*sorted(folder.glob('*.json')),*sorted(port_folder.glob('*.json'))]],
        'excluded_research':['River Master Plan returned a captcha page, not accepted as substantive evidence','USACE page returned403, no bypass','Census and City material classes do not verify individual riverbank materials or bridge decks']})
    print('PLAN_LANDUSE_STANDARDIZED',dict(categories),flush=True)
