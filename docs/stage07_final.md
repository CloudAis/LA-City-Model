# 第七阶段：近景街区修订2

本修订延续 Historic Core 与 Civic Center 两个既有350×400m工作窗口，合计280000m²。所有位置使用既有项目原点和米制坐标；原始地理距离不调整。它是有来源、可编辑的近景外观工程，五个研究对象采用参考资料指导的近似方案，完整测量立面数为0。

当前文档定义交付及验收机制。实际生成、重开、渲染和目视验收状态以 `work/reports/stage07_final/`、`outputs/stage07_final_acceptance.json` 和 `STATUS.md` 为准；这些文件实际存在且通过之前，本页不构成验收通过声明。

## 工程与依赖

- 最终场景：`scenes/stage07_final.blend`。
- 必须同时保留：`scenes/stage07_city_medium.blend`。最终文件用相对路径 `//stage07_city_medium.blend` 链接其中未变更的城市网格，以避免在有限磁盘中再复制整城。移动交付时将两个文件保存在同一 `scenes` 目录。仅复制最终文件会造成链接缺失。
- 本次新增建筑、入口、地面和材质可在最终文件中直接编辑。未变更的链接网格在上述源文件编辑；需要单独修改时可在 Blender 中 Make Local，并相应增加内存和磁盘预算。
- 五个研究建筑资产位于 `assets/buildings/stage07_final/{alexandria,arcade,times,records,theatre}.blend`。它们是对象库，用 Blender 的 File → Append → Object 追加；不是含相机和灯光的完整独立场景。独立后台追加检查记录于 `library_check.json`。
- 修订输入与三角网格：`data/processed/stage07_final/index.json`、各建筑NPZ、地形NPZ、`public_surface.json`、道路更新、街道设施位置及原创叶片资产。固定种子在 `config/stage07_final.json`。
- 旧技术检查点、旧清单及其真实失败/未完成状态保留；历史冻结目录为 `work/history/stage07_technical_v1`。本修订使用新的最终清单，不改写旧验收记录。

## 建筑范围及资料边界

既有103个县建筑记录被重新解释为100份建筑记录及1座映射空中连桥。记录中97份生成可用地面入口；967433、968803、1042507是约0.82/2.61/7.54㎡微小屋顶轮廓，独立地面建筑/入口尚未确立，保留来源和缺口。县记录1005397、1052445、1056567先前被错误估为约85m高的狭长体块；它们对应OSM way425993596的连桥，采用来源 `min_height=6m`，封闭桥体高度3.6m为明确估算。连桥不应具有地面入口；其下的人行道应连续。

普通建筑保留来源平面、分部和庭院关系，使用真实几何开洞、凹进玻璃、门厅和逐栋落地处理。中性窗格、门型、楼层节奏和屋顶设备是有标记的视觉设计推断。它们不意味着已逐栋测量实际立面。

五个研究对象的进一步来源、观察盲区和维度定义见 `docs/stage07_revision_research.md` 及原有来源登记：

| 对象 | 使用的资料特征 | 仍须保留的近似声明 |
| --- | --- | --- |
| Alexandria Hotel | 原始8层、后部12层扩建，砖石及檐口组织 | 34.6m前部高度、内部前后分割和未测量饰件；来源最高51.5m未独立核验 |
| Spring Arcade | 两座12层塔楼、连接3层拱廊、上部玻璃拱、街道两端入口和无线电塔 | 塔楼分界、塔架尺寸及精细立面均近似；26.2×7.9m是内部拱廊尺寸，不是整座足迹 |
| Los Angeles Times Building | 低层主体、退台塔部、浅色竖向组织、红色入口 | 塔楼平面、钟面位置和屋顶层级并非测量图；来源高度42.7m仍未核验 |
| Hall of Records | 来源建筑分部、北侧办公窗节奏、南侧储藏翼、百叶及8层陶瓷屏 | 储藏层高、屏栅精确格网、后部细节和来源高度51.2m未测量核验 |
| Los Angeles Theatre | 官方五层立面、约3.2m地面门、上方独立大拱、雨棚、柱列及竖向招牌 | 门上大拱与地面入口分别建模；17m装饰立面屏和超出来源最大屋顶边0.5m的位置为照片指导推断，门斗0.35m为浅层视觉替代；装饰和精确比例近似，21m来自层数推断，不能称为实测高度 |

阶段06十个独立地标继续保留原有实际位置与近似状态。本修订不把它们改称为精确复制品。

## 地面与街道

原始DTM和旧工程保持原样。本修订使用既有道路与人行道控制点计算共同的推断街道坡面，在工作区及50m过渡带作视觉衔接。相邻地形块使用同一全局采样规则，不再分别向块边缘衰减。该地形是街景接口的视觉修整，不能称为更高精度裸地测量。

近、远景建筑版本均包含按不超过4m边段采样的随坡基础，避免简化版本出现悬空。连续人行道替换相应范围中的旧三角面；采用精确平面裁切，检查旧新重叠面积。路缘高0.15m为推断配置，表面绕开原有坡道轮廓，并在坡道口省略竖直路缘。坡道只将原平面轮廓重整到0–0.15m视觉坡面；不构成无障碍合规认证。连桥下恢复人行道。原OSM54个树木及设施点的XY保持来源，Z随新的视觉街道坡面衔接。树种与树冠形态未实测，新增叶片为固定种子的原创通用几何。

## 运行与验收

统一入口完成集成后使用 `./project run --stage 7 --region city --quality medium` 和对应 `check`。当前模块也可直接使用：

```sh
.venv/bin/python scripts/stage07_final.py execute --region city --quality medium
.venv/bin/python scripts/stage07_final.py libraries
.venv/bin/python scripts/stage07_final.py register
.venv/bin/python scripts/stage07_final.py check --region city --quality medium
```

仅支持city/medium，其他组合明确返回3“未实现”。缺少最终人工图像审查或其他尚未执行的证据返回4“待验收”。真实检查失败或哈希变化返回1；已注册、证据完整且输入/成果哈希一致时才返回0。已有最终场景或可编辑数据不会被统一入口静默覆盖。

验收必须具备以下实际证据：

1. 最终文件保存后由另一个Blender进程重开，`blender_check.json`记录米制、100栋建筑、十个保留地标、无非数值顶点、无退化面、有效材质索引和无旧代理重叠。链接源文件必须存在。
2. `ground_generation_check.json`实际检查人行道绕坡道、路缘方向、旧新面裁切及连桥下地面。生成检查本身不能替代打开场景与图像检查。
3. `renders_all.json`必须对应 `config/stage07_final_views.json` 的十个正式相机，真实CPU Cycles最终PNG必须为配置尺寸。街道2张、五个研究对象各1张、两个顶视图及Civic Plaza1张；草稿图不计。
4. 实际逐图打开检查后记录 `visual_inspection.json`：`status=accepted_with_documented_approximations`、`stage_gate_passed=true`、`actual_images_viewed=10`、当前最终场景SHA256，以及十张图片的路径、SHA256和 `actual_view_image_inspection=true`。未观察到或无法确认的部分写入 `limits`；脚本不生成视觉通过结论。
5. 五个对象库在独立factory-startup进程中实际追加，检查非空网格及有限坐标。结果为 `library_check.json`。
6. `geometry_audit.json`由实际读取来源与生成网格的独立审查产生，检查建筑来源、分部及接口；审查必须实际通过，并绑定当前index文件及全部生成NPZ的SHA256，报告纳入最终清单。

满足上述证据后，`register`生成 `outputs/stage07_final_acceptance.json` 与 `outputs/stage07_final.manifest.json`。清单将保留的源场景、实际读取的源数据、原始研究资料、脚本、配置和清洗几何作为输入；登记最终工程、五个对象库、十张真实PNG和检查证据的SHA256。修改已登记输入或成果时，检查报错并要求保留编辑，不会回写虚假成功。

场景的默认可见三角形预算为1500000，保存及重开时实际核对。每个检查相机的可见面数另行记录；为观察立面、屋顶采用不同静态视距。这里的LOD是作者场景与渲染时的可见选择，没有实现运行时距离切换、流式加载或交互查看器。后续阶段的实现与验收独立登记，本修订清单只证明阶段07。
