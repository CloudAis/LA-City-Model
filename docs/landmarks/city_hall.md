# Los Angeles City Hall

状态：**近似完成**。已建立具有专项几何特征的资产；不计为逐处核实的写实精修完成。

目标外观：post2001 seismic restoration exterior; 1928 historic tower。

位置WGS84：[-118.24275656264929, 34.05368382246557]；局部原点city metres：[310.234598858869, 1622.6059215545126, 91.73436494699872]。
朝向：从投影东逆时针-38.555417°；完整矩阵与真实来源平面见`data/processed/stage06/cards/city_hall.json`。

来源平面：`osm:relation:6333145`，面积8746.12m²；轴向包络{'x': 79.91215656536568, 'y': 131.80190204593504}。原始ID、编辑日期和分部保留在JSON。
高度定义：secondary published454ft; OSM top part138.4m; primary heritage page confirms1928 three-tier form, not dimensional survey。地形单独采用NAVD88米制；未知OSM ele/县ELEV未混入。

主要材质：石材/玻璃/金属/涂装钢板/红瓦/铜等依参考分配；程序化微表面并非经采样的实物PBR材质。

## 已建立的识别特征

- source lower-building courtyards
- three-tier civic composition
- vertical window rhythm and setbacks
- pyramidal crown, observation colonnade and arched civic entry

## 资料覆盖与差异

2003/2017/2022正面/斜景、2025近景；OSM多层平面，缺完整实测背面及独立屋顶照片。
保留来源低层庭院与层次；门窗节奏、观察层柱列、金字塔顶为参数化近似，浮雕、铭文未复刻。

- historic sculpted reliefs/inscriptions
- precise crown profiles and recess dimensions
- courtyard service entrances

环境：邻接建筑、路网、地形按同一真实地理变换提取；场地整平、入口台阶和平台属标记推断。未改变道路XY或地标相对距离。

## 资产和实际图像

- 可编辑：`assets/landmarks/stage06/city_hall.blend`；内含near/mid/far独立命名集合、米制、参数/来源文本及少量可编辑修改器。
- 实时简化：`outputs/stage06/glb/city_hall/near.glb`、`mid.glb`、`far.glb`。已实际重新导入；无自动距离切换。
- 图像：`work/previews/stage06/city_hall/front.png`、`side.png`、`top.png`、`environment.png`。
- 环境工程：`scenes/stage06_context_city_hall.blend`；430/650m半径的真实邻域提取，用于离线检查，非运行时流送。

| 版本 | 作者网格三角形 |
|---|---:|
|near|129872|
|mid|11664|
|far|580|

## 已核查网页与授权参考图

- https://www.laconservancy.org/learn/historic-places/los-angeles-city-hall/；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- https://lacity.gov/government/history；HTTP/可用状态：unavailable。网页更新不等于建筑资料采集年。
- [File:Los Angeles City Hall, 2022.jpg](https://commons.wikimedia.org/wiki/File:Los_Angeles_City_Hall,_2022.jpg)；CC BY-SA 4.0；作者：Another Believer；拍摄日期说明：2022-09-08 17:18:25。完整署名/许可URL在来源登记。
- [File:Los Angeles City Hall dllu.jpg](https://commons.wikimedia.org/wiki/File:Los_Angeles_City_Hall_dllu.jpg)；CC BY-SA 4.0；作者：Daniel L. Lu (user:dllu)；拍摄日期说明：2017-05-27 19:48:06。完整署名/许可URL在来源登记。
- [File:Los Angeles City Hall (color) edit1.jpg](https://commons.wikimedia.org/wiki/File:Los_Angeles_City_Hall_(color)_edit1.jpg)；CC BY-SA 3.0；作者：Brion VIBBER；拍摄日期说明：8 August 2003 (according to   Exif   data)。完整署名/许可URL在来源登记。
- [File:Los Angeles City Hall up-close (April 2025).jpg](https://commons.wikimedia.org/wiki/File:Los_Angeles_City_Hall_up-close_(April_2025).jpg)；CC BY 4.0；作者：Busition；拍摄日期说明：2025-04-28 09:24:24。完整署名/许可URL在来源登记。
- [File:Los Angeles City Hall, Downtown Los Angeles, California 07.jpg](https://commons.wikimedia.org/wiki/File:Los_Angeles_City_Hall,_Downtown_Los_Angeles,_California_07.jpg)；CC BY-SA 4.0；作者：Levi Clancy；拍摄日期说明：2012-10-06 02:25:31。完整署名/许可URL在来源登记。

没有引入第三方三维模型。上述照片仅供有署名的内部研究与对比，不作为纹理。其他版权页面只缓存文字/HTML研究记录，未下载其远程照片。室内未建。
