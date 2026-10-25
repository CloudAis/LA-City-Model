# 阶段07：Historic Core 与 Civic Center 近景街区

本轮依据现有 PROJECT_SPEC 第07行及用户“第六阶段完成后自动进入第七阶段”执行。两个350×400m工作窗合计280000m²；工作窗相交的整栋建筑唯一归属，因此部分建筑延伸到窗外。市政厅保留阶段06独立资产，另外103栋进行可编辑的近景模块细化。没有执行08–10。

状态为 `technical_checkpoint_valid_visual_refinement_incomplete`：生成、保存、重开、数值检查及真实图像检查已完成，但通用立面与广场地形未达到近景写实精修要求，因此第07阶段整体视觉门禁未通过。按完整资料逐栋核实精修完成的普通建筑为0栋，不能将通用窗框、名字或颜色当成真实立面复原。

## 交付与逐项检查

| 项目 | Historic Core | Civic Center | 验证及边界 |
|---|---|---|---|
| 普通建筑 |81栋|22栋，另保留阶段06市政厅|103栋保存模型数值检查；原轮廓、庭院、分部、相对高度保留。源高度仍有83个未核实县导入报告、20个推断。|
| 门窗 |两区合计11446组实体窗框/窗台/侧向回口共享实例|同左|采用阶段05已有程序化凹窗位置，排除32组与入口冲突的窗框；这些位置并不是实测门窗表。中性模板名masonry不证明实际建筑砌体材料。|
| 入口 |沿街及推断入口|沿街及推断入口|102组双门/把手/雨棚、101处实体台阶/平台/扶手；一栋无入口、一处入口低于邻近采样地面约2.835m，明确未解决。玻璃为暗色外观视觉替代，没有实测室内。|
| 路缘和人行道 |沿用04可编辑几何，增加局部米制铺装|同左|只改变工作窗内面材质，未更改路网位置；路缘、触觉坡道与交叉口保留阶段04近似及局部接口缺口，未声称全部无障碍合规。|
| 街道设施 |按实际OSM点|按实际OSM点|两区42路灯、4消防栓、2防撞柱、1垃圾桶、5树木。没有可靠点位的长椅和棕榈只入资产库，未凭空布满街道。形状、朝向及多数尺寸为明确推断。|
| 材料 |中性玻璃/金属/石色外框及0.6m铺装|同左|程序化材质，没有抓取地图瓦片作纹理，没有把参考照片直接贴在建筑上。|
| 地面接口 |记录下调地板及可编辑地形变体|同左|11栋仅移动Z，幅度约1.88–6.33m；5块地形保留原XY、三角面、道路切孔及边界Z，局部最大地形显示修整约13.307m。属于视觉分级/整平，不是工程土方或测量成果。|

主工程 `scenes/stage07_city_medium.blend` 从阶段06城市工程另存；保留全市可编辑体量、地形、道路及10个独立地标。`assets/street_furniture/stage07_modules.blend` 提供12种原始可编辑模块。新几何/来源在 `data/processed/stage07`，不修改阶段01–06文件和原始DEM。

默认静态工作视图半径180m，1385275三角形（含实例，见`blender_check.json`），低于medium的1500000预算。检查相机可显示更大范围，属于CPU离线检查，不是实时帧率或显卡能力测量。完整城市数据仍保存在工程内，不能将保存视图裁切称为流式加载。运行时LOD/GLB分块查看器仍留待09。

## 实际证据

- `work/reports/stage07/blender_check.json`：新进程打开保存工程，检查非数值顶点、退化面、材质索引、默认可见数量、10地标及已移除代理。
- `building_audit.json`：103栋保存的authoring几何与来源三角面逐项比较，XY误差为0；Z只允许记录的地板修整，容差0.0001m。这是计算一致性检查，不是地理数据自身精度。
- `terrain_seams.json`：5块新变体的边界高度相对前一阶段逐值不变，平面道路切孔不被填回；继承阶段06约4.565e-7m计算边界差，不宣称原始测绘误差为零。
- `work/previews/stage07/`：两区各street/entry/top，共6张1440×1080、32采样CPU Cycles检查图；另有1200×900模块图库真实渲染、数据细化范围图。未启用当前Blender不支持的降噪，检查图有可见采样噪声。
- `visual_inspection.json`：记录实际查看的8张最终图及SHA；只在查看并记录缺口后验收。
- 初次入口近景机位进入相邻建筑，黑图被拒绝，改用经过建筑轮廓/视线检查的Spring Arcade沿街位置重新渲染；见 `camera_correction.json`。台阶局部坐标反射导致的面朝向已修正，见 `stair_normal_correction.json`。
- Civic Center旧机位暴露了广场裸地/铺装接口的粗糙坡面与黑色边界，问题图保留在`work/previews/stage07/rejected/civic_center_street_draft.png`。这是未解决的视觉缺口。补充的正式街景位于OSM way1127429323 North Spring Street中心线，不能用更换机位宣称原广场问题已修复。
- 32组推断窗框与入口重叠，已从新增窗框实例中去掉；门玻璃移到原墙面前方，属于明确的外观视觉替代，没有声称把所有原墙体切出了可进入的真实门洞。

## 来源与外观差异

原始小范围OSM XML两份实际下载于2026-10-23，与04的2026-10-20 PBF状态分开登记。OSM采用©OpenStreetMap contributors，ODbL1.0：<https://www.openstreetmap.org/copyright>。元素编辑时间不是现场采集时间。WGS84经纬度转EPSG32611后减固定城市原点；高度只采用既有NAVD88地形，OSM ele及LARIAC ELEV不直接混入。

5个研究对象有资料记录及10张经实际目视筛选的可复制外观参考，作者、CC/PD许可、拍摄日期、下载日期及SHA在`source_registry.json`/`research_registry.json`。已排除Alexandria采访肖像、宴会、另一场馆Los Angeles Theatre Center、错误Hall of Justice及1962年前的Hall of Records城市照片。后来找到正确Hall of Records夜景及局部后立面，并取得Conservancy的1962建筑文字资料。Conservancy HTML仅作内部事实研究，没有复制页面上的远程版权照片。

已核对的事实包括：Alexandria的pressed brick/terracotta及Beaux-Arts细节、Spring Arcade入口大拱、Times红色石材入口、Hall of Records外屏/百叶、Los Angeles Theatre装饰立面。这些观察没有自动转换成完整测量模型，本轮尚未复原完整装饰、拱廊、Times复杂门框、Records八层陶屏和剧院雕饰。参考照片有年代和观察盲区，不构成2026同日实况。

Alexandria来源推导的17层与照片约8排主要窗层明显不一致；来源高度本身仍未独立核实。本轮保留高度来源并登记差异，没有据此拍脑袋改变高度。Spring Arcade两个尝试的官方URL为404，保留失败记录和有限外观参考。其他未知建筑不能因位于Historic Core就分配历史砖石风格。

## 重现和增量入口

```bash
./project env
./project check --stage 6 --region city --quality medium
./project run --stage 7 --region city --quality medium
./project check --stage 7 --region city --quality medium
```

本轮技术检查点使用输入/交付SHA验证，缓存相同则复用，不重复下载或覆盖。第07阶段run/check对当前检查点返回4，明确指出技术检查点有效、整体视觉验收未通过；这不是崩溃或假成功。low/high、单区流水线、统一export及阶段08–10明确退出3“未实现”。存在未验收工程时退出4提示继续实际检查，不返回假成功。

本轮实际先运行research/data/geometry，随后Blender `build7`、修正、`check-render7`、`library7`，最后reports、参考/结果目视登记及验收。运行记录在`work/logs/stage07`。完整离线重建需要保留已有经过人工筛选的资料输入（含两次补充和review记录）；只重新进行搜索不能保证得到相同结果。

```bash
.venv/bin/python scripts/stage07_data.py
.venv/bin/python scripts/stage07_geometry.py
blender --background scenes/stage06_city_medium.blend --threads 4 --python-exit-code 1 --python scripts/stage07_blender.py -- --mode build7
blender --background scenes/stage07_city_medium.blend --threads 4 --python-exit-code 1 --python scripts/stage07_blender.py -- --mode check-render7
blender --background --factory-startup --threads 4 --python-exit-code 1 --python scripts/stage07_blender.py -- --mode library7
.venv/bin/python scripts/stage07_reports.py
```

在隔离输出位置使用上述重建命令，避免覆盖已有交付或用户编辑；检查器对哈希变化会停止。尚未执行清空所有缓存后的全网络重建，不承诺Blender二进制逐字节相同。

目前机器4核/32GiB，GPU和显存仍未知，实际使用CPU。保存阶段07后剩余约4.49GiB；正式阶段01–06不删除。未来增加完整场景前需要重新评估磁盘预算。
