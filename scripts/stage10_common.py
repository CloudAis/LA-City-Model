from pathlib import Path
import hashlib,json,os,shutil
ROOT=Path(__file__).resolve().parents[1]
DELIVERY=ROOT/'outputs/LA_Delivery'
REPORTS=ROOT/'work/reports/stage10'
def read(path):return json.loads((ROOT/path).read_text())
def write(path,value):
 p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def sha(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def retain_link(source,target):
 source=Path(source);target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists():
  if sha(target)!=sha(source):raise RuntimeError('Preserve changed delivery file '+str(target))
  return
 os.link(source,target)
def link_tree(source,target):
 for p in Path(source).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:retain_link(p,Path(target)/p.relative_to(source))
