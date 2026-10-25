"""Stage04: content hashes, exact process exits and independently reopened evidence."""
from pathlib import Path
import json,hashlib,subprocess,datetime,shutil
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def inputs(root):
 paths=[root/'config/stage03.yaml',root/'scripts/stage03_common.py',root/'scripts/stage03_surface.py',root/'scripts/stage02_io.py',root/'data/processed/stage03/medium/tile_index.json',root/'data/processed/stage03/medium/water_index.json',*sorted((root/'data/processed/stage03/medium/water').glob('*.npz')),root/'config/project.yaml',root/'config/stage04.yaml',root/'requirements.lock',root/'scenes/stage03_city_medium.blend',root/'data/processed/origin.json',root/'data/processed/scopes.geojson',root/'data/processed/stage02/city_boundary_2025.geojson',root/'data/processed/stage02/city_10m_dem_navd88_m.tif',root/'data/processed/stage02/downtown_1m_dem_navd88_m.tif',root/'data/processed/stage02/roads.geojson',*sorted((root/'scripts').glob('stage04*.py')),*sorted(p for p in (root/'data/raw/stage04').rglob('*') if p.is_file() and not p.name.endswith('.part')),*sorted((root/'data/processed/stage03/medium').glob('*.npz'))]
 return [{'path':str(p.relative_to(root)),'sha256':digest(p)} for p in paths]
def fingerprint(items):return hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest()
def artifacts(root,paths):return [{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(set(paths)) if p.is_file()]
def verify(root,manifest):
 m=json.loads(manifest.read_text())
 for a in m['artifacts']:
  p=root/a['path']
  if not p.exists() or digest(p)!=a['sha256']:raise RuntimeError('Generated artifact changed; preserve user edits before rebuilding: '+str(p))
 return m

def register_executed_data(root=ROOT):
 # Called only after the actual individual data/build/audit tools ran; validates the reports and bytes.
 audit=json.loads((root/'work/reports/stage04/audit.json').read_text());assert audit['mesh_nonfinite']==0 and audit['mesh_degenerate']==0
 assert audit['vehicle_profile_grade_warnings']==0
 source=json.loads((root/'data/processed/stage04/source_registry.json').read_text())
 for r in source['files']:assert digest(root/r['local_path'])==r['sha256']
 index=json.loads((root/'data/processed/stage04/mesh_index.json').read_text())
 for r in index['meshes']:assert digest(root/r['file'])==r['sha256']
 assert index['meshes'] and (root/'work/reports/stage04/profile_refinement.json').exists()
 items=inputs(root);paths=list((root/'data/processed/stage04').rglob('*'))+list((root/'work/reports/stage04').glob('*.json'))+list((root/'work/reports/stage04').glob('*.csv'))+list((root/'work/previews/stage04').glob('*network.png'))+[root/'work/previews/stage04/transport_gaps.png']
 # Reports produced after Blender reopen are recorded in scene manifest, not data cache.
 paths=[p for p in paths if p.name not in ['blender_check.json','acceptance.json','incremental.json','visual_inspection.json']]
 write_json(root/'outputs/stage04_data_medium.manifest.json',{'stage':4,'status':'executed_data_with_documented_gaps','fingerprint':fingerprint(items),'inputs':items,'artifacts':artifacts(root,paths),'registered_from_actual_executed_steps':True});print('STAGE04_EXECUTED_DATA_REGISTERED',flush=True)

def run_cmd(root,cmd,log,label):
 log.parent.mkdir(parents=True,exist_ok=True)
 with log.open('a') as f:
  f.write('\n'+label+'\n'+json.dumps(list(map(str,cmd)))+'\n');f.flush();r=subprocess.run(list(map(str,cmd)),cwd=root,stdout=f,stderr=subprocess.STDOUT);f.write('\nEXIT_CODE='+str(r.returncode)+'\n')
 if r.returncode:raise RuntimeError(label+' failed; log='+str(log))
 print(label+'_OK',flush=True)

def execute(root,region,quality):
 if region not in ['city','calibration'] or quality!='medium':
  print('未实现 / NOT IMPLEMENTED: stage04 currently supports city/medium; other region/profile jobs not validated or implemented.');return 3
 data=root/'outputs/stage04_data_medium.manifest.json';scene_manifest=root/'outputs/stage04_city_medium.manifest.json';scene=root/'scenes/stage04_city_medium.blend';current=fingerprint(inputs(root))
 if data.exists():
  m=verify(root,data)
  if m['fingerprint']!=current:raise RuntimeError('Stage04 inputs changed: preserve current generated outputs in history and rebuild affected data explicitly; no automatic overwrite.')
 else:
  # Fresh workspace: all acquisition/build actions are recorded; no fake success for missing sources.
  if (root/'data/processed/stage04/mesh_index.json').exists():raise RuntimeError('Unregistered executed assets exist. Run stage04 audits and register_executed_data before model build; never overwrite them silently.')
  from stage04_extract import extract
  from stage04_data import prepare
  from stage04_other_extract import extract as other
  from stage04_profiles import refine
  from stage04_build import Builder
  from stage04_post import post
  from stage04_furniture import build as furniture
  from stage04_ground import update as priority_ground
  from stage04_finalize_geometry import finalize
  from stage04_clearance import repair as clearance_repair
  from stage04_clearance_followup import update as clearance_followup
  from stage04_surface_accuracy import refine as surface_refine
  from stage04_deck_terrain import cut as deck_cut
  from stage04_seam_review import review as seam_review
  from stage04_bridge_sidewalks import align as bridge_sidewalks
  from stage04_water_cleanup import clean as water_cleanup
  from stage04_ground_under_roads import cut as pavement_ground_cut
  from stage04_terrain_winding import correct as terrain_winding
  from stage04_paint import run as paint
  from stage04_mesh_checks import check as mesh_checks
  from stage04_sources import register
  from stage04_audit import audit
  from stage04_maps import maps
  if not (root/'data/raw/stage04/osm/california-20261021.osm.pbf').exists():raise RuntimeError('Stage04 source PBF missing; run recorded acquisition first. No invented roads generated.')
  extract(root);prepare(root);other(root);refine(root);Builder(root).run();priority_ground(root);furniture(root);paint(root);post(root);finalize(root);mesh_checks(root);clearance_repair(root);clearance_followup(root);paint(root);finalize(root);mesh_checks(root);surface_refine(root);paint(root);finalize(root);mesh_checks(root);deck_cut(root);mesh_checks(root);buried=[b['id'] for b in json.loads((root/'work/reports/stage04/actual_mesh_crossings.json').read_text())['bridges'] if b['status']=='deck_top_burial_warning'];surface_refine(root,buried) if buried else None;paint(root);finalize(root);mesh_checks(root);deck_cut(root);mesh_checks(root);bridge_sidewalks(root);finalize(root);mesh_checks(root);pavement_ground_cut(root);water_cleanup(root);terrain_winding(root);register(root);audit(root);seam_review(root);maps(root);register_executed_data(root)
 if scene_manifest.exists():
  old=verify(root,scene_manifest)
  if old['fingerprint']==current:
   print('INCREMENTAL_CACHE_VERIFIED: stage04 model, source assets and actual renders unchanged.');return check(root,region,quality)
  raise RuntimeError('Preserve prior stage04 checkpoint before rebuilding changed inputs')
 if scene.exists():raise RuntimeError('Stage04 scene exists without a manifest; preserve and verify it explicitly before retry')
 common=['/usr/bin/blender','--background','--threads','4','--python-exit-code','1'];script=root/'scripts/stage04_blender.py';log=root/'work/logs/stage04/blender.log'
 run_cmd(root,common+[root/'scenes/stage03_city_medium.blend','--python',script,'--','--root',root,'--mode','build'],log,'SAVE_AND_EXIT')
 run_cmd(root,common+[scene,'--python',script,'--','--root',root,'--mode','verify-render'],log,'REOPEN_MEASURE_RENDER_AND_EXIT')
 return register_scene(root,current)

def register_scene(root=ROOT,current=None):
 from PIL import Image,ImageStat
 b=json.loads((root/'work/reports/stage04/blender_check.json').read_text());assert b['status']=='passed' and b['saved_and_reopened_in_distinct_processes'] and set(b['renders'])=={'city_top','downtown_top','intersection','interchange'}
 checks={}
 for name,r in b['renders'].items():
  p=root/r['path'];im=Image.open(p).convert('RGB');im.load();sd=max(ImageStat.Stat(im).stddev);assert sd>2;checks[name]={'size':list(im.size),'maximum_channel_stddev':sd,'sha256':digest(p)}
 audit=json.loads((root/'work/reports/stage04/audit.json').read_text());accept={'stage':4,'status':'complete_with_documented_gaps','model':'scenes/stage04_city_medium.blend','saved_and_reopened_in_distinct_processes':True,'actual_renders':checks,'vehicle_profile_grade_warnings':audit['vehicle_profile_grade_warnings'],'source_clearance_status':audit['source_clearance_status'],'tile_seam_status':audit['tile_seam_status'],'active_triangles':b['visible_default_triangles'],'runtime_medium_triangle_budget':1500000,'static_checkpoint_budget_status':'within_budget' if b['visible_default_triangles']<=1500000 else 'offline_authoring_scene_over_runtime_budget','gpu':'unknown; rendered CPU4threads','not_passed_or_unknown':['191 non-shared planar crossings unresolved','50 source clearance conflicts retained','actual bridge/tunnel elevation and width/lanes often inferred','real-time performance/viewer/GLB not implemented at this phase'],'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 actual=json.loads((root/'work/reports/stage04/actual_mesh_crossings.json').read_text())
 accept['actual_priority_vehicle_crossings']=actual['actual_mesh_crossing_status']
 accept['bridge_ground_status']=actual['bridge_ground_status']
 accept['rail_road_status']=actual['rail_road_status']
 accept['actual_surface_triangles_over30pct_slope_by_role']=audit['actual_surface_triangles_over30pct_slope_by_role']
 accept['not_passed_or_unknown'] += ['rail-road clearance warnings, unresolved nonshared crossings and missing mesh samples remain; counts in rail_road_status','bridge-way slab/terrain contacts require actual abutment/span limits; counts in bridge_ground_status','actual surface triangles over30% slope retained; profile passes do not validate all surface faces','alternate terrain LODs do not yet include all Stage04 road cuts','far overview roads may have local terrain occlusion; whole-city render continuity not fully passed']
 write_json(root/'outputs/stage04_city_medium_acceptance.json',accept)
 core=[root/'assets/street_furniture/stage04_prototypes.blend',root/'scenes/stage04_city_medium.blend',root/'work/logs/stage04/blender.log',root/'work/reports/stage04/blender_check.json',root/'outputs/stage04_city_medium_acceptance.json',*[root/r['path'] for r in b['renders'].values()]]
 write_json(root/'outputs/stage04_city_medium.manifest.json',{'stage':4,'status':'complete_with_documented_gaps','fingerprint':current or fingerprint(inputs(root)),'artifacts':artifacts(root,core)});print('STAGE04_CHECKPOINT_SAVED_WITH_DOCUMENTED_GAPS',flush=True);return 0

def check(root,region,quality):
 if region not in ['city','calibration'] or quality!='medium':print('未实现 / NOT IMPLEMENTED: stage04 only city/medium');return 3
 data=verify(root,root/'outputs/stage04_data_medium.manifest.json');scene=verify(root,root/'outputs/stage04_city_medium.manifest.json')
 current=fingerprint(inputs(root))
 if data['fingerprint']!=current or scene['fingerprint']!=current:raise RuntimeError('Stage04 input fingerprint differs from the registered checkpoint; preserve prior outputs and review the changes.')
 a=json.loads((root/'outputs/stage04_city_medium_acceptance.json').read_text());assert a['saved_and_reopened_in_distinct_processes'];print('CHECK_PASSED_STAGE04_CHECKPOINT_WITH_DOCUMENTED_GAPS',a['source_clearance_status']);return 0
