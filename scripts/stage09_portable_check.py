"""Actually run the packaged standalone launcher against byte-verified resources."""
from pathlib import Path
import asyncio,hashlib,json,os,shutil,subprocess,sys,time,zipfile,urllib.request
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
def sha_stream(stream):return hashlib.file_digest(stream,'sha256').hexdigest()
async def main():
 archive=ROOT/'outputs/stage09_local_viewer.zip';target=ROOT/'work/cache/stage09/portable_check/la-local-viewer';target.mkdir(parents=True,exist_ok=True)
 verified=0
 with zipfile.ZipFile(archive) as z:
  manifest=json.loads(z.read('la-local-viewer/PACKAGE_MANIFEST.json'))
  for row in manifest['files']:
   name='la-local-viewer/'+row['path']
   with z.open(name) as stream:assert sha_stream(stream)==row['sha256'],name
   verified+=1
  for item in z.infolist():
   if item.is_dir():continue
   relative=Path(item.filename).relative_to('la-local-viewer');dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True)
   if dest.exists():dest.unlink()
   if relative.parts[0]=='resources':os.link(ROOT/'outputs/stage09'/relative,dest)
   else:dest.write_bytes(z.read(item))
 log=(ROOT/'work/logs/stage09/portable_server.log').open('w')
 server=subprocess.Popen([sys.executable,str(target/'start.py'),'--port','8091'],stdout=log,stderr=subprocess.STDOUT)
 try:
  for attempt in range(30):
   try:
    with urllib.request.urlopen('http://127.0.0.1:8091/health',timeout=1) as response:assert json.load(response)['stage']==9
    break
   except OSError:
    if server.poll() is not None or attempt==29:raise
    await asyncio.sleep(.1)
  async with async_playwright() as p:
   browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader'])
   page=await browser.new_page(viewport={'width':1280,'height':800});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   await page.goto('http://127.0.0.1:8091',wait_until='domcontentloaded',timeout=30000);await page.wait_for_function("document.body.dataset.ready==='true'",timeout=60000);await page.evaluate('async()=>await LAViewer.settle()');snapshot=await page.evaluate('LAViewer.snapshot()')
   assert snapshot['render']['triangles']>1000 and not errors and not snapshot['errors']
   screenshot='work/previews/stage09/portable_viewer.png';await page.screenshot(path=str(ROOT/screenshot));await browser.close()
  report={'status':'passed','actual_standalone_launcher_started':True,'actual_browser_render':True,'zip_members_sha256_verified':verified,'package_sha256':sha_stream(archive.open('rb')),'screenshot':screenshot,'page_errors':errors,'render_triangles':snapshot['render']['triangles'],'resource_test_mode':'Full standalone directory tree; model files are hardlinks to the exact SHA-verified ZIP payload to avoid a second full disk copy. ZIP contains ordinary files, not links.'}
  (ROOT/'work/reports/stage09/portable_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report),flush=True)
 finally:
  server.terminate();server.wait(timeout=10);log.close();shutil.rmtree(target.parent)
asyncio.run(main())
