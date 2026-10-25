# Los Angeles Memorial Coliseum

状态：**近似完成**。已建立具有专项几何特征的资产；不计为逐处核实的写实精修完成。

目标外观：post2019 Scholarship Club Tower; venue remains Los Angeles Memorial Coliseum; old aerials used for plan only。

位置WGS84：[-118.28793534097615, 34.014044437345014]；局部原点city metres：[-3914.993505772392, -2721.396699088065, 53.9011537613764]。
朝向：从投影东逆时针0.094786°；完整矩阵与真实来源平面见`data/processed/stage06/cards/memorial_coliseum.json`。

来源平面：`osm:relation:6100581`，面积47849.45m²；轴向包络{'x': 320.4783080227721, 'y': 232.63073915558476}。原始ID、编辑日期和分部保留在JSON。
高度定义：OSM bowl34.9m source report; club-tower envelope40m inferred, official seven stories not an exact height。地形单独采用NAVD88米制；未知OSM ele/县ELEV未混入。

主要材质：石材/玻璃/金属/涂装钢板/红瓦/铜等依参考分配；程序化微表面并非经采样的实物PBR材质。

## 已建立的识别特征

- real oval footprint and field void
- east peristyle arches and central Olympic cauldron
- post2019 south Scholarship Club Tower
- cardinal seating tiers, circulation openings and exterior colonnade

## 资料覆盖与差异

2025全景确认2019后俱乐部楼；2008/2017航拍只支持旧平面和周边关系；1987/更早历史图不代表当下。
东侧柱廊拱门、火炬、南侧七层俱乐部楼、椭圆看台/标准足球场；精确剖面、雕像和铭文、设施位置为近似或缺失。

- exact club facade dimensions/seat counts
- sculptures, inscriptions and sponsor graphics
- bowl/field ground offsets inferred; not structural survey

环境：邻接建筑、路网、地形按同一真实地理变换提取；场地整平、入口台阶和平台属标记推断。未改变道路XY或地标相对距离。

## 资产和实际图像

- 可编辑：`assets/landmarks/stage06/memorial_coliseum.blend`；内含near/mid/far独立命名集合、米制、参数/来源文本及少量可编辑修改器。
- 实时简化：`outputs/stage06/glb/memorial_coliseum/near.glb`、`mid.glb`、`far.glb`。已实际重新导入；无自动距离切换。
- 图像：`work/previews/stage06/memorial_coliseum/front.png`、`side.png`、`top.png`、`environment.png`。
- 环境工程：`scenes/stage06_context_memorial_coliseum.blend`；430/650m半径的真实邻域提取，用于离线检查，非运行时流送。

| 版本 | 作者网格三角形 |
|---|---:|
|near|50292|
|mid|18260|
|far|2752|

## 已核查网页与授权参考图

- https://www.lacoliseum.com/coliseum-history/；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- https://www.lacoliseum.com/venue-information/；HTTP/可用状态：unavailable。网页更新不等于建筑资料采集年。
- [File:Los Angeles Memorial Coliseum.png](https://commons.wikimedia.org/wiki/File:Los_Angeles_Memorial_Coliseum.png)；CC BY 4.0；作者：Quintin Soloviev；拍摄日期说明：2025-08-18。完整署名/许可URL在来源登记。
- [File:LA Memorial Coliseum aerial.jpg](https://commons.wikimedia.org/wiki/File:LA_Memorial_Coliseum_aerial.jpg)；Public domain；作者：NASA；拍摄日期说明：2008-11。完整署名/许可URL在来源登记。
- [File:LA Memorial Coliseum aerial view, August 2017.jpg](https://commons.wikimedia.org/wiki/File:LA_Memorial_Coliseum_aerial_view,_August_2017.jpg)；CC BY 2.0；作者：Ron Reiring；拍摄日期说明：2017-08-11 12:11:43。完整署名/许可URL在来源登记。

没有引入第三方三维模型。上述照片仅供有署名的内部研究与对比，不作为纹理。其他版权页面只缓存文字/HTML研究记录，未下载其远程照片。室内未建。
