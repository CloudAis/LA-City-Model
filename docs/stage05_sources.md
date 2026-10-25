# 第五阶段来源、年份与高度语义

逐条地址、下载日期、单位、精度未知项、使用条件及文件校验见`data/processed/stage05/source_registry.json`，继承阶段二/三/四的完整档案。新增网页原字节及HTTP回执位于`data/raw/stage05/research`；正文提取仅作研究索引，不能代替原文件。

| 来源 | 本阶段用途 | 年代与限制 |
|---|---|---|
| LA County LARIAC6 Countywide Building Outlines(2020条目) | 主屋顶轮廓、原始HEIGHT/ELEV候选 | 实际行记录主要2008，另2014/2017/2020及少量1992/2003；条目2020不等于全市2020实况。字段定义未核实，ELEV不作绝对高程 |
| OSM/Geofabrik California PBF | 用途、报告高度、屋顶、分部、入口、补充轮廓与拆除标记 | 头部数据库状态2026-10-20T20:23:47Z，取得2026-10-22；编辑时间不是采集年。大量县编号/高度共享县源血统 |
| U.S. Bank Tower物业网站 | 1018英尺公布高度 | 本次取得2026-10-23；页面/数据更新日期与数值精度未知，不能当测量控制 |
| Thornton Tomasetti/Wilshire Grand | 1100英尺含尖塔总高 | 本次取得2026-10-23；不是整个足迹的屋面高度。AC Martin提供项目/用途资料，不据名称虚构屋顶细节 |
| OSM Wiki height/levels/roof:shape | 标签单位和语义 | 文档定义不保证每个要素录入正确，不独立证明县原字段定义 |
| USGS原始DTM、阶段四派生显示地形 | NAVD88地面/基础结合 | 延用实际原分辨率与精度未知状态；地面重采样和道路显示修整不是提高原始测绘精度 |
| 本项目程序化模块/材质 | 外观近似 | 原创几何，无第三方照片纹理；位置、尺寸和外观推断不冒充实测 |

县GIS公开访问不是无限制再分发许可；继续保存县免责声明与eGIS条款，未执行对外发布。OSM署名为©OpenStreetMap contributors，按ODbL1.0及相关数据库义务使用，未抓取OSM标准瓦片。研究网页的图像/正文未获纹理再分发授权，未用于模型纹理。

Native GDB元数据、LARIAC4/6产品指南和服务XML均做了实际字段调查，但仍未发现HEIGHT/ELEV的正式定义。调查记录在`work/cache/stage05/gdb_building_definition.txt`、`lariac6_guide.txt`等以及阶段二语义档案。第三方ArcGIS外观场景不作为官方字段证据。受限/失败网页请求保留于`work/logs/stage05/reference_requests.jsonl`，不算取得或通过。

`temporal_corrections.json`保留拆除标记对应关系，`verified_height_references.json`保留两栋公布资料的不同高度定义，`part_review.json`记录分部修正。不将混合年份数据描述成同一天完整城市快照；没有可靠依据的新建/重建和更名对象仍可能漏报。

## 最终补充

3张300×300m范围Esri World Imagery导出PNG仅用于核对异常候选所在的低层环境，位于data/raw/stage05/research/height_review_*.png；采集日期、精度及再分发授权未知，保留请求与SHA，不用于材质。不能从垂直影像直接量出本项目3m估算高度。

展开GDB缓存已经清理，原始LARIAC6_Buildings_2020.gdb.zip校验无误并保留，字段文本也保留；可重新解包恢复。primary.sqlite缓存已无损Zstandard压缩、解压SHA核对，并有自动恢复入口。正式阶段01–05模型及原始数据未删除；第一次未验收的阶段05草稿只保留增量几何/原行/哈希和构建资料，不再保留其完整二进制，不宣称字节级可恢复。
