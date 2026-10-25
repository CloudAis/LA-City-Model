# Griffith Observatory

状态：**近似完成**。已建立具有专项几何特征的资产；不计为逐处核实的写实精修完成。

目标外观：post2006 expansion/restoration; three domes, upper terrace, publicly visible exterior only。

位置WGS84：[-118.30034801755656, 34.11825390271322]；局部原点city metres：[-4914.26716633628, 8848.86924627892, 346.2937234027568]。
朝向：从投影东逆时针-0.729471°；完整矩阵与真实来源平面见`data/processed/stage06/cards/griffith_observatory.json`。

来源平面：`osm:way:422130705`，面积2243.63m²；轴向包络{'x': 71.6211713319042, 'y': 53.53134798331943}。原始ID、编辑日期和分部保留在JSON。
高度定义：Official Observatory Fun Facts: main dome77ft, telescope domes55ft above front lawn; OSM35.9m not used; local front-lawn datum remains DEM-based estimate。地形单独采用NAVD88米制；未知OSM ele/县ELEV未混入。

主要材质：石材/玻璃/金属/涂装钢板/红瓦/铜等依参考分配；程序化微表面并非经采样的实物PBR材质。

## 已建立的识别特征

- central planetarium and two smaller telescope domes
- cream Art Deco wings and fluted entrance
- copper dome ribs/slit and upper terraces
- real Mount Hollywood slope and south retaining platform

## 资料覆盖与差异

2012北草坪正景、2015南坡斜景、2016望远镜穹顶、铜饰近景和2025平台局部；无完整屋顶航测。
官网77ft/55ft顶部高度和236ft/176ft外墙尺寸作为公布参考；球面曲率、雕刻、鼓座细节仍近似，地下扩建未建。

- exact dome rise and post2006 underground layout
- Art Deco sculptural panels
- site elevation text and source ele are not height control

环境：邻接建筑、路网、地形按同一真实地理变换提取；场地整平、入口台阶和平台属标记推断。未改变道路XY或地标相对距离。

## 资产和实际图像

- 可编辑：`assets/landmarks/stage06/griffith_observatory.blend`；内含near/mid/far独立命名集合、米制、参数/来源文本及少量可编辑修改器。
- 实时简化：`outputs/stage06/glb/griffith_observatory/near.glb`、`mid.glb`、`far.glb`。已实际重新导入；无自动距离切换。
- 图像：`work/previews/stage06/griffith_observatory/front.png`、`side.png`、`top.png`、`environment.png`。
- 环境工程：`scenes/stage06_context_griffith_observatory.blend`；430/650m半径的真实邻域提取，用于离线检查，非运行时流送。

| 版本 | 作者网格三角形 |
|---|---:|
|near|17088|
|mid|12096|
|far|956|

## 已核查网页与授权参考图

- https://griffithobservatory.org/about/；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- https://griffithobservatory.org/explore/exhibits/the-building/；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- https://griffithobservatory.lacity.gov/about/fun-facts/；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- [File:Griffith Observatory Telescope.jpg](https://commons.wikimedia.org/wiki/File:Griffith_Observatory_Telescope.jpg)；CC BY-SA 4.0；作者：Dancorona21；拍摄日期说明：Taken on 13 July 2016, 20:58:25。完整署名/许可URL在来源登记。
- [File:Griffith Observatory 2012 02.jpg](https://commons.wikimedia.org/wiki/File:Griffith_Observatory_2012_02.jpg)；CC BY-SA 4.0；作者：Photograph by  Mike Peel  ( www.mikepeel.net ).；拍摄日期说明：2012-07-21。完整署名/许可URL在来源登记。
- [File:Griffith Observatory, Los Angeles 2015-07-19.jpg](https://commons.wikimedia.org/wiki/File:Griffith_Observatory,_Los_Angeles_2015-07-19.jpg)；CC BY-SA 4.0；作者：Eric C Gardner；拍摄日期说明：2015-07-19 08:48:58。完整署名/许可URL在来源登记。
- [File:Detail of Griffith Observatory - Los Angeles, CA - USA (6914402087).jpg](https://commons.wikimedia.org/wiki/File:Detail_of_Griffith_Observatory_-_Los_Angeles,_CA_-_USA_(6914402087).jpg)；CC BY-SA 2.0；作者：Adam Jones  from Kelowna, BC, Canada；拍摄日期说明：2012-02-18 16:19。完整署名/许可URL在来源登记。
- [File:Los Angeles from Griffith Observatory 2025-03-18 pano 02.jpg](https://commons.wikimedia.org/wiki/File:Los_Angeles_from_Griffith_Observatory_2025-03-18_pano_02.jpg)；CC BY-SA 4.0；作者：Joe Mabel；拍摄日期说明：Taken on 18 March 2025。完整署名/许可URL在来源登记。

没有引入第三方三维模型。上述照片仅供有署名的内部研究与对比，不作为纹理。其他版权页面只缓存文字/HTML研究记录，未下载其远程照片。室内未建。
