"""Unified stage05 checkpoint, actual process evidence and immutable input hashes."""
from pathlib import Path
import json,hashlib,subprocess,datetime,shutil
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def inputs(root):
 paths=[root/'config/project.yaml',root/'config/stage05.yaml',root/'config/stage05_views.json',root/'requirements.lock',root/'data/processed/origin.json',root/'data/processed/scopes.geojson',root/'data/processed/stage02/city_boundary_2025.geojson',root/'data/processed/stage02/buildings.geojsonl.gz',root/'data/processed/stage02/city_10m_dem_navd88_m.tif',root/'data/processed/stage02/downtown_1m_dem_navd88_m.tif',root/'data/processed/stage03/medium/tile_index.json',root/'data/processed/stage04/mesh_index.json',root/'data/processed/stage04/road_floor_index.json',root/'data/processed/stage04/downtown_surface_masks.geojson',root/'work/reports/stage04/geometry.json',root/'scenes/stage04_city_medium.blend',root/'data/raw/stage04/osm/california-20261021.osm.pbf',*sorted((root/'scripts').glob('stage05*.py')),*[root/'scripts'/n for n in ['stage03_common.py','stage03_surface.py','stage04_geometry.py','stage02_dataset.py','stage02_io.py']],*sorted(p for p in (root/'data/raw/stage05').rglob('*') if p.is_file())]
 # Ground() and its DTM fallback consume the selected terrain, cut variants and
 # pavement floors directly. Track the bytes, not just their index filenames.
 import yaml
 cfg3=yaml.safe_load((root/'config/stage03.yaml').read_text());paths.append(root/'config/stage03.yaml');paths.append(root/'data/processed/stage03/medium/water_index.json')
 for t in json.loads((root/'data/processed/stage03/medium/tile_index.json').read_text())['tiles']:paths.append(root/t['file'])
 paths.extend(sorted((root/'data/processed/stage04/ground').glob('*.npz')))
 for m in json.loads((root/'data/processed/stage04/road_floor_index.json').read_text())['meshes']:paths.append(root/m['file'])
 for p in [cfg3['surface']['landcover'],cfg3['surface']['facilities'],cfg3['water']['coastline_source'],cfg3['water']['polygon_source'],'data/processed/stage03/selected_plan_landuse.geojson','data/processed/stage02/source_registry.json','data/processed/stage04/source_registry.json']:paths.append(root/p)
 return [{'path':str(p.relative_to(root)),'sha256':digest(p)} for p in sorted(set(paths))]
def fingerprint(items):return hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest()
def artifacts(root,paths):return [{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(set(paths)) if p.is_file()]
def verify(root,path):
 m=json.loads(path.read_text())
 for a in m['artifacts']:
  p=root/a['path']
  if not p.exists() or digest(p)!=a['sha256']:raise RuntimeError('Generated file changed; preserve user edits before rebuild: '+str(p))
 return m
def run(root,command,log,label):
 with log.open('a') as f:
  f.write('\n'+label+'\n'+json.dumps(list(map(str,command)))+'\n');f.flush();p=subprocess.run(list(map(str,command)),cwd=root,stdout=f,stderr=subprocess.STDOUT);f.write('\nEXIT_CODE='+str(p.returncode)+'\n')
 if p.returncode:raise RuntimeError(label+' failed; log='+str(log))
 print(label+'_OK',flush=True)
def register(root=ROOT):
 from PIL import Image,ImageStat
 b=json.loads((root/'work/reports/stage05/blender_check.json').read_text());s=json.loads((root/'work/reports/stage05/building_sample_audit.json').read_text());geometry=json.loads((root/'work/reports/stage05/geometry.json').read_text());stats=json.loads((root/'work/reports/stage05/source_statistics.json').read_text());placement=json.loads((root/'work/reports/stage05/placement_audit.json').read_text());inspection=json.loads((root/'work/reports/stage05/visual_inspection.json').read_text());assert b['status']=='passed' and b['file_reopened_in_independent_process'];assert s['status']=='passed' and s['sample_count']>=20;assert b['unique_authoring_building_ids']==geometry['counts']['buildings'];renders={}
 for name in json.loads((root/'config/stage05_views.json').read_text()):
  p=root/'work/previews/stage05'/f'{name}.png';im=Image.open(p).convert('RGB');im.load();assert im.size==(1536,1152) and max(ImageStat.Stat(im).stddev)>2;assert name in inspection['images'];renders[name]={'path':str(p.relative_to(root)),'sha256':digest(p),'size':list(im.size)}
 gaps=['county geometry represents rooflines, not verified ground-wall footprints','945k-class OSM heights mostly share county lineage; reported values are not independent survey control','raw LARIAC HEIGHT definition/unit hypothesis and ELEV vertical datum remain unresolved; ELEV unused','roof defaults, facade grids, entrances and equipment mostly explicitly inferred','high hillside foundations and unresolved entrance connections require review','some exact mesh T junctions remain; inspect sample topology report; watertightness not universally passed','mixed acquisition years and OSM state; no single-date/current complete city claim','stage04 transport clearance/occlusion/LOD-interface gaps remain','runtime streaming, GLB, viewer and GPU/FPS validation not implemented in stage05']
 a={'stage':5,'status':'complete_with_documented_gaps','model':'scenes/stage05_city_medium.blend','saved_and_reopened_in_distinct_processes':True,'actual_renders':renders,'source_buildings':stats['counts']['active'],'built_buildings':geometry['counts']['buildings'],'source_height_statistics':stats['height_sources'],'ordinary_building_types':stats['types'],'sample_count':s['sample_count'],'default_visible_triangles_including_GN_instances':b['visible_default_triangles_including_GN_instances'],'runtime_medium_triangle_budget':1500000,'geometry_checks':{k:b[k] for k in ['nonfinite_coordinates','degenerate_triangles','invalid_material_indices','downward_building_roof_faces','building_ids_in_multiple_authoring_cells']},'placement_warnings':geometry['counts'],'not_passed_or_unknown':gaps,'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};write_json(root/'outputs/stage05_city_medium_acceptance.json',a)
 paths=[root/'scenes/stage05_city_medium.blend',root/'assets/buildings/stage05_modules.blend',*list((root/'data/processed/stage05').rglob('*')),*list((root/'work/reports/stage05').rglob('*')),*list((root/'work/previews/stage05').glob('*.png')),root/'outputs/stage05_city_medium_acceptance.json'];paths=[p for p in paths if p.name not in ['incremental.json','delivery_integrity.json']];items=inputs(root);write_json(root/'outputs/stage05_city_medium.manifest.json',{'stage':5,'status':'complete_with_documented_gaps','fingerprint':fingerprint(items),'inputs':items,'artifacts':artifacts(root,paths),'registered_from_actual_executed_steps':True});print('STAGE05_CHECKPOINT_REGISTERED_WITH_DOCUMENTED_GAPS',flush=True);return 0
def check(root,region,quality):
 if region!='city' or quality!='medium':print('未实现 / NOT IMPLEMENTED: stage05 only validated city/medium');return 3
 m=verify(root,root/'outputs/stage05_city_medium.manifest.json');assert m['fingerprint']==fingerprint(inputs(root)),'Stage05 inputs differ; preserve existing artifacts and rebuild affected inputs explicitly'
 a=json.loads((root/'outputs/stage05_city_medium_acceptance.json').read_text());assert a['saved_and_reopened_in_distinct_processes'];assert a['sample_count']>=20;assert a['default_visible_triangles_including_GN_instances']<=1500000;print('CHECK_PASSED_STAGE05_CHECKPOINT_WITH_DOCUMENTED_GAPS',a['built_buildings'],a['sample_count']);return 0
def execute(root,region,quality):
 if region!='city' or quality!='medium':print('未实现 / NOT IMPLEMENTED: stage05 only validated city/medium');return 3
 manifest=root/'outputs/stage05_city_medium.manifest.json'
 if manifest.exists():
  old=verify(root,manifest);now=fingerprint(inputs(root))
  if old['fingerprint']==now:print('INCREMENTAL_CACHE_VERIFIED: stage05 source assets, editable model and actual previews unchanged.');return check(root,region,quality)
  raise RuntimeError('Stage05 inputs changed. Preserve previous checkpoint before rebuilding the affected cells; no silent overwrite.')
 if (root/'scenes/stage05_city_medium.blend').exists():raise RuntimeError('Unregistered stage05 checkpoint exists; complete independent audits and register it before any rebuild')
 from stage05_osm import extract
 from stage05_data import enrich
 from stage05_refine import refine
 from stage05_geometry import build
 from stage05_views import prepare
 from stage05_reports import source_reports,model_reports,compare_saved_samples
 from stage05_registry import register as registry
 extract(root);enrich(root);refine(root)
 from stage05_semantics import fix as semantic_filter
 semantic_filter(root)
 index=root/'data/processed/stage05/mesh_index.json'
 if not index.exists():build(root)
 else:
  d=json.loads(index.read_text());assert d['source_sqlite_sha256']==digest(root/'data/processed/stage05/buildings.sqlite') and d['config_sha256']==digest(root/'config/stage05.yaml') and d['script_sha256']==digest(root/'scripts/stage05_geometry.py')
 source_stat=root/'work/reports/stage05/source_statistics.json'
 if source_stat.exists():
  a=json.loads(source_stat.read_text());b=json.loads((root/'work/reports/stage05/building_data.json').read_text());assert a['counts']['active']==b['active_buildings'] and a['height_sources']==b['height_sources'];assert digest(root/'data/processed/stage05/buildings.sqlite')==b['sqlite_sha256'];print('EXECUTED_SOURCE_STATISTICS_REUSED_FOR_VERIFIED_SQLITE',flush=True)
 else:source_reports(root)
 model_reports(root);prepare(root);registry(root)
 from stage05_urban_audit import audit as urban_audit
 urban_audit(root)
 common=['/usr/bin/blender','--background','--threads','4','--python-exit-code','1'];script=root/'scripts/stage05_blender.py';scene=root/'scenes/stage05_city_medium.blend';log=root/'work/logs/stage05/blender.log'
 run(root,common+[root/'scenes/stage04_city_medium.blend','--python',script,'--','--root',root,'--mode','build'],log,'SAVE_AND_EXIT')
 run(root,common+[scene,'--python',script,'--','--root',root,'--mode','check'],log,'REOPEN_AND_MEASURE')
 compare_saved_samples(root)
 run(root,common+[scene,'--python',script,'--','--root',root,'--mode','render'],log,'REOPEN_AND_RENDER')
 from stage05_compare_views import comparisons
 comparisons(root)
 if not (root/'work/reports/stage05/visual_inspection.json').exists():print('CHECKPOINT_RENDERED_VISUAL_REVIEW_PENDING: saved/reopened images require actual inspection before acceptance');return 4
 return register(root)
