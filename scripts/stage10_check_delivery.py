"""Portable standard-library verification of the exact final local handoff."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
try:
 manifest=json.loads((ROOT/'metadata/DELIVERY_MANIFEST.json').read_text());verified=0
 for row in manifest['files']:
  p=(ROOT/row['path']).resolve()
  if not p.is_relative_to(ROOT) or not p.is_file():raise RuntimeError('Missing/outside delivery file: '+row['path'])
  with p.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
  if actual!=row['sha256']:raise RuntimeError('Changed accepted file; preserve edits before rebuilding: '+row['path'])
  verified+=1
 print(json.dumps({'status':'passed','actual_files_verified':verified,'version':manifest['version'],'overall_model_acceptance':manifest['overall_result'],'not_all_fidelity_goals_passed':True},ensure_ascii=False))
except Exception as error:print('DELIVERY_CHECK_FAILED:',error,file=sys.stderr);sys.exit(1)
