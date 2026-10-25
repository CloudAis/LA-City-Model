"""Independent component caches: new landmark research does not rebuild a million footprints."""
import hashlib
import inspect
import json
from pathlib import Path
from stage02_io import digest,write_json


def components(root):
    from stage02_enrich import terrain,buildings,read_refs
    from stage02_audit import audit
    from stage02_extra import official,landcover,esri_geometry
    base=root/'data/processed/stage02';reports=root/'work/reports/stage02';raw=root/'data/raw/stage02'
    common=[root/'data/processed/scopes.geojson',root/'data/processed/origin.json',base/'city_boundary_2025.geojson']
    return {
        'terrain':([terrain,read_refs],common+list((raw/'dem').glob('*.tif')),
            [base/'downtown_1m_dem_navd88_m.tif',base/'city_10m_dem_navd88_m.tif',reports/'terrain.json'],lambda:terrain(root)),
        'buildings':([buildings,read_refs,audit],common+[raw/'buildings/LARIAC6_Buildings_2020.gdb.zip',base/'city_10m_dem_navd88_m.tif'],
            [base/x for x in ['buildings.geojsonl.gz','downtown_buildings.geojson','building_parts.geojson',
             'building_height_anomalies.json',
             'building_coverage_counts_1km.json','building_geometry_duplicate_review.json']]+[reports/'buildings.json',reports/'building_output_audit.json'],
             lambda:(buildings(root),audit(root))),
        'official':([official,esri_geometry,read_refs],common+[p for d in ['landmarks/hcm','official/city_trees_downtown','official/city_boundary'] for p in (raw/d).glob('*.json') if not p.name.endswith('receipt.json')],
            [base/x for x in ['official_hcm.geojson','park_trees.geojson','municipal_boundary.geojson','trees.geojson','landmark_research_index.json',
             'independent_landmark_regions.geojson','outside_city_landmark_references.geojson']]+[reports/'official_layers.json'],lambda:official(root)),
        'landcover':([landcover,read_refs],common+[raw/'landcover/nlcd2021_city_30m.tif',raw/'canopy/downtown_canopy_2023_1m.tif'],
            [base/'landcover_nlcd2021_30m.tif',base/'downtown_canopy_2023_1m.tif',reports/'landcover_canopy.json'],lambda:landcover(root))}


def signature(functions,inputs):
    h=hashlib.sha256()
    for f in functions:h.update(inspect.getsource(f).encode())
    for p in inputs:h.update(str(p).encode());h.update(digest(p).encode())
    return h.hexdigest()


def adopt_verified_outputs(root):
    """One-time registration after functions and the full output audit actually ran."""
    audit=json.loads((root/'work/reports/stage02/building_output_audit.json').read_text())
    if not audit['all_geometry_checked'] or not audit['stable_ids_unique']:raise ValueError('Actual output audit required before cache adoption')
    cache={}
    for name,(funcs,inputs,outputs,run) in components(root).items():
        if any(not p.exists() for p in outputs):raise ValueError('Component output missing: '+name)
        cache[name]={'signature':signature(funcs,inputs),'outputs':[{'path':str(p.relative_to(root)),'sha256':digest(p)} for p in outputs],
                     'evidence':'Functions executed in current task and full building stream audited; existing results registered without rebuilding.'}
    write_json(root/'work/reports/stage02/component_cache.json',cache)


def run_cached(root):
    path=root/'work/reports/stage02/component_cache.json';cache=json.loads(path.read_text()) if path.exists() else {}
    for name,(funcs,inputs,outputs,run) in components(root).items():
        fp=signature(funcs,inputs);old=cache.get(name)
        if old:
            for item in old['outputs']:
                if digest(root/item['path'])!=item['sha256']:raise ValueError('Component output changed: '+item['path'])
        if old and old['signature']==fp:print('COMPONENT_CACHE_VERIFIED',name,flush=True);continue
        run()
        cache[name]={'signature':fp,'outputs':[{'path':str(p.relative_to(root)),'sha256':digest(p)} for p in outputs]}
        write_json(path,cache)
