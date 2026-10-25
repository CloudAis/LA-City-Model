# 第四阶段来源与许可

逐文件来源登记：`data/processed/stage04/source_registry.json`。全部原始响应有`.receipt.json`和SHA256；实际请求/错误/缓存验证见`work/logs/stage04/requests.jsonl`。

| 数据 | 原始页面/下载入口 | 年代与精度 | 条件 |
|---|---|---|---|
| OSM California完整矢量PBF | https://download.geofabrik.de/north-america/us/california-latest.osm.pbf | 文件头数据库状态2026-10-20T20:23:47Z；采集日期/精度不统一且未知；SHA保留固定内容 | © OpenStreetMap contributors；Geofabrik摘录；ODbL1.0 |
| OSM版权 | https://www.openstreetmap.org/copyright | 实际保存页面，不等同几何采集日期 | 派生数据库公开分发遵守ODbL及署名；交通数据库与Census/DEM分开 |
| 市桥梁 | https://maps.lacity.org/lahub/rest/services/Street_Information/MapServer/0 | 1907条，采集/更新日期未知；Under_Clearance/Over_Clearance单位未核验，不采用 | 公开访问不等于无限再分发授权；外发前保留原机构条款 |
| LADOT信号 | https://maps.lacity.org/lahub/rest/services/LADOT/MapServer/30 | 5592条；采集年代、布置精度未知 | 仅作路口有信号设施的证据，杆件形状与位置仍近似 |
| Metro站点/线路 | https://maps.lacity.org/lahub/rest/services/Metro_Bus_and_Rail/MapServer/1 和 /2 | 107点/6线；条目未提供可靠数据年代，不能证明2026服务清单完整 | 保留为比较参考；OSM实际轨道/站台几何另存 |
| 标线规范 | https://dot.ca.gov/programs/safety-programs/camutcd | 实际取得2026版Part3A/3B PDF；规范年代不是现状道路年代 | Caltrans官方文件；仅作为样式/尺寸研究依据 |
| Census TIGER2025道路/设施 | 沿用阶段02登记 | 2025产品；市界法律参考2025-01-01；实际道路采集日期混合 | 美国联邦数据，按原登记注明来源，不冒充测绘精度 |
| USGS裸地高程 | 沿用阶段02/03登记 | DT原生1m，采集2023-01-08至2024-01-07；市域10m混合年代 | NAVD88米；未作未知垂直基准混合 |

Overpass两次 bounded 请求仍503；未取得的服务没有冒充下载成功。BBBike实际边界仅[-118.5,-118]×[33.7,34.2]，不足覆盖市域，未采用。
Geofabrik整包下载前实际HEAD核对1.33GB体积及磁盘预算；一次503后既定重试成功，响应长度与缓存SHA验证通过。
未批量下载OSM标准地图瓦片。没有调用付费API、照片服务或创建外部发布。

复现获取脚本：`scripts/stage04_acquire.py`（记录预算、缓存、SHA与短ID分页）；调查入口另见`stage04_research.py`、`stage04_investigate.py`。
历史PBF以SHA冻结。远端latest将来变化时，获取脚本明确失败并要求建立新来源版本，不用不同内容冒充同一时点。
