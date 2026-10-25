"""Stage06 reproducible local-input pipeline and acceptance backed by actual evidence."""
from pathlib import Path
import datetime,hashlib,json,subprocess
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def inputs(root):
 paths=[root/'config/stage06.json',root/'config/stage03.yaml',root/'requirements.lock',root/'data/processed/origin.json',root/'data/processed/stage05/mesh_index.json',root/'data/processed/stage05/buildings.sqlite',root/'data/processed/stage05/osm_buildings.sqlite',root/'scenes/stage05_city_medium.blend',root/'data/processed/stage02/city_10m_dem_navd88_m.tif',root/'data/processed/stage02/downtown_1m_dem_navd88_m.tif',root/'data/processed/stage03/medium/tile_index.json',root/'data/processed/stage03/medium/water_index.json',root/'data/processed/stage04/mesh_index.json',root/'data/processed/stage04/road_floor_index.json',*sorted((root/'scripts').glob('stage06*.py')),*[root/'scripts'/n for n in ['stage02_io.py','stage03_common.py','stage03_surface.py','stage04_geometry.py']],*sorted(p for p in (root/'data/raw/stage06').rglob('*') if p.is_file())]
 paths += [root/'data/processed/scopes.geojson',root/'data/processed/stage02/city_boundary_2025.geojson',*sorted((root/'data/processed/stage04/ground').glob('*.npz'))]
 for m in json.loads((root/'data/processed/stage04/road_floor_index.json').read_text())['meshes']:paths.append(root/m['file'])
 ctx=root/'data/processed/stage06/context_index.json'
 if ctx.exists():
  for c in json.loads(ctx.read_text())['contexts']:
   for m in c['meshes']:
    if not m['source_file'].startswith('data/processed/stage06/'):paths.append(root/m['source_file'])
 ground=root/'data/processed/stage06/ground_index.json'
 if ground.exists():
  for t in json.loads(ground.read_text())['tiles']:
   paths.append(root/t['source_file']);v=root/'data/processed/stage04/ground'/(t['id']+'.npz')
   if v.exists():paths.append(v)
 import yaml
 c=yaml.safe_load((root/'config/stage03.yaml').read_text())
 for s in [c['surface']['landcover'],c['surface']['facilities'],c['water']['coastline_source'],c['water']['polygon_source'],'data/processed/stage03/selected_plan_landuse.geojson']:paths.append(root/s)
 return [{'path':str(p.relative_to(root)),'sha256':digest(p)} for p in sorted(set(paths))]
def fingerprint(items):return hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest()
def verify(root):
 m=json.loads((root/'outputs/stage06_city_medium.manifest.json').read_text())
 for a in m['artifacts']:
  p=root/a['path'];assert p.exists() and digest(p)==a['sha256'],'Artifact changed; preserve edits before rebuild: '+a['path']
 assert m['fingerprint']==fingerprint(inputs(root)),'Stage06 consumed inputs changed; preserve checkpoint and rebuild affected landmark/region explicitly'
 return m
def register(root=ROOT):
 a=json.loads((root/'work/reports/stage06/main_check.json').read_text());g=json.loads((root/'work/reports/stage06/glb_reimport.json').read_text());v=json.loads((root/'work/reports/stage06/visual_inspection.json').read_text());mass=json.loads((root/'work/reports/stage06/massing_visual_review.json').read_text());assert a['status']==g['status']=='passed' and a['saved_checkpoint_reopened_in_independent_process'] and g['actual_blender_import_count']==30;assert v['actual_images_viewed']==40 and mass['status']=='passed_with_documented_approximations'
 cfg=json.loads((root/'config/stage06.json').read_text());assets=[]
 for lm in cfg['landmarks']:
  ident=lm['id'];q=json.loads((root/'work/reports/stage06/assets'/(ident+'.json')).read_text());c=json.loads((root/'work/reports/stage06/contexts'/(ident+'.json')).read_text());assert q['status']==c['status']=='passed' and len(q['lods'])==3
  for view in ['front','side','top','environment']:
   path='work/previews/stage06/'+ident+'/'+view+'.png';assert digest(root/path)==v['images'][path]['sha256'],'Visual review stale: '+path
  assets.append({'id':ident,'status':'近似完成','status_code':'approximate_complete_with_documented_gaps','editable':'assets/landmarks/stage06/'+ident+'.blend','lods':q['lods'],'difference_card':'docs/landmarks/'+ident+'.md'})
 out={'stage':6,'status':'pipeline_complete_landmarks_approximate_with_documented_gaps','model':cfg['output_checkpoint'],'landmarks':assets,'verified_refinement_complete':0,'approximate_complete':10,'entire_landmark_missing':0,'saved_reopened_rendered':True,'actual_check_images':40,'mass_checkpoint':'scenes/stage06_massing.blend','glb_count':30,'glb_actual_reimports':30,'proxy_faces_remaining':a['removed_proxy_faces_remaining'],'proxy_module_points_remaining':a['removed_proxy_module_points_remaining'],'default_visible_triangles':a['actual_default_visible_triangles'],'source_accuracy_not_certified':True,'runtime_streaming_and_distance_switching':False,'limits':['complex shell/panel/roof/support profiles partly inferred','mixed reference years and unverified2025/26 renovation gaps','site grading/foundations/entrance details inferred; not engineering plans','full city inherited height/transport/interface limitations remain','static Blender alternatives and individual GLBs only; viewer stage09 not implemented'],'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};write_json(root/'outputs/stage06_city_medium_acceptance.json',out)
 paths=[root/cfg['output_checkpoint'],root/'scenes/stage06_massing.blend',*sorted((root/'scenes').glob('stage06_context_*.blend')),*sorted(p for folder in ['assets/landmarks/stage06','data/processed/stage06','work/previews/stage06','work/reports/stage06','docs/landmarks'] for p in (root/folder).rglob('*') if p.is_file()),*sorted((root/'docs').glob('stage06*.md')),*sorted((root/'outputs/stage06').rglob('*.glb')),root/'outputs/stage06_city_medium_acceptance.json'];excluded={'incremental.json','cli_gates.json','integrity.json','environment_final.json'};paths=[p for p in paths if p.name not in excluded];items=inputs(root);artifacts=[{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(set(paths))];write_json(root/'outputs/stage06_city_medium.manifest.json',{'stage':6,'status':out['status'],'inputs':items,'fingerprint':fingerprint(items),'artifacts':artifacts,'registered_from_actual_checks_and_visual_review':True});print('STAGE06_REGISTERED',len(artifacts),'10_APPROXIMATE_LANDMARKS',flush=True);return 0
def check(root,region,quality):
 if (region,quality)!=('city','medium'):print('未实现 / NOT IMPLEMENTED: stage06 validates city/medium; per-asset workers use --id');return 3
 verify(root);a=json.loads((root/'outputs/stage06_city_medium_acceptance.json').read_text());assert a['approximate_complete']==10 and a['actual_check_images']==40 and a['glb_actual_reimports']==30;print('CHECK_PASSED_STAGE06: 10 approximate landmarks; source/visual gaps documented');return 0
def run(root,command,label):
 p=root/'work/logs/stage06'/label;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w') as f:r=subprocess.run(list(map(str,command)),cwd=root,stdout=f,stderr=subprocess.STDOUT);f.write('\nEXIT_CODE='+str(r.returncode)+'\n')
 assert r.returncode==0,str(p);print(label+'_OK',flush=True)
def execute(root,region,quality):
 if (region,quality)!=('city','medium'):print('未实现 / NOT IMPLEMENTED: stage06 city/medium only');return 3
 if (root/'outputs/stage06_city_medium.manifest.json').exists():verify(root);print('INCREMENTAL_CACHE_VERIFIED_STAGE06');return check(root,region,quality)
 if (root/'assets/landmarks/stage06/us_bank_tower.blend').exists():
  if (root/'work/reports/stage06/visual_inspection.json').exists() and (root/'work/reports/stage06/main_check.json').exists():return register(root)
  print('STAGE06_UNREGISTERED_CHECKPOINT: complete independent render/GLB/city audits and actual image review; no silent overwrite. Detailed replay commands: docs/stage06.md');return 4
 from stage06_data import prepare
 from stage06_geometry import build
 assert (root/'data/processed/stage06/research_registry.json').exists(),'Frozen researched inputs missing; run stage06_research.py and review selected photos/source cards first'
 prepare(root);build(root,massing=True);common=['blender','--background','--threads','4','--python-exit-code','1'];worker=root/'scripts/stage06_blender.py';run(root,common+['--factory-startup','--python',worker,'--','--mode','massing-build'],'massing_build.log');run(root,common+[root/'scenes/stage06_massing.blend','--python',worker,'--','--mode','massing-check'],'massing_check.log');print('MASSING_REVIEW_PENDING: actual image inspection required before detailed construction; no success reported');return 4
if __name__=='__main__':register()
