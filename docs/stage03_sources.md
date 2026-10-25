# 第三阶段补充来源登记

阶段二原始DEM、水文、Census分类、NLCD等完整登记保持在 `data/processed/stage02/source_registry.json`。本阶段不改原始数据；本表补充City规划资料。

| 字段 | 记录 |
|---|---|
| 发布机构 | City of Los Angeles Department of City Planning |
| General Plan Land Use原页面 | https://maps.lacity.org/lahub/rest/services/City_Planning_Department/MapServer/7 |
| 港区规划原页面 | https://services5.arcgis.com/7nsPwEMP38bSkCjy/arcgis/rest/services/Community_Plan_Areas/FeatureServer/0 |
| 源水平坐标声明 | {'wkid': 102100, 'latestWkid': 3857, 'xyTolerance': 0.001, 'zTolerance': 0.001, 'mTolerance': 0.001, 'falseX': -20037700, 'falseY': -30241100, 'xyUnits': 148923141.92838538, 'falseZ': -100000, 'zUnits': 10000, 'falseM': -100000, 'mUnits': 10000}；实际查询outSR4326，后转EPSG32611米 |
| 垂直基准/高度单位 | 二维规划面不适用；未提供地面高度 |
| 实际采集年份 | 未知；ADOPTDATE/UPDATE_是规划采纳/修订时间，不是影像采集或当前用途调查 |
| 取得与计数 | GeneralPlan1005条全ID/计数核对；工业963、机场42；港区查询返回3条，仅精确NAME_ALF=Port of LosAngeles采用1条 |
| 空间覆盖 | LA市内选定工业/机场规划面和港区规划域，不是全市土地用途全分类 |
| 精度 | 数字水平精度未知；原始CRS、范围及返回字段保留于元数据 |
| 使用条件 | City GIS公开服务原条款/免责声明适用；未确认无限制公开再分发授权，不作当前地块用途证明 |
| 标准路径 | data/processed/stage03/selected_plan_landuse.geojson |
| 原始路径 | data/raw/stage03/landuse_selected；port_plan_verified |
| 请求、日期和SHA256 | data/processed/stage03/source_requests.json（完整URL、参数、下载日期、字节数与文件哈希）；原文件旁receipt |

## 调查与未采用项

USACE页面403、River Master Plan验证码页、无效CityPlanning服务名和猜测的FAQ404均保留请求日志，不声称取得正文工程资料。ArcGIS搜索结果中的第三方港口项目未作为正式边界输入。

河段材料和桥面资料未知；面水文填补了线水文省略的Downtown附近河段。7个原始1米DEM断面是地形调查，不是工程设计断面或当前流宽。

海面使用项目0米显示参考；湖泊平面来自DEM估计；其余水文掩膜贴合地面。未作潮位基准转换、未混合不明高度、未声称测得真实水位。
