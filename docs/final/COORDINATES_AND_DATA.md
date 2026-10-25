# 坐标、范围与来源口径

全局交换坐标WGS84/EPSG:4326；米制工作坐标WGS84/UTM11N/EPSG:32611。Blender/项目X为网格东、Y为网格北、Z为上，1BU=1m；UTM原点(384992.75594820484,3767182.3649733574)。glTF仅转换一次(x,y,z)→(x,z,-y)。每块的origin_city_m为外部地理位置，几何为局部米坐标；查看器按1000m格网重置渲染原点。

Downtown参考UTM网格收敛角约−0.697480°；参考真北的网格方位约+0.69749°。指南针是该参考换算，坐标小数位和正反算误差不表示原数据精度。

USGS裸地地面为NAVD88米；未知建筑ELEV不当绝对高程。源英尺先按各条目定义转换，美国测量英尺为1200/3937m，国际英尺为0.3048m。水位0或其他显示估计不作为已核基准转换。视觉整平、基础和台阶为有记录推断，不改写原始DEM。

metadata/coordinate_system.json保存完整投影、原点、轴向和矩阵；metadata/terrain_tile_index.json保存分块地理范围、原点、邻接和数据覆盖；tiles/manifest.json为实际实时资源清单。landmarks独立GLB已经烘焙到城市网格朝向，定位时只加origin_city_m，不能再次套源资料卡yaw。

原始资料、处理数据、推断和艺术补充不能合成一个“真实性百分比”。以下仅为全部活动来源建筑高度字段的证据分布，分母1096502；地标补充公布尺寸另见资料卡，不混入此分母。

|高度证据|数量|占来源建筑分母|
|---|---:|---:|
|source_reported_county_import_unverified|945,437|86.223007%|
|inferred_official_field_interpretation|136,853|12.480871%|
|inferred_type|13,035|1.188780%|
|inferred_levels|968|0.088281%|
|source_reported_unverified|141|0.012859%|
|inferred_part_levels|40|0.003648%|
|source_reported_part_height_unverified|27|0.002462%|
|verified_published_reference|1|0.000091%|

“source_reported_county_import_unverified”不能当独立实测；OSM部分县编号/高度共享县来源血统。县屋顶线作为足迹代理，水平位置也不能当外墙测绘。立面、类型默认、屋顶设备、材质和窗灯绝大多数为来源引导推断或原创视觉模块；不把HEIGHT数值非空当作已核高度完整率。
