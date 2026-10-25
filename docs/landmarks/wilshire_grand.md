# Wilshire Grand Center

状态：**近似完成**。已建立具有专项几何特征的资产；不计为逐处核实的写实精修完成。

目标外观：completed2017, operating hotel/office exterior; construction photos excluded as current reference。

位置WGS84：[-118.26042468854307, 34.05015813057608]；局部原点city metres：[-1325.3143025731413, 1251.5959399045846, 94.06128033523949]。
朝向：从投影东逆时针-37.727577°；完整矩阵与真实来源平面见`data/processed/stage06/cards/wilshire_grand.json`。

来源平面：`osm:way:496246723`，面积8196.85m²；轴向包络{'x': 116.22987922405395, 'y': 97.08965684385801}。原始ID、编辑日期和分部保留在JSON。
高度定义：engineer overall 1100 international feet incl spire; secondary roof928ft conflicts with OSM245/255.5 part heights; crown interpolation inferred。地形单独采用NAVD88米制；未知OSM ele/县ELEV未混入。

主要材质：石材/玻璃/金属/涂装钢板/红瓦/铜等依参考分配；程序化微表面并非经采样的实物PBR材质。

## 已建立的识别特征

- curved glass shaft distinct from large low podium
- asymmetric sail crown and needle
- floor bands and vertical mullions
- curved entry atrium/plaza

## 资料覆盖与差异

2022远景、2025地面斜景、2024入口夜景；施工照片不用于当前外观；屋顶/背面有盲区。
三个73层来源分部合并为完整塔身；245m带标签分部不能单独代表全塔平面。源屋顶/针塔高度定义冲突保留，冠顶按次级928ft参考插值；针塔总高使用工程师1100ft。

- crown control points and exact roof/antenna height definitions
- unseen rear podium equipment
- glass coating and lighting states

环境：邻接建筑、路网、地形按同一真实地理变换提取；场地整平、入口台阶和平台属标记推断。未改变道路XY或地标相对距离。

## 资产和实际图像

- 可编辑：`assets/landmarks/stage06/wilshire_grand.blend`；内含near/mid/far独立命名集合、米制、参数/来源文本及少量可编辑修改器。
- 实时简化：`outputs/stage06/glb/wilshire_grand/near.glb`、`mid.glb`、`far.glb`。已实际重新导入；无自动距离切换。
- 图像：`work/previews/stage06/wilshire_grand/front.png`、`side.png`、`top.png`、`environment.png`。
- 环境工程：`scenes/stage06_context_wilshire_grand.blend`；430/650m半径的真实邻域提取，用于离线检查，非运行时流送。

| 版本 | 作者网格三角形 |
|---|---:|
|near|316662|
|mid|15062|
|far|214|

## 已核查网页与授权参考图

- https://www.acmartin.com/portfolio/wilshire-grand-center；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- https://www.thorntontomasetti.com/project/wilshire-grand-center；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- [File:Wilshire Grand Center, Los Angeles (July 2022) from Aven.jpg](https://commons.wikimedia.org/wiki/File:Wilshire_Grand_Center,_Los_Angeles_(July_2022)_from_Aven.jpg)；CC BY-SA 4.0；作者：Benoît Prieur；拍摄日期说明：2022-07-25 17:49:40。完整署名/许可URL在来源登记。
- [File:Wilshire Grand - February 2024 - Sarah Stierch.jpg](https://commons.wikimedia.org/wiki/File:Wilshire_Grand_-_February_2024_-_Sarah_Stierch.jpg)；CC BY 4.0；作者：Missvain；拍摄日期说明：Taken on 5 February 2024。完整署名/许可URL在来源登记。
- [File:Wilshire Grand Center.jpg](https://commons.wikimedia.org/wiki/File:Wilshire_Grand_Center.jpg)；CC0；作者：AmeteurAngeleno；拍摄日期说明：May 18, 2025。完整署名/许可URL在来源登记。
- [File:Tree at Wilshire Grand Center - February 2024 - Sarah Stierch.jpg](https://commons.wikimedia.org/wiki/File:Tree_at_Wilshire_Grand_Center_-_February_2024_-_Sarah_Stierch.jpg)；CC BY 4.0；作者：Missvain；拍摄日期说明：Taken on 5 February 2024。完整署名/许可URL在来源登记。

没有引入第三方三维模型。上述照片仅供有署名的内部研究与对比，不作为纹理。其他版权页面只缓存文字/HTML研究记录，未下载其远程照片。室内未建。
