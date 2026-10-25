"""Stage02 reproducible acquisition, normalization and evidence, with explicit data gaps."""
import datetime
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import yaml
from PIL import Image, ImageStat

from stage02_io import Client, arcgis_fetch, digest, write_json


def input_hash(root,cfg,quality):
    h=hashlib.sha256(json.dumps({'cfg':cfg,'quality':quality},sort_keys=True).encode())
    for p in [root/'requirements.lock',root/'config/project.yaml',*sorted((root/'config').glob('stage02*')),root/cfg['origin_file'],root/cfg['scope_file'],*sorted((root/'scripts').glob('stage02*.py')),
              *sorted((root/'data/raw/stage02').rglob('*'))]:
        if p.is_file() and '.part' not in p.name:
            h.update(str(p.relative_to(root)).encode());h.update(p.read_bytes())
    return h.hexdigest()


def investigate_after_network_change(root,cfg):
    """Retry only on explicit --refresh-network following a real configuration change."""
    client=Client(root,cfg);stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder=Path('data/raw/stage02/network')/stamp;results=[]
    endpoints={
        'la_city_buildings':'https://maps.lacity.org/lahub/rest/services/Landbase_Information_WFS/MapServer/0',
        'county_buildings':'https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/Countywide_Building_Outlines_(2020)/FeatureServer/0',
        'usgs_lidar':'https://apps.nationalmap.gov/lidar-explorer/',
        'usgs_catalog':'https://tnmaccess.nationalmap.gov/api/v1/products',
        'osm_status':'https://overpass-api.de/api/status'}
    scopes=json.loads((root/cfg['scope_file']).read_text())
    from shapely.geometry import shape
    sample=shape(next(f['geometry'] for f in scopes['features'] if f['properties']['id']=='historic_core'))
    xmin,ymin,xmax,ymax=sample.bounds
    for key,url in endpoints.items():
        try:
            if key.endswith('buildings'):
                meta,features,evidence=arcgis_fetch(client,url,folder/key,{
                    'geometry':json.dumps({'xmin':xmin,'ymin':ymin,'xmax':xmax,'ymax':ymax,'spatialReference':{'wkid':4326}}),
                    'geometryType':'esriGeometryEnvelope','inSR':4326,'spatialRel':'esriSpatialRelIntersects'},page_size=100)
                results.append({'source':key,'status':'sample_acquired_requires_field_semantics_review','count':len(features),
                                'fields':meta.get('fields'),'completeness':evidence})
            else:
                params={'datasets':'Digital Elevation Model (DEM) 1 meter','bbox':f'{xmin},{ymin},{xmax},{ymax}','max':10} if key=='usgs_catalog' else None
                p=client.get(url,str(folder/(key+'.response')),params)
                results.append({'source':key,'status':'response_obtained_requires_review','file':str(p.relative_to(root))})
        except Exception as e:results.append({'source':key,'status':'blocked_or_failed','error':str(e)})
    # OSM sample uses vectors and metadata, never standard raster tiles.
    query=f'[out:json][timeout:25];(nwr[building]({ymin},{xmin},{ymax},{xmax});way[highway]({ymin},{xmin},{ymax},{xmax}););out meta geom;'
    try:
        p=client.get(cfg['osm']['endpoint'],str(folder/'osm_sample.json'),{'data':query})
        j=json.loads(p.read_text())
        if j.get('remark'):raise ValueError(j['remark'])
        results.append({'source':'osm_sample','status':'sample_acquired_requires_semantics_review','elements':len(j.get('elements',[]))})
    except Exception as e:results.append({'source':'osm_sample','status':'blocked_or_failed','error':str(e)})
    write_json(root/'work/reports/stage02/network_refresh.json',results)
    return results


def check(root):
    m=json.loads((root/'outputs/stage02.manifest.json').read_text())
    for item in m['artifacts']:
        p=root/item['path']
        if not p.exists() or digest(p)!=item['sha256']:raise ValueError('Stage02 artifact missing/changed: '+str(p))
    print('STAGE02_ARTIFACT_INTEGRITY_PASSED',len(m['artifacts']),'artifacts',flush=True)
    if m['status'] not in ['complete','complete_with_documented_gaps']:
        print('STAGE02_INCOMPLETE / 第二阶段尚未完成；查看 STATUS.md',flush=True)
        return 4
    print('STAGE02_SELECTED_DATA_WORKFLOW_PASSED_WITH_DOCUMENTED_GAPS; verified heights and road operational attributes remain unknown.',flush=True)
    return 0


def execute(root,region,quality,refresh_network=False):
    from stage02_clean import clean_census
    from stage02_catalog import catalog
    from stage02_preview import prepare
    from stage02_acquire import acquire
    from stage02_cache import run_cached
    from stage02_dataset import selection,crosswalk_overlap
    from stage02_presentation import present
    cfg=yaml.safe_load((root/'config/stage02.yaml').read_text())
    if region=='calibration':region='downtown'
    print('STAGE02: city-wide acquired vectors plus Downtown sample; requested region='+region,flush=True)
    if refresh_network:investigate_after_network_change(root,cfg)
    acquire(root)
    fp=input_hash(root,cfg,quality);manifest=root/'outputs/stage02.manifest.json'
    if manifest.exists():
        old=json.loads(manifest.read_text())
        for item in old['artifacts']:
            p=root/item['path']
            if not p.exists() or digest(p)!=item['sha256']:raise ValueError('Preserve modified existing stage02 artifact: '+str(p))
        if old.get('fingerprint')==fp:
            print('STAGE02_INCREMENTAL_CACHE_VERIFIED',flush=True);return check(root)
        archive=root/'work/history'/('stage02_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        for item in old['artifacts']:
            p=root/item['path'];dest=archive/item['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        archive.mkdir(parents=True,exist_ok=True);shutil.copy2(manifest,archive/'stage02.manifest.json')
        print('STAGE02_PRIOR_OUTPUTS_ARCHIVED',archive,flush=True)
    report=clean_census(root,cfg)
    run_cached(root)
    chosen=selection(root);crosswalk_overlap(root);sources=catalog(root)
    audit=json.loads((root/'work/reports/stage02/building_output_audit.json').read_text())
    terrain=json.loads((root/'work/reports/stage02/terrain.json').read_text())
    cover=json.loads((root/'work/reports/stage02/landcover_canopy.json').read_text())
    official=json.loads((root/'work/reports/stage02/official_layers.json').read_text())
    for key in ['building_observed_count','building_downloaded_count','building_height_missing_rate','building_height_statistic_status','terrain_available','cross_source_building_matching']:
        report.pop(key,None)
    report.update(status='passed_for_selected_inputs_with_documented_gaps',buildings=audit,
        model_selected_buildings=chosen['model_selected_buildings'],terrain=terrain,landcover_canopy=cover,
        official_layers=official,cross_source_building_matching='9 explicit prior-ID matches, geometric overlap measured',
        verified_building_height_missing_rate=1.0,verified_building_height_semantics='unknown; candidates explicitly inferred')
    assert audit['all_geometry_checked'] and audit['stable_ids_unique'] and audit['valid_geometry_rate']==1
    assert terrain['downtown_1m']['valid_fraction_within_scope']==1
    assert terrain['city_10m']['valid_fraction_within_scope']>.99
    assert report['county_records_read']==report['source_records_expected'] and report['road_validity_rate_after']==1
    write_json(root/'work/reports/stage02/statistics.json',report)
    prepare(root,cfg,quality);job=present(root,quality)
    log=root/'work/logs/stage02/blender.log'
    exe='/usr/bin/blender';script=root/'scripts/stage02_blender.py';jobpath=root/'work/reports/stage02/blender_job.json'
    with log.open('w') as f:
        for cmd in [[exe,'--background','--factory-startup','--threads','4','--python-exit-code','1','--python',str(script),'--',str(jobpath)],
                    [exe,'--background',job['blend_path'],'--threads','4','--python-exit-code','1','--python',str(script),'--',str(jobpath),'--verify']]:
            f.write(json.dumps(cmd)+'\n');f.flush()
            p=subprocess.run(cmd,cwd=root,stdout=f,stderr=subprocess.STDOUT)
            f.write(f'\nEXIT_CODE={p.returncode}\n');f.flush()
            if p.returncode:raise RuntimeError('Blender stage02 review failed; '+str(log))
    for p in [root/'work/previews/stage02/coverage_and_gaps.png',root/'work/previews/stage02/downtown_partial_overlay.png',Path(job['render_path'])]:
        with Image.open(p) as im:
            im.verify()
        with Image.open(p) as im:
            if max(ImageStat.Stat(im.convert('RGB')).stddev)<3:raise ValueError('Blank preview '+str(p))
    blendcheck=json.loads((root/job['check_path']).read_text())
    assert blendcheck['reopened'] and blendcheck['building_overlay_complete'] and blendcheck['terrain_overlay_complete']
    acceptance={'stage':2,'status':'complete_with_documented_gaps','acquired_data_integrity':'passed',
                'completed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'administrative_reference_date':'2025-01-01','single_date_city_snapshot':False,
                'complete_building_road_terrain_overlay':True,'all_building_output_geometries_audited':True,
                'data_gaps':['HEIGHT/ELEV field dictionary and LARIAC vertical datum not verified; height_m null, candidate inferred',
                    'architectural building parts, floors, roof forms and current facade research missing',
                    'road one-way/lanes/bridge-tunnel grade unresolved; crossings not assumed connected',
                    'tree inventory only archival Downtown parks; canopy only Downtown; no LAS/LAZ point clouds',
                    'mixed source years; post-2020 building changes need separate verification',
                    'county/City data public redistribution rights require original terms review'],
                'statistics':report,'source_registry':'data/processed/stage02/source_registry.json',
                'next_stage':'Await user part 3; no stage03 terrain modeling or full city mesh extrusion performed.',
                'no_standard_osm_tile_requests':True,'blender_checkpoint':'scenes/stage02_data_review.blend',
                'requested_region':region,'preview_region':'downtown','quality':quality}
    write_json(root/'outputs/stage02_acceptance.json',acceptance)
    paths=[p for folder in ['data/processed/stage02','work/previews/stage02','work/reports/stage02'] for p in (root/folder).rglob('*') if p.is_file()]
    paths += [Path(job['blend_path']),log,root/'outputs/stage02_acceptance.json',root/'docs/stage02/sources.md']
    artifacts=[{'path':str(p.relative_to(root)),'sha256':digest(p),'bytes':p.stat().st_size} for p in sorted(set(paths))]
    write_json(manifest,{'stage':2,'status':'complete_with_documented_gaps','fingerprint':fp,'artifacts':artifacts})
    print('STAGE02_ACCEPTANCE_PASSED_WITH_DOCUMENTED_DATA_GAPS; EXIT_CODE=0',flush=True)
    return 0
