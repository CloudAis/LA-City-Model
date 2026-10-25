"""Prepare an independent local handoff tree using immutable content hardlinks."""
import json,shutil,os
from importlib.metadata import version
from stage10_common import *
for folder in ('tiles','landmarks','assets','viewer','previews','video','metadata','scripts','docs','config','sample_inputs'):(DELIVERY/folder).mkdir(parents=True,exist_ok=True)
link_tree(ROOT/'assets',DELIVERY/'assets')
for name in ('stage07_city_medium.blend','stage07_final.blend'):retain_link(ROOT/'scenes'/name,DELIVERY/'assets/linked'/name)
for p in (ROOT/'assets/landmarks/stage06').glob('*.blend'):retain_link(p,DELIVERY/'landmarks'/p.name)
link_tree(ROOT/'outputs/stage09/resources',DELIVERY/'tiles')
# The catalog will be updated independently if final audit repairs a tile.
p=DELIVERY/'tiles/manifest.json';p.unlink();shutil.copy2(ROOT/'outputs/stage09/resources/manifest.json',p)
for source in ('src','public'):
 target=DELIVERY/'viewer/source'/source
 if target.exists():shutil.rmtree(target)
 shutil.copytree(ROOT/'viewer'/source,target)
for name in ('package.json','package-lock.json','tsconfig.json','index.html'):shutil.copy2(ROOT/'viewer'/name,DELIVERY/'viewer/source'/name)
node_modules=DELIVERY/'viewer/source/node_modules'
if not node_modules.exists():node_modules.symlink_to(ROOT/'viewer/node_modules',target_is_directory=True)
source=DELIVERY/'viewer/source/src/main.ts';s=source.read_text();needle='snapshot,setView:(id:string)';assert needle in s;s=s.replace(needle,'snapshot,setInspectionCamera:(view:View)=>setView(view),setView:(id:string)');source.write_text(s)
for name in ('package.json','package-lock.json','tsconfig.json','index.html'):assert (DELIVERY/'viewer/source'/name).exists()
link_tree(ROOT/'docs',DELIVERY/'docs/history')
for stage in ('stage02','stage04','stage05','stage06'):
 retain_link(ROOT/'data/processed'/stage/'source_registry.json',DELIVERY/'metadata/source_registry'/('source_'+stage+'.json'))
for name in ('origin.json','scopes.geojson'):retain_link(ROOT/'data/processed'/name,DELIVERY/'metadata'/name)
for file in ('coordinate_system.json','control_points.json'):retain_link(ROOT/'data/processed/stage03'/file,DELIVERY/'metadata'/file)
retain_link(ROOT/'data/processed/stage03/medium/tile_index.json',DELIVERY/'metadata/terrain_tile_index.json')
retain_link(ROOT/'data/processed/stage06/landmark_index.json',DELIVERY/'metadata/landmark_index.json')
for p in (ROOT/'data/processed/stage06/cards').glob('*.json'):retain_link(p,DELIVERY/'metadata/landmark_cards'/p.name)
for p in (ROOT/'config').glob('*.json'):retain_link(p,DELIVERY/'config/history'/p.name)
retain_link(ROOT/'requirements.lock',DELIVERY/'scripts/requirements.lock')
(DELIVERY/'scripts/requirements-sample.txt').write_text('numpy=='+version('numpy')+'\n')
shutil.copy2(ROOT/'scripts/stage09_glb.py',DELIVERY/'scripts/glb_writer.py')
idx=read('data/processed/stage09/extracted/index.json');rows=[r for r in idx['objects'] if r['id']=='building:960933' and r['lod']==0]
selected=[]
for r in rows:
 target=DELIVERY/'sample_inputs'/Path(r['file']).name;retain_link(ROOT/r['file'],target);selected.append(dict(r,file='sample_inputs/'+target.name))
materials={name:idx['materials'][name] for r in rows for name in r['materials']}
write('outputs/LA_Delivery/sample_inputs/index.json',{'objects':selected,'materials':materials,'origin_city_m':rows[0]['origin_city_m'],'source_id':'lariac6:485890839707','source_year':2008,'interpretation':'Actual source08 editable geometry; inferred façade, unverified imported height. Local-use source dependency, not a new surveyed asset.'})
write('outputs/LA_Delivery/config/sample.json',{'include_window_frames':True,'roughness_multiplier':1.0,'seed':20261021,'output':'tiles/rebuild/sample.glb'})
server=(ROOT/'scripts/stage09_server.py').read_text().replace('ROOT=Path(__file__).resolve().parents[1]','ROOT=Path(__file__).resolve().parent').replace("ROOT/'outputs/stage09/resources'","ROOT/'tiles'").replace("ROOT/'viewer/dist'","ROOT/'viewer/dist'").replace("ROOT/'outputs/stage09/resources/manifest.json'","ROOT/'tiles/manifest.json'")
server=server.replace("'stage':9","'stage':10").replace("'LA_LOCAL_VIEWER","'LA_FINAL_VIEWER")
(DELIVERY/'start.py').write_text(server);(DELIVERY/'start.bat').write_text('@echo off\r\ncd /d "%~dp0"\r\npy -3 start.py %*\r\n')
write('work/reports/stage10/preparation.json',{'status':'prepared_requires_master_and_actual_checks','delivery_path':str(DELIVERY),'immutable_files_hardlinked_for_disk_budget':True,'portable_tree_does_not_require_original_absolute_paths_for_runtime':True,'node_modules_symlink_development_only_not_in_archive':True,'free_bytes':shutil.disk_usage(ROOT).free})
print('FINAL_LOCAL_TREE_PREPARED',DELIVERY,flush=True)
