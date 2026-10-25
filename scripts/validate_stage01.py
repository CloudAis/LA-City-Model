"""Acceptance regression: future tasks must fail explicitly, never report fake success."""
import json
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[1]
for name in ['PROJECT_SPEC.md','STATUS.md']:(root/name).read_text()
cases=[]
for stage in range(5,11):
    cases.append((['run','--stage',str(stage),'--region','downtown','--quality','medium'],3,'未实现'))
cases += [(['export','--stage','1'],3,'未实现'),
          (['run','--stage','1','--region','does_not_exist'],2,'invalid choice'),
          (['run','--stage','11'],2,'invalid choice')]
results=[]
for args,expected,token in cases:
    p=subprocess.run([str(root/'project'),*args],cwd=root,text=True,capture_output=True,timeout=20)
    result={'args':args,'expected_exit_code':expected,'actual_exit_code':p.returncode,
            'stdout':p.stdout,'stderr':p.stderr,
            'passed':p.returncode==expected and token in p.stdout+p.stderr}
    results.append(result)
report={'status':'passed' if all(r['passed'] for r in results) else 'failed',
        'executed_cases':len(results),'passed_cases':sum(r['passed'] for r in results),'results':results}
(root/'work/reports/entrypoint_tests.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(f"ENTRYPOINT_TESTS: {report['passed_cases']}/{len(results)} passed")
raise SystemExit(0 if report['status']=='passed' else 1)
