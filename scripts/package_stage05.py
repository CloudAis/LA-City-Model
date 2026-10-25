"""Index formal project deliverables; caches and diagnostic history remain separate."""
from pathlib import Path
import json,datetime,subprocess
from stage02_io import digest,write_json
ROOT=Path(__file__).resolve().parents[1]
def package(root=ROOT):
 root=Path(root);skip={'outputs/stage05_delivery.json','outputs/stage05_files.sha256','outputs/stage05_integrity.json','work/logs/stage05/packaging.log','work/logs/stage05/delivery_sha_verification.log'};paths=[]
 for folder in ['assets','config','data','docs','outputs','scenes','scripts','viewer','work/logs','work/previews','work/reports']:
  for p in (root/folder).rglob('*'):
   rel=str(p.relative_to(root))
   if p.is_file() and rel not in skip and '__pycache__' not in p.parts and not p.name.endswith(('.blend1','.part','.pyc')):paths.append(p)
 paths.extend(root/name for name in ['README.md','PROJECT_SPEC.md','STATUS.md','AGENTS.md','project','requirements.lock','.gitignore']);records=[]
 for i,p in enumerate(sorted(set(paths)),1):
  records.append({'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':digest(p)})
  if i%5000==0:print('DELIVERY_FILES_HASHED',i,flush=True)
 manifest=root/'outputs/stage05_files.sha256';manifest.write_text(''.join(r['sha256']+'  '+r['path']+'\n' for r in records));total=sum(r['bytes'] for r in records);write_json(root/'outputs/stage05_delivery.json',{'stage':5,'status':'complete_with_documented_gaps','model':'scenes/stage05_city_medium.blend','acceptance':'outputs/stage05_city_medium_acceptance.json','files':records,'file_count':len(records),'total_logical_bytes':total,'scope':'formal current project files including inherited sources/models; excludes venv, caches, diagnostic/frozen history, blend backups and this self-referential ledger','history_preservation':'work/reports/stage05/stage04_preservation_delivery.json; local snapshots retained','sources_and_dates':'data/processed/stage05/source_registry.json; mixed vintages, not one-day city','created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 log=root/'work/logs/stage05/delivery_sha_verification.log'
 # Verification log is excluded from its own input to avoid self-reference.
 if any(r['path']==str(log.relative_to(root)) for r in records):raise RuntimeError('Remove/rename prior verification log before repackaging')
 with log.open('w') as stream:p=subprocess.run(['sha256sum','--quiet','--check',str(manifest.relative_to(root))],cwd=root,stdout=stream,stderr=subprocess.STDOUT)
 assert p.returncode==0,'Delivery SHA verification failed; see '+str(log);write_json(root/'outputs/stage05_integrity.json',{'status':'passed','checked_files':len(records),'checked_logical_bytes':total,'sha256_manifest':str(manifest.relative_to(root)),'sha256_manifest_digest':digest(manifest),'check_command':'sha256sum --quiet --check outputs/stage05_files.sha256','check_exit_code':p.returncode,'self_referential_outputs_and_verification_log_excluded':True,'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()});print('STAGE05_FORMAL_DELIVERY_SHA_VERIFIED',len(records),total,flush=True)
if __name__=='__main__':package()
