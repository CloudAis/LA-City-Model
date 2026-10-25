# Los Angeles Union Station

状态：**近似完成**。已建立具有专项几何特征的资产；不计为逐处核实的写实精修完成。

目标外观：1939 Mission Moderne main station exterior; current train platforms inherited from stage04。

位置WGS84：[-118.23579925796983, 34.05607428062992]；局部原点city metres：[955.5807524968895, 1879.9019551593876, 89.0153559504226]。
朝向：从投影东逆时针-10.512350°；完整矩阵与真实来源平面见`data/processed/stage06/cards/union_station.json`。

来源平面：`osm:relation:1483140`，面积16245.35m²；轴向包络{'x': 154.12254126621764, 'y': 186.84848980498862}。原始ID、编辑日期和分部保留在JSON。
高度定义：OSM reported39.1m interpreted only as clock-tower envelope; hall roof heights photo-estimated。地形单独采用NAVD88米制；未知OSM ele/县ELEV未混入。

主要材质：石材/玻璃/金属/涂装钢板/红瓦/铜等依参考分配；程序化微表面并非经采样的实物PBR材质。

## 已建立的识别特征

- Mission Moderne long west facade with arched glazing
- clock tower/belfry and red tile roof
- waiting-hall/ticket-hall differentiated roof volumes
- court/patio connections

## 资料覆盖与差异

2013/2022西立面及钟塔多个角度；并非六个独立完整方位，东侧/后方/屋顶覆盖不足。
钟塔、拱窗、差异化红瓦大厅、推断庭院与原交通层关联；屋顶分区、钟面、庭院界线及东后立面均有推断。

- east/rear roofs and exact patio boundaries
- clock face design, inscriptions and reliefs
- no interior or full platform rebuild

环境：邻接建筑、路网、地形按同一真实地理变换提取；场地整平、入口台阶和平台属标记推断。未改变道路XY或地标相对距离。

## 资产和实际图像

- 可编辑：`assets/landmarks/stage06/union_station.blend`；内含near/mid/far独立命名集合、米制、参数/来源文本及少量可编辑修改器。
- 实时简化：`outputs/stage06/glb/union_station/near.glb`、`mid.glb`、`far.glb`。已实际重新导入；无自动距离切换。
- 图像：`work/previews/stage06/union_station/front.png`、`side.png`、`top.png`、`environment.png`。
- 环境工程：`scenes/stage06_context_union_station.blend`；430/650m半径的真实邻域提取，用于离线检查，非运行时流送。

| 版本 | 作者网格三角形 |
|---|---:|
|near|22053|
|mid|2629|
|far|404|

## 已核查网页与授权参考图

- https://www.unionstationla.com/history/；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- [File:Exterior of Los Angeles Union Station.JPG](https://commons.wikimedia.org/wiki/File:Exterior_of_Los_Angeles_Union_Station.JPG)；CC BY-SA 3.0；作者：ZhengZhou；拍摄日期说明：2013-12-16。完整署名/许可URL在来源登记。
- [File:Los Angeles. Union Station. Exterior. 2022-03-02 15-40-37.jpg](https://commons.wikimedia.org/wiki/File:Los_Angeles._Union_Station._Exterior._2022-03-02_15-40-37.jpg)；CC BY-SA 4.0；作者：Shesmax；拍摄日期说明：2022-03-02 15:40:37。完整署名/许可URL在来源登记。
- [File:Los Angeles. Union Station. Exterior. 2022-03-02 15-48-48.jpg](https://commons.wikimedia.org/wiki/File:Los_Angeles._Union_Station._Exterior._2022-03-02_15-48-48.jpg)；CC BY-SA 4.0；作者：Shesmax；拍摄日期说明：2022-03-02 15:48:48。完整署名/许可URL在来源登记。
- [File:Los Angeles. Union Station. Exterior. 2022-03-02 15-45-52.jpg](https://commons.wikimedia.org/wiki/File:Los_Angeles._Union_Station._Exterior._2022-03-02_15-45-52.jpg)；CC BY-SA 4.0；作者：Shesmax；拍摄日期说明：2022-03-02 15:45:52。完整署名/许可URL在来源登记。
- [File:Los Angeles. Union Station. Exterior. 2022-03-02 15-49-13.jpg](https://commons.wikimedia.org/wiki/File:Los_Angeles._Union_Station._Exterior._2022-03-02_15-49-13.jpg)；CC BY-SA 4.0；作者：Shesmax；拍摄日期说明：2022-03-02 15:49:13。完整署名/许可URL在来源登记。
- [File:Los Angeles. Union Station. Exterior. 2022-03-02 15-40-20.jpg](https://commons.wikimedia.org/wiki/File:Los_Angeles._Union_Station._Exterior._2022-03-02_15-40-20.jpg)；CC BY-SA 4.0；作者：Shesmax；拍摄日期说明：2022-03-02 15:40:20。完整署名/许可URL在来源登记。

没有引入第三方三维模型。上述照片仅供有署名的内部研究与对比，不作为纹理。其他版权页面只缓存文字/HTML研究记录，未下载其远程照片。室内未建。
