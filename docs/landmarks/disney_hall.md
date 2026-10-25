# Walt Disney Concert Hall

状态：**近似完成**。已建立具有专项几何特征的资产；不计为逐处核实的写实精修完成。

目标外观：completed2003 stainless-steel exterior, not historical mirror-polished portions。

位置WGS84：[-118.249949423293, 34.05539705097998]；局部原点city metres：[-351.33016779929756, 1820.6720640289566, 118.2449839817219]。
朝向：从投影东逆时针-38.801728°；完整矩阵与真实来源平面见`data/processed/stage06/cards/disney_hall.json`。

来源平面：`osm:relation:6333150`，面积11202.44m²；轴向包络{'x': 96.3778337257542, 'y': 142.19691241346402}。原始ID、编辑日期和分部保留在JSON。
高度定义：OSM reported36.7m, not verified dimensional survey; curved shell heights photo-estimated inside this envelope。地形单独采用NAVD88米制；未知OSM ele/县ELEV未混入。

主要材质：石材/玻璃/金属/涂装钢板/红瓦/铜等依参考分配；程序化微表面并非经采样的实物PBR材质。

## 已建立的识别特征

- multiple curved stainless-steel sails with distinct orientations
- main acoustic volume and lower glass foyer
- metal panel seam organization
- Grand Avenue entry stairs/terraces

## 资料覆盖与差异

2015金属曲面近景、两幅可复制航拍；可检查整体曲面组织，背后接缝/庭园局部仍不清楚。
11片可编辑采样曲面，不是原CATIA施工曲面；面板缝按近似分格生成，并未重建官方6000余片逐片形状。

- no original CATIA/NURBS construction surfaces
- individual6000+ panel layout and back-of-house junctions
- shells are sampled editable approximations; not fabrication geometry

环境：邻接建筑、路网、地形按同一真实地理变换提取；场地整平、入口台阶和平台属标记推断。未改变道路XY或地标相对距离。

## 资产和实际图像

- 可编辑：`assets/landmarks/stage06/disney_hall.blend`；内含near/mid/far独立命名集合、米制、参数/来源文本及少量可编辑修改器。
- 实时简化：`outputs/stage06/glb/disney_hall/near.glb`、`mid.glb`、`far.glb`。已实际重新导入；无自动距离切换。
- 图像：`work/previews/stage06/disney_hall/front.png`、`side.png`、`top.png`、`environment.png`。
- 环境工程：`scenes/stage06_context_disney_hall.blend`；430/650m半径的真实邻域提取，用于离线检查，非运行时流送。

| 版本 | 作者网格三角形 |
|---|---:|
|near|120100|
|mid|4804|
|far|1328|

## 已核查网页与授权参考图

- https://www.laphil.com/visit/walt-disney-concert-hall；HTTP/可用状态：unavailable。网页更新不等于建筑资料采集年。
- https://www.musiccenter.org/visit-explore/visit-explore/campus/walt-disney-concert-hall/；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- [File:Walt Disney Concert Hall exterior 03.jpg](https://commons.wikimedia.org/wiki/File:Walt_Disney_Concert_Hall_exterior_03.jpg)；CC0；作者：Leviclancy；拍摄日期说明：2015-11-12 11:00:57。完整署名/许可URL在来源登记。
- [File:Walt Disney Concert Hall exterior 04.jpg](https://commons.wikimedia.org/wiki/File:Walt_Disney_Concert_Hall_exterior_04.jpg)；CC0；作者：Leviclancy；拍摄日期说明：2015-11-12 11:01:47。完整署名/许可URL在来源登记。
- [File:Walt Disney Concert Hall exterior 01.jpg](https://commons.wikimedia.org/wiki/File:Walt_Disney_Concert_Hall_exterior_01.jpg)；CC0；作者：Leviclancy；拍摄日期说明：2015-11-12 10:57:54。完整署名/许可URL在来源登记。
- [File:Disneyext.jpg](https://commons.wikimedia.org/wiki/File:Disneyext.jpg)；Public domain；作者：Hurling7  ( talk )；拍摄日期说明：2007-03。完整署名/许可URL在来源登记。
- [File:Aerial view of Walt Disney Concert Hall in Los Angeles, California LCCN2013633216.tif](https://commons.wikimedia.org/wiki/File:Aerial_view_of_Walt_Disney_Concert_Hall_in_Los_Angeles,_California_LCCN2013633216.tif)；Public domain；作者：Carol M. Highsmith；拍摄日期说明：Taken on 29 June 2012, 16:40 (according to   Exif   data)。完整署名/许可URL在来源登记。
- [File:Aerial view of Walt Disney Concert Hall in Los Angeles, California LCCN2013633215.tif](https://commons.wikimedia.org/wiki/File:Aerial_view_of_Walt_Disney_Concert_Hall_in_Los_Angeles,_California_LCCN2013633215.tif)；Public domain；作者：Carol M. Highsmith；拍摄日期说明：Taken on 29 June 2012, 16:40 (according to   Exif   data)。完整署名/许可URL在来源登记。

没有引入第三方三维模型。上述照片仅供有署名的内部研究与对比，不作为纹理。其他版权页面只缓存文字/HTML研究记录，未下载其远程照片。室内未建。
