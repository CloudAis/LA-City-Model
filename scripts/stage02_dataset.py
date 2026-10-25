"""Shared model selection: preserve archived observations, never instantiate exact duplicates twice."""
import gzip
import json
import csv
from pathlib import Path
import pyogrio.raw
from stage02_io import write_json


def selection(root):
    base=root/'data/processed/stage02'
    pairs=json.loads((base/'building_geometry_duplicate_review.json').read_text())
    ids={p[k].split(':',1)[1] for p in pairs for k in ['first_id','other_id']}
    gdb=next((root/'work/cache/lariac6').rglob('*.gdb'))
    where='BLD_ID IN ('+','.join("'"+v.replace("'","''")+"'" for v in sorted(ids))+')'
    m,f,_,a=pyogrio.raw.read(gdb,layer='LARIAC6_BUILDINGS_2020',read_geometry=False,where=where,return_fids=True,
                           columns=['BLD_ID','DATE_','HEIGHT','ELEV','STATUS','SOURCE'])
    rows=[{'original_id':int(fid),**{str(k):(v[i].item() if hasattr(v[i],'item') else v[i]) for k,v in zip(m['fields'],a)}} for i,fid in enumerate(f)]
    lookup={'lariac6:'+r['BLD_ID']:r for r in rows};excluded={}
    for p in pairs:
        candidates=[p['first_id'],p['other_id']]
        winner=max(candidates,key=lambda uid:(int(lookup[uid].get('DATE_') or 0),uid))
        loser=next(uid for uid in candidates if uid!=winner)
        excluded[loser]={'canonical_id':winner,'reason':'Exact normalized geometry match; prefer later explicitly recorded imagery year; raw older observation preserved.'}
    audit=json.loads((root/'work/reports/stage02/building_output_audit.json').read_text())
    value={'excluded_duplicate_ids':excluded,'building_records':audit['buildings'],'model_selected_buildings':audit['buildings']-len(excluded),
           'solar_structures_separate':audit['other_structures'],'source_lookup':rows,'lookup_where':where}
    write_json(base/'model_selection.json',value)
    write_json(base/'buildings.geojson',{'type':'FeatureCollection','storage':'buildings.geojsonl.gz',
        'availability':'downloaded_standardized_and_fully_audited','building_records':audit['buildings'],
        'other_structure_records':audit['other_structures'],'model_selected_buildings':value['model_selected_buildings'],
        'selection_file':'model_selection.json','features':[]})
    temporal=base/'temporal_corrections.csv'
    with temporal.open() as stream:changes=list(csv.DictReader(stream))
    for change in changes:
        year=change['source_observation_year']
        change['event_interval']={'2014':'2008–2014 source update cycle','2017':'2014–2017 source update cycle',
            '2020':'2017–2020 source update cycle'}.get(year,'before_or_in_'+year+'; earlier baseline unknown')
        change['interpretation']='Source-reported change flag and DATE_ year; exact construction/demolition date not established.'
    with temporal.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['feature_id','old_building_id','source_status','source_observation_year','event_interval','interpretation'])
        writer.writeheader();writer.writerows(changes)
    write_json(root/'work/reports/stage02/temporal_change_summary.json',{'rows':len(changes),
        'meaning':'Source-reported archival changes; not a list of verified changes between 2020 and 2026',
        'unverified_period':'2020–2026 for building geometry/facades; requires newer observation sources'})
    return value


def iter_model_buildings(root):
    base=Path(root)/'data/processed/stage02';excluded=json.loads((base/'model_selection.json').read_text())['excluded_duplicate_ids']
    with gzip.open(base/'buildings.geojsonl.gz','rt') as stream:
        for line in stream:
            f=json.loads(line);p=f['properties']
            if p['feature_type']=='building_roofline' and p['id'] not in excluded:yield f


def crosswalk_overlap(root):
    from shapely.geometry import shape
    from shapely.ops import transform
    from pyproj import Transformer
    from stage02_extra import esri_geometry
    base=Path(root)/'data/processed/stage02';tx=Transformer.from_crs(4326,32611,always_xy=True)
    target=json.loads((base/'cross_source_building_matches.json').read_text())
    oldpath=next(iter(sorted((Path(root)/'data/raw/stage02/network').glob('*/la_city_buildings/page_00000000.json'))))
    old={f['attributes']['BLD_ID']:f for f in json.loads(oldpath.read_text())['features']}
    current={f['properties']['id']:f for f in json.loads((base/'downtown_buildings.geojson').read_text())['features']}
    for row in target['matches']:
        new=current.get(row['selected_id']);prior=old.get(row['older_BLD_ID'])
        if new and prior:
            a=transform(tx.transform,shape(new['geometry']));b=transform(tx.transform,esri_geometry(prior['geometry']))
            row['footprint_iou']=a.intersection(b).area/a.union(b).area
            row['centroid_delta_m']=a.centroid.distance(b.centroid)
            row['identity_note']='Explicit old-ID relationship; geometric change does not imply the older outline should also be modeled.'
    write_json(base/'cross_source_building_matches.json',target)
