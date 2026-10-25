"""Self-contained offline viewer ZIP; original authoring project is kept separately."""
from pathlib import Path
import hashlib,json,shutil,zipfile,py_compile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/stage09_local_viewer.zip'
def sha(p):
 with p.open('rb') as s:return hashlib.file_digest(s,'sha256').hexdigest()
def main():
 base=ROOT/'outputs/stage09/resources';manifest=json.loads((base/'manifest.json').read_text());prefix='la-local-viewer/'
 server=(ROOT/'scripts/stage09_server.py').read_text().replace('ROOT=Path(__file__).resolve().parents[1]','ROOT=Path(__file__).resolve().parent')
 server=server.replace("base=ROOT/'outputs/stage09/resources'","base=ROOT/'resources'").replace("base=ROOT/'viewer/dist'","base=ROOT")
 server=server.replace("ROOT/'viewer/dist/index.html'","ROOT/'index.html'").replace("ROOT/'outputs/stage09/resources/manifest.json'","ROOT/'resources/manifest.json'")
 compile(server,'start.py','exec')
 files={}
 for p in (ROOT/'viewer/dist').rglob('*'):
  if p.is_file():files[str(p.relative_to(ROOT/'viewer/dist'))]=p
 required={base/r['url'] for r in manifest['resources']}
 required.add(base/'manifest.json')
 for folder in ('textures','textures-low','metadata','vendor','comparison'):
  required.update(p for p in (base/folder).rglob('*') if p.is_file())
 for p in required:files['resources/'+str(p.relative_to(base))]=p
 for p in (ROOT/'viewer/src').rglob('*'):
  if p.is_file():files['source/src/'+str(p.relative_to(ROOT/'viewer/src'))]=p
 for name in ('package.json','package-lock.json','tsconfig.json','index.html'):files['source/'+name]=ROOT/'viewer'/name
 for p in (ROOT/'docs').glob('stage09*.md'):files['docs/'+p.name]=p
 # Preserve actual source/license registers with the offline model package.
 # Raw research photographs and the full authoring data archive stay in the
 # project; these registers do not grant rights beyond their recorded terms.
 for name in ('sources.md','stage02/sources.md','stage03_sources.md','stage04_sources.md','stage05_sources.md','stage06_sources.md'):
  p=ROOT/'docs'/name
  if p.is_file():files['docs/source_history/'+name]=p
 for stage in ('stage02','stage04','stage05','stage06'):
  p=ROOT/'data/processed'/stage/'source_registry.json'
  if p.is_file():files['docs/source_history/'+stage+'_registry.json']=p
 files['authoring_sample/stage09_runtime_checkpoint.blend']=ROOT/'scenes/stage09_runtime_checkpoint.blend'
 readme='''洛杉矶本地查看器 · 阶段09

解压整个文件夹，安装Python3.10以上后运行：
  python start.py
浏览器打开 http://127.0.0.1:8090 。浏览时不需Node、Blender或互联网。
Windows也可运行start.bat；macOS/Linux可运行python3 start.py。
请使用支持WebGL2的浏览器。数据、纹理、解码器和来源署名均在本包内。

W/A/S/D自由飞行，Q/E升降，Shift加速，F飞行，O环绕，G概览，H说明。
默认鼠标左键环绕、右键平移、滚轮缩放，单击模型查看属性。

中档按本次CPU软件测试降低内部分辨率/材质开销；具体帧率与验证边界见docs/stage09_performance.md。
完整作者工程仍在原项目scenes/stage08_city_medium.blend及两个链接源；本包的authoring_sample只是实际运行时抽样检查点。
source目录提供查看器源代码，重新构建需按package-lock安装Node依赖。
不同年份的建筑与地形资料混合，源高度和立面存在明确近似；本包不是同日城市快照或测绘成果。
原始地理数据的使用条件与软件MIT许可分开；可见署名在查看器底部及来源面板。
'''
 members=[]
 with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as archive:
  for name,p in sorted(files.items()):
   archive.write(p,prefix+name);members.append({'path':name,'bytes':p.stat().st_size,'sha256':sha(p)})
  for name,content in [('start.py',server),('README.txt',readme),('start.bat','@echo off\r\ncd /d "%~dp0"\r\npy -3 start.py %*\r\n')]:
   payload=content.encode();archive.writestr(prefix+name,payload);members.append({'path':name,'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()})
  archive.writestr(prefix+'PACKAGE_MANIFEST.json',json.dumps({'stage':9,'files':members,'source_catalog_sha256':sha(base/'manifest.json')},ensure_ascii=False,indent=2))
 with zipfile.ZipFile(OUT) as archive:assert archive.testzip() is None
 report={'status':'built_zip_crc_verified','path':str(OUT.relative_to(ROOT)),'bytes':OUT.stat().st_size,'sha256':sha(OUT),'members':len(members)+1,'all_runtime_models_textures_decoders_local':True,'full_authoring_city_included':False,'representative_native_checkpoint_included':True}
 (ROOT/'work/reports/stage09/package_build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
