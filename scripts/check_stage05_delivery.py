"""Exercise the real unified CLI, unchanged artifact reuse and workspace lock."""
from pathlib import Path
import sys,json,subprocess,fcntl,datetime
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage02_io import digest,write_json
ROOT=Path(__file__).resolve().parents[1]
def call(args,expected):
 p=subprocess.run([str(ROOT/'project'),*args],cwd=ROOT,capture_output=True,text=True);r={'args':args,'exit_code':p.returncode,'expected_exit':expected,'stdout':p.stdout.strip(),'stderr':p.stderr.strip()};assert p.returncode==expected,r;return r
def check():
 scene=ROOT/'scenes/stage05_city_medium.blend';paths=[scene,*[ROOT/'work/previews/stage05'/f'{name}.png' for name in json.load(open(ROOT/'config/stage05_views.json'))]];before={str(p.relative_to(ROOT)):digest(p) for p in paths};normal=call(['check','--stage','5','--region','city','--quality','medium'],0);replay=call(['run','--stage','5','--region','city','--quality','medium'],0);assert 'INCREMENTAL_CACHE_VERIFIED' in replay['stdout'];after={str(p.relative_to(ROOT)):digest(p) for p in paths};assert before==after;write_json(ROOT/'work/reports/stage05/incremental.json',{'status':'passed','actual_unified_check':normal,'actual_unified_run':replay,'sha256_before':before,'sha256_after':after,'model_and_all_seven_renders_unchanged':True,'not_a_cold_rebuild_test':True})
 gates=[]
 for stage in range(6,11):
  for action in ['run','check']:gates.append(call([action,'--stage',str(stage),'--region','city','--quality','medium'],3))
 for args in [['export','--stage','5','--region','city','--quality','medium'],['run','--stage','5','--region','downtown','--quality','medium'],['run','--stage','5','--region','city','--quality','low'],['run','--stage','5','--region','city','--quality','high']]:gates.append(call(args,3))
 with (ROOT/'work/cache/project-build.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);busy=call(['run','--stage','5','--region','city','--quality','medium'],75);fcntl.flock(lock,fcntl.LOCK_UN)
 write_json(ROOT/'work/reports/stage05/cli_gates.json',{'status':'passed','unimplemented_cases':gates,'unimplemented_case_count':len(gates),'workspace_lock':busy,'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()});print('STAGE05_UNIFIED_CHECK_CACHE_AND_14_UNIMPLEMENTED_GATES_PASSED_LOCK75',flush=True)
if __name__=='__main__':check()
