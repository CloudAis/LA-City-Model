# U.S. Bank Tower

状态：**近似完成**。已建立具有专项几何特征的资产；不计为逐处核实的写实精修完成。

目标外观：1989 tower, renovated operating exterior; no former Skyslide。

位置WGS84：[-118.25442201554075, 34.051065542859995]；局部原点city metres：[-770.0226012841333, 1345.4085060389448, 101.16952358443982]。
朝向：从投影东逆时针-28.570304°；完整矩阵与真实来源平面见`data/processed/stage06/cards/us_bank_tower.json`。

来源平面：`osm:way:23973401`，面积2305.71m²；轴向包络{'x': 48.12149344092171, 'y': 58.5177102008851}。原始ID、编辑日期和分部保留在JSON。
高度定义：owner 1018 international feet; rounded published overall top reference。地形单独采用NAVD88米制；未知OSM ele/县ELEV未混入。

主要材质：石材/玻璃/金属/涂装钢板/红瓦/铜等依参考分配；程序化微表面并非经采样的实物PBR材质。

## 已建立的识别特征

- stepped cruciform/cylindrical shaft
- pale stone piers and dark recessed glazing
- circular tiered lantern/crown
- Fifth Street podium/entry

## 资料覆盖与差异

2008/2014/2022地面正/斜侧景；未取得独立屋顶俯视，背面与裙房服务立面不完整。
圆冠/灯笼层、石材竖梃和分段窗格为照片指导近似；未复制商标、过时Skyslide、隐蔽设备。

- exact stone coursing and service facade
- current lobby and roof equipment
- commercial marks omitted; no obsolete Skyslide

环境：邻接建筑、路网、地形按同一真实地理变换提取；场地整平、入口台阶和平台属标记推断。未改变道路XY或地标相对距离。

## 资产和实际图像

- 可编辑：`assets/landmarks/stage06/us_bank_tower.blend`；内含near/mid/far独立命名集合、米制、参数/来源文本及少量可编辑修改器。
- 实时简化：`outputs/stage06/glb/us_bank_tower/near.glb`、`mid.glb`、`far.glb`。已实际重新导入；无自动距离切换。
- 图像：`work/previews/stage06/us_bank_tower/front.png`、`side.png`、`top.png`、`environment.png`。
- 环境工程：`scenes/stage06_context_us_bank_tower.blend`；430/650m半径的真实邻域提取，用于离线检查，非运行时流送。

| 版本 | 作者网格三角形 |
|---|---:|
|near|234772|
|mid|13812|
|far|732|

## 已核查网页与授权参考图

- https://www.usbanktower.com/；HTTP/可用状态：200。网页更新不等于建筑资料采集年。
- [File:Los Angeles Library Tower (small) crop.jpg](https://commons.wikimedia.org/wiki/File:Los_Angeles_Library_Tower_(small)_crop.jpg)；CC BY-SA 3.0；作者：；拍摄日期说明：未知。完整署名/许可URL在来源登记。
- [File:U.S. Bank Tower (Los Angeles) July 2022.JPG](https://commons.wikimedia.org/wiki/File:U.S._Bank_Tower_(Los_Angeles)_July_2022.JPG)；CC0；作者：Benoît Prieur；拍摄日期说明：2022-07-13 14:16:57。完整署名/许可URL在来源登记。
- [File:U.S. Bank Tower, Los Angeles, California (3124933391).jpg](https://commons.wikimedia.org/wiki/File:U.S._Bank_Tower,_Los_Angeles,_California_(3124933391).jpg)；CC BY-SA 2.0；作者：Ken Lund  from Reno, Nevada, USA；拍摄日期说明：2008-10-17 17:06。完整署名/许可URL在来源登记。
- [File:U.S. Bank Tower and 7th Street (Los Angeles) July 2022.JPG](https://commons.wikimedia.org/wiki/File:U.S._Bank_Tower_and_7th_Street_(Los_Angeles)_July_2022.JPG)；CC0；作者：Benoît Prieur；拍摄日期说明：2022-07-28 12:32:31。完整署名/许可URL在来源登记。
- [File:US Bank Tower, Los Angeles, California (14338570787).jpg](https://commons.wikimedia.org/wiki/File:US_Bank_Tower,_Los_Angeles,_California_(14338570787).jpg)；CC BY-SA 2.0；作者：Ken Lund  from Reno, Nevada, USA；拍摄日期说明：2014-06-27 18:03。完整署名/许可URL在来源登记。

没有引入第三方三维模型。上述照片仅供有署名的内部研究与对比，不作为纹理。其他版权页面只缓存文字/HTML研究记录，未下载其远程照片。室内未建。
