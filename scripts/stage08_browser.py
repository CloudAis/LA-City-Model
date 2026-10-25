"""Five GLB/PBR compatibility samples; not the stage09 city viewer.

Preparation never launches a browser. Explicit ``--check`` runs the real test.
The coordinator must enforce stage07 acceptance before requesting that check.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import http.server
import json
import shutil
import struct
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = Path('assets/browser_dependencies/stage08')
SAMPLES = ('building', 'road', 'vegetation', 'water', 'landmark')
REPORT = Path('work/reports/stage08/browser_check.json')
SCREENSHOT = Path('work/previews/stage08/browser_samples.png')
PAGE = VENDOR / 'samples.html'
FLAGS = ['--no-sandbox', '--disable-dev-shm-usage', '--disable-background-networking',
         '--use-angle=swiftshader', '--enable-unsafe-swiftshader']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def verify_vendor(root=ROOT):
    root = Path(root)
    lock = json.loads((root / VENDOR / 'vendor.lock.json').read_text())
    for entry in lock['files']:
        path = root / VENDOR / entry['path']
        if not path.is_file() or digest(path) != entry['sha256']:
            raise RuntimeError('Pinned browser dependency missing or changed: ' + str(path))
    return lock


HTML = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<link rel="icon" href="data:,"><title>Stage08 GLB material compatibility</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#101820;color:#e3e9ed;font:15px system-ui,sans-serif}
header,footer{width:1320px;margin:auto;padding:16px 8px}header{display:flex;justify-content:space-between;align-items:center;height:88px}
h1{font-size:24px;margin:0 0 6px}p{margin:0;color:#b4c1cc;font-size:13px}.badge{color:#d5dcb4;font:12px monospace}
#stage{position:relative;width:1320px;height:820px;margin:auto}canvas{display:block;width:1320px;height:820px}
.label{position:absolute;width:440px;padding:14px 18px;pointer-events:none;color:#c1ccd6;text-transform:uppercase;font-size:12px;letter-spacing:1px}
.summary{position:absolute;left:880px;top:410px;width:440px;padding:52px 30px;color:#a9bdc9;font:13px/1.7 monospace}
footer{font-size:12px;color:#a4b3be;line-height:1.6}#error{color:#ffad93;white-space:pre-wrap}
</style>
<script type="importmap">{"imports":{"three":"./three/build/three.module.js"}}</script>
<header><div><h1>Five GLB material samples</h1><p>Actual exported assets · metre scale · local Three.js 0.179.1 / GLTFLoader</p></div><div class="badge">STAGE 08 / TECHNICAL COMPATIBILITY</div></header>
<main id="stage"><canvas id="samples"></canvas><div class="summary" id="summary">Loading five local GLBs…</div></main>
<footer>Software WebGL2 / SwiftShader. This test checks sample loading and material rendering; it does not measure hardware GPU performance or implement the stage09 city viewer.<div id="error"></div></footer>
<script type="module">
import * as THREE from 'three';
import {GLTFLoader} from './three/examples/jsm/loaders/GLTFLoader.js';
import {RoomEnvironment} from './three/examples/jsm/environments/RoomEnvironment.js';
const names=['building','road','vegetation','water','landmark'];
const result=window.stage08Result={status:'running',page_loaded:true,glbs_loaded:0,samples:[],errors:[],shader_errors:[],textures_declared:0,textures_loaded:0};
window.addEventListener('unhandledrejection',e=>result.errors.push(String(e.reason)));
const textureInfo=t=>{const image=t?.image;return {name:t?.name||'',width:image?.width||image?.videoWidth||0,height:image?.height||image?.videoHeight||0,color_space:t?.colorSpace||'',flip_y:t?.flipY,loaded:!!image&&(image.width>0||image.videoWidth>0)};};
try {
 const renderer=new THREE.WebGLRenderer({canvas:document.getElementById('samples'),antialias:true,preserveDrawingBuffer:true,alpha:false,powerPreference:'low-power'});
 renderer.setPixelRatio(1);renderer.setSize(1320,820,false);renderer.setClearColor(0x1b2b37,1);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1;
 renderer.debug.checkShaderErrors=true;renderer.debug.onShaderError=(gl,program,vs,fs)=>result.shader_errors.push({program:gl.getProgramInfoLog(program),vertex:gl.getShaderInfoLog(vs),fragment:gl.getShaderInfoLog(fs)});
 const gl=renderer.getContext(),ext=gl.getExtension('WEBGL_debug_renderer_info');
 result.capabilities={webgl2:gl instanceof WebGL2RenderingContext,renderer:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),vendor:ext?gl.getParameter(ext.UNMASKED_VENDOR_WEBGL):gl.getParameter(gl.VENDOR),version:gl.getParameter(gl.VERSION),max_texture_size:gl.getParameter(gl.MAX_TEXTURE_SIZE),software_webgl_requested:true,hardware_gpu_proven:false};
 result.capabilities.software_renderer_detected=/swiftshader|llvmpipe|software/i.test(result.capabilities.renderer);
 if(!result.capabilities.webgl2)throw new Error('WebGL2 unavailable');
 const room=new RoomEnvironment(),pmrem=new THREE.PMREMGenerator(renderer),environment=pmrem.fromScene(room,.04);room.dispose();pmrem.dispose();
 const manager=new THREE.LoadingManager();manager.onError=url=>result.errors.push('Resource failed: '+url);const loader=new GLTFLoader(manager);
 renderer.setScissorTest(true);
 for(let i=0;i<names.length;i++){
  const name=names[i],row=Math.floor(i/3),col=i%3,x=col*440,y=820-(row+1)*410;
  const label=document.createElement('div');label.className='label';label.style.left=x+'px';label.style.top=(row*410)+'px';label.textContent=name;document.getElementById('stage').appendChild(label);
  const path='/outputs/stage08/glb/'+name+'.glb';const gltf=await loader.loadAsync(path),json=gltf.parser.json;
  const textures=await gltf.parser.getDependencies('texture');const ti=textures.map(textureInfo);if(ti.some(t=>!t.loaded))throw new Error(name+': declared texture has no loaded image');
  const scene=new THREE.Scene();scene.background=new THREE.Color(0x1b2b37);scene.environment=environment.texture;
  scene.add(new THREE.HemisphereLight(0xe2efff,0x6c6558,1.7));const key=new THREE.DirectionalLight(0xfff0dd,3);key.position.set(-5,9,6);scene.add(key);
  const fill=new THREE.DirectionalLight(0xbcd9f5,1.2);fill.position.set(5,3,-6);scene.add(fill);scene.add(gltf.scene);gltf.scene.updateMatrixWorld(true);
  const bounds=new THREE.Box3().setFromObject(gltf.scene),size=bounds.getSize(new THREE.Vector3()),center=bounds.getCenter(new THREE.Vector3());
  if(bounds.isEmpty()||![...size.toArray(),...center.toArray()].every(Number.isFinite))throw new Error(name+': empty or non-finite bounds');
  const radius=Math.max(size.length()/2,.001),camera=new THREE.PerspectiveCamera(36,440/410,Math.max(radius/1000,.0001),radius*100);
  camera.position.copy(center).add(new THREE.Vector3(1,0.72,1.25).normalize().multiplyScalar(radius/Math.sin(THREE.MathUtils.degToRad(18))*1.13));camera.lookAt(center);camera.updateMatrixWorld();
  let meshCount=0,triangleCount=0;const materials=new Set(),materialDetails=[];
  gltf.scene.traverse(o=>{if(!o.isMesh)return;meshCount++;triangleCount+=(o.geometry.index?o.geometry.index.count:o.geometry.attributes.position.count)/3;for(const m of (Array.isArray(o.material)?o.material:[o.material]))materials.add(m);});
  for(const m of materials){
   const slots={};for(const slot of ['map','emissiveMap','normalMap','roughnessMap','metalnessMap','aoMap'])if(m[slot]){
    const expected=['map','emissiveMap'].includes(slot)?THREE.SRGBColorSpace:THREE.NoColorSpace;
    slots[slot]={color_space:m[slot].colorSpace,expected_color_space:expected,valid:m[slot].colorSpace===expected};
    if(!slots[slot].valid)throw new Error(name+': incorrect glTF texture color space '+m.name+'/'+slot);
   }
   materialDetails.push({name:m.name,type:m.type,metalness:m.metalness??null,roughness:m.roughness??null,opacity:m.opacity,transparent:m.transparent,alpha_test:m.alphaTest,side:m.side,texture_slots:slots,color_space:m.map?.colorSpace||null,normal_map:!!m.normalMap,roughness_map:!!m.roughnessMap,metalness_map:!!m.metalnessMap,base_color_map:!!m.map});
  }
  if(ti.length!==(json.textures||[]).length)throw new Error(name+': declared/loaded texture count mismatch');
  renderer.setViewport(x,y,440,410);renderer.setScissor(x,y,440,410);renderer.compile(scene,camera);renderer.render(scene,camera);gl.finish();
  const pixels=new Uint8Array(440*410*4);gl.readPixels(x,y,440,410,gl.RGBA,gl.UNSIGNED_BYTE,pixels);const background=pixels.slice(0,3);let visiblePixels=0;
  for(let j=0;j<pixels.length;j+=4)if(Math.abs(pixels[j]-background[0])+Math.abs(pixels[j+1]-background[1])+Math.abs(pixels[j+2]-background[2])>12)visiblePixels++;
  const glError=gl.getError();if(glError!==gl.NO_ERROR)throw new Error(name+': WebGL error '+glError);if(!meshCount||!renderer.info.render.calls||visiblePixels<100)throw new Error(name+': rendered model has no visible pixels');
  result.samples.push({name,path,loaded:true,mesh_count:meshCount,triangles:triangleCount,material_count:materials.size,source_material_count:(json.materials||[]).length,materials:materialDetails,textures_declared:(json.textures||[]).length,textures_loaded:ti.filter(t=>t.loaded).length,textures:ti,extensions_used:json.extensionsUsed||[],extensions_required:json.extensionsRequired||[],compression_extensions:(json.extensionsUsed||[]).filter(e=>/draco|meshopt|basisu|texture_webp|texture_avif/i.test(e)),buffer_count:(json.buffers||[]).length,image_count:(json.images||[]).length,bounds_size_m:size.toArray(),render_calls:renderer.info.render.calls,visible_pixels:visiblePixels,webgl_error:glError});
  result.glbs_loaded++;result.textures_declared+=(json.textures||[]).length;result.textures_loaded+=ti.filter(t=>t.loaded).length;
  label.textContent=name+' / '+materials.size+' materials / '+ti.length+' textures';
 }
 if(result.errors.length||result.shader_errors.length)throw new Error('Page resource/shader failures');
 result.status='passed';document.getElementById('summary').innerText='5 / 5 GLBs loaded\n'+result.textures_loaded+' textures decoded\n'+result.samples.reduce((a,s)=>a+s.material_count,0)+' material instances\nWebGL2 · software renderer\n\nTechnical sample preview only\nNo city streaming / LOD / FPS claim';
} catch(e){result.status='failed';result.errors.push(String(e.stack||e));document.getElementById('error').textContent=result.errors.join('\n');}
document.body.dataset.checkComplete='true';
</script></html>
'''


def prepare(root=ROOT):
    """Verify cached dependencies and write the local test page; do not run it."""
    root = Path(root)
    lock = verify_vendor(root)
    (root / PAGE).write_text(HTML)
    report = {'status': 'not_run', 'executed': False,
              'reason': 'Browser test awaits coordinator stage07 acceptance and explicit check request.',
              'page_loaded': None, 'glbs_loaded': None, 'textures_loaded': None,
              'samples_present': {name: (root / f'outputs/stage08/glb/{name}.glb').is_file()
                                  for name in SAMPLES},
              'dependencies': {'package': lock['package'], 'version': lock['version'],
                               'sha256_lock': str(VENDOR / 'vendor.lock.json')},
              'interactive_city_viewer_implemented': False}
    if not (root / REPORT).exists():
        write_json(root / REPORT, report)
    return report


def inspect_glb(path):
    content = Path(path).read_bytes()
    if len(content) < 20:
        raise RuntimeError('Truncated GLB: ' + str(path))
    magic, version, length = struct.unpack_from('<4sII', content)
    chunk_length, chunk_type = struct.unpack_from('<II', content, 12)
    if magic != b'glTF' or version != 2 or length != len(content) or chunk_type != 0x4E4F534A:
        raise RuntimeError('Invalid GLB2 header: ' + str(path))
    document = json.loads(content[20:20 + chunk_length])
    uris = [entry['uri'] for key in ('buffers', 'images') for entry in document.get(key, [])
            if entry.get('uri') and not entry['uri'].startswith('data:')]
    if uris:
        raise RuntimeError('GLB sample has external buffer/image dependencies: ' + str(uris))
    return {'path': str(path), 'bytes': len(content), 'sha256': digest(path),
            'asset': document.get('asset'), 'extensions_used': document.get('extensionsUsed', []),
            'extensions_required': document.get('extensionsRequired', []),
            'declared_textures': len(document.get('textures', [])),
            'declared_materials': len(document.get('materials', []))}


def run(root=ROOT):
    """Load all five actual GLBs in WebGL2, capture a screenshot and evidence."""
    from playwright.sync_api import sync_playwright
    from PIL import Image, ImageStat

    root = Path(root)
    browser = shutil.which('chromium')
    report = {'status': 'failed', 'executed': False, 'started_utc': datetime.now(timezone.utc).isoformat(),
              'interactive_city_viewer_implemented': False,
              'hardware_gpu_proven': False, 'rendering_backend': 'explicit software WebGL2 / SwiftShader',
              'driver': 'Playwright / installed Chromium', 'browser_flags': FLAGS,
              'errors': [], 'samples': []}
    server = None
    try:
        prepare(root)
        if not browser:
            raise RuntimeError('Chromium executable unavailable')
        inputs = {name: inspect_glb(root / f'outputs/stage08/glb/{name}.glb') for name in SAMPLES}
        report['inputs'] = inputs
        report['vendor_lock_sha256'] = digest(root / VENDOR / 'vendor.lock.json')

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0),
                  functools.partial(Quiet, directory=str(root)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{server.server_port}/{PAGE.as_posix()}'
        errors, console, requests = [], [], []
        report['page_errors'], report['console'], report['http_responses'] = errors, console, requests
        screenshot = root / SCREENSHOT
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            instance = playwright.chromium.launch(executable_path=browser, headless=True, args=FLAGS)
            try:
                report['browser_version'] = instance.version
                page = instance.new_page(viewport={'width': 1440, 'height': 1020}, device_scale_factor=1)
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console', lambda message: console.append({'type': message.type, 'text': message.text}))
                page.on('requestfailed', lambda request: errors.append(request.url + ': ' + str(request.failure)))
                page.on('response', lambda response: requests.append({'url': response.url, 'status': response.status}))
                response = page.goto(url, wait_until='load', timeout=30000)
                report['executed'] = True
                if response.status != 200:
                    raise RuntimeError('Local sample page did not return HTTP200')
                page.wait_for_function('document.body.dataset.checkComplete === "true"', timeout=120000)
                result = page.evaluate('window.stage08Result')
                page.screenshot(path=str(screenshot), full_page=False, timeout=30000)
                (root / 'work/previews/stage08/browser_samples.dom.html').write_text(page.content())
                report.update(result)
                report['page_errors'] = errors
                report['console'] = console
                report['http_responses'] = requests
                report['screenshot'] = SCREENSHOT.as_posix()
                report['screenshot_sha256'] = digest(screenshot)
                report['runtime_network_requests_local_only'] = all(
                    request['url'].startswith((f'http://127.0.0.1:{server.server_port}/', 'blob:', 'data:'))
                    for request in requests)
                if errors or result['status'] != 'passed' or result['glbs_loaded'] != len(SAMPLES):
                    raise RuntimeError('Five-sample browser check failed: ' + str(errors or result.get('errors')))
                if not report['runtime_network_requests_local_only'] or any(r['status'] >= 400 for r in requests):
                    raise RuntimeError('Unexpected external request or HTTP failure')
            finally:
                instance.close()
        with Image.open(screenshot) as image:
            if image.size != (1440, 1020) or max(ImageStat.Stat(image.convert('RGB')).stddev) < 5:
                raise RuntimeError('Actual browser screenshot is blank or has incorrect dimensions')
            report['screenshot_dimensions_px'] = list(image.size)
        for name, entry in inputs.items():
            if digest(root / f'outputs/stage08/glb/{name}.glb') != entry['sha256']:
                raise RuntimeError('Sample changed while browser was loading it: ' + name)
        report['status'] = 'passed'
        report['actual_browser_executed']=report['executed'] is True
        report['actual_webgl_render']=report.get('page_loaded') is True and report.get('glbs_loaded')==len(SAMPLES) and report.get('capabilities',{}).get('webgl2') is True
        report['sample_sha256']={name:entry['sha256'] for name,entry in inputs.items()}
        report['console_errors']=[row['text'] for row in console if row['type']=='error']+report.get('shader_errors',[])
        if report['console_errors'] or not report['actual_webgl_render']:raise RuntimeError('Actual WebGL rendering or console validation failed')
        report['screenshot_path']=SCREENSHOT.as_posix()
        report['screenshot']={'path':SCREENSHOT.as_posix(),'sha256':digest(screenshot)}
        report['limitations'] = ['Five local compatibility samples only; no full-city performance measurement',
                                 'SwiftShader rendering does not prove hardware GPU availability',
                                 'Browser load, texture-slot color spaces and drawing tested; visual parity with Blender needs image review',
                                 'Source material counts may differ from runtime instances because glTF materials can be shared or cloned',
                                 'No streaming, runtime LOD switching or stage09 viewer implemented']
        return report
    except Exception as error:
        report['status'] = 'failed'
        report.setdefault('errors', []).append(str(error))
        raise
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        write_json(root / REPORT, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare', action='store_true', help='Verify vendor cache; do not launch browser')
    action.add_argument('--check', action='store_true', help='Actually load and render all five exported GLBs')
    args = parser.parse_args()
    result = run() if args.check else prepare()
    print(json.dumps({'status': result['status'], 'executed': result.get('executed', False),
                      'report': REPORT.as_posix()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
