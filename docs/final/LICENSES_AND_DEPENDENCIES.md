# 许可、来源与准确依赖

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
