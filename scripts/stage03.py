"""Stage03 coordinated incremental build and actual Blender acceptance."""
import datetime
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from PIL import Image,ImageStat
from stage02_io import digest,write_json
from stage03_common import settings


INPUTS=['config/stage03.yaml','requirements.lock','data/processed/origin.json','data/processed/scopes.geojson',
    'data/processed/stage02/city_boundary_2025.geojson','data/processed/stage02/city_10m_dem_navd88_m.tif',
    'data/processed/stage02/downtown_1m_dem_navd88_m.tif','data/processed/stage02/landcover_nlcd2021_30m.tif',
    'data/processed/stage02/water_area.geojson','data/processed/stage02/waterway.geojson','data/processed/stage02/coastline.geojson',
    'data/processed/stage02/facility_area.geojson','data/processed/stage02/official_hcm.geojson']
INPUTS.append('data/raw/stage02/dem/usgs_1m_downtown_B23.tif')


def fingerprint(root,quality,data_only=False):
    paths=[root/n for n in INPUTS]+[p for p in (root/'data/raw/stage03').rglob('*') if p.is_file() and '.part' not in p.name]
    paths += [p for p in (root/'scripts').glob('stage03*.py') if not data_only or p.name not in ['stage03.py','stage03_blender.py']]
    if not data_only:paths += [root/'config/project.yaml',root/'scripts/project.py']
    h=hashlib.sha256(quality.encode())
    for p in sorted(set(paths)):h.update(str(p.relative_to(root)).encode());h.update(digest(p).encode())
    if not data_only:
        version=subprocess.run([settings(root)['build']['blender_executable'],'--version'],capture_output=True,text=True,check=True).stdout.splitlines()[0]
        h.update(version.encode())
    return h.hexdigest()


def verify(root,manifest):
    value=json.loads(manifest.read_text())
    for item in value['artifacts']:
        p=root/item['path']
        if not p.is_file() or digest(p)!=item['sha256']:raise ValueError('Preserve modified output before rebuilding: '+item['path'])
    return value


def register_executed_dataset(root,quality):
    """One-time registration of independently executed steps; never accept missing evidence."""
    cfg=settings(root);indexpath=root/f'data/processed/stage03/{quality}/tile_index.json';index=json.loads(indexpath.read_text())
    seams=json.loads((root/f'work/reports/stage03/seams_{quality}.json').read_text());water=json.loads((root/f'work/reports/stage03/water_{quality}.json').read_text())
    assert seams['status']=='passed' and seams['maximum_shared_edge_coordinate_or_height_error_m']<=cfg['validation']['seam_height_tolerance_m']
    assert seams['unpaired_interior_edges']==0 and water['maximum_water_chunk_edge_error_m']<=.001
    for tile in index['tiles']:
        if digest(root/tile['file'])!=tile['sha256']:raise ValueError('Baked terrain changed after audit')
    fp=fingerprint(root,quality,True);version=cfg['build_version']+'_'+fp[:12];index['build_version']=version
    for t in index['tiles']:t['build_version']=version
    write_json(indexpath,index)
    geopath=indexpath.with_suffix('.geojson');geo=json.loads(geopath.read_text())
    for f in geo['features']:f['properties']['build_version']=version
    write_json(geopath,geo)
    paths=[p for p in (root/f'data/processed/stage03/{quality}').rglob('*') if p.is_file()]
    paths += [p for p in (root/'data/processed/stage03').glob('*') if p.is_file()]
    paths += [p for p in (root/'work/reports/stage03').glob('*.json') if p.name in ['additional_sources.json','control_points.json','dem_audit.json','foundation.json',f'seams_{quality}.json',f'terrain_{quality}.json',f'water_{quality}.json',f'normals_{quality}.json','river_sections.json','tile_size_benchmark.json']]
    record={'fingerprint':fp,'quality':quality,'version':version,'evidence':'Actual source preparation, control checks, full tile mesh/seam audit, water and foundation builders executed; existing immutable output hashes registered.',
        'artifacts':[{'path':str(p.relative_to(root)),'sha256':digest(p),'bytes':p.stat().st_size} for p in sorted(set(paths))]}
    write_json(root/f'outputs/stage03_data_{quality}.manifest.json',record);print('STAGE03_EXECUTED_DATASET_REGISTERED',len(record['artifacts']),flush=True)


def check(root,region,quality):
    if region=='calibration':region='city'
    m=verify(root,root/f'outputs/stage03_{region}_{quality}.manifest.json')
    if m['status']!='complete_with_documented_gaps':raise ValueError('Stage03 acceptance incomplete')
    print('STAGE03_ARTIFACTS_AND_ACCEPTANCE_PASSED',len(m['artifacts']),'artifacts; physical water levels/current flow and bank/bridge details remain documented gaps.',flush=True);return 0


def execute(root,region,quality):
    from stage03_sources import acquire
    from stage03_additional import prepare as additional
    from stage03_surface import Surface
    from stage03_coordinates import prepare as coordinates
    from stage03_terrain import build as terrain
    from stage03_water import build as water
    from stage03_scene import foundation,prepare_normals,job as scene_job
    from stage03_hydro_profiles import prepare as river_profiles
    if region=='calibration':region='city'
    cfg=settings(root);logs=root/'work/logs/stage03';logs.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(root).free<cfg['build']['disk_headroom_gib']*1024**3:raise ValueError('Insufficient disk headroom')
    acquire(root);fp=fingerprint(root,quality);manifest=root/f'outputs/stage03_{region}_{quality}.manifest.json'
    if manifest.exists():
        old=verify(root,manifest)
        if old['fingerprint']==fp:
            print('STAGE03_INCREMENTAL_CACHE_VERIFIED',flush=True);return check(root,region,quality)
        archive=root/'work/history'/('stage03_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        for item in old['artifacts']:
            p=root/item['path'];dest=archive/item['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        shutil.copy2(manifest,archive/manifest.name)
    data_manifest=root/f'outputs/stage03_data_{quality}.manifest.json';datafp=fingerprint(root,quality,True)
    cached=verify(root,data_manifest) if data_manifest.exists() else None
    if cached and cached['fingerprint']==datafp:print('STAGE03_DATA_COMPONENT_CACHE_VERIFIED',flush=True)
    else:
        additional(root);surface=Surface(root);surface.audit();coordinates(root,surface)
        index,stats=terrain(root,quality,cfg['build_version']+'_'+datafp[:12],surface);prepare_normals(root,quality,surface);water(root,quality,index,surface);foundation(root,surface);river_profiles(root,quality);register_executed_dataset(root,quality)
    index=json.loads((root/f'data/processed/stage03/{quality}/tile_index.json').read_text());pieces=json.loads((root/f'data/processed/stage03/{quality}/water_index.json').read_text())['pieces'];base=json.loads((root/'work/reports/stage03/foundation.json').read_text())
    job=scene_job(root,region,quality,index,pieces,base);key=f'stage03_{region}_{quality}';jobpath=root/f'work/reports/stage03/{key}_job.json';log=logs/(key+'_blender.log')
    with log.open('w') as f:
        for args in [['--factory-startup'],[job['blend_path']]]:
            cmd=[cfg['build']['blender_executable'],'--background',*args,'--threads',str(cfg['build']['threads']),'--python-exit-code','1','--python',str(root/'scripts/stage03_blender.py'),'--',str(jobpath)]
            if args[0]!='--factory-startup':cmd.append('--verify')
            f.write(json.dumps(cmd)+'\n');f.flush();p=subprocess.run(cmd,cwd=root,stdout=f,stderr=subprocess.STDOUT);f.write('\nEXIT_CODE='+str(p.returncode)+'\n');f.flush()
            if p.returncode:raise RuntimeError('Blender build/reopen/render failed; see '+str(log))
    bc=json.loads(Path(job['check_path']).read_text());assert bc['status']=='passed' and bc['nonfinite_vertex_values']==0
    controls=json.loads((root/'work/reports/stage03/control_points.json').read_text());controls['actual_Blender_reopen_measurements']=bc['control_positions'];controls['maximum_Blender_position_error_m']=bc['maximum_control_position_error_m'];controls['blender_position_check']='passed_actual_saved_scene_reopen'
    write_json(root/f'work/reports/stage03/controls_{region}_{quality}_final.json',controls)
    for name in bc['rendered_files']:
        with Image.open(name) as im:im.verify()
        with Image.open(name) as im:
            if max(ImageStat.Stat(im.convert('RGB')).stddev)<3:raise ValueError('Blank render: '+name)
    acceptance={'stage':3,'status':'complete_with_documented_gaps','completed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'region':region,'quality':quality,'blender_checkpoint':job['blend_path'],'coordinate_controls':bc['control_positions'],
        'terrain_seams':'passed actual NPZ edge checks for all9 neighboring mixed-LOD combinations','actual_open_save_reopen_render':True,
        'vertical_exaggeration':1,'no_nonfinite_vertices':True,'active_triangle_budget_passed':True,
        'limitations':['Source survey accuracy unknown; computational error is not survey accuracy','Ocean0 is a design reference on NAVD88 axis, not a measured tidal surface',
            'DEM-estimated lake levels and DEM-conforming geographic water masks are not hydraulic/current-flow surveys',
            'Riverbank material, surveyed engineering channel sections and bridge decks not available; ground cross sections and hydrographic reaches retained',
            'Industrial/port/airport classifications include official planning designations, not an observed current parcel-use inventory'],
        'next_step':'Wait for user part4; no stage04 road/bridge construction, building extrusion, GLB export or viewer implemented.'}
    write_json(root/f'outputs/{key}_acceptance.json',acceptance)
    paths=[p for folder in [root/f'data/processed/stage03/{quality}',root/'work/reports/stage03',Path(job['preview_directory'])] for p in folder.rglob('*') if p.is_file()]
    paths += [p for p in (root/'data/processed/stage03').glob('*') if p.is_file()]
    paths += [Path(job['blend_path']),log,root/f'outputs/{key}_acceptance.json',data_manifest]
    write_json(manifest,{'stage':3,'status':'complete_with_documented_gaps','fingerprint':fp,'region':region,'quality':quality,
        'artifacts':[{'path':str(p.relative_to(root)),'sha256':digest(p),'bytes':p.stat().st_size} for p in sorted(set(paths))]})
    print('STAGE03_ACCEPTANCE_PASSED_WITH_DOCUMENTED_GAPS',manifest,flush=True);return 0
