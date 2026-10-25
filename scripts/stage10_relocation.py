"""Real relocated tree + direct documented Blender command, with exact local files."""
import os,shutil,subprocess,time
from stage10_common import *
clone=ROOT/'work/cache/stage10/relocated_delivery';assert not clone.exists(),'Preserve previous relocation test before a new one';clone.mkdir(parents=True)
for path in DELIVERY.rglob('*'):
 if not path.is_file() or 'node_modules' in path.parts:continue
 target=clone/path.relative_to(DELIVERY);target.parent.mkdir(parents=True,exist_ok=True);os.link(path,target)
command=['blender','-b',str(clone/'LA_Master.blend'),'--threads','4','--python-exit-code','1','--python',str(clone/'scripts/inspect_scene.py'),'--','--check-resources','--view','civic_street','--export-id','landmark:city_hall','--output','tiles/rebuild/selected_city_hall.glb']
with (ROOT/'work/logs/stage10/relocated_blender.log').open('w') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
if result.returncode:raise RuntimeError('Actual relocated Blender command failed; retained tree and log')
resource=json.loads((clone/'metadata/resource_paths_smoke.json').read_text());export=json.loads((clone/'tiles/rebuild/selected_city_hall.check.json').read_text());assert resource['status']==export['status']=='passed'
for name in ('selected_city_hall.glb','selected_city_hall.check.json'):retain_link(clone/'tiles/rebuild'/name,DELIVERY/'tiles/rebuild'/name)
write('work/reports/stage10/command_checks.json',{'status':'passed','actual_command':command,'exit_code':result.returncode,'clean_relocated_master_and_dependencies':resource,'selected_export_and_blank_reimport':export,'source_and_final_trees_do_not_require_absolute_original_model_paths':True,'whole_network_cold_rebuild_tested':False})
shutil.rmtree(clone);print('ACTUAL_RELOCATED_MASTER_AND_DOCUMENTED_EXPORT_COMMAND_PASSED',flush=True)
