"""48 actual native1080p WebGL inspection frames and a ten-landmark index."""
from pathlib import Path
import asyncio,json,time,hashlib,math
from playwright.async_api import async_playwright
from stage10_common import *
async def main():
 cfg=read('config/stage10.json');rows=[];errors=[];console=[];catalog_sha=sha(DELIVERY/'tiles/manifest.json')
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader'])
  page=await browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1);page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:console.append(m.text) if m.type=='error' else None)
  await page.goto('http://127.0.0.1:8092',wait_until='domcontentloaded');await page.wait_for_function("document.body.dataset.ready==='true'",timeout=60000);await page.evaluate("LAViewer.setQuality('high')");await page.evaluate('async()=>await LAViewer.settle()')
  await page.add_style_tag(content='header,.locations,footer .toolbar,.orientation,#progress{display:none!important}footer{bottom:12px!important}.attribution{background:#132b34bb!important;color:#fff!important}body{cursor:default}')
  await page.evaluate("""()=>{const label=document.createElement('div');label.id='inspection-title';Object.assign(label.style,{position:'fixed',left:'28px',top:'20px',zIndex:'30',padding:'8px 13px',background:'#132b34a0',color:'#e9efee',font:'16px system-ui',borderRadius:'5px'});document.body.append(label)}""")
  for index,(ident,original) in enumerate(cfg['views'].items(),1):
   view=dict(original,id=ident,name=original['label_zh'])
   if ident=='city_overview':await page.evaluate("LAViewer.setView('overview')")
   else:
    if ident=='downtown_top':view.update(position_m=[0,0,4200],lens_mm=18)
    if ident=='us_bank_tower':view.update(position_m=[view['target_m'][i]+(view['position_m'][i]-view['target_m'][i])*1.25 for i in range(3)],lens_mm=30)
    await page.evaluate('(v)=>LAViewer.setInspectionCamera(v)',view)
   await page.evaluate('async()=>await LAViewer.settle()');await page.wait_for_timeout(1200)
   for light in cfg['lights']:
    await page.evaluate('(name)=>LAViewer.setLighting(name)',light);await page.evaluate('(text)=>document.getElementById("inspection-title").textContent=text',f'{original["label_zh"]} · {light}');before=await page.evaluate('LAViewer.snapshot().frame_count');await page.wait_for_function('(n)=>LAViewer.snapshot().frame_count>n',arg=before,timeout=45000)
    await page.wait_for_timeout(400);snap=await page.evaluate('LAViewer.snapshot()');assert not snap['errors'] and snap['render']['triangles']>0 and snap['render_resolution']==[1920,1080],(ident,snap['errors'])
    folder=DELIVERY/'previews/checks'/ident;folder.mkdir(parents=True,exist_ok=True);file=folder/(light+'.png');await page.evaluate('LAViewer.pauseRenderForCapture()')
    try:await page.screenshot(path=str(file),timeout=90000)
    finally:await page.evaluate('LAViewer.resumeRenderAfterCapture()')
    record={'view':ident,'light':light,'path':str(file.relative_to(DELIVERY)),'sha256':sha(file),'actual_webgl_render':True,'camera_city_m':snap['position_city_m'],'target_city_m':snap['target_city_m'],'width':1920,'height':1080,'internal_render_resolution':snap['render_resolution'],'quality':snap['quality'],'triangles':snap['render']['triangles'],'draw_calls':snap['render']['calls'],'software_compatibility':'high PBR600k target, shadows off and opaque glass; full native materials preserved','capture_method':'Pause repeated redraw after an actual completed frame to allow screenshot compositing; no FPS claim from capture mode','source_camera_overview_or_native_orthographic_difference':'Runtime uses its saved overview, and a4200m perspective top camera for Downtown to retain localLOD. Actual camera recorded here.' if ident in ('city_overview','downtown_top') else None};rows.append(record)
    if light=='clear_day':retain_link(file,DELIVERY/'previews'/(f'{index:02d}_'+ident+'.png'))
   write('work/reports/stage10/showcase.in_progress.json',{'status':'in_progress','images':rows});print('ACTUAL_1080P_FOUR_LIGHT_VIEWS',ident,flush=True)
  landmark_rows=[];await page.evaluate("LAViewer.setLighting('clear_day')")
  for landmark in read('outputs/LA_Delivery/tiles/manifest.json')['landmarks']:
   ident=landmark['id'];await page.evaluate('(id)=>LAViewer.setView("landmark-"+id)',ident);await page.evaluate('async()=>await LAViewer.settle()');await page.wait_for_timeout(800);await page.evaluate('(text)=>document.getElementById("inspection-title").textContent=text',landmark['name']+' · 有资料的近似')
   file=DELIVERY/'previews/landmarks'/(ident+'.png');file.parent.mkdir(parents=True,exist_ok=True);await page.evaluate('LAViewer.pauseRenderForCapture()');await page.screenshot(path=str(file),timeout=90000);await page.evaluate('LAViewer.resumeRenderAfterCapture()');landmark_rows.append({'id':ident,'name':landmark['name'],'status':'部分通过：近似完成，保留资料盲区','path':str(file.relative_to(DELIVERY)),'sha256':sha(file)})
  assert not errors and not console,(errors,console);await browser.close()
 report={'status':'actual_48_inspection_renders_completed','browser':'installed Chromium software WebGL2; actual version in final browser check','catalog_sha256':catalog_sha,'images':rows,'landmarks':landmark_rows,'page_errors':errors,'console_errors':console,'frames_are_actual_native_1920x1080_high_pbr':True,'not_cycles_or_photographs':True};write('work/reports/stage10/showcase.json',report)
 print('ACTUAL_SHOWCASE_COMPLETE',len(rows),len(landmark_rows),flush=True)
asyncio.run(main())
