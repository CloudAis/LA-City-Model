"""Phase09 source preservation, actual build orchestration and evidence registry."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
MANIFEST='outputs/stage09_city_medium.manifest.json'
ACCEPTANCE='outputs/stage09_city_medium_acceptance.json'
class Pending(RuntimeError):pass
def read(path):return json.loads((ROOT/path).read_text())
def sha(path):
 with Path(path).open('rb') as s:return hashlib.file_digest(s,'sha256').hexdigest()
def write(path,data):
 p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def require(test,message):
 if not test:raise RuntimeError(message)
def context():
 for name in ('PROJECT_SPEC.md','STATUS.md'):require(bool((ROOT/name).read_text().strip()),'Missing contract '+name)
def gate():
 from stage08 import check
 require(check(ROOT,'city','medium')==0,'Preserved source stage08 failed verification')
def fingerprint_inputs():
 paths={ROOT/p for p in ('config/stage09.json','requirements.lock','outputs/stage08_city_medium_acceptance.json','outputs/stage08_city_medium.manifest.json','data/processed/origin.json',
  'data/processed/stage03/medium/tile_index.json','data/processed/stage03/medium/water_index.json','data/processed/stage04/mesh_index.json','data/processed/stage04/roads.json','data/processed/stage04/road_profiles.npz','data/processed/stage05/mesh_index.json','data/processed/stage05/buildings.sqlite','data/processed/stage06/landmark_index.json','data/processed/stage07_final/index.json',
  'viewer/package.json','viewer/package-lock.json','viewer/index.html','viewer/tsconfig.json')}
 paths.update((ROOT/'scripts').glob('stage09*'))
 paths.update(p for p in (ROOT/'viewer/src').rglob('*') if p.is_file())
 paths.update((ROOT/'viewer').glob('*.mjs'))
 paths.update(p for p in (ROOT/'viewer/public').rglob('*') if p.is_file())
 for stage in ('stage03/medium','stage04','stage05'):
  paths.update(p for p in (ROOT/'data/processed'/stage).rglob('*.npz'))
 for landmark in read('data/processed/stage06/landmark_index.json')['landmarks']:paths.add(ROOT/landmark['card'])
 for path in paths:require(path.is_file(),'Missing phase09 reproducible input: '+str(path))
 return [{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in sorted(paths)]
def fp(rows):return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
def files_for_artifacts():
 paths={ROOT/'scenes/stage09_runtime_checkpoint.blend',ROOT/'viewer/start.sh',ROOT/'viewer/README.md'}
 for folder in ('outputs/stage09/resources','viewer/dist','work/reports/stage09','work/previews/stage09'):
  paths.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and 'in_progress' not in p.name)
 paths.update((ROOT/'docs').glob('stage09*.md'))
 paths.update((ROOT/'config').glob('stage09*.json'))
 portable=ROOT/'outputs/stage09_local_viewer.zip'
 if portable.exists():paths.add(portable)
 return sorted(paths)
def catalog_check():
 catalog=read('outputs/stage09/resources/manifest.json');require(len(catalog['landmarks'])==10,'Missing landmark entries')
 require(catalog['resources'],'No actual exported runtime resources')
 for r in catalog['resources']:
  p=ROOT/'outputs/stage09/resources'/r['url'];require(p.is_file() and sha(p)==r['sha256'],'Runtime resource changed; preserve edits: '+r['url'])
  require(all(k in r for k in ('origin_city_m','bounds_city_m','lod','feature_count','metadata_url','source_summary')),'Incomplete runtime resource metadata')
 return catalog
def verify():
 m=read(MANIFEST)
 for row in m['artifacts']:
  p=ROOT/row['path'];require(p.is_file() and sha(p)==row['sha256'],'Stage09 artifact changed; preserve edited file: '+row['path'])
 require(fp(fingerprint_inputs())==m['fingerprint'],'Stage09 source or configuration changed; retain accepted checkpoint before rebuild')
 return m
def register():
 context();gate()
 if (ROOT/MANIFEST).exists():verify();return 0
 required=('browser_check','streaming_check','gltf_validation','checkpoint','spatial_validation','performance','visual_inspection','portable_check')
 missing=[name for name in required if not (ROOT/'work/reports/stage09'/(name+'.json')).exists()]
 if missing:raise Pending('Actual phase09 evidence missing: '+', '.join(missing))
 catalog=catalog_check();browser=read('work/reports/stage09/browser_check.json');native=read('work/reports/stage09/checkpoint.json');visual=read('work/reports/stage09/visual_inspection.json');performance=read('work/reports/stage09/performance.json')
 require(browser['status']=='passed' and browser['actual_browser_executed'] is True and all(c['passed'] for c in browser['checks']),'Actual interaction/streaming/release checks have not passed')
 require(browser.get('catalog_sha256')==sha(ROOT/'outputs/stage09/resources/manifest.json'),'Browser check belongs to a different catalog')
 require(browser.get('viewer_build_fingerprint')==build_fingerprint(),'Browser check belongs to a different built viewer')
 require(native['status']=='passed' and native['actual_independent_reopen'] is True and native['actual_cpu_cycles_render'] is True,'Actual native checkpoint reopen/render missing')
 require(native['saved_checkpoint_sha256']==sha(ROOT/'scenes/stage09_runtime_checkpoint.blend'),'Native checkpoint changed after actual check')
 for name in ('gltf_validation','spatial_validation','portable_check','streaming_check'):require(read('work/reports/stage09/'+name+'.json')['status']=='passed','Actual '+name+' not passed')
 for sample in read('work/reports/stage09/gltf_validation.json')['samples']:
  resource=next(r for r in catalog['resources'] if r['id']==sample['resource'] and r['lod']==sample['lod'])
  require(sample['source_sha256']==resource['sha256'],'Decoded GLB validation belongs to an older resource: '+sample['resource'])
 if visual.get('status')!='accepted_with_documented_approximations' or visual.get('actual_images_viewed',0)<5:raise Pending('Actual final viewer/native image inspection is pending')
 require(visual.get('viewer_build_fingerprint')==build_fingerprint() and visual.get('catalog_sha256')==browser['catalog_sha256'],'Visual inspection belongs to a different build/catalog')
 for image in visual.get('images',[]):require(image.get('actual_view_image_inspection') is True and image['sha256']==sha(ROOT/image['path']),'Visual inspection image changed or was not actually viewed')
 require(read('work/reports/stage09/portable_check.json')['package_sha256']==sha(ROOT/'outputs/stage09_local_viewer.zip'),'Portable package changed after actual launch check')
 require(performance.get('actual_measurement_completed') is True,'Actual performance measurements missing')
 require(bool(performance.get('limits')),'Performance and device validation boundaries missing')
 timestamp=datetime.now(ZoneInfo('Asia/Singapore')).isoformat()
 accepted={'stage':9,'status':'operational_with_documented_limits','stage_gate_passed':True,'functional_acceptance_passed':True,
  'performance_target_30_fps_passed':performance.get('target_30_fps_met',False),'performance_report':'docs/stage09_performance.md',
  'viewer':'viewer/dist/index.html','launcher':'viewer/start.sh','portable_package':'outputs/stage09_local_viewer.zip',
  'catalog':'outputs/stage09/resources/manifest.json','runtime_resources':len(catalog['resources']),'checkpoint':'scenes/stage09_runtime_checkpoint.blend',
  'full_editable_source':'scenes/stage08_city_medium.blend','actual_browser_checks':'work/reports/stage09/browser_check.json','limits':visual.get('limits',[])+performance['limits'],
  'stage10_executed':False,'created_at':timestamp}
 inputs=fingerprint_inputs();artifacts=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files_for_artifacts()]
 write(ACCEPTANCE,accepted);artifacts.append({'path':ACCEPTANCE,'bytes':(ROOT/ACCEPTANCE).stat().st_size,'sha256':sha(ROOT/ACCEPTANCE)})
 write(MANIFEST,{'stage':9,'status':accepted['status'],'fingerprint':fp(inputs),'inputs':inputs,'artifacts':sorted(artifacts,key=lambda r:r['path']),'created_at':timestamp})
 print('STAGE09_ACTUAL_LOCAL_VIEWER_ACCEPTED',len(catalog['resources']),'RESOURCES;30FPS_TARGET',accepted['performance_target_30_fps_passed'],flush=True)
 return 0
def build_fingerprint():
 rows=[(str(p.relative_to(ROOT/'viewer/dist')),sha(p)) for p in sorted((ROOT/'viewer/dist').rglob('*')) if p.is_file()]
 return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
def command(args,label):
 p=ROOT/'work/logs/stage09'/label;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('a') as log:
  result=subprocess.run(list(map(str,args)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT);log.write('\nEXIT_CODE='+str(result.returncode)+'\n')
 require(result.returncode==0,'Actual phase09 command failed: '+str(p))
def supported(region,quality):
 if (region,quality)!=('city','medium'):
  print('未实现 / NOT IMPLEMENTED: stage09 pipeline validates city/medium; viewer has three runtime quality modes',flush=True);return False
 return True
def check(root,region,quality):
 if not supported(region,quality):return 3
 context();gate()
 if not (ROOT/MANIFEST).exists():print('STAGE09_ACTUAL_ACCEPTANCE_PENDING; exit4',flush=True);return 4
 verify();print('STAGE09_LOCAL_VIEWER_AND_RESOURCE_CACHE_VERIFIED; see actual performance limits',flush=True);return 0
def execute(root,region,quality,export_only=False):
 if not supported(region,quality):return 3
 context();gate()
 if (ROOT/MANIFEST).exists():return check(root,region,quality)
 if export_only and (ROOT/'outputs/stage09/resources/manifest.json').exists():
  catalog=catalog_check();print('STAGE09_ACTUAL_EXPORTS_VERIFIED',len(catalog['resources']),'no claim of final viewer acceptance');return 0
 if (ROOT/'outputs/stage09/resources/manifest.json').exists():return register()
 command(['blender','-b',ROOT/'scenes/stage08_city_medium.blend','--threads','4','--python-exit-code','1','--python',ROOT/'scripts/stage09_blender_extract.py'],'coordinator_extract.log')
 if not (ROOT/'viewer/node_modules/three/package.json').exists():command(['npm','ci','--prefix','viewer','--no-audit','--no-fund'],'coordinator_dependencies.log')
 command(['bash',ROOT/'scripts/stage09_build_runtime.sh'],'coordinator_runtime.log')
 command(['npm','run','build','--prefix','viewer'],'coordinator_build.log')
 raise Pending('Actual browser, native, performance and visual evidence must be completed before registration')
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('check','register','export','execute'),nargs='?',default='check');parser.add_argument('--region',default='city');parser.add_argument('--quality',default='medium');a=parser.parse_args()
 try:
  if a.action=='register':return register()
  if a.action=='check':return check(ROOT,a.region,a.quality)
  return execute(ROOT,a.region,a.quality,a.action=='export')
 except Pending as e:print('STAGE09_ACTUAL_ACCEPTANCE_PENDING:',e,file=sys.stderr);return 4
 except (OSError,ValueError,KeyError,RuntimeError) as e:print('STAGE09_FAILED:',e,file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
