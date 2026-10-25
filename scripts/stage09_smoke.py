"""Actual installed Chromium/WebGL smoke; keeps screenshots and real errors."""
from pathlib import Path
import asyncio,json,time,sys,os
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
LABEL=sys.argv[1] if len(sys.argv)>1 else 'initial'
if '--limit-cpu' in sys.argv:os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:4]))
async def main():
 async with async_playwright() as p:
  backend='swiftshader-webgl' if '--webgl-only' in sys.argv else 'swiftshader'
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle='+backend,'--enable-unsafe-swiftshader','--enable-precise-memory-info'])
  page=await browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
  errors=[];console=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:console.append(m.text) if m.type=='error' else None)
  await page.goto('http://127.0.0.1:8090',wait_until='domcontentloaded',timeout=60000)
  await page.wait_for_function("document.body.dataset.ready==='true'",timeout=60000)
  await page.evaluate('async()=>{await LAViewer.settle()}')
  await page.evaluate('LAViewer.resetMetrics()')
  await page.wait_for_timeout(3000)
  initial=await page.evaluate('LAViewer.snapshot()');await page.screenshot(path=str(ROOT/f'work/previews/stage09/overview_{LABEL}.png'))
  await page.evaluate("LAViewer.setView('historic_street')");await page.evaluate('async()=>{await LAViewer.settle()}');await page.wait_for_timeout(3000)
  await page.evaluate('LAViewer.resetMetrics()');await page.wait_for_timeout(4000)
  street=await page.evaluate('LAViewer.snapshot()');await page.screenshot(path=str(ROOT/f'work/previews/stage09/historic_{LABEL}.png'))
  report={'actual_browser':True,'browser':browser.version,'angle_backend':backend,'browser_cpu_affinity':sorted(os.sched_getaffinity(0)),'errors':errors,'console_errors':console,'overview':initial,'street':street}
  (ROOT/f'work/reports/stage09/smoke_{LABEL}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps({'errors':errors,'console':console,'overview_fps':initial['fps'],'overview_triangles':initial['render']['triangles'],'street_fps':street['fps'],'street_triangles':street['render']['triangles'],'resource_errors':street['errors']},ensure_ascii=False),flush=True)
  await browser.close()
asyncio.run(main())
