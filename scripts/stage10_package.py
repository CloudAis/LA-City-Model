"""Local private viewer handoff and a separate cleared-source materials/tools subset."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from stage10_common import *
parser=argparse.ArgumentParser();parser.add_argument('kind',choices=['viewer','cleared']);args=parser.parse_args();files={}
def add_tree(folder,prefix=None):
 folder=Path(folder)
 for p in folder.rglob('*'):
  if p.is_file() and 'node_modules' not in p.parts and '__pycache__' not in p.parts:files[(prefix+'/' if prefix else '')+str(p.relative_to(folder))]=p
if args.kind=='viewer':
 out=ROOT/'outputs/LA_Local_Private_Viewer_1.0.zip';prefix='LA_Local_Private_Viewer_1.0/';catalog=read('outputs/LA_Delivery/tiles/manifest.json')
 for name in ['start.py','start.bat']:files[name]=DELIVERY/name
 add_tree(DELIVERY/'viewer/dist','viewer/dist');files['tiles/manifest.json']=DELIVERY/'tiles/manifest.json'
 for r in catalog['resources']:files['tiles/'+r['url']]=DELIVERY/'tiles'/r['url']
 for folder in ['metadata','textures','textures-low','vendor']:add_tree(DELIVERY/'tiles'/folder,'tiles/'+folder)
 for folder in ['previews','video']:add_tree(DELIVERY/folder,folder)
 for name in ['PERFORMANCE.md','FINAL_ACCEPTANCE.md','LICENSES_AND_DEPENDENCIES.md','COORDINATES_AND_DATA.md']:files['docs/'+name]=DELIVERY/'docs'/name
 add_tree(DELIVERY/'metadata/source_registry','metadata/source_registry');files['metadata/license_manifest.json']=DELIVERY/'metadata/license_manifest.json'
 readme='''洛杉矶 · 最终本地查看器1.0.0（私有工作副本）

完整解压后运行 python start.py ，同机浏览器访问 http://127.0.0.1:8090 。需要Python3.10+和WebGL2，不需要Node、Blender或互联网。Windows可使用start.bat。端口占用时使用 --port 8093。

展示图 /previews/index.html ，视频 /video/city_tour.mp4 。本小包不含完整编辑主工程和关联库；编辑请使用原项目outputs/LA_Delivery完整目录，不能把本小包当作完整作者工程。

中档采用960×540内部渲染；复杂街景帧率低于巡游平均，云端可选低档。性能见docs/PERFORMANCE.md。所有模型及展示来自实际场景，数据年代/高度/细节近似见验收报告。

本包是本次任务本地工作资料的私有副本，包含尚未确认公开再分发条款的县/市派生几何，不能据此推定公开/商业分发许可。许可明确的原创材质/工具另有独立资源包；源页面、获取方法和准确依赖在docs及metadata/source_registry，不包含研究照片。没有对外发布。
'''
else:
 out=ROOT/'outputs/LA_Original_Materials_And_Tools_1.0.zip';prefix='LA_Original_Materials_And_Tools_1.0/'
 add_tree(DELIVERY/'viewer/source/src','viewer/src');add_tree(DELIVERY/'viewer/source/public','viewer/public')
 for name in ['package.json','package-lock.json','tsconfig.json','index.html']:files['viewer/'+name]=DELIVERY/'viewer/source'/name
 for name in ['glb_writer.py','rebuild_sample.py','inspect_scene.py','scene_tools.py','requirements-sample.txt','requirements.lock']:files['scripts/'+name]=DELIVERY/'scripts'/name
 add_tree(ROOT/'assets/textures/stage08','assets/textures/stage08');add_tree(ROOT/'assets/materials/stage08','assets/materials/stage08')
 files['LICENSES_AND_DEPENDENCIES.md']=DELIVERY/'docs/LICENSES_AND_DEPENDENCIES.md'
 readme='''洛杉矶项目1.0.0 · 原创材质与工具子集

包含本项目原创通用PBR/实际程序砖材质与纹理、查看器源码/依赖锁、样本重建和检查代码。Three.js与meshoptimizer的MIT条款保留于viewer/public/licenses；原生材质资产不含市县建筑几何或研究照片。

此子集不是完整城市，也不是一个可以无数据启动的替代模型。LA_Master、关联城市几何、所有县/市/LA Times派生数据、独立地标几何、研究照片以及城市展示图没有放入此可再分发子集。缺少sample_inputs或模型时，相应脚本会明确失败，不能冒充成功重建城市。

完整私有工作目录仍在原项目outputs/LA_Delivery。若需再分发含地理数据的模型，按LICENSES_AND_DEPENDENCIES.md中源登记逐项核对/取得所需授权，并遵守OSM ODbL署名及数据库义务。原创内容的后续许可由项目所有者选择，不能把软件MIT许可自动套到地理数据。
'''
members=[]
with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,p in sorted(files.items()):z.write(p,prefix+name);members.append({'path':name,'bytes':p.stat().st_size,'sha256':sha(p)})
 data=readme.encode();z.writestr(prefix+'README.txt',data);members.append({'path':'README.txt','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()});z.writestr(prefix+'PACKAGE_MANIFEST.json',json.dumps({'version':'1.0.0','kind':args.kind,'files':members,'complete_authoring_city_included':False,'public_city_redistribution_cleared':False},ensure_ascii=False,indent=2))
with zipfile.ZipFile(out) as z:assert z.testzip() is None
report={'status':'passed','kind':args.kind,'actual_zip_crc_verified':True,'path':str(out.relative_to(ROOT)),'bytes':out.stat().st_size,'sha256':sha(out),'members':len(members)+1,'cleared_subset_excludes_unconfirmed_geodata_and_city_models':args.kind=='cleared','not_a_public_license_for_private_city_bundle':True}
write('work/reports/stage10/'+('license_pack' if args.kind=='cleared' else 'viewer_package')+'.json',report);print(json.dumps(report),flush=True)
