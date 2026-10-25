"""Actual before/after geometry, file, load and pixel comparison in local WebGL."""
from pathlib import Path
import asyncio,base64,json,shutil
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'outputs/stage09/resources'
HTML='''<!doctype html><meta charset="utf-8"><title>Actual indexed geometry comparison</title><style>body{margin:0;background:#afc4cc}canvas{display:block}</style><script type="importmap">{"imports":{"three":"/resources/vendor/three/build/three.module.js","three/addons/":"/resources/vendor/three/examples/jsm/"}}</script><canvas id="view" width="1200" height="900"></canvas><script type="module">
import * as THREE from 'three';import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';import {MeshoptDecoder} from '/resources/vendor/meshopt_decoder.mjs';
const renderer=new THREE.WebGLRenderer({canvas:document.querySelector('canvas'),antialias:false,preserveDrawingBuffer:true});renderer.setSize(1200,900);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1;
const loader=new GLTFLoader();loader.setMeshoptDecoder(MeshoptDecoder);const result={status:'running',actual_browser_render:true,variants:[],errors:[]};window.result=result;window.addEventListener('error',e=>result.errors.push(e.message));let firstPixels;
for(const name of ['before','after']){
 const begin=performance.now(),response=await fetch('/resources/comparison/'+name+'.glb',{cache:'no-store'});const bytes=await response.arrayBuffer();const loaded=await loader.parseAsync(bytes,new URL('/resources/comparison/',location.href).href),loadMs=performance.now()-begin;
 const scene=new THREE.Scene();scene.background=new THREE.Color(0xafc4cc);scene.add(new THREE.HemisphereLight(0xe2efff,0x716752,1.7));const sun=new THREE.DirectionalLight(0xffefdb,3);sun.position.set(3,6,4);scene.add(sun);scene.add(loaded.scene);scene.updateMatrixWorld(true);
 const bounds=new THREE.Box3().setFromObject(loaded.scene),center=bounds.getCenter(new THREE.Vector3()),radius=bounds.getSize(new THREE.Vector3()).length()/2,camera=new THREE.PerspectiveCamera(38,1200/900,.1,10000);camera.position.copy(center).add(new THREE.Vector3(1,.6,1.2).normalize().multiplyScalar(radius/Math.sin(THREE.MathUtils.degToRad(19))*1.12));camera.lookAt(center);camera.updateMatrixWorld();
 let vertices=0,triangles=0,objects=0;scene.traverse(o=>{if(o.isMesh){objects++;vertices+=o.geometry.attributes.position.count;triangles+=(o.geometry.index?o.geometry.index.count:o.geometry.attributes.position.count)/3;}});
 renderer.render(scene,camera);renderer.getContext().finish();const pixels=new Uint8Array(1200*900*4);renderer.getContext().readPixels(0,0,1200,900,renderer.getContext().RGBA,renderer.getContext().UNSIGNED_BYTE,pixels);
 const row={name,bytes:bytes.byteLength,actual_load_parse_ms:loadMs,vertices,triangles,objects,bounds:[bounds.min.toArray(),bounds.max.toArray()],camera:{position:camera.position.toArray(),target:center.toArray(),fov:38},actual_render_calls:renderer.info.render.calls,image:renderer.domElement.toDataURL('image/png')};
 if(firstPixels){let sum=0,max=0,different=0;for(let i=0;i<pixels.length;i++){const d=Math.abs(pixels[i]-firstPixels[i]);sum+=d;max=Math.max(max,d);if(d>0)different++;}result.pixel_comparison={mean_absolute_channel_difference:sum/pixels.length,max_channel_difference:max,different_channels:different,total_channels:pixels.length};}else firstPixels=pixels;
 result.variants.push(row);const geometries=new Set(),materials=new Set(),textures=new Set();scene.traverse(o=>{if(o.isMesh){geometries.add(o.geometry);for(const m of Array.isArray(o.material)?o.material:[o.material]){materials.add(m);for(const key of ['map','normalMap','roughnessMap','metalnessMap'])if(m[key])textures.add(m[key]);}}});for(const g of geometries)g.dispose();for(const m of materials)m.dispose();for(const t of textures)t.dispose();
}
result.status=result.errors.length?'failed':'passed';document.body.dataset.done='true';</script>'''
async def main():
 (BASE/'comparison').mkdir(parents=True,exist_ok=True)
 vendor=BASE/'vendor';vendor.mkdir(exist_ok=True)
 shutil.copytree(ROOT/'assets/browser_dependencies/stage08/three',vendor/'three',dirs_exist_ok=True)
 shutil.copy2(ROOT/'viewer/node_modules/meshoptimizer/meshopt_decoder.mjs',vendor/'meshopt_decoder.mjs')
 shutil.copy2(ROOT/'work/history/stage09_unindexed_comparison/landmark-city_hall-l1.glb',BASE/'comparison/before.glb')
 shutil.copy2(BASE/'tiles/landmark-city_hall-l1.glb',BASE/'comparison/after.glb')
 (BASE/'comparison/index.html').write_text(HTML)
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader'])
  page=await browser.new_page(viewport={'width':1200,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://127.0.0.1:8090/resources/comparison/index.html',wait_until='domcontentloaded');await page.wait_for_function("document.body.dataset.done==='true'",timeout=60000)
  report=await page.evaluate('window.result');report['page_errors']=errors
  for row in report['variants']:
   relative='work/previews/stage09/indexing_'+row['name']+'.png';(ROOT/relative).write_bytes(base64.b64decode(row.pop('image').split(',')[1]));row['actual_render_image']=relative
  report['geometry_triangle_count_identical']=report['variants'][0]['triangles']==report['variants'][1]['triangles'];report['bounds_identical']=report['variants'][0]['bounds']==report['variants'][1]['bounds'];report['limits']=['One actual City Hall mid asset, fixed camera and lighting; one load measurement per variant, with shared local texture HTTP cache. Not an all-city FPS benchmark.']
  if errors or not report['geometry_triangle_count_identical'] or not report['bounds_identical']:report['status']='failed'
  (ROOT/'work/reports/stage09/indexing_comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='variants'}),flush=True);await browser.close()
  if report['status']!='passed':raise RuntimeError('Actual indexing comparison failed')
asyncio.run(main())
