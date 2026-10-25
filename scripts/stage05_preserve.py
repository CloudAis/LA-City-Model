"""Freeze Stage04 and losslessly compress only obsolete diagnostic scene copies."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def preserve(root=ROOT):
 target=root/'work/history/stage04_before_stage05';entries=(root/'outputs/stage04_files.sha256').read_text().splitlines();total=0;linked=0
 for row in entries:
  expected,name=row.split('  ',1);source=root/name;dest=target/name
  if not dest.exists():
   assert sha(source)==expected,name;dest.parent.mkdir(parents=True,exist_ok=True)
   if name.startswith(('data/','scenes/','assets/')):os.link(source,dest);linked+=1
   else:shutil.copy2(source,dest)
  assert sha(dest)==expected,name;total+=dest.stat().st_size
 target.mkdir(parents=True,exist_ok=True);shutil.copy2(root/'outputs/stage04_files.sha256',target/'stage04_files.sha256')
 report={'status':'passed','files':len(entries),'bytes':total,'immutable_files_hardlinked_this_run':linked,'mutable_configuration_docs_scripts_copied':True,'original_stage04_scene_sha256':sha(root/'scenes/stage04_city_medium.blend')}
 rp=root/'work/reports/stage05';rp.mkdir(parents=True,exist_ok=True);(rp/'stage04_preservation.json').write_text(json.dumps(report,indent=2)+'\n');print('STAGE04_FROZEN_VERIFIED',len(entries),total,flush=True)
 compressed=[]
 for dirname in ['stage04_before_water_microface_fix','stage04_before_view_fix','stage04_before_pavement_occlusion_fix','stage04_before_winding_fix']:
  p=root/'work/history'/dirname/'scenes/stage04_city_medium.blend';z=Path(str(p)+'.zst')
  if not p.exists():
   if z.exists():continue
   raise FileNotFoundError(p)
  original=sha(p);size=p.stat().st_size;pending=Path(str(z)+'.pending')
  subprocess.run(['zstd','-3','-T2','--no-progress','-f',str(p),'-o',str(pending)],check=True,capture_output=True)
  proc=subprocess.Popen(['zstd','-d','-c',str(pending)],stdout=subprocess.PIPE,stderr=subprocess.PIPE);h=hashlib.sha256()
  for b in iter(lambda:proc.stdout.read(8*1024*1024),b''):h.update(b)
  assert proc.wait()==0 and h.hexdigest()==original,'Compression round-trip failed'
  pending.replace(z);record={'original_path':str(p.relative_to(root)),'compressed_path':str(z.relative_to(root)),'original_bytes':size,'compressed_bytes':z.stat().st_size,'original_sha256':original,'compressed_sha256':sha(z),'decompression_sha256_verified':True};compressed.append(record)
  # Only obsolete archive copies are replaced, after a complete round-trip hash check.
  p.unlink();(rp/'archive_compression.json').write_text(json.dumps({'status':'executed','archives':compressed,'restore':'zstd -d archive.blend.zst -o restored.blend'},indent=2)+'\n');print('DIAGNOSTIC_ARCHIVE_COMPRESSED_VERIFIED',dirname,size-z.stat().st_size,flush=True)
 print('PRESERVATION_AND_DISK_PREPARATION_COMPLETE',shutil.disk_usage(root).free,flush=True)
if __name__=='__main__':preserve()
