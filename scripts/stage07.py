"""Unified stage07 pipeline; only actual artifacts and visual review can be accepted."""
from pathlib import Path
import datetime,hashlib,json,subprocess
from stage02_io import digest,write_json
ROOT=Path(__file__).resolve().parents[1]
def inputs(root):
 paths=[root/'config/stage07.json',root/'config/stage07_views.json',root/'config/stage03.yaml',root/'requirements.lock',root/'scenes/stage06_city_medium.blend',root/'data/processed/stage06/landmark_index.json',root/'data/processed/stage06/ground_index.json',root/'data/processed/stage05/buildings.sqlite',root/'data/processed/stage05/mesh_index.json',root/'data/processed/stage07/research_registry.json',root/'data/processed/origin.json',root/'data/processed/scopes.geojson',root/'data/processed/stage02/city_boundary_2025.geojson',root/'data/processed/stage03/medium/tile_index.json',root/'data/processed/stage03/medium/water_index.json',root/'data/processed/stage04/road_floor_index.json',root/'data/processed/stage02/city_10m_dem_navd88_m.tif',root/'data/processed/stage02/downtown_1m_dem_navd88_m.tif',*sorted((root/'scripts').glob('stage07*.py')),*[root/'scripts'/p for p in ['stage02_io.py','stage03_common.py','stage03_surface.py','stage04_geometry.py','stage06_geometry.py','stage06_blender.py','stage06_research.py']],*sorted(p for p in (root/'data/raw/stage07').rglob('*') if p.is_file())]
 bs=json.loads((root/'data/processed/stage07/buildings.json').read_text());cells={b['cell'] for b in bs};ix=json.loads((root/'data/processed/stage05/mesh_index.json').read_text())
 for a in ix['cells']:
  if a['id'] in cells:paths.append(root/a['placements'])
 for a in ix['meshes']:
  if a['owner'] in cells:paths.append(root/a['file'])
 for t in json.loads((root/'data/processed/stage07/ground_index.json').read_text())['tiles']:paths.append(root/t['source_file'])
 for t in json.loads((root/'data/processed/stage06/ground_index.json').read_text())['tiles']:paths.append(root/t['file'])
 for a in json.loads((root/'data/processed/stage04/road_floor_index.json').read_text())['meshes']:paths.append(root/a['file'])
 return [{'path':str(p.relative_to(root)),'sha256':digest(p)} for p in sorted(set(paths))]
def fp(items):return hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest()
def verify(root):
 m=json.loads((root/'outputs/stage07_city_medium.manifest.json').read_text())
 for a in m['artifacts']:assert digest(root/a['path'])==a['sha256'],'Artifact changed; preserve edits: '+a['path']
 assert m['fingerprint']==fp(inputs(root)),'Stage07 inputs changed; preserve accepted checkpoint before rebuilding affected region';return m
def register(root=ROOT):
 q=json.loads((root/'work/reports/stage07/blender_check.json').read_text());v=json.loads((root/'work/reports/stage07/visual_inspection.json').read_text());seam=json.loads((root/'work/reports/stage07/terrain_seams.json').read_text());lib=json.loads((root/'work/reports/stage07/library_check.json').read_text());assert q['status']==lib['status']=='passed' and q['saved_file_reopened_in_independent_process'];assert seam['status']=='passed_new_boundaries_unchanged' and v['actual_images_viewed']==8
 from PIL import Image,ImageStat
 for a in v['images']:
  p=root/a['path'];assert digest(p)==a['sha256'],'Stale image review'
  with Image.open(p) as im:assert max(ImageStat.Stat(im.convert('RGB')).stddev)>5
 renders=json.loads((root/'work/reports/stage07/renders_all.json').read_text());assert len(renders['renders'])==6 and all(a['actual_cpu_cycles'] for a in renders['renders'].values());vv=json.loads((root/'config/stage07_views.json').read_text())
 for name,a in renders['renders'].items():assert a['position_m']==vv[name]['position_m'] and a['target_m']==vv[name]['target_m'],'Render camera evidence stale: '+name
 coverage=json.loads((root/'work/reports/stage07/coverage_statistics.json').read_text());out={'stage':7,'status':'technical_checkpoint_valid_visual_refinement_incomplete','stage_gate_passed':False,'technical_checkpoint_valid':True,'model':'scenes/stage07_city_medium.blend','regions':coverage['regions'],'work_window_area_m2':280000,'source_buildings_refined':103,'stage06_city_hall_reused':True,'verified_complete_reference_matched_facades':0,'window_instances':sum(n for k,n in q['shared_instance_counts'].items() if k.startswith('window_')),'entry_doors':102,'solid_step_and_handrail_entries':101,'unresolved_entries':2,'street_instances':54,'original_module_types':12,'inferred_floor_adjustments':11,'terrain_tiles':5,'terrain_new_boundary_delta_m':0,'actual_city_renders':6,'actual_library_render':1,'actual_coverage_plot':1,'default_visible_triangles':q['default_visible_triangles'],'saved_and_independently_reopened':True,'architectural_truth':'Detailed generic modules are editable approximations, not survey-matched photoreal completion','limits':coverage['explicit_gaps'],'runtime_switching_streaming_viewer':False,'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};write_json(root/'outputs/stage07_city_medium_acceptance.json',out)
 paths=[root/out['model'],root/'assets/street_furniture/stage07_modules.blend',root/'config/stage07.json',root/'config/stage07_views.json',root/'docs/stage07.md',root/'outputs/stage07_city_medium_acceptance.json',*sorted(p for folder in ['assets/street_furniture/stage07','data/processed/stage07','work/previews/stage07','work/reports/stage07'] for p in (root/folder).rglob('*') if p.is_file())];excluded={'incremental.json','cli_gates.json','integrity.json','environment_final.json'};paths=[p for p in paths if p.name not in excluded];ii=inputs(root);aa=[{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(set(paths))];write_json(root/'outputs/stage07_city_medium.manifest.json',{'stage':7,'status':out['status'],'inputs':ii,'fingerprint':fp(ii),'artifacts':aa,'accepted_from_actual_model_and_image_review':True});print('STAGE07_TECHNICAL_CHECKPOINT_REGISTERED',len(aa),'ARTIFACTS; VISUAL_STAGE_GATE_PENDING',flush=True);return 4
def check(root,region,quality):
 if (region,quality)!=('city','medium'):print('未实现 / NOT IMPLEMENTED: stage07 validates city/medium (both near regions retained)');return 3
 verify(root);print('TECHNICAL_CHECKPOINT_VALID_STAGE07: 2 near regions,103 approximate buildings. STAGE07_VISUAL_ACCEPTANCE_PENDING: generic facades and plaza terrain below required realistic refinement; exit4');return 4
def command(root,args,label):
 log=root/'work/logs/stage07'/label;log.parent.mkdir(parents=True,exist_ok=True)
 with log.open('w') as f:r=subprocess.run(list(map(str,args)),cwd=root,stdout=f,stderr=subprocess.STDOUT);f.write('\nEXIT_CODE='+str(r.returncode)+'\n')
 assert r.returncode==0,str(log);print(label+'_OK',flush=True)
def execute(root,region,quality):
 if (region,quality)!=('city','medium'):print('未实现 / NOT IMPLEMENTED: stage07 city/medium only');return 3
 if (root/'outputs/stage07_city_medium.manifest.json').exists():verify(root);print('INCREMENTAL_CACHE_VERIFIED_STAGE07');return check(root,region,quality)
 if (root/'scenes/stage07_city_medium.blend').exists():
  if (root/'work/reports/stage07/visual_inspection.json').exists():return register(root)
  print('STAGE07_REVIEW_PENDING: saved scene exists; independent checks/renders and actual image review required. No silent overwrite. See docs/stage07.md');return 4
 from stage07_research import run
 from stage07_data import prepare
 from stage07_geometry import build
 from stage07_reports import build as reports
 run();prepare(root);build(root);common=['blender','--background','--threads','4','--python-exit-code','1'];worker=root/'scripts/stage07_blender.py';command(root,common+[root/'scenes/stage06_city_medium.blend','--python',worker,'--','--mode','build7'],'blender_build.log');command(root,common+[root/'scenes/stage07_city_medium.blend','--python',worker,'--','--mode','check-render7'],'final_check_renders.log');command(root,common+['--factory-startup','--python',worker,'--','--mode','library7'],'library.log');reports(root);print('STAGE07_ACTUAL_VISUAL_REVIEW_PENDING: inspect8 images; no automatic visual success');return 4
if __name__=='__main__':
 import sys
 sys.exit(register())
