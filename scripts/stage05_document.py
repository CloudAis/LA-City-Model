"""Write the human checkpoint record only after actual acceptance and CLI checks."""
from pathlib import Path
import json,datetime
ROOT=Path(__file__).resolve().parents[1]
def write(root=ROOT):
 root=Path(root);a=json.load(open(root/'outputs/stage05_city_medium_acceptance.json'));b=json.load(open(root/'work/reports/stage05/blender_check.json'));s=json.load(open(root/'work/reports/stage05/source_statistics.json'));g=json.load(open(root/'work/reports/stage05/geometry.json'));v=json.load(open(root/'work/reports/stage05/building_sample_audit.json'));env=json.load(open(root/'work/reports/environment.json'));gate=json.load(open(root/'work/reports/stage05/cli_gates.json'));inc=json.load(open(root/'work/reports/stage05/incremental.json'));assert gate['status']=='passed' and inc['status']=='passed';stamp=datetime.datetime.now(datetime.timezone.utc).isoformat();size=(root/a['model']).stat().st_size;instances=json.load(open(root/'assets/buildings/stage05_catalog.json'))['shared_instances_by_kind'];tc=sum(instances.values());heights='\n'.join(f'| {k} | {n} |' for k,n in s['height_sources'].items())
 status=f'''# 洛杉矶城市项目状态：第五阶段检查点已交付

更新时间：{stamp}（UTC）。工程：`/workspace/Base`。

**阶段05状态为`complete_with_documented_gaps`。模型、数据、模块和本轮检查已完成；近景只是初版，不能解释为全市外观、所有高度或道路/建筑接口均已核实。等待用户第六部分，不执行阶段06–10。**

## 交付

| 内容 | 路径/实际内容 |
|---|---|
| 可编辑主模型 | `scenes/stage05_city_medium.blend`，{size}字节（约{size/1024**3:.2f}GiB），Blender原生Zstandard压缩 |
| 标准建筑数据 | `data/processed/stage05/buildings.sqlite`，{s['counts']['active']}栋活动建筑；WKB米制坐标、UID、原始字段、年代、高度/类型依据和分部 |
| 可重复生成与块网格 | `scripts/stage05*.py`、`config/stage05.yaml`、`data/processed/stage05/mesh_index.json`及`meshes/` |
| 作者/简化层 | 1691个质心归属块、3382个建筑网格；全市1000m、Downtown250m、近景125m；同一建筑只归属一块，跨界不裁断 |
| 建筑模块库 | `assets/buildings/stage05_modules.blend`、`stage05_catalog.json`；11种原创近似模板，实际{tc}个共享GN实例 |
| 实际渲染 | `work/previews/stage05/`：city_top、downtown_top、skyline_northwest/northeast/south、historic_core_street、civic_center_street；7张1536×1152 CPU Cycles原图 |
| 数据/模型对比 | 同目录3张`skyline_*_comparison.png`；固定机位的来源高度包络/公布尖塔与实际保存网格，不是独立街景照片比对 |
| 统计与地图 | source_statistics.json及height_sources/building_types/source_years/roof_shapes.csv；building_heights_city、height_evidence_city、downtown_height_evidence、building_placement_gaps.png |
| 来源与说明 | `data/processed/stage05/source_registry.json`，`docs/stage05.md`、`stage05_sources.md`、`stage05_validation.md` |
| 验收/清单 | `outputs/stage05_city_medium_acceptance.json`、`stage05_city_medium.manifest.json`；完整交付索引为`stage05_delivery.json`、`stage05_files.sha256`和`stage05_integrity.json` |

## 实际通过的检查

- {s['counts']['active']}栋主体，13种资料支持/未知类型；Downtown7316栋（含近景104栋）。保留14096个来源庭院、21个真正多部件建筑。391栋关联分部，其中287栋实际形成多高度分段，裙房/塔楼按区间并集生成，未叠加贯穿全高父体。
- 独立Blender进程重开：非数值坐标{b['nonfinite_coordinates']}、退化三角形{b['degenerate_triangles']}、无效材质索引{b['invalid_material_indices']}、向下屋顶面{b['downward_building_roof_faces']}、重复作者块归属{b['building_ids_in_multiple_authoring_cells']}、错误平滑建筑面{b['smooth_building_faces']}。米制1BU=1m。
- 从保存文件提取并抽查{v['sample_count']}栋，覆盖全部13类型、庭院、多部件、分部、架空、山坡、各高度来源及主要高层。轮廓IoU最低{min(x['source_model_footprint_iou'] for x in v['buildings']):.6f}；高度/落地、孔洞、法线和材质分配检查通过。数值一致只验证模型实现，**不代表原资料测绘精度**。
- 实际保存的默认显示{b['visible_default_triangles_including_GN_instances']}三角形（含GN实际实例），小于medium1500000；静态范围约150m。完整作者/简化资产仍驻留文件，共{b['all_stored_unique_triangles']}个唯一使用网格三角形；离线全市图约3273万可见，不作实时FPS或RAM预算声明。
- 区域集合`B5_Authoring_*`、`B5_Runtime_*`、`B5_Modules_*`区分城市、Downtown、Historic Core、Civic Center。5051个建筑/模块对象重组前后几何、材质、ID、变换、显隐哈希相同，并独立重开确认。
- 修复float32后445个屋顶微面朝向、隔离2201个退化微面；建筑/模块显式硬边着色，消除了平滑直墙的假阴影。Wilshire尖塔依最高OSM分部定位，8个基点实际接触支撑顶面，整体高度335.28m不扩展到全足迹。
- 七张最终图已逐张实际查看；全市港区构图完整，NW机位改为距地80m、NE60m虚拟俯瞰，未移动地物。`visual_inspection.json`记录近景及材质问题。压缩模型在环境短暂离线恢复后通过`zstd --test`，图像SHA也已复核。
- `./project env`、阶段05 check与相同输入run实际通过；模型/7图SHA重跑前后相同，见incremental.json。未实现阶段/区域/质量和export正确退出3，并发run退出75，见cli_gates.json。

## 高度来源（报告值不等于实测）

| 方法 | 数量 |
|---|---:|
{heights}

没有随机高度。大量OSM高度带县建筑编号，血统与县资料相同，不能当独立验证。县HEIGHT正式定义仍未知，候选美国测量英尺解释标推断；ELEV/OSM ele不作为绝对屋顶或地面高程。物业公布U.S.Bank1018国际英尺=310.2864m只作舍入公布顶部参考；Wilshire1100英尺=335.28m为含尖塔总高，主体分部/屋面候选与总高分开。

## 未通过、未知与后续资料缺口

1. 原县几何是屋顶轮廓，地面外墙足迹尚未核实。大部分来自2008，另2014/2017/2020及少量更早；OSM2026-10-20数据库状态不是采集年，不称同一天完整城市快照。
2. 大量报告高度、楼层、外观及用途未独立测量。286个高度/小结构类型冲突有单独档案：3个91–199m未核实候选结合小范围低层环境影像后改为**类型估算**，不是测出新高度；65栋保留报告高度并降为用途未知，余218个冲突继续待查。未把真正高楼按house标签统一压低。
3. 467条明确拆除匹配与7个building=no区域停止建模，原行/几何均保留；后者不是拆除日期证明。新增OSM补充10164栋，未知的新建/拆除/重建仍可能漏报。
4. 6151栋台基高度>8m，305处入口超过当前连接阈值，208处屋顶代理与估算沥青重叠；缺口共6398栋（可重叠）。入口82处有OSM节点，其余推断；没有移动真实建筑去适应估算道路。Civic地形/台基/人行道交接仍需修整，未通过最终近景真实性验收。
5. 21/{v['sample_count']}抽样建筑含T形边/非水密警告；只通过本阶段外观几何检查，不声称全市水密。42处不支持的复杂屋顶采用标注平顶代理。原始庭院保留检查与2D计算伪孔洞过滤分开记录，过滤没有改变网格。
6. 11478个几何凹窗/共享框、59662段女儿墙、5469个HVAC、7315组门/雨棚和20642级台阶多为明确推断。材质采用类型调色板和程序化窗格；原材质/颜色标签保留供研究，未声称全部逐栋复刻。无依据的消防梯/太阳能/水箱只留模板，不批量安放；室内未建。
7. 阶段04的50处源净空冲突、191处非共享交叉层级不明、445处铁路净空警告、18处铁路层级不明、37处缺样及远道路地形遮盖/备用LOD接口等继续保留，不算通过。水面仍是显示参考而非现时水位。
8. 运行时LOD、GLB、交互查看器、GPU/显存与实时FPS未实现/未测。本阶段仅city/medium构建已验证，其他配置明确未实现。完整作者文件的内存需求高于未来查看器的medium缓存目标。

## 环境、保存与下一步

Blender4.3.2 `/usr/bin/blender`；Python3.12.14项目.venv、Node24.19.0、32个锁定依赖。CPU配额4核、32GiB，GPU/显存仍未知；实际Cycles CPU4线程、无降噪。最终环境检查可用磁盘约{env['disk_free_bytes']/1024**3:.2f}GiB。低/中/高规划仍见config/project.yaml和docs/quality.md，不能将离线图片当实时性能测试。

阶段04的21378文件在`work/history/stage04_before_stage05`冻结并复核，正式阶段01–04场景和原始数据未改。可重建缓存已压缩/清理；第一次未验收阶段05草稿仅保留差量几何、原行和哈希，旧二进制已清理，未宣称其字节级可恢复；正式阶段05文件保留，见unaccepted_draft_compaction.json。期间云环境短暂offline，连接恢复后文件、图像校验和模型压缩容器均已确认。

```bash
cd /workspace/Base
./project env
./project check --stage 5 --region city --quality medium
./project run --stage 5 --region city --quality medium
```

start_skill启动草稿的保存状态见docs/cloud_start_stage05.md及对应回执；保存草稿不等于应用/发布，新任务冷恢复与完整冷重建尚未独立验证。没有自动Git提交或推送。

**等待第六部分。** 下一次先读PROJECT_SPEC.md与本状态，从现有Downtown/近景初版继续资料核实和精修；不把推断外观、地形交接或未知高度当已核实实况。
'''
 (root/'STATUS.md').write_text(status)
 readme='''# Base

洛杉矶可扩展三维城市工程，当前第五阶段检查点和未通过项见[STATUS.md](STATUS.md)。开始前先读[PROJECT_SPEC.md](PROJECT_SPEC.md)。

主工程：[stage05_city_medium.blend](scenes/stage05_city_medium.blend)。包含约109.65万栋真实地理轮廓代理、Downtown街区和两个近景初版，保留可编辑块网格、来源ID及共享模块。大量高度/外观仍是报告值或明确推断，尚未达到最终城市写实验收。

```bash
cd /workspace/Base
./project env
./project check --stage 5 --region city --quality medium
./project run --stage 5 --region city --quality medium
```

七张真实CPU检查图与来源/缺口图位于`work/previews/stage05/`。说明见[建模与运行](docs/stage05.md)、[来源](docs/stage05_sources.md)、[验证口径](docs/stage05_validation.md)。模块库位于`assets/buildings/stage05_modules.blend`。

默认仅显示约150m焦点；完整作者资产仍驻留文件。角色下的区域子集合与内嵌`STAGE05_VIEW_PRESETS.py`支持静态查看。GLB、运行时LOD、交互查看器及阶段06–10尚未实现，等待下一部分。阶段01–04正式模型、原始资料及冻结证据保留。
'''
 (root/'README.md').write_text(readme)
 p=root/'AGENTS.md';text=p.read_text();start=text.index('阶段01');end=text.index('使用现有',start);text=text[:start]+'阶段01–05实际检查点已建立；阶段05为complete_with_documented_gaps，来源高度/类型、近景接口、拓扑与阶段04交通缺口见STATUS.md。用户授权到阶段05；等待第六部分，不推进阶段06–10。\n'+text[end:];p.write_text(text)
 print('STAGE05_ACTUAL_STATUS_AND_README_SAVED',flush=True)
if __name__=='__main__':write()
