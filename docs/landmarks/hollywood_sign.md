# Hollywood Sign

状态：**近似完成**。已建立具有专项几何特征的资产；不计为逐处核实的写实精修完成。

目标外观：nine-letter1978 replacement steel sign, current arrangement; not1923 HOLLYWOODLAND。

位置WGS84：[-118.32165468549334, 34.13406193322046]；局部原点city metres：[-6856.663840969456, 10627.067304505888, 483.638080808522]。
朝向：从投影东逆时针0.000000°；完整矩阵与真实来源平面见`data/processed/stage06/cards/hollywood_sign.json`。

来源平面：`osm:relation:1706337`，面积51.14m²；轴向包络{'x': 105.93592477368293, 'y': 14.05333757491826}。原始ID、编辑日期和分部保留在JSON。
高度定义：45 international feet nominal letters; OSM each13.7m; individual baseline elevations from actual ground with inferred anchor adjustment。地形单独采用NAVD88米制；未知OSM ele/县ELEV未混入。

主要材质：石材/玻璃/金属/涂装钢板/红瓦/铜等依参考分配；程序化微表面并非经采样的实物PBR材质。

## 已建立的识别特征

- nine actual letter line locations and directions
- custom editable block letter outlines with real holes
- rear steel posts and triangulated braces
- terrain-following separate letter baselines

## 资料覆盖与差异

2015/2021正面远景、2019背面钢架和可复制航拍；个别字母背侧与锚固不完整。
九条来源线分别定位，含O/D内洞、自制H/O/L/Y/W/D字形；钢架截面和锚固推断，基脚从10m裸地DEM估计，非原厂字体/施工图。

- steel member sections/anchor depths and precise corrugation
- letter outlines estimated from photos, not original shop drawings
- supports inferred except broad observed structure

环境：邻接建筑、路网、地形按同一真实地理变换提取；场地整平、入口台阶和平台属标记推断。未改变道路XY或地标相对距离。

## 资产和实际图像

- 可编辑：`assets/landmarks/stage06/hollywood_sign.blend`；内含near/mid/far独立命名集合、米制、参数/来源文本及少量可编辑修改器。
- 实时简化：`outputs/stage06/glb/hollywood_sign/near.glb`、`mid.glb`、`far.glb`。已实际重新导入；无自动距离切换。
- 图像：`work/previews/stage06/hollywood_sign/front.png`、`side.png`、`top.png`、`environment.png`。
- 环境工程：`scenes/stage06_context_hollywood_sign.blend`；430/650m半径的真实邻域提取，用于离线检查，非运行时流送。

| 版本 | 作者网格三角形 |
|---|---:|
|near|1348|
|mid|916|
|far|376|

## 已核查网页与授权参考图

- https://www.hollywoodsign.org/history；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- https://www.hollywoodsign.org/the-sign-at-a-glance；HTTP/可用状态：unavailable。网页更新不等于建筑资料采集年。
- https://www.hollywoodsign.org/history-timeline；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- [File:Hollywood Sign.jpg](https://commons.wikimedia.org/wiki/File:Hollywood_Sign.jpg)；CC BY-SA 3.0；作者：Thomas Wolf  ,   www.foto-tw.de；拍摄日期说明：2015-09-11。完整署名/许可URL在来源登记。
- [File:Hollywood Sign (Zuschnitt).jpg](https://commons.wikimedia.org/wiki/File:Hollywood_Sign_(Zuschnitt).jpg)；CC BY-SA 3.0；作者：Thomas Wolf  ,   www.foto-tw.de；拍摄日期说明：2015-09-11。完整署名/许可URL在来源登记。
- [File:View from behind Hollywood Sign overlooking LA.jpg](https://commons.wikimedia.org/wiki/File:View_from_behind_Hollywood_Sign_overlooking_LA.jpg)；CC BY-SA 4.0；作者：Michael E. Arth；拍摄日期说明：2019-01-06 16:29:09。完整署名/许可URL在来源登记。
- [File:Hollywood Sign close up.jpg](https://commons.wikimedia.org/wiki/File:Hollywood_Sign_close_up.jpg)；CC BY-SA 4.0；作者：Wiki person that edits；拍摄日期说明：2021-08-29 19:02:47。完整署名/许可URL在来源登记。
- [File:Aerial Hollywood Sign.jpg](https://commons.wikimedia.org/wiki/File:Aerial_Hollywood_Sign.jpg)；Public domain；作者：Jelson25；拍摄日期说明：2009-07-25。完整署名/许可URL在来源登记。

没有引入第三方三维模型。上述照片仅供有署名的内部研究与对比，不作为纹理。其他版权页面只缓存文字/HTML研究记录，未下载其远程照片。室内未建。
