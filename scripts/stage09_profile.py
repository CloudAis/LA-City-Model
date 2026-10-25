"""Separate streaming CPU, renderer submission and actual software-GPU completion."""
import asyncio,json,os
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader','--enable-precise-memory-info','--num-raster-threads=4'])
  page=await browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
  await page.goto('http://127.0.0.1:8090',wait_until='domcontentloaded');await page.wait_for_function("document.body.dataset.ready==='true'")
  await page.evaluate("LAViewer.setView('historic_street')");await page.evaluate('async()=>await LAViewer.settle()');await page.wait_for_timeout(3000)
  details={'loaded':await page.evaluate('LAViewer.inspectLoaded()'),'floor_hits':await page.evaluate('LAViewer.probe(1100,850)'),'state':await page.evaluate('LAViewer.snapshot()')}
  profiles=[]
  for condition in ['normal','basic','half_pixels']:
   result=await page.evaluate('(condition)=>LAViewer.profile(condition)',condition)
   profiles.append(result);print(condition,{k:sum(r[k] for r in result['rows'])/len(result['rows']) for k in result['rows'][0]},flush=True)
  details['profiles']=profiles
  (ROOT/'work/reports/stage09/bottleneck_profile.json').write_text(json.dumps(details,ensure_ascii=False,indent=2)+'\n')
  await browser.close()
asyncio.run(main())
