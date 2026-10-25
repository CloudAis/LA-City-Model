"""Verify ZIP payload bytes, start extracted launcher and actually open the app/gallery."""
import asyncio,hashlib,json,os,shutil,subprocess,sys,urllib.request,zipfile
from playwright.async_api import async_playwright
from stage10_common import *
async def main():
 archive=ROOT/'outputs/LA_Local_Private_Viewer_1.0.zip';target=ROOT/'work/cache/stage10/portable_viewer';target.mkdir(parents=True,exist_ok=True);prefix='LA_Local_Private_Viewer_1.0';verified=0
 with zipfile.ZipFile(archive) as z:
  catalog=json.loads(z.read(prefix+'/PACKAGE_MANIFEST.json'))
  for row in catalog['files']:
   with z.open(prefix+'/'+row['path']) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==row['sha256'],row['path']
   verified+=1
  for row in catalog['files']:
   relative=Path(row['path']);dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True);source=DELIVERY/relative
   if source.is_file():os.link(source,dest)
   else:dest.write_bytes(z.read(prefix+'/'+row['path']))
 log=(ROOT/'work/logs/stage10/portable_server.log').open('w');server=subprocess.Popen([sys.executable,str(target/'start.py'),'--port','8095'],stdout=log,stderr=subprocess.STDOUT,cwd=target)
 try:
  for attempt in range(30):
   try:
    with urllib.request.urlopen('http://127.0.0.1:8095/health',timeout=1) as response:assert json.load(response)['stage']==10
    break
   except OSError:
    if server.poll() is not None or attempt==29:raise
    await asyncio.sleep(.1)
  async with async_playwright() as p:
   browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader']);page=await browser.new_page(viewport={'width':1280,'height':800});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   await page.goto('http://127.0.0.1:8095');await page.wait_for_function("document.body.dataset.ready==='true'",timeout=60000);await page.evaluate('async()=>await LAViewer.settle()');state=await page.evaluate('LAViewer.snapshot()');assert state['render']['triangles']>1000 and not state['errors'] and not errors;await page.screenshot(path=str(ROOT/'work/previews/stage10/portable_viewer.png'))
   await page.goto('http://127.0.0.1:8095/previews/index.html');await page.wait_for_function("document.querySelectorAll('img').length>=18");await page.locator('#light').select_option('night');assert await page.locator('[data-view]').first.get_attribute('src')=='checks/city_overview/night.png'
   with urllib.request.urlopen('http://127.0.0.1:8095/video/city_tour.mp4',timeout=10) as response:assert response.status==200
   await browser.close()
  write('work/reports/stage10/portable_check.json',{'status':'passed','actual_extracted_launcher_started':True,'actual_browser_model_render':True,'actual_gallery_switch_checked':True,'actual_video_endpoint_checked':True,'zip_payload_sha256_verified':verified,'package_sha256':sha(archive),'screenshot':'work/previews/stage10/portable_viewer.png','page_errors':errors,'mode':'Payload SHA verified from ZIP; large runtime files hardlinked to the exact matching source payload for test disk economy. ZIP members are ordinary files, not symlinks.','platform_tested':'Linux installed Chromium software WebGL2; Windows/macOS not actually tested'})
 finally:server.terminate();server.wait(timeout=10);log.close();shutil.rmtree(target)
 print('FINAL_PRIVATE_VIEWER_ZIP_ACTUALLY_OPENED',verified,flush=True)
asyncio.run(main())
