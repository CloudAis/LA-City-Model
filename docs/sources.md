# 来源登记

实际原始响应位于 data/raw；取得时刻、字节数、SHA-256 和不可变 Git 提交 URL 在相邻 *.receipt.json。
config/sources.lock.json 锁定每个源文件与哈希。原始响应未清洗、未重投影、未简化。
执行 scripts/fetch_stage01_sources.py 可校验本地数据或按不可变地址恢复缺失数据，不覆盖不匹配文件。

| 来源 | 原始文件 | 用途 / 权威性 | 时间与精度 | 许可与限制 |
|---|---|---|---|---|
| U.S. Census Bureau / CitySDK 官方 GitHub 归档 | census_2020_ca_places_500k.geojson | 建制城市边界，按 GEOID 提取 LA、Santa Monica、Beverly Hills | 2020 / 1:500,000 cartographic boundary | 美国联邦 Census 地理数据一般为 public domain；不代表现行法律地界或地块测绘精度 |
| CitySDK 上游说明 | census_citysdk_README.md | 确认发布者、归档状态、cartographic GeoJSON 层级 | 获取时 Git 提交固定 | CitySDK 代码已归档且提示不用于 production，本工程只读取静态数据，不执行其代码 |
| LA Times / Mapping LA，经 Code for Germany click_that_hood 转存 | la_neighborhoods.geojson | Downtown 参考多边形及投影质心；编辑性街区，非行政范围 | GeoJSON 属性时间为 2013；地图来源不明示更新版本 | 原数据权利属于其来源，不能把转存项目代码 MIT 许可自动套到 LA Times 数据；公开或商业再分发前需核对原始条款 |
| click_that_hood 来源元数据 | la_neighborhoods_metadata.json | 明确 dataTitle=Los Angeles Times，dataUrl 指向 Mapping LA | 固定提交 | 来源链证据；不是独立的地理测绘精度证明 |
| click_that_hood 软件许可 | click_that_hood_LICENSE.txt | 保留 MIT 许可原文 | 固定提交 | 仅证实该软件许可，不扩张原始地图权利 |
| 本项目 Python / Blender 生成 | 校准建筑、标尺、轴、地面、材质、灯光、相机 | artistic_synthetic，用于尺度和运行验证 | 第一阶段 | 本工程原创；无下载的建筑/材质/贴图，不冒充真实地标 |

不可变上游提交：

- Census: `fc5d7880529fedcde181269fc5d518767221281e`
- click_that_hood: `48ba05ad4c6969e3b3c25735492169227ae411f1`

行政归属由 Census GEOID + LSAD=25 独立记录核对：LA=0644000、Santa Monica=0670000、Beverly Hills=0606308。
保留背景城市独立几何且 enabled=false；概化图中可能有海岸或边界细微重叠，不据此重新定义行政归属。
来源中的官方 ALAND/AWATER 面积与概化多边形计算面积含义不同，不强行让两者相等。

## 派生与推断

原始 Downtown 存在微小自交，processed 中使用 GEOS make_valid，只保留多边形部分；面积变动和原始错误见报告。
4×4 km 焦点是项目定义的工作窗，非市政划定 Downtown 边界。
两个 350×400 m 近景窗为项目选定，覆盖 Historic Core 与 Civic Center 的代表性街区；街道级边沿尚待道路数据确认。
原始观察数据和 processed 数据不混放；工作窗标记 inferred；校准几何标记 artistic_synthetic。

## 阶段 01 网络限制历史（已于阶段 02 重新调查）

首次访问 geohub.lacity.org、www.arcgis.com 和 en.wikipedia.org 均得到代理 403，未取得其正文，不能声称已核查。
使用已允许的 GitHub 获取并校验上述静态来源；未绕过网络限制、未关闭 TLS 或修改校验值。
环境草稿中已登记后续官方地理来源所需域名，保存草稿不代表当前运行时已放行或环境已发布。
阶段 02 已实际获取与核验的来源、下载日期、数据年代、CRS、垂直基准、精度未知项、许可和本地哈希，
见 [完整来源登记](stage02/sources.md) 与 `data/processed/stage02/source_registry.json / .csv`。

## 阶段 02 正式输入

- Census TIGER/Line 2025 完整分辨率市界、道路、水体、设施、铁路、海岸线；边界参考日 2025-01-01。
- County LARIAC6 2020 建筑归档，实际每要素采集年 1992–2020，主要为 2008/2014/2017/2020。
- USGS 3DEP Downtown 1 m NAVD88 DEM（2023–2024 采集），全市约 10 m DEM（采集年混合/未知）。
- MRLC/USGS NLCD 2021 分类土地覆盖（约 30 m），不是土地使用分区或当前地籍用途。
- County LARIAC7 2023 Downtown 1 m 树冠掩膜（来源有单位说明矛盾和质量警告）。
- 原始 City Recreation and Parks 75 个 Downtown 查询包络树点；GPS 日期为历史采集日期，不能以第三方条目 2026 更新时间替代。
- City Planning 官方 Historic Cultural Monuments 全服务 1,347 条名称/位置，Designation 日期不是建造年份。
- City GIS 市界作为第二独立来源比较，生效/采集日期未知，不取代明确有版本日期的 Census 主边界。

ArcGIS 页和 2026 更新项只是资料登记日期，不是城市同时相快照；各层年代冲突、来源更新标志和近年未核变化见 docs/stage02/data_readiness.md。
OSM 许可及标准瓦片政策已取得，但 Overpass 有限重试后不可用，没有 OSM 要素进入正式数据，也未请求标准瓦片。
县/市数据原始条款保留，未确认不受限制的公开再分发授权；当前内部工程与联邦公开数据的权限不自动扩张至全部数据及照片。
地标只有官方名称/坐标研究索引，外观照片尚未取得或授权，不能声称精修研究已完成。

## 阶段03补充

City Planning工业/机场/港区规划资料、实际下载日期/参数/哈希和未采用的调查见 [第三阶段补充来源](stage03_sources.md)。水位、材料和当前用途未知项保持明确标识，详见 [第三阶段说明](stage03.md)。

第四阶段交通来源见[阶段四来源登记](stage04_sources.md)及`data/processed/stage04/source_registry.json`：OSM/Geofabrik完整矢量、City桥梁/信号与Metro服务、California MUTCD2026；采集年份、数据库状态、网页时间与下载时间分别记录。交通高度、宽度及设施模板的推断见`docs/stage04.md`。

第五阶段建筑来源及真实使用限制见[stage05_sources.md](stage05_sources.md)和data/processed/stage05/source_registry.json。县屋顶轮廓、OSM报告高度/分部、两个公布高度参考、3个小范围研究影像与原创模块分别登记；同源高度不作为独立验证，影像未用于模型纹理。

## 阶段06独立地标

完整条目在data/processed/stage06/source_registry.json；逐图作者、许可URL、拍摄日期说明与下载日期分开记录。参考图仅限逐图验证的CC/公共领域；官网版权图片未抓取，保存页面链接和文字研究记录。县/OSM轮廓与裸地DEM继承原来源年代/基准；不声称2026同日实况。
# 阶段07补充来源（2026-10-23）

完整逐文件地址、下载/拍摄日期、许可、作者与SHA在`data/processed/stage07/source_registry.json`及`research_registry.json`。
两份OSM小范围矢量XML实际下载于2026-10-23，仅作Historic Core/Civic Center设施和入口研究，©OpenStreetMap contributors，ODbL1.0：<https://www.openstreetmap.org/copyright>。编辑时间不等于实测时间，不覆盖阶段04的冻结PBF。
5栋建筑经Conservancy文字资料/Commons逐图许可参考核查；只复制具有具体CC/PD许可的照片，不用作纹理。错主体/室内/1962年前旧楼资料已排除。Times和Hall of Records初始官方链接失效后找到了有效补充；Spring Arcade官方入口仍404，明确缺口。资料观察及尚未复原的细节见`docs/stage07.md`。
103栋高度来源保持独立登记：83个未核实县导入报告、20个推断，不能被新的网页或细节模块描述为已核实城市实况。旧有原始数据和所有阶段06交付保持不变。

