"""Local-only browser capability test, not the stage 09 city viewer."""
import functools
import html
import http.server
import json
import re
import shutil
import subprocess
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright


def probe(root, render_path):
    preview = root / 'work/previews'
    relative_image = Path(render_path).relative_to(root).as_posix()
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>LA Stage 01 / Review</title>
<style>*{box-sizing:border-box}body{margin:0;background:#101d2b;color:#e7ecef;font:16px system-ui,sans-serif;padding:32px}header{display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid #375363;padding-bottom:20px}h1{margin:8px 0;font-size:32px}small{color:#9bb6c6}.tag{color:#f6be60}main{display:grid;grid-template-columns:1.1fr 1fr;gap:24px;margin-top:24px}section{background:#182a39;border:1px solid #304959;border-radius:12px;padding:20px}img{width:100%;display:block}h2{font-size:18px}p{line-height:1.8}#probe{white-space:pre-wrap;font-size:12px;color:#add8c1}</style>
<header><div><small>LOS ANGELES / GEOGRAPHIC CITY EXTERIOR</small><h1>第一阶段 · 范围与米制校准</h1></div><b class="tag">STAGE 01 / ACTUAL ARTIFACT REVIEW</b></header>
<main><section><h2>Blender CPU render / synthetic calibration</h2><img src="/''' + relative_image + '''"><p>测试建筑主体 12 × 18 × 24 m；标尺 20 m，每格 1 m。<br>合成技术样板，不是真实洛杉矶建筑。</p></section>
<section><h2>Geographic scope / preserved relative positions</h2><img src="/work/previews/scopes.svg"><p>行政范围：U.S. Census 2020 / 1:500,000 概化版本。<br>Downtown：4 × 4 km；近景工作窗：两处，总计 0.28 km²。<br>Santa Monica 与 Beverly Hills 单独登记，默认未启用。</p><h2>Browser capability probe</h2><pre id="probe">pending</pre></section></main>
<canvas id="capability" width="16" height="16" hidden></canvas><script>
const c=document.getElementById('capability');let gl=c.getContext('webgl2');const result={page_loaded:true,webgl2:!!gl,renderer:null,hardware_gpu_proven:false,images_ok:false};
if(gl){const ext=gl.getExtension('WEBGL_debug_renderer_info');result.renderer=ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);}
window.addEventListener('load',()=>{result.images_ok=[...document.images].every(i=>i.complete&&i.naturalWidth>0);document.getElementById('probe').textContent=JSON.stringify(result,null,2);document.body.dataset.probeComplete='true';});
</script></html>'''
    key=Path(render_path).stem
    page_path=preview/(key+'_review.html')
    page_path.write_text(page)
    (preview / 'stage01_review.html').write_text(page)
    browser = shutil.which('chromium')
    if not browser:
        raise RuntimeError('Chromium unavailable: browser preview and screenshot unverified')
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1',0), functools.partial(Quiet,directory=str(root)))
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/work/previews/{page_path.name}'
    screenshot = preview / (key+'_browser.png')
    if screenshot.exists(): screenshot.unlink()
    flags = ['--no-sandbox','--disable-dev-shm-usage','--disable-background-networking',
             '--use-angle=swiftshader','--enable-unsafe-swiftshader']
    try:
        messages=[]
        with sync_playwright() as p:
            b=p.chromium.launch(executable_path=browser,headless=True,args=flags,timeout=30000)
            try:
                page=b.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
                page.on('pageerror',lambda e:messages.append(str(e)))
                response=page.goto(url,wait_until='load',timeout=30000)
                if response.status!=200:raise RuntimeError('Local review page HTTP failure')
                page.wait_for_function('document.body.dataset.probeComplete === "true"',timeout=20000)
                result=json.loads(page.locator('#probe').inner_text())
                page.screenshot(path=str(screenshot),full_page=False,timeout=20000)
                (preview/(key+'_review.dom.html')).write_text(page.content())
            finally:b.close()
        browser_log=root/'work/logs'/(key+'_browser.log')
        browser_log.write_text(json.dumps({'driver':'Playwright','page_errors':messages,'args':flags},indent=2)+'\n')
        if messages:raise RuntimeError('Browser page JavaScript errors: '+str(messages))
        if not result['page_loaded'] or not result['images_ok'] or not screenshot.exists():
            raise RuntimeError('Browser did not load expected generated artifacts')
        from PIL import Image, ImageStat
        with Image.open(screenshot) as im:
            if im.size != (1440,1100) or max(ImageStat.Stat(im.convert('RGB')).stddev)<5:
                raise RuntimeError('Browser screenshot dimensions or variance invalid')
        report = {'status':'passed','driver':'Playwright / installed Chromium',
                  'page_loaded':True,'screenshot_path':str(screenshot),
                  'screenshot_dimensions_px':[1440,1100], 'capabilities':result,
                  'security_context':'sandbox disabled for isolated, trusted localhost probe; not instructions for external browsing',
                  'interactive_city_viewer_implemented':False}
        (root/'work/reports/browser.json').write_text(json.dumps(report,indent=2)+'\n')
        (root/'work/reports'/(key+'_browser.json')).write_text(json.dumps(report,indent=2)+'\n')
        print('BROWSER_SCREENSHOT_OK', json.dumps(result))
        return report
    except Exception as e:
        (root/'work/logs/browser_failure.log').write_text(str(e)+'\n')
        raise
    finally:
        server.shutdown()
        server.server_close()

