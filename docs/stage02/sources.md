# 第二阶段来源与精度登记

完整逐字段登记见 data/processed/stage02/source_registry.json / .csv。null 表示未知，不能据名称、坐标小数位或网页日期补写。

| 数据集 | 状态 | 采集/参考年代 | 条目更新 | 本地数据文件数 |
|---|---|---|---|---|
| ca places 2025 | downloaded_verified | acquisition=None; reference=2025 | None | 1 |
| la roads 2025 | downloaded_verified | acquisition=None; reference=2025 | None | 1 |
| la area water 2025 | downloaded_verified | acquisition=None; reference=2025 | None | 1 |
| la linear water 2025 | downloaded_verified | acquisition=None; reference=2025 | None | 1 |
| ca area landmarks 2025 | downloaded_verified | acquisition=None; reference=2025 | None | 1 |
| ca point landmarks 2025 | downloaded_verified | acquisition=None; reference=2025 | None | 1 |
| us rails 2025 | downloaded_verified | acquisition=None; reference=2025 | None | 1 |
| us coastline 2025 | downloaded_verified | acquisition=None; reference=2025 | None | 1 |
| Countywide Building Outlines (2020) | downloaded_full_county_standardized_city | acquisition=[1992, 2003, 2008, 2014, 2017, 2020]; reference=2020 | 2026-01-16T21:50:39+00:00 | 1 |
| LA County Elevation | rejected_for_downtown_extent | acquisition=None; reference=None | 2016-02-02T19:58:07+00:00 | 0 |
| Los Angeles County Land Cover | metadata_only_not_selected | acquisition=None; reference=None | 2024-03-26T20:59:28+00:00 | 0 |
| County maintained road trees | metadata_only_not_selected | acquisition=None; reference=None | 2026-08-05T22:27:34+00:00 | 0 |
| Historic Cultural Monuments | downloaded_complete_service_id_set | acquisition=None; reference=None | 2026-10-15T09:07:31+00:00 | 6 |
| Airports | metadata_only_not_selected | acquisition=None; reference=None | 2026-08-25T21:44:30+00:00 | 0 |
| Metro Stations | metadata_only_not_selected | acquisition=None; reference=None | 2026-07-06T21:12:12+00:00 | 0 |
| LA official building footprints | sample_acquired_older_source_not_primary | acquisition=None; reference=None | None | 1 |
| USGS 3DEP 1m bare-earth DEM / CA_LosAngeles_B23 | downloaded_verified | acquisition=[2023, 2024]; reference=None | 2025-08-12 | 1 |
| OpenStreetMap vectors | investigated_unavailable_not_adopted | acquisition=None; reference=None | None | 0 |
| USGS 3DEP 1/3 arc-second city overview DEM | downloaded_verified | acquisition=None; reference=selected publication versions 2025; acquisition mixed/unknown | None | 2 |
| NLCD 2021 land cover / MRLC WCS | downloaded_verified_categorical_values | acquisition=None; reference=2021 | None | 1 |
| LARIAC7 2023 canopy presence mask | downloaded_downtown_quality_limitations | acquisition=2023; reference=None | None | 1 |
| LA Recreation and Parks tree inventory / Downtown envelope | downloaded_sample_complete_not_all_city_trees | acquisition=['2004']; reference=None | None | 1 |
| LA City GIS published administrative boundary | downloaded_verified_reference_date_unknown | acquisition=None; reference=None | None | 1 |

Census 技术文档实际已读取：边界法律参考日 2025-01-01，但不是地籍法律描述；坐标精度因原始资料而异。
派生产品使用 U.S. Census Bureau, 2025 TIGER/Line® Shapefiles。TIGER/Line 是 Census Bureau 注册商标，本项目不是其官方产品，也不获其背书。
Census 设施/公园分类仅支持概略功能范围，不替代完整土地覆盖、当前运营交通网或法定文保名单。
县建筑资料是 2020 参考版，条目 2026 更新不改变采集年份。产品指南为美国测量英尺；HEIGHT/ELEV 字段含义仍缺字典确认，候选高度单列为 inferred，已核实 height_m 保持 null。
OSM 标准瓦片政策原文已读取，明确禁止批量抓取与离线预取；本工程未请求任何标准地图瓦片。
