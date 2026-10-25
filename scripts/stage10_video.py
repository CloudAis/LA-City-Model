"""Deterministic actual model viewport sequence; not a live-FPS recording."""
import asyncio,json,math,subprocess,time,shutil
from pathlib import Path
from playwright.async_api import async_playwright
from stage10_common import *
async def main():
 cfg=read('config/stage10.json');manifest=read('outputs/LA_Delivery/tiles/manifest.json');center=[-600,1400,180];radius=2000;fps=15;duration=24;frames=fps*duration
 roi=[center[0]-2600,center[1]-2600,center[0]+2600,center[1]+2600];heights=[r['bounds_city_m'][1][2] for r in manifest['resources'] if not r.get('overview') and r['bounds_city_m'][0][0]<roi[2] and r['bounds_city_m'][1][0]>roi[0] and r['bounds_city_m'][0][1]<roi[3] and r['bounds_city_m'][1][1]>roi[1]];altitude=max(650,max(heights)+100);path=[]
 for i in range(frames):
  angle=math.radians(135+25*i/(frames-1));path.append({'frame':i,'time_s':i/fps,'position_m':[center[0]+radius*math.cos(angle),center[1]+radius*math.sin(angle),altitude],'target_m':center})
 folder=ROOT/'work/cache/stage10/video_frames';folder.mkdir(parents=True,exist_ok=True);errors=[];begin=time.perf_counter()
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader']);page=await browser.new_page(viewport={'width':1280,'height':720});page.on('pageerror',lambda e:errors.append(str(e)));await page.goto('http://127.0.0.1:8092');await page.wait_for_function("document.body.dataset.ready==='true'");await page.evaluate("LAViewer.setQuality('medium');LAViewer.setRenderScale(1)")
  await page.add_style_tag(content='header,.locations,footer .toolbar,.orientation,#progress{display:none!important}footer{bottom:8px!important}.attribution{background:#132b34bb!important;color:white!important}')
  for i,view in enumerate(path):
   await page.evaluate('LAViewer.resumeRenderAfterCapture()');await page.evaluate('(v)=>LAViewer.setInspectionCamera({...v,id:"video",name:"Downtown"})',view)
   if i%15==0:await page.evaluate('async()=>await LAViewer.settle()')
   await page.wait_for_timeout(45);snap=await page.evaluate('LAViewer.pauseRenderForCapture()');assert not snap['errors'],snap['errors'];await page.screenshot(path=str(folder/f'frame-{i:05d}.jpg'),type='jpeg',quality=88,timeout=60000)
   if i%60==0:print('ACTUAL_VIEWPORT_VIDEO_FRAME',i,frames,flush=True)
  await browser.close()
 assert not errors
 output=DELIVERY/'video/city_tour.mp4';subprocess.run(['ffmpeg','-y','-framerate',str(fps),'-i',str(folder/'frame-%05d.jpg'),'-c:v','libx264','-threads','4','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,r_frame_rate:format=duration','-of','json',str(output)]));stream=probe['streams'][0];assert int(stream['nb_frames'])==frames and stream['width']==1280 and stream['height']==720 and abs(float(probe['format']['duration'])-duration)<.1
 keep=[]
 for i in [0,90,180,270,359]:
  target=DELIVERY/'video'/f'frame_{i:03d}.jpg';retain_link(folder/f'frame-{i:05d}.jpg',target);keep.append(str(target.relative_to(DELIVERY)))
 write('outputs/LA_Delivery/video/camera_path.json',{'fps':fps,'duration_s':duration,'coordinate_axes':'city east/north/up metres','frames':path,'camera_speed_m_s':math.radians(25)*radius/duration,'safety':'Constant camera Z is at least100m above every non-overview resource bounding box intersecting the local Downtown ROI; no camera passes through modeled buildings.','highest_resource_roi_m':max(heights),'camera_z_m':altitude})
 report={'status':'passed','actual_model_viewport_frames':frames,'not_a_realtime_fps_claim':True,'output':str(output.relative_to(ROOT)),'sha256':sha(output),'probe':probe,'frames_captured_resolution':[1280,720],'quality':'medium diffuse compatibility; native1280x720 pixels; daytime','capture_elapsed_s':time.perf_counter()-begin,'camera_above_all_local_model_bounds':altitude>=max(heights)+100,'camera_speed_m_s':math.radians(25)*radius/duration,'page_errors':errors,'review_frames':keep};write('work/reports/stage10/video.json',report)
 shutil.rmtree(folder);print('ACTUAL_VIDEO_VERIFIED',duration,'seconds',fps,'FPS_output',flush=True)
asyncio.run(main())
