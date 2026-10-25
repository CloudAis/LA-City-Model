"""Freeze accepted stage06 and mutable contracts before stage07; never duplicate big data."""
from pathlib import Path
import hashlib,json,os,shutil
ROOT=Path(__file__).resolve().parents[1]
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def freeze():
 r=ROOT;m=json.loads((r/'outputs/stage06_city_medium.manifest.json').read_text());paths={a['path'] for a in m['artifacts']}|{i['path'] for i in m['inputs']}|{'outputs/stage06_city_medium.manifest.json','work/reports/stage06/incremental.json','work/reports/stage06/cli_gates.json','work/reports/stage06/environment_final.json','scripts/freeze_stage06.py','scripts/project.py','project','AGENTS.md','PROJECT_SPEC.md','STATUS.md','README.md','config/project.yaml','docs/sources.md','docs/coordinates.md'};rows=[];dst=r/'work/history/stage06_before_stage07';linked=copied=0
 for name in sorted(paths):
  p=r/name;assert p.is_file(),name;checksum=sha(p);q=dst/name;q.parent.mkdir(parents=True,exist_ok=True)
  if q.exists():assert sha(q)==checksum,name
  elif name.startswith(('data/','assets/','scenes/','outputs/')):os.link(p,q);linked+=1
  else:shutil.copy2(p,q);copied+=1
  assert sha(q)==checksum,name;rows.append(checksum+'  '+name)
 (r/'outputs/stage06_files.sha256').write_text('\n'.join(rows)+'\n');shutil.copy2(r/'outputs/stage06_files.sha256',dst/'stage06_files.sha256')
 cache={};verified=0
 for line in (r/'work/history/stage05_before_stage06/stage05_files.sha256').read_text().splitlines():
  expected,name=line.split('  ',1);p=r/'work/history/stage05_before_stage06'/name;st=p.stat();key=(st.st_dev,st.st_ino,st.st_size)
  if key not in cache:cache[key]=sha(p)
  assert cache[key]==expected,name
  if name.startswith(('data/','assets/','scenes/')):
   q=r/name;assert q.stat().st_ino==st.st_ino or sha(q)==expected,name
  verified+=1
 report={'status':'passed','phase06_frozen_files':len(rows),'hardlinked':linked,'copied_mutable':copied,'phase05_frozen_files_sha_verified':verified,'phase06_scene_sha256':sha(r/'scenes/stage06_city_medium.blend'),'physical_disk_free_bytes':shutil.disk_usage(r).free,'replay_scope':'stage06 outputs and consumed inputs; prior phase manifests remain separately available','next_authorized_stage':7};(r/'outputs/stage06_integrity.json').write_text(json.dumps(report,indent=2)+'\n');print('STAGE06_FROZEN_READY_FOR_STAGE07',report,flush=True)
if __name__=='__main__':freeze()
