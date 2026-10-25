"""Actually verify distance LODs and idle-time eviction without explicit clear."""
from pathlib import Path
import asyncio,json
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
async def main():
 rows=[];errors=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader'])
  page=await browser.new_page(viewport={'width':1280,'height':800});page.on('pageerror',lambda error:errors.append(str(error)));await page.goto('http://127.0.0.1:8090');await page.wait_for_function("document.body.dataset.ready==='true'")
  # Isolate landmark LOD selection from the intentional medium triangle budget.
  for layer in ['terrain','roads','buildings','vegetation','furniture','water']:await page.evaluate('(layer)=>LAViewer.setLayer(layer,false)',layer)
  await page.evaluate("LAViewer.setQuality('high');LAViewer.setView('landmark-city_hall')");await page.evaluate('async()=>await LAViewer.settle()')
  await page.mouse.move(700,400)
  for wanted in [2,1,0]:
   delta=1500 if wanted==2 else -500
   for attempt in range(16):
    loaded=await page.evaluate('LAViewer.inspectLoaded()');visible=[r for r in loaded if r['id']=='landmark-city_hall' and r['visible']]
    if len(visible)==1 and visible[0]['lod']==wanted:break
    await page.mouse.wheel(0,delta);await page.wait_for_timeout(500);await page.evaluate('async()=>await LAViewer.settle()')
   else:raise AssertionError(('Actual wheel zoom did not reach LOD',wanted,visible))
   state=await page.evaluate('LAViewer.snapshot()');rows.append({'wheel_delta':delta,'wheel_steps':attempt,'visible':visible,'actual_camera_city_m':state['position_city_m']});print('ACTUAL_DISTANCE_LOD',visible,flush=True)
  assert {r['lod'] for row in rows for r in row['visible']}=={0,1,2},rows
  before=await page.evaluate('LAViewer.snapshot()');await page.evaluate("LAViewer.setView('landmark-griffith_observatory')");await page.evaluate('async()=>await LAViewer.settle()');await page.wait_for_timeout(14500)
  after=await page.evaluate('LAViewer.snapshot()');remaining=await page.evaluate("LAViewer.inspectLoaded().filter(r=>r.id==='landmark-city_hall')")
  assert not remaining and after['resources']['released']>before['resources']['released'] and not errors and not after['errors'],remaining
  await browser.close()
 report={'status':'passed','actual_browser_distance_lods':[0,1,2],'lod_samples':rows,'test_quality':'high, isolated landmark layer; medium intentionally applies tighter budgets','automatic_idle_eviction_without_releaseAll_or_quality_reset':True,'wait_after_leaving_ms':14500,'release_count_delta':after['resources']['released']-before['resources']['released'],'page_errors':errors}
 (ROOT/'work/reports/stage09/streaming_check.json').write_text(json.dumps(report,indent=2)+'\n');print('ACTUAL_LOD_AND_IDLE_EVICTION_PASSED',flush=True)
asyncio.run(main())
