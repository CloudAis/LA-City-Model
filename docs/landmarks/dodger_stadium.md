# Dodger Stadium

状态：**近似完成**。已建立具有专项几何特征的资产；不计为逐处核实的写实精修完成。

目标外观：post2020 center-field configuration, reference views2024 and older; 2025/26 clubhouse changes not fully verified。

位置WGS84：[-118.24014556574288, 34.073533522647466]；局部原点city metres：[577.9132238888093, 3820.793391733834, 153.03238902763113]。
朝向：从投影东逆时针-24.070433°；完整矩阵与真实来源平面见`data/processed/stage06/cards/dodger_stadium.json`。

来源平面：`osm:relation:7348164`，面积29316.86m²；轴向包络{'x': 254.12412798589887, 'y': 242.46919451654594}。原始ID、编辑日期和分部保留在JSON。
高度定义：grandstand heights inferred from aerial/field photos; OSM height2m is not stadium overall height。地形单独采用NAVD88米制；未知OSM ele/县ELEV未混入。

主要材质：石材/玻璃/金属/涂装钢板/红瓦/铜等依参考分配；程序化微表面并非经采样的实物PBR材质。

## 已建立的识别特征

- baseball diamond and northeast outfield opening
- horseshoe decks with differentiated seat colors
- pavilions, hexagonal scoreboards and canopy
- concourse piers, light towers and outer circulation

## 资料覆盖与差异

2024航拍、2007布局航拍、2015本垒看台场内照片；1962–1980历史照片不当作当前细节。
NNE外场开口、分层彩色看台、波形水平罩棚、六角计分牌和灯塔；座位/通道/结构数量与2025/26改造尚未逐处核实。

- seating aisles/row counts and exact structural spans
- 2025/26 renovation geometry not fully verified
- retaining bowl/field datum photo-estimated from ground

环境：邻接建筑、路网、地形按同一真实地理变换提取；场地整平、入口台阶和平台属标记推断。未改变道路XY或地标相对距离。

## 资产和实际图像

- 可编辑：`assets/landmarks/stage06/dodger_stadium.blend`；内含near/mid/far独立命名集合、米制、参数/来源文本及少量可编辑修改器。
- 实时简化：`outputs/stage06/glb/dodger_stadium/near.glb`、`mid.glb`、`far.glb`。已实际重新导入；无自动距离切换。
- 图像：`work/previews/stage06/dodger_stadium/front.png`、`side.png`、`top.png`、`environment.png`。
- 环境工程：`scenes/stage06_context_dodger_stadium.blend`；430/650m半径的真实邻域提取，用于离线检查，非运行时流送。

| 版本 | 作者网格三角形 |
|---|---:|
|near|40020|
|mid|10388|
|far|1324|

## 已核查网页与授权参考图

- https://www.mlb.com/dodgers/ballpark；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- https://www.mlb.com/dodgers/ballpark/information/guide；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- [File:Aerial view of Dodger Stadium, April 2024.JPG](https://commons.wikimedia.org/wiki/File:Aerial_view_of_Dodger_Stadium,_April_2024.JPG)；CC BY-SA 4.0；作者：Pi.1415926535；拍摄日期说明：Taken on 6 April 2024。完整署名/许可URL在来源登记。
- [File:Dodger Stadium from the Air.jpg](https://commons.wikimedia.org/wiki/File:Dodger_Stadium_from_the_Air.jpg)；CC BY 2.0；作者：User  kla4067  on  Flickr；拍摄日期说明：2007-06-27。完整署名/许可URL在来源登记。
- [File:Dodger Stadium field from upper deck 2015-10-04.jpg](https://commons.wikimedia.org/wiki/File:Dodger_Stadium_field_from_upper_deck_2015-10-04.jpg)；CC0；作者：Junkyardsparkle；拍摄日期说明：2015-10-04 12:57:59。完整署名/许可URL在来源登记。
- [File:Dodger Stadium-Downtown L.A.jpg](https://commons.wikimedia.org/wiki/File:Dodger_Stadium-Downtown_L.A.jpg)；CC BY 2.0；作者：User  kla4067  on  Flickr；拍摄日期说明：Commons upload by  UCinternational  ( talk ) 08:08, 21 July 2008 (UTC)。完整署名/许可URL在来源登记。
- [File:Dodger Stadium field from upper deck (crop).jpg](https://commons.wikimedia.org/wiki/File:Dodger_Stadium_field_from_upper_deck_(crop).jpg)；CC0；作者：Junkyardsparkle；拍摄日期说明：2015-10-04 12:57:59。完整署名/许可URL在来源登记。

没有引入第三方三维模型。上述照片仅供有署名的内部研究与对比，不作为纹理。其他版权页面只缓存文字/HTML研究记录，未下载其远程照片。室内未建。
