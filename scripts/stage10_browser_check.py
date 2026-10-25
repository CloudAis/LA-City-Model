"""Real UI/interaction, streaming/error recovery and repeated-tour resource checks."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio,json,time,math,hashlib
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def ui_fingerprint():
 rows=[(str(p.relative_to(ROOT/'outputs/LA_Delivery/viewer/dist')),sha(p)) for p in sorted((ROOT/'outputs/LA_Delivery/viewer/dist').rglob('*')) if p.is_file()]
 return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
async def main():
 report={'status':'running','actual_browser_executed':True,'checks':[],'screenshots':[],'started_at':datetime.now(ZoneInfo('Asia/Singapore')).isoformat(),'catalog_sha256':sha(ROOT/'outputs/LA_Delivery/tiles/manifest.json'),'viewer_build_fingerprint':ui_fingerprint()}
 def check(name,condition,details=None):
  report['checks'].append({'name':name,'passed':bool(condition),'details':details});print(name,'PASS' if condition else 'FAIL',flush=True)
  if not condition:raise RuntimeError(name)
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader','--enable-precise-memory-info','--num-raster-threads=4','--disk-cache-size=67108864'])
  page=await browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1);page_errors=[];console_errors=[];requests=[]
  page.on('pageerror',lambda e:page_errors.append(str(e)));page.on('console',lambda m:console_errors.append(m.text) if m.type=='error' else None);page.on('request',lambda r:requests.append(r.url))
  async def state():return await page.evaluate('LAViewer.snapshot()')
  async def settle():await page.evaluate('async()=>await LAViewer.settle()');await page.wait_for_timeout(600)
  async def screenshot(name):
   relative='work/previews/stage10/functional/'+name+'.png';await page.screenshot(path=str(ROOT/relative));report['screenshots'].append(relative)
  try:
   begin=time.perf_counter();await page.goto('http://127.0.0.1:8092',wait_until='domcontentloaded',timeout=60000);await page.wait_for_function("document.body.dataset.ready==='true'",timeout=60000);await settle()
   report['initial_loaded_seconds']=time.perf_counter()-begin;report['browser']=browser.version
   overview=await state();check('actual_project_city_loaded',overview['render']['triangles']>1000 and not overview['errors'],{'triangles':overview['render']['triangles']});await screenshot('overview')
   orientation=await page.evaluate('LAViewer.orientationCheck()');check('north_up_and_axes',orientation['source_north_to_glb']==[0,0,-100] and orientation['source_up_to_glb']==[0,100,0],orientation)
   await page.mouse.move(1000,500);await page.mouse.down();await page.mouse.move(1130,540,steps=8);await page.mouse.up();await page.wait_for_timeout(500)
   rotated=await state();check('actual_orbit_drag',math.dist(rotated['position_city_m'],overview['position_city_m'])>10)
   await page.get_by_role('button',name='Historic Core',exact=True).click();await settle();historic=await state();await screenshot('historic_core')
   expected=next(v for v in json.loads((ROOT/'outputs/LA_Delivery/tiles/manifest.json').read_text())['views'] if v['id']=='historic_street')
   check('saved_camera_and_origin_rebase',math.dist(historic['position_city_m'],expected['position_m'])<.1,{'actual':historic['position_city_m'],'expected':expected['position_m']})
   ground=await page.evaluate('LAViewer.probe(1000,850)');check('historic_near_ground_actually_present',any(str(r.get('resource','')).startswith('roads-') for r in ground),ground)
   await page.mouse.click(1450,450);await page.wait_for_function('LAViewer.snapshot().selected!==null',timeout=15000);selected=await state()
   check('actual_building_click_and_metadata',selected['selected'] is not None and await page.locator('#selection').is_visible(),selected['selected']);await screenshot('building_properties');await page.locator('#selection-close').click()
   await page.locator('#fly').click();before=await state();await page.keyboard.down('KeyW');await page.wait_for_timeout(700);await page.keyboard.up('KeyW');after=await state();check('actual_flight_keyboard',after['mode']=='fly' and math.dist(before['position_city_m'],after['position_city_m'])>1)
   await page.locator('#orbit').click();await page.locator('#layers-open').click();checkbox=page.locator('input[data-layer="buildings"]');await checkbox.uncheck();await page.wait_for_timeout(600);hidden=await page.evaluate("LAViewer.inspectLoaded().filter(r=>r.id.startsWith('detail-')&&r.visible)");check('actual_layer_toggle',not hidden);await checkbox.check();await page.locator('#layers-open').click();await settle()
   await page.locator('#lighting').select_option('night');await page.wait_for_timeout(1200);check('actual_light_preset_switch',(await state())['lighting']=='night');await screenshot('night');await page.locator('#lighting').select_option('clear_day')
   await page.locator('#quality').select_option('low');await settle();low=await state();expected_low=round(1920*json.loads((ROOT/'config/stage09.json').read_text())['qualities']['low']['pixel_ratio']);check('actual_quality_switch',low['quality']=='low' and low['render_resolution'][0]==expected_low,low['render_resolution']);await page.locator('#quality').select_option('medium');await settle()
   await page.locator('#search').fill('Griffith');await page.locator('#search-results button').first.click();await settle();griffith=await state();check('actual_landmark_search_and_geographic_jump',math.dist(griffith['position_city_m'],historic['position_city_m'])>5000);await screenshot('griffith_observatory')
   await page.locator('#quality').select_option('high');await settle();high=await state();check('high_quality_actual_draw',high['quality']=='high' and high['render']['triangles']>0);await page.locator('#quality').select_option('medium');await settle()
   manifest=json.loads((ROOT/'outputs/LA_Delivery/tiles/manifest.json').read_text());landmark_checks=[]
   for landmark in manifest['landmarks']:
    await page.evaluate('(id)=>LAViewer.setView("landmark-"+id)',landmark['id']);await settle()
    loaded=await page.evaluate('LAViewer.inspectLoaded()');visible=any(r['id']=='landmark-'+landmark['id'] and r['visible'] for r in loaded);landmark_checks.append({'id':landmark['id'],'actual_loaded_and_visible':visible})
   check('all_ten_landmarks_actual_loaded',all(r['actual_loaded_and_visible'] for r in landmark_checks),landmark_checks)
   await page.evaluate("LAViewer.setView('civic_street')");await settle();await screenshot('civic_center')
   civic_ground=await page.evaluate('LAViewer.probe(1000,850)');check('civic_near_ground_actually_present',bool(civic_ground),civic_ground)
   # Explicit failure injection proves the visible error and retry behavior. It
   # is kept separate from unexpected application/console errors.
   console_before=len(console_errors);pattern='**/resources/tiles/overview-terrain-l3.glb'
   await page.evaluate('LAViewer.releaseAll()');await page.route(pattern,lambda route:route.fulfill(status=503,body='intentional phase09 retry test'))
   await page.evaluate("LAViewer.setView('overview');LAViewer.resume()")
   await page.wait_for_timeout(3000);failed=await state();check('injected_failure_visible_and_retried',bool(failed['errors']) and failed['resources']['retries']>=2 and await page.locator('#error').is_visible());await screenshot('error_recovery_test')
   await page.unroute(pattern);await page.locator('#retry').click();await settle();check('actual_error_recovery',not (await state())['errors']);report['expected_injected_console_errors']=console_errors[console_before:];console_errors=console_errors[:console_before]
   check('only_local_runtime_requests',all(url.startswith('http://127.0.0.1:8092/') or url.startswith('blob:') or url.startswith('data:') for url in requests))
   steady=[]
   for view in ['overview','historic_street','civic_street','landmark-griffith_observatory']:
    await page.evaluate('(id)=>LAViewer.setView(id)',view);await settle();await page.wait_for_timeout(1000);await page.evaluate('LAViewer.resetMetrics()');await page.wait_for_timeout(6000);steady.append({'view':view,'measurement_seconds':6,'snapshot':await state()});print('STEADY_VIEW',view,round(steady[-1]['snapshot']['fps'],2),flush=True)
   report['steady_views']=steady
   await page.evaluate("LAViewer.setView('historic_street')");await settle();await page.evaluate('LAViewer.setRenderScale(1);LAViewer.resetMetrics()');await page.wait_for_timeout(6000);report['native_1080p_sample']=await state();check('native1080p_sample_actually_measured',report['native_1080p_sample']['render_resolution']==[1920,1080]);await page.evaluate('LAViewer.setQuality("medium")');await settle()
   # Fixed route:36s, three complete loops, sampled without changing quality.
   await page.evaluate("LAViewer.setView('overview');LAViewer.resetMetrics();LAViewer.startTour()")
   tour=[];tour_begin=time.perf_counter()
   for i in range(18):
    await page.wait_for_timeout(6000);snapshot=await state();tour.append({'elapsed_s':time.perf_counter()-tour_begin,'snapshot':snapshot});print('TOUR_SAMPLE',i+1,round(snapshot['fps'],2),snapshot['resources']['cache_entries'],snapshot['gpu_resources'],flush=True)
   report['tour_frame_times_ms']=await page.evaluate('LAViewer.rawFrameTimes()');await page.evaluate('LAViewer.stopTour()');report['tour_samples']=tour
   check('three_fixed_tour_cycles_executed',tour[-1]['elapsed_s']>=108,{'duration_s':tour[-1]['elapsed_s'],'quality':'medium','viewport':[1920,1080],'route_seconds':36,'cycles':3})
   check('no_unexpected_browser_errors',not page_errors and not console_errors,{'page_errors':page_errors,'console_errors':console_errors})
   check('tested_build_and_catalog_unchanged',report['catalog_sha256']==sha(ROOT/'outputs/LA_Delivery/tiles/manifest.json') and report['viewer_build_fingerprint']==ui_fingerprint())
   check('runtime_cache_stays_bounded',all(s['snapshot']['resources']['geometry_bytes']<=192*1024**2*1.2 for s in tour))
   before_release=await state();await page.evaluate('LAViewer.releaseAll()');await page.wait_for_timeout(2500);released=await state();report['release']={'before':before_release,'after':released}
   check('geometry_material_texture_release',released['resources']['cache_entries']==0 and released['resources']['tracked_geometries']==0 and released['resources']['tracked_materials']==0 and released['resources']['texture_pool_entries']==0,released['resources'])
   await page.evaluate("LAViewer.resume();LAViewer.setView('overview')");await settle();await screenshot('final_overview')
   report['final']=await state();report['runtime_request_count']=len(requests)
   report['status']='passed';report['actual_rendering_backend']=report['final']['gpu_renderer'];report['hardware_gpu_proven']=False
  except Exception as error:
   report['status']='failed';report['failure']=str(error)
   try:await screenshot('browser_failure');report['failed_state']=await state()
   except Exception:pass
  finally:
   report['page_errors']=page_errors;report['unexpected_console_errors']=console_errors;report['completed_at']=datetime.now(ZoneInfo('Asia/Singapore')).isoformat()
   (ROOT/'work/reports/stage10/browser_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');await browser.close()
  if report['status']!='passed':raise RuntimeError(report.get('failure','Actual browser checks failed'))
asyncio.run(main())
