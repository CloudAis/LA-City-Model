# The Broad

状态：**近似完成**。已建立具有专项几何特征的资产；不计为逐处核实的写实精修完成。

目标外观：2015 main museum; proposed/under-construction expansion not represented as completed。

位置WGS84：[-118.25059371491125, 34.05445775426338]；局部原点city metres：[-412.0690777259272, 1717.2412241461243, 116.92599781136084]。
朝向：从投影东逆时针-37.806729°；完整矩阵与真实来源平面见`data/processed/stage06/cards/the_broad.json`。

来源平面：`osm:way:427532197`，面积3466.15m²；轴向包络{'x': 60.219190699612184, 'y': 57.866801186813824}。原始ID、编辑日期和分部保留在JSON。
高度定义：OSM reported27.4m; veil cell dimensions and oculus photo estimates。地形单独采用NAVD88米制；未知OSM ele/县ELEV未混入。

主要材质：石材/玻璃/金属/涂装钢板/红瓦/铜等依参考分配；程序化微表面并非经采样的实物PBR材质。

## 已建立的识别特征

- porous diagonal veil surrounding dark vault
- central concave oculus
- lifted entrance corner and glass lobby
- roof daylight grid

## 资料覆盖与差异

2015格栅细节、两幅洛杉矶馆正/转角夜景；Michigan同名馆、运动/铁路误匹配均排除；背面和屋顶缺图。
连续斜向格栅、凹入眼窗、玻璃底层/入口角和采光格构已建；孔型、真实每块GFRC、屋面布局、扩建工地未完整复刻。

- exact2500-panel unique fabrication geometry
- roof layout partly inferred: no confirmed overhead photo
- expansion work/status and unseen back facade

环境：邻接建筑、路网、地形按同一真实地理变换提取；场地整平、入口台阶和平台属标记推断。未改变道路XY或地标相对距离。

## 资产和实际图像

- 可编辑：`assets/landmarks/stage06/the_broad.blend`；内含near/mid/far独立命名集合、米制、参数/来源文本及少量可编辑修改器。
- 实时简化：`outputs/stage06/glb/the_broad/near.glb`、`mid.glb`、`far.glb`。已实际重新导入；无自动距离切换。
- 图像：`work/previews/stage06/the_broad/front.png`、`side.png`、`top.png`、`environment.png`。
- 环境工程：`scenes/stage06_context_the_broad.blend`；430/650m半径的真实邻域提取，用于离线检查，非运行时流送。

| 版本 | 作者网格三角形 |
|---|---:|
|near|37714|
|mid|20930|
|far|324|

## 已核查网页与授权参考图

- https://www.thebroad.org/about；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- https://dsrny.com/project/the-broad；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- https://www.thebroad.org/about/future-expansion；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- [File:Close up - The Broad Museum - In Explore - Flickr - Joey Z1.jpg](https://commons.wikimedia.org/wiki/File:Close_up_-_The_Broad_Museum_-_In_Explore_-_Flickr_-_Joey_Z1.jpg)；CC BY 2.0；作者：joey  zanotti  from Rancho Palos Verdes, CA, USA；拍摄日期说明：Taken on 1 July 2017, 03:13。完整署名/许可URL在来源登记。
- [File:Nighttime view of the Broad in LA, corner dllu.jpg](https://commons.wikimedia.org/wiki/File:Nighttime_view_of_the_Broad_in_LA,_corner_dllu.jpg)；CC BY-SA 4.0；作者：Dllu；拍摄日期说明：2024-12-31 20:45:14。完整署名/许可URL在来源登记。
- [File:Nighttime view of the Broad in LA, front dllu.jpg](https://commons.wikimedia.org/wiki/File:Nighttime_view_of_the_Broad_in_LA,_front_dllu.jpg)；CC BY-SA 4.0；作者：Dllu；拍摄日期说明：2024-12-31 20:39:04。完整署名/许可URL在来源登记。

没有引入第三方三维模型。上述照片仅供有署名的内部研究与对比，不作为纹理。其他版权页面只缓存文字/HTML研究记录，未下载其远程照片。室内未建。
