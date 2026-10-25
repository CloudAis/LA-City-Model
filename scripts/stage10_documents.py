"""Assemble final factual docs only from completed measurements."""
from datetime import datetime
from zoneinfo import ZoneInfo
import json,shutil,collections
from stage10_common import *
g=read('work/reports/stage10/geography.json');p=read('work/reports/stage10/performance.json');n=read('work/reports/stage10/master_geometry.json');r=read('work/reports/stage10/runtime_geometry_after.json');s=read('work/reports/stage10/showcase.json');a=read('work/reports/stage10/administrative_scope_check.json');v=read('work/reports/stage10/video.json');ln=read('work/reports/stage10/landmark_native.json');assert a['status']=='passed'
date=datetime.now(ZoneInfo('Asia/Singapore')).isoformat();citykm=g['administrative_boundary']['area_projected_m2']/1e6;finekm=g['coverage']['actual_refined_building_footprint_union_m2']/1e6
stage_rows=[
 ('01','范围、单位、环境和可运行工程','米制样板、真实范围、Blender与浏览器技术检查','历史样板重开/尺寸/图像及冻结清单；最终环境复核','通过','metadata/history/stage01_calibration_medium.manifest.json;metadata/acceptance/environment.json','旧市界概化版仅保留为阶段01历史，当前使用2025完整边界'),
 ('02','真实数据、来源、精度和时间档案',f'全市来源、{g["buildings"]["counts"]["active"]:,}有效建筑记录；完整来源登记','本次逐行/几何检查、年代/单位/许可登记核对','部分通过','metadata/source_registry/;metadata/acceptance/geography.json','县高度字段定义与公开分发许可未明确；缺少完整近期LAS/LAZ与同日城市快照'),
 ('03','坐标、真实地形、水体和底座',f'{citykm:.3f}km²行政分块域、1554块、米制UTM/NAVD88地面','13位置/道路控制、38对运行时LOD边界、原DEM与变换记录','部分通过','metadata/coordinate_system.json;metadata/acceptance/spatial_validation.json','计算误差不等于测绘精度；部分水位、海面和场地整平为估计，远景回退与局部地面仍有视觉过渡'),
 ('04','道路、桥隧、铁路和交通设施','真实来源交通网络、分级断面及估计纵断面；原生薄面朝向修复','全量模型数值/索引检查、实际立交机位、原交通审计保留','部分通过','metadata/acceptance/master_build.json;previews/checks/freeway_interchange/;docs/history/stage04_validation.md','桥隧净空/高程与部分道路宽度推断；没有全城工程级穿地/断路逐项复核'),
 ('05','真实轮廓建筑、街区和天际线',f'1,096,386一般建筑可绘制ID；真实轮廓、来源高度与推断分开','全量GLB解码/ID检查、全部原生网格数值检查；原62栋类型样本保留','部分通过','metadata/acceptance/runtime_geometry_after.json;metadata/acceptance/geography.json;docs/history/stage05_validation.md','大量高度未独立核实；县屋顶线是足迹代理；全城建筑基础/入口与重叠风险未全部复核'),
 ('06','十个独立精修地标','10个有资料的近似；最终独立PBR原生资产和30标准GLB','逐资产关闭重开、贴图检查、来源位置/朝向、十地标实际图索引','部分通过','landmarks/;metadata/acceptance/landmark_native.json;previews/landmarks/index.html','全部仍有观察盲区；复杂曲面/细部及近年扩建/改造未完整复原，不能按轮廓可识别就计精修通过'),
 ('07','两个近景街区精修',f'HistoricCore/CivicCenter共0.28km²工作窗；100栋细化足迹约{finekm:.4f}km²','四光照街景/入口抽查、原近景地面与几何审计、固定来源ID','部分通过','previews/checks/historic_street/;previews/checks/civic_street/;docs/history/stage07_final.md','仅5栋有重点外观研究；100栋并非逐栋实测精修，地面/门厅/坡面仍近似'),
 ('08','PBR、光照和视觉风格','14类原创PBR、实际程序砖烘焙、四个正确时区太阳预设','最终同机位四张1920×1080 CPU图；48个实际WebGL检查图；GLB实际回载','部分通过','previews/native_lighting/;metadata/acceptance/native_lighting.json;docs/history/stage08_export.md','16采样有噪声，未达到全城照片写实；实时玻璃/阴影/间接光兼容取舍与Cycles不同'),
 ('09','优化、分块与本地查看器',f'8919资源、自动LOD/缓存释放、关键交互；新预算中档巡游{p["tour_fps"]:.2f}FPS','当前构建23项实际浏览器检查、3轮巡游、错误注入恢复、释放','通过','metadata/acceptance/browser_check.json;docs/PERFORMANCE.md','按用户许可降低软件设备性能目标；原生1080p30FPS未达标；只测本Linux软件浏览器，未认证硬件GPU/所有平台'),
 ('10','全面核查、修复、展示和交付','零面积面修复、相对路径主工程、独立资产、图/视频/文档与来源许可分离','全量运行时及原生数值检查、干净会话重开、样本配置改建、最终目录启动和成果哈希','通过','metadata/acceptance/;docs/DELIVERY.md;metadata/DELIVERY_MANIFEST.json','本阶段交付流程完成，不代表前述数据、写实、工程精度和许可缺口全部通过')]
table='|阶段|目标|实际成果|验证方式|结果|证据路径|遗留问题|\n|---|---|---|---|---|---|---|\n'+'\n'.join('|'+ '|'.join(row)+'|' for row in stage_rows)
acceptance=f'''# 十阶段最终验收报告

版本1.0.0；{date}（Asia/Singapore）。**整体：部分通过。** 已交付可以打开、检查和本地浏览的真实地理城市工程；下表不把技术检查、可识别地标或低数值误差冒充最终照片写实/测绘/工程合规。

{table}

## 本轮实际修复

新主工程仅对明确分类的开放交通薄面反向三角形作绕序修正，4561165面，保留顶点和相应UV；桥面底面等特殊结构不盲目翻转。原工程未覆盖。8919实时资源全量解码后，在813个派生文件中仅删除249786个量化后精确零面积面；修复后{r['triangles_including_exclusive_lods']:,}三角形（包含互斥LOD），零面积、非数值、越界索引、混合面ID和缺失贴图均0，1,096,386一般建筑ID仍有实际可绘制几何。

最终主工程30141份唯一网格、118557419三角形（包含隐藏LOD/共享库），全量数值检查通过、原生精确零面积面0。初始工作视图限制为HistoricCore约1409177三角形。30份结构拓扑样本保留开放边和复杂接点，不为让计数归零强行封闭真实开放结构。没有把数字检查扩大解释为全城任意两面穿插均已检查。

查看器增加真实来源远景地形回退、与局部分块一致的显示/拾取掩码，修复远处地标因地面漏载看似悬空的问题。分层预算保留近景道路中间LOD，修复极低预算下直接跳到省略支路的远景模型。失败候选已保留，未用于最终展示。当前低/中/高仍有明确简化，详见性能报告。

## 地理、年代与精细面积

当前行政基准为Census TIGER/Line2025 LosAngeles city/GEOID0644000，法律参考日2025-01-01，约{citykm:.3f}km²。1554分块域覆盖该多边形；域覆盖不等于每平方米表面无缺口或已精修。SantaMonica、BeverlyHills为独立城市且未启用背景。原始2020概化市界仅作历史保留。

本次1,096,502个活动建筑轮廓全部作行政相交检查；非相交记录{len(a['nonintersecting_building_ids'])}，跨界完整建筑{a['boundary_crossing_geometries']}。保留相交整栋时，建筑可越过市界几米，并不表示加入整个邻市。

Downtown工作窗16km²；HistoricCore和CivicCenter各350×400m，工作窗合计0.28km²。100栋实际细化建筑足迹并集约{finekm:.4f}km²，5栋研究建筑约{g['coverage']['reference_guided_five_building_footprint_union_m2']/1e6:.4f}km²。足迹面积、工作窗面积和已完全核实的精修面积分开；逐栋实测立面完成数为0，不能把工作窗整块涂成全精修通过。

县轮廓主要实际年份2008，另有1992/2003/2014/2017/2020；OSM数据库状态2026-10-20不是每条要素采集年。Downtown1m DTM采集2023-01-08至2024-01-07，2025发布；全市约10m DTM多来源采集年未知；NLCD2021。太阳参考日2025-09-21与城市资料年代分开。

## 未被本轮消除的缺口

大量县/OSM高度只为来源报告而非独立核验；HEIGHT/ELEV语义缺口保留，不把ELEV直接混入NAVD88。大部分立面、屋顶类型、材料、设备、窗灯和设施尺寸为推断/原创视觉补充。十地标有资料盲区及近年改建状态未核，水位/海岸瞬时水线/河槽细节不足。

阶段05曾记录6151个高台基、305个入口连接及208个建筑/估计道路重叠候选；后续局部近景修整后，尚无逐项全城工程复核证据。这些是历史风险候选，不当作最终确认缺陷数量，也不当作已经全部修复。桥隧高度、净空、场地整平和无障碍细节仍有推断。近景地面色差、局部坡面/接口和远近LOD过渡仍可见。

本项目为外景；简化入口/室内替代不保证可进入。树木只按取得的点位和通用模板，不是完整街树清单。场景未做工程、测绘或完整现状城市认证。完整冷联网重建和所有设备长期运行未测试。
'''
(DELIVERY/'docs/FINAL_ACCEPTANCE.md').write_text(acceptance)
write('work/reports/stage10/final_stage_table.json',{'overall':'部分通过','version':'1.0.0','created_at':date,'rows':[dict(zip(['stage','goal','actual','validation','result','evidence','remaining'],row)) for row in stage_rows]})
heights=g['buildings']['height_evidence'];denom=g['buildings']['counts']['active'];hr='\n'.join(f'|{k}|{v:,}|{v/denom*100:.6f}%|' for k,v in heights.items())
coord='''# 坐标、范围与来源口径

全局交换坐标WGS84/EPSG:4326；米制工作坐标WGS84/UTM11N/EPSG:32611。Blender/项目X为网格东、Y为网格北、Z为上，1BU=1m；UTM原点(384992.75594820484,3767182.3649733574)。glTF仅转换一次(x,y,z)→(x,z,-y)。每块的origin_city_m为外部地理位置，几何为局部米坐标；查看器按1000m格网重置渲染原点。

Downtown参考UTM网格收敛角约−0.697480°；参考真北的网格方位约+0.69749°。指南针是该参考换算，坐标小数位和正反算误差不表示原数据精度。

USGS裸地地面为NAVD88米；未知建筑ELEV不当绝对高程。源英尺先按各条目定义转换，美国测量英尺为1200/3937m，国际英尺为0.3048m。水位0或其他显示估计不作为已核基准转换。视觉整平、基础和台阶为有记录推断，不改写原始DEM。

metadata/coordinate_system.json保存完整投影、原点、轴向和矩阵；metadata/terrain_tile_index.json保存分块地理范围、原点、邻接和数据覆盖；tiles/manifest.json为实际实时资源清单。landmarks独立GLB已经烘焙到城市网格朝向，定位时只加origin_city_m，不能再次套源资料卡yaw。

原始资料、处理数据、推断和艺术补充不能合成一个“真实性百分比”。以下仅为全部活动来源建筑高度字段的证据分布，分母1096502；地标补充公布尺寸另见资料卡，不混入此分母。

|高度证据|数量|占来源建筑分母|
|---|---:|---:|
'''+hr+'''

“source_reported_county_import_unverified”不能当独立实测；OSM部分县编号/高度共享县来源血统。县屋顶线作为足迹代理，水平位置也不能当外墙测绘。立面、类型默认、屋顶设备、材质和窗灯绝大多数为来源引导推断或原创视觉模块；不把HEIGHT数值非空当作已核高度完整率。
'''
(DELIVERY/'docs/COORDINATES_AND_DATA.md').write_text(coord)
delivery=f'''# 使用与维护 ·1.0.0

完整本地交付目录：outputs/LA_Delivery。它是本任务的私有本地工作副本，含许可尚未明确的市/县派生资料，不能据此推定可公开/商业再分发。许可明确的代码/原创材质另有单独资源包，未明确条款的数据只保留来源、获取方法和依赖说明。详见LICENSES_AND_DEPENDENCIES.md。

## 打开完整主工程

Blender4.3.2打开LA_Master.blend，保留整个assets目录，尤其assets/linked/stage07_city_medium.blend和stage07_final.blend。它是完整可编辑城市的关联组织，不是六样本检查场景。默认HistoricCore约1409177三角形、米制、材质色实体视图，渲染使用CPU Cycles。99_FINAL_CHECK_CAMERAS保存十二个检查机位。

不要只复制主文件而遗漏关联库。相同工作区为节约磁盘对未修改文件使用硬链接；另存为新文件再编辑，避免改动冻结来源。拷贝到别的磁盘/机器时普通复制文件即可，不依赖原始绝对工作区路径。独立地标landmarks/*.blend已逐个保存/关闭/重开，包含三LOD及打包PBR纹理，不需要原工程库；它们均保持有资料的近似状态。

## 启动实际本地查看器

从交付目录运行：

```bash
python start.py --port 8090
```

同机浏览器打开http://127.0.0.1:8090。若端口已被旧阶段服务占用可改为8093。Python3.10+与WebGL2即可，运行时无需Node/Blender/互联网。云环境localhost不是用户电脑localhost；下载本地查看器工作副本或复制交付目录到本机后启动。

鼠标左键环绕，右键平移，滚轮缩放；F飞行、O环绕、G概览、H说明；飞行时WASD、QE升降、Shift加速，左键调整朝向。单击模型查看ID、来源、年份和高度证据。可切换图层、四光照、三质量、两个近景区和十地标。自由飞行没有实体碰撞，不是行人导航系统。/previews/index.html展示检查图，/video/city_tour.mp4为巡游。

云端低配优先低档；中档内部960×540实测巡游{p['tour_fps']:.2f}FPS，复杂HistoricCore约9–10FPS；原生1080p街景{p['native1080p_street_fps']:.2f}FPS。高档600k局部目标、PBR映射、阴影关闭、玻璃不透射兼容，原始物理材质保留在原生/GLB中。详见PERFORMANCE.md，不将图像输出15FPS当作实时测试。

## 修改配置并重建样本区域

本包包含HistoricCore两栋真实建筑的源数组与元数据，配置config/sample.json。重建使用实际测试的Python3.12.14与锁定NumPy；仅浏览查看器的Python3.10+要求与重建环境分开。可使用原工作区.venv，或创建Python3.12环境：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r scripts/requirements-sample.txt
.venv/bin/python scripts/rebuild_sample.py --config config/sample.json --output tiles/rebuild/my_sample.glb
```

Windows相应Python为.venv\\Scripts\\python.exe。样本依赖锁定实际NumPy版本；不要求安装全套地理依赖。include_window_frames和roughness_multiplier可调整，随机种子固定。此命令已实际执行：68725面→18469面、SHA改变、原点不变，并实际导入空场景复查。样本不是整个城市全联网冷构建，也不会覆盖已验收分块。

GLB为局部坐标，旁边JSON记录origin_city_m与稳定ID。独立地标GLB为标准可直接导入版本；实时tiles为带Meshopt的版本，查看器已含本地解码器。要将新模型接入查看器，登记局部原点、轴向、范围、LOD、来源/精度、属性包、SHA及字节数，并按稳定ID替换旧主体，避免追加重复代理。

## 编辑、导出、扩展

主工程中的链接几何应在新副本的关联库编辑，或MakeLocal后另存。近景按r2_building/source_uid组织，地标按stable_id与近/中/远集合组织。不要为构图移动地理位置。新增街区先选真实多边形，核对城市归属，取得有使用依据的轮廓/地形/交通并登记年代、单位和许可；缺失尺寸推断要单列。新增地标先建资料卡与体量、核对高度定义/朝向，再细化，保留未观察部分。

scripts/inspect_scene.py支持固定机位/光照和按稳定ID导出，Blender调用示例与实际命令检查见metadata/acceptance/command_checks.json。渲染输出1920×1080/16采样CPU；不要覆盖LA_Master.blend或已登记分块。完整地理处理/城市再生成仍使用原项目scripts与config及原始数据档案；本交付不声称已作新机器全联网冷重建。原始县/城市资料若缺失，按来源登记获取并自行确认使用条款，不能用空文件替代成功。

修改查看器：viewer/source中npm ci、npm run build；package-lock固定Three0.179.1、meshoptimizer1.3.0、TypeScript7.0.2、Vite8.3.5。生产目录viewer/dist的实际依赖包含本地解码器/WASM和MIT许可；运行时不能只复制HTML而丢弃tiles。开发node_modules链接只是当前工作区便利，不属于可移植运行依赖，公开包与本地查看器包均不携带该链接。

完整工程需要足够内存/磁盘；本次CPU4核、32GiB、GPU/显存未知。Blender后台打开约9–12GiB工作集；全部最高LOD同时显示会增加开销。磁盘紧张采用完整目录加相对关联，最低操作保留0.75GiB；全城冷重建需要另行预算空间，未以本次余量认证。不要删除来源缓存和旧正式检查点来隐藏缺口。
'''
(DELIVERY/'docs/DELIVERY.md').write_text(delivery)
licenses='''# 许可、来源与准确依赖

本交付区分完整本地工作目录与可再分发子集。完整LA_Delivery包含用户任务中已取得资料的本地派生模型，不是整包公开/商业授权声明；没有对外发布。县/市资料许可尚未明确，不等于已被证明禁止所有本地使用，但也不能因可公开查询就推定无限再分发权利。

## 随可再分发子集提供

本项目原创通用PBR纹理/程序砖材质、相应原生材质库、本人任务中编写的代码、依赖锁与说明；Three.js和meshoptimizer按各自MIT许可保留原文。USGS/Census公开资料的许可与OSM ODbL义务分别登记，不能扩张到县/市和照片。没有研究照片贴图或远程标准瓦片抓取。

## 不放入可再分发子集

县LARIAC屋顶线与未明确再分发条款的市级要素、LA Times街区参考多边形、研究照片/影像、含这些资料的城市派生GLB/主工程/关联几何和独立地标数据。它们只保留于本任务本地工作副本，分发前须按原条款确认。不能把软件MIT许可套在这些数据上。

确切依赖：LA_Master.blend→assets/linked/stage07_city_medium.blend与stage07_final.blend，以及打包或相对assets/textures的图像；查看器→tiles/manifest.json列出的8919GLB、metadata属性包、textures/textures-low及本地解码器。可再分发资源包不会以空GLB伪装完整城市，缺失数据不返回成功。

## 来源与获取

- LA市建筑服务：https://maps.lacity.org/lahub/rest/services/Landbase_Information_WFS/MapServer/0
- 县建筑条目：https://www.arcgis.com/home/item.html?id=e6a1e375e12a4fe6849d896a26ec028a；产品归档/真实下载地址、原始SHA与采集年见metadata/source_registry/source_stage02.json和source_stage05.json，不能把条目更新时间当采集年。
- OSM/Geofabrik矢量来源、冻结PBF时间及使用条件见source_stage04.json；署名©OpenStreetMap contributors，https://www.openstreetmap.org/copyright，ODbL1.0。不采用标准瓦片批量预取。
- USGS3DEP DEM/Lidar入口：https://apps.nationalmap.gov/lidar-explorer/；已取得DEM与未取得LAS/LAZ分开，准确瓦片和下载地址见来源登记。
- Census TIGER/Line2025、NLCD2021及树冠资料分别继承逐条来源与单位档案。
- 地标官方页面、CC/公共领域研究图的逐图许可和观察盲区见source_stage06.json与landmark_cards。本交付没有复制未授权官网图片。

重建依赖原项目固定数据档案和许可前提。获取入口/配置存在不表示已在新机器完成下载或能够重建同日实况；失败、未知与未实现应明确报告。metadata/license_manifest.json列出分组策略；最终资源哈希与状态在DELIVERY_MANIFEST.json。
'''
(DELIVERY/'docs/LICENSES_AND_DEPENDENCIES.md').write_text(licenses)
write('outputs/LA_Delivery/metadata/license_manifest.json',{'version':'1.0.0','full_local_tree':'private working handoff, not a public/commercial blanket license','groups':[{'paths':['LA_Master.blend','assets/linked/','tiles/','landmarks/','sample_inputs/'],'redistribution':'not cleared for public bundle','reason':'Mixed county/city/LA Times derived inputs; preserve registered terms and obtain necessary clearance'},{'paths':['assets/textures/stage08/','assets/materials/stage08/'],'redistribution':'project-authored reusable materials; registry kept','reason':'Original generic PBR and actual procedural bake, no research-photo textures'},{'paths':['viewer/dist/licenses/'],'redistribution':'MIT notices included','reason':'Three.js and meshoptimizer, separate from geodata rights'}],'source_registers':['metadata/source_registry/source_stage02.json','metadata/source_registry/source_stage04.json','metadata/source_registry/source_stage05.json','metadata/source_registry/source_stage06.json'],'no_external_publication_performed':True})
(DELIVERY/'README.md').write_text(f'''# 洛杉矶城市外景 ·1.0.0

最终核查与本地交付已整理，整体验收**部分通过**，保留明确的数据、写实与工程接口缺口。

打开LA_Master.blend，保持assets/linked和纹理目录相对位置；独立资产见landmarks。查看器从本目录运行`python start.py --port 8090`，同机浏览器访问http://127.0.0.1:8090。

行政分块域约{citykm:.3f}km²，Downtown重点工作窗16km²，两个近景工作窗0.28km²；100栋细化足迹约{finekm:.4f}km²，十地标均为有资料的近似，非完整测绘精修。

[展示图与四光照](previews/index.html) · [十地标索引](previews/landmarks/index.html) · [24秒实际视口视频](video/city_tour.mp4) · [最终验收表](docs/FINAL_ACCEPTANCE.md) · [打开/维护/重建](docs/DELIVERY.md) · [性能](docs/PERFORMANCE.md) · [许可与依赖](docs/LICENSES_AND_DEPENDENCIES.md)。

本目录为任务中的完整私有本地工作副本。许可尚未明确的县/市派生数据没有作为已获公开授权的数据提供；可再分发子集另行打包。不能只复制主文件或viewer/dist而遗漏实际依赖。
''')
(DELIVERY/'metadata/acceptance').mkdir(parents=True,exist_ok=True)
for source in REPORTS.glob('*.json'):
 if 'in_progress' not in source.name:shutil.copy2(source,DELIVERY/'metadata/acceptance'/source.name)
print('FACTUAL_FINAL_DOCS_WRITTEN',date,flush=True)
