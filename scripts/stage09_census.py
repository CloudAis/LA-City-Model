"""Actual visible loaded-group census, separate from renderer draw calls."""
from pathlib import Path
import asyncio,json
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
async def main():
 catalog=json.loads((ROOT/'outputs/stage09/resources/manifest.json').read_text());lookup={(r['id'],r['lod']):r for r in catalog['resources']};rows=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader'])
  page=await browser.new_page(viewport={'width':1920,'height':1080});await page.goto('http://127.0.0.1:8090');await page.wait_for_function("document.body.dataset.ready==='true'")
  for view in ['overview','historic_street','civic_street','landmark-griffith_observatory']:
   await page.evaluate('(id)=>LAViewer.setView(id)',view);await page.evaluate('async()=>await LAViewer.settle()');await page.wait_for_timeout(300)
   loaded=await page.evaluate('LAViewer.inspectLoaded()');state=await page.evaluate('LAViewer.snapshot()');visible=[r for r in loaded if r['visible']]
   rows.append({'view':view,'visible_loaded_groups':len(visible),'visible_group_gltf_mesh_nodes_before_per_object_frustum_culling':sum(lookup[(r['id'],r['lod'])]['objects'] for r in visible),'visible_group_declared_material_slots':sum(lookup[(r['id'],r['lod'])]['materials'] for r in visible),'actually_drawn_triangles':state['render']['triangles'],'draw_calls':state['render']['calls'],'retained_cache_groups':len(loaded),'texture_dimensions':state['resources']['texture_dimensions'],'loaded':loaded})
  await browser.close()
 report={'status':'actual_browser_census_measured','viewport':[1920,1080],'quality':'medium','views':rows,'interpretation':'Visible group/node counts include group meshes subsequently culled by Three.js. Repeated source fixtures/trees are separate InstancedMeshes; draw calls count actual rendering passes and are not object counts.'}
 (ROOT/'work/reports/stage09/object_census.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('ACTUAL_RUNTIME_OBJECT_CENSUS',[(r['view'],r['visible_loaded_groups'],r['visible_group_gltf_mesh_nodes_before_per_object_frustum_culling']) for r in rows],flush=True)
asyncio.run(main())
