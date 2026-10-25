"""Final handoff registry: real evidence, immutable hashes and explicit partial fidelity."""
from pathlib import Path
import argparse,hashlib,json,sys
from datetime import datetime
from zoneinfo import ZoneInfo
from stage10_common import *
MANIFEST=ROOT/'outputs/stage10_delivery.manifest.json'
REQUIRED=('geography','administrative_scope_check','runtime_geometry_after','runtime_repairs','master_geometry','native_lighting','showcase','spatial_validation','config_rebuild','glb_blank_scene_check','gltf_validation','landmark_native','browser_check','video','command_checks','portable_check','visual_review','environment','performance','build_parity','license_pack')
def context():
 for file in ('PROJECT_SPEC.md','STATUS.md'):
  if not (ROOT/file).read_text().strip():raise RuntimeError('Missing project contract/state')
def input_files():
 paths=set((ROOT/'scripts').glob('stage10*'));paths.update((ROOT/'config').glob('stage10*.json'));paths.add(ROOT/'requirements.lock');paths.add(ROOT/'outputs/stage09_city_medium.manifest.json')
 paths.update(p for p in (DELIVERY/'viewer/source').rglob('*') if p.is_file() and not {'node_modules','dist'}&set(p.relative_to(DELIVERY/'viewer/source').parts))
 return sorted(p for p in paths if p.is_file())
def fingerprint():return [{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in input_files()]
def artifact_files():
 paths={p for p in DELIVERY.rglob('*') if p.is_file() and 'node_modules' not in p.parts and '__pycache__' not in p.parts and p.name!='DELIVERY_MANIFEST.json'}
 paths.update(p for p in REPORTS.glob('*.json') if 'in_progress' not in p.name)
 paths.update((ROOT/'outputs').glob('LA_*_1.0.zip'));return sorted(paths)
def verify():
 m=json.loads(MANIFEST.read_text())
 for row in m['artifacts']:
  p=ROOT/row['path']
  if not p.is_file() or sha(p)!=row['sha256']:raise RuntimeError('Changed/missing accepted file; preserve user edits: '+row['path'])
 if fingerprint()!=m['inputs']:raise RuntimeError('Final scripts/config/source changed; preserve accepted delivery before rebuilding')
 return m
def evidence():
 missing=[n for n in REQUIRED if not (REPORTS/(n+'.json')).exists()]
 if missing:print('STAGE10_ACCEPTANCE_PENDING_ACTUAL_EVIDENCE:',','.join(missing));return None
 reports={n:read('work/reports/stage10/'+n+'.json') for n in REQUIRED}
 for n in ('administrative_scope_check','runtime_geometry_after','spatial_validation','glb_blank_scene_check','gltf_validation','landmark_native','browser_check','video','command_checks','portable_check','environment','license_pack'):assert reports[n]['status']=='passed',(n,reports[n].get('status'))
 native=reports['master_geometry'];assert native['master_sha256']==sha(DELIVERY/'LA_Master.blend') and native['nonfinite_values']==0 and native['exact_zero_area_native_triangles']==0 and native['removed_proxies_remaining_faces']==0
 assert len(reports['showcase']['images'])>=48 and len({i['view'] for i in reports['showcase']['images']})>=12
 assert len(reports['native_lighting']['images'])==4 and len(reports['landmark_native']['independent_editable_assets'])==10
 for row in reports['showcase']['images']+reports['native_lighting']['images']:
  assert row['width']>=1920 and row['height']>=1080 and row['sha256']==sha(DELIVERY/row['path'])
 browser=reports['browser_check'];assert browser['status']=='passed' and all(r['passed'] for r in browser['checks'])
 assert browser['catalog_sha256']==sha(DELIVERY/'tiles/manifest.json')
 rows=[(str(p.relative_to(DELIVERY/'viewer/dist')),sha(p)) for p in sorted((DELIVERY/'viewer/dist').rglob('*')) if p.is_file()];fp=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest();assert fp==browser['viewer_build_fingerprint']
 assert reports['build_parity']['current_source_build_files_match_production'] is True
 assert reports['portable_check']['package_sha256']==sha(ROOT/'outputs/LA_Local_Private_Viewer_1.0.zip')
 assert reports['visual_review']['status']=='reviewed_with_documented_visual_limits' and reports['visual_review']['actual_scene_images_reviewed']>=52
 assert reports['performance']['status']=='actual_measurement_completed'
 return reports
def register():
 context()
 if MANIFEST.exists():verify();print('STAGE10_ACCEPTED_HANDOFF_CACHE_VERIFIED_OVERALL_PARTIAL');return 0
 reports=evidence()
 if reports is None:return 4
 from stage09 import check
 if check(ROOT,'city','medium')!=0:raise RuntimeError('Prior accepted stage09 preservation failed')
 package=read('work/reports/stage10/viewer_package.json');performance=reports['performance']
 acceptance={'version':'1.0.0','stage':10,'status':'部分通过','delivery_workflow_status':'通过','all_ten_original_fidelity_goals_passed':False,'directory':'outputs/LA_Delivery','master':'outputs/LA_Delivery/LA_Master.blend','viewer_private_zip':package['path'],'cleared_subset_zip':'outputs/LA_Original_Materials_And_Tools_1.0.zip','performance_mean_fps':performance['tour_fps'],'initial_native1080p30fps_passed':False,'actual_final_visual_limits_preserved':True,'actual_views':12,'actual_four_light_viewport_images':48,'actual_four_light_native_images':4,'video':'outputs/LA_Delivery/video/city_tour.mp4','report':'outputs/LA_Delivery/docs/FINAL_ACCEPTANCE.md','created_at':datetime.now(ZoneInfo('Asia/Singapore')).isoformat()}
 write('outputs/stage10_delivery_acceptance.json',acceptance)
 artifacts=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in artifact_files()]
 artifacts.append({'path':'outputs/stage10_delivery_acceptance.json','bytes':(ROOT/'outputs/stage10_delivery_acceptance.json').stat().st_size,'sha256':sha(ROOT/'outputs/stage10_delivery_acceptance.json')})
 manifest={'version':'1.0.0','stage':10,'overall_result':'部分通过','delivery_workflow_result':'通过','inputs':fingerprint(),'artifacts':artifacts,'created_at':acceptance['created_at']};MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 delivery_rows=[{'path':str(p.relative_to(DELIVERY)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(DELIVERY.rglob('*')) if p.is_file() and 'node_modules' not in p.parts and '__pycache__' not in p.parts and p.name!='DELIVERY_MANIFEST.json']
 inner=DELIVERY/'metadata/DELIVERY_MANIFEST.json';inner.write_text(json.dumps({'version':'1.0.0','overall_result':'部分通过','local_handoff_not_blanket_redistribution_license':True,'files':delivery_rows},ensure_ascii=False,indent=2)+'\n')
 manifest['artifacts'].append({'path':str(inner.relative_to(ROOT)),'bytes':inner.stat().st_size,'sha256':sha(inner)});MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print('FINAL_ACTUAL_HANDOFF_REGISTERED_OVERALL_PARTIAL',len(manifest['artifacts']),flush=True);return 0
def supported(region,quality):
 if (region,quality)!=('city','medium'):print('未实现 / NOT IMPLEMENTED: stage10 pipeline accepts city/medium; local viewer has three runtime qualities');return False
 return True
def check(root,region,quality):
 if not supported(region,quality):return 3
 context()
 if not MANIFEST.exists():print('STAGE10_ACTUAL_ACCEPTANCE_PENDING');return 4
 verify();print('STAGE10_FINAL_DELIVERY_VERIFIED; overall partially passed, see FINAL_ACCEPTANCE.md');return 0
def execute(root,region,quality,export_only=False):
 if not supported(region,quality):return 3
 return check(root,region,quality) if MANIFEST.exists() else register()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['check','register'],nargs='?',default='check');a=p.parse_args()
 try:sys.exit(register() if a.action=='register' else check(ROOT,'city','medium'))
 except Exception as e:print('STAGE10_FAILED:',str(e),file=sys.stderr);sys.exit(1)
