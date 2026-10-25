# 坐标与单位

阶段03已锁定并实际验证：完整参数/PROJ管线与矩阵见 `data/processed/stage03/coordinate_system.json`，每块转换见 `medium/tile_index.json`；详细记录见 [第三阶段说明](stage03.md)。
地形分块采用1000米；下文250米为未来GLB资产分块约定，两者分别记录，不混用。

所有空间建模尺寸为米，Blender 1 BU = 1 m；Z 向上。尺度校验以实际世界包围盒为准，而不只看 UI 单位。

## 水平坐标

- 交换：GeoJSON RFC 7946，EPSG:4326，经度在前、纬度在后，角度单位为度。
- 工作：EPSG:32611 / WGS 84 UTM zone 11N，easting、northing，单位米。
- 原始数据保持原字节；这些来源 GeoJSON 按经纬度解析，不声称其地理精度优于原始概化和基准转换精度。
- 从 LA Times Downtown 多边形转换 UTM 后取面积质心。原始街区边界有微小自交，用 GEOS make_valid 修复，
  原始文件不变，修复方法与面积差记在 work/reports/scopes.json。
- 固定工程原点、经纬度和 UTM 数值见 data/processed/origin.json；所有城市分块共用该原点。
- Blender：X = UTM easting − origin_easting；Y = UTM northing − origin_northing。
  X/Y 是投影网格东/北，和当地真东/真北有子午线收敛差；UTM 有尺度因子，4 km 指投影工作距离。
- data/processed/scopes.geojson 为真实经纬度多边形；scopes.local-meters.json 为明确注明的本地米制数据，
  不能作为 RFC7946 GeoJSON 发布或交给自动假设 WGS84 的客户端。

## 高程

阶段 01 地面 Z=0 为合成校准平面，**不是海平面，也不是 Downtown 实测海拔**。
阶段 02 已引入 USGS 3DEP bare-earth DEM：Downtown 1 m、全市约 10 m，均为 NAVD88 正高、单位米。
Blender 阶段 02 检查点的地面 Z 直接使用 NAVD88 米制正高，不减去合成 z=0，不作垂直夸张。
建筑轮廓线/道路线各有明确 0.7/0.4 m 显示偏移，不是屋顶海拔或桥面实测高程。
LARIAC HEIGHT/ELEV 的官方字段定义与垂直基准尚未确认，ELEV 不作为地面高程。
height_candidate_m 只是 raw HEIGHT ×(1200/3937) 的明确推断；height_m、roof_height_m、min_height_m 保持未知。
不得将 NAVD88 正高当成 WGS84 椭球高；当前未做大地水准面模型转换。

## 阶段 02 来源坐标

Census 原始 EPSG:4269 / NAD83；LARIAC6 原始 EPSG:6424 / NAD83(2011) CA zone 5、美国测量英尺。
USGS 1 m 原始 EPSG:26911、全市 DEM 原始 EPSG:4269；NLCD 服务返回 EPSG:5070。
标准矢量交换为 EPSG:4326；栅格及几何计算统一 EPSG:32611 米。原始与目标 CRS 均在来源登记保留。
PROJ 默认可用坐标操作用于城市可视化，未进行测量控制点或厘米级基准转换验证；数值往返精度不是测绘精度。
全市活动边界是 stage02/city_boundary_2025.geojson；历史 scopes.geojson 的城市边界保留为 v1，Downtown 原点及工作窗冻结。

## 单位与导出约定

国际英尺 ×0.3048 = 米；美国测量英尺 ×(1200/3937) = 米。来源必须标明是哪一种英尺。
英寸 ×0.0254 = 米。角度不可按固定“每度多少米”生成工作窗，必须使用投影转换。
阶段 09 GLB 使用米和 glTF 的 Y-up：Blender (x,y,z) → glTF (x,z,−y)，标准 Blender 导出器完成轴变换。
每个分块登记 grid_id、UTM 原点偏移、局部包围盒、水平/垂直基准、数据来源与 LOD。
分块采用 tile_size_m=250；区域不为构图而平移。此导出约定当前仅为规范，尚未实施 GLB 导出。

## 验证

入口进行范围有效性、焦点与近景包含关系、4 km 面积、近景总面积、来源哈希、投影往返 <1 mm 的数值检查。
<1 mm 只代表浮点转换往返误差，不代表地理数据达到毫米精度。
测试建筑主体 12×18×24 m；外置窗框、屋顶测试设施为独立对象，不包含在主体包围盒尺寸内。
地面 60×50×0.2 m；20 m 标尺共 21 个标记，间隔 1 m；三轴线段各 14 m，箭头单独建模。

阶段04继续使用同一EPSG32611工作原点及米制、Z向上。道路/桥隧高程为NAVD88地面坐标轴上的推断值，不是新垂直基准；没有引入未核实的OSM ele或City净空字段。
道路局部切口/桥下地形为独立派生变体，原始DEM、阶段三网格及其高程均保留。实例新增旋转Y表示按估算端点高程调整护栏倾角，不改变全局轴向。

阶段05继续沿用同一工作原点、单位、轴和NAVD88地面，不改原始origin.json。上文“height_m保持未知”描述阶段02冻结库；阶段05在独立buildings.sqlite中建立报告值/推断值，并保留证据分类，原库不填改。高度是相对建筑基准面的尺寸，不是绝对屋顶海拔；仅在明确的NAVD88地面/推断楼面上相加形成模型Z。县ELEV和OSM ele仍未混用。
建筑质心归属块分别为1000/250/125m，完整建筑不沿块裁切。mesh_index.json中origin_m为该块相对城市原点的平移；局部顶点加origin_m恢复Blender城市坐标，再加原点UTM恢复EPSG32611。GN模块的位置同样先减所属块原点。建筑与地形可使用不同块尺寸，均记录真实全局位置，不改变相互距离。

## 阶段06地标局部坐标

每个地标原点为来源平面质心、米制UTM11局部方向，asset_to_city_matrix在各资料卡中。GLB采用glTF Y-up，实际重新导入恢复Blender Z-up并核对包络。城市原点、NAVD88地面和Z偏移不变；来源ele/ELEV未知，不混用。45组地标间距离及十点正反变换见work/reports/stage06/geographic_validation.json；数值误差不能解释为测绘精度。
# 阶段07坐标与视觉修整补充

继续EPSG32611米制工作坐标、既定城市原点和NAVD88地形Z。两个近景模块集合的平移原点分别约(-432.3949595,857.11258,0)、(215.43239,1747.54794,0)，只是可编辑对象局部坐标，原城市位置不变。原始WGS84 OSM XML保留；转换记录和实际相机位置在config/stage07_views.json。
11栋入口接口仅对Z作明确的视觉修整，建筑源XY和相对高度保留。5块地形变体保留原XY、面索引、道路切孔和边界Z。最大约13.307m的局部地形显示变化是推断整平，不是实际土方或更高精度DEM。未知ELEV/ele不混入NAVD88；stage07地形边界相对前一阶段0差只是计算一致性。
OSM设施点XY不移动。新增外观/朝向和树木多数尺寸为推断，入口源点投到已有轮廓的最大变化约0.00358m，属计算投影差异，不是测绘精度。单元构件/门窗旋转采用网格X轴参考；没有把模板旋转当成实测立面朝向。

