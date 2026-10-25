# 统一要素结构与存储

矢量交换遵循 GeoJSON RFC 7946，经度/纬度，EPSG:4326。几何操作和 tile_id 均用 EPSG:32611 米。
全市建筑以 gzip JSON Lines 逐条流式读取，避免一次加载百万条 Python 对象；见 scripts/stage02_dataset.py。
所有来源原始 ID、原字段及参数响应可回溯，未用顺序号伪装跨来源同一建筑。

| 属性 | 含义 |
|---|---|
| id / source_id / original_id | 来源命名空间稳定键和原生 ID；建筑同时保留 BLD_ID 与 GDB FID |
| data_vintage / acquisition_year / acquisition_date | 发布参考版与实际采集分开；未知为 null |
| geometry_source / height_source | 平面和高度的独立出处；含义未知照实记录 |
| data_class / evidence_class | raw_observed、processed_observed、inferred、artistic_synthetic 明确区分 |
| inferred_fields / confidence | 推断字段列表及依据，不用无校准的百分数冒充精度 |
| regions / tile_id / visual_level | 固定工作区、250 m 工作网格及计划内容等级；不是已完成精修 |
| height_m / roof_height_m / min_height_m / levels | 相对总高、屋顶高、底部高度、层数；无定义时未知 |
| height_candidate_m / source_HEIGHT / source_ELEV | 候选高度及原值；不覆盖核实字段，不当成地面海拔 |
| ground_elevation_m / ground_elevation_source | 单独 DEM 代表点地面正高；NAVD88 米，缺失保留 null |
| source_CODE / feature_type | 建筑、Courtyard、Free Standing Solar Structure 分别处理 |
| crosses_city_boundary | 全市界线相交建筑保留整栋轮廓并标记，不沿行政线切成假建筑 |

Census 道路保留 MTFCC、RTTYP 原分类和 FULLNAME；oneway / lanes / bridge / tunnel / level 未提供则 null。
平面线交叉不自动建立通行节点，DEM 地面高程也不等于高架桥面或隧道高程。
Census coastline 无原生唯一 ID，使用标准化原始几何 SHA-256 作显式派生 ID。

## 几何与去重

make_valid 修复只作用于 processed 副本；原始 byte 不变。保留 MultiPolygon 与内环。
Courtyard 作为洞减去，太阳能结构单列；3 个无法保留为面及4个庭院完全抵消对象隔离/排除，不偷偷填补。
3 对标准化几何完全重复记录由 model_selection.json 选择明确年代较新者，其余原始观测仍保留。
9 个新旧来源对应使用 OLD_BLD_ID，另测轮廓 IoU 与质心差；没有证据的对应不生成。
建筑分部没有独立语义来源，building_parts.geojson 的 availability 明确未取得，空集合不是“全市没有分部”。
道路裁切后665个仅点触/非线结果隔离，保留了所有有效线结果，详见 quarantine.json。

## 栅格

DEM float32、米、NAVD88，NoData=-9999；重投影 bilinear，不以0填洞。
NLCD uint8，nearest 分类重采样，0为NoData；类别编码保留，不能 bilinear 混出不存在类别。
树冠 uint8 {0,1}；0只是未选中/未分类，不保证不存在树木。不是树高或逐树清单。
101×101 Blender DEM 网格只作第二阶段数据检查减采样，不是第三阶段地形交付。
