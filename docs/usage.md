# 当前入口：第五阶段

先读PROJECT_SPEC.md与STATUS.md。已验证的是city/medium；其他阶段05区域/质量、阶段06–10及export明确退出3。

```bash
cd /workspace/Base
./project env
./project check --stage 5 --region city --quality medium
./project run --stage 5 --region city --quality medium
```

主工程scenes/stage05_city_medium.blend，默认约150m静态显示，完整作者资产仍驻留。Blender内嵌STAGE05_VIEW_PRESETS.py或B5_Authoring/Runtime/Modules区域子集合用于查看；不是动态LOD/流送。细节见[stage05.md](stage05.md)。对用户修改过的已登记输出，哈希门禁停止，先另存用户工作，不静默覆盖。

以下旧阶段命令是历史说明；检查旧阶段请使用对应冻结快照及其配置，不能用当前stage05配置冒充旧阶段输入。

# 运行、复查与保存

每次先读 PROJECT_SPEC.md 和 STATUS.md。当前工作为阶段04交通层，实际验收状态以STATUS为准。第四阶段操作与限制见 docs/stage04.md；原地形说明见docs/stage03.md。
工作目录 `/workspace/Base`；没有需要保持运行的服务。

```bash
bash scripts/bootstrap.sh
./project env
./project check --stage 4 --region city --quality medium
./project run --stage 4 --region city --quality medium
./project check --stage 2 --region downtown --quality medium
./project check --stage 1 --region calibration --quality medium
```

项目 Python 为 .venv；requirements.lock 固定全部依赖；uv 缓存位于 work/cache/uv。
Blender 使用 /usr/bin/blender 的内置 bpy/Python，不向普通 Python 混装 bpy。
质量可选 low / medium / high。阶段 02 默认 medium；数据集为全市，验收预览固定 Downtown，
region 表示此次请求的区域上下文，不声称为每个 region 分别下载了不同城市数据集。
阶段 02 不同质量改变检查渲染分辨率，共用标准数据；改变质量会归档并替换阶段 02 自动检查点。

## 阶段 02 流程

1. 校验 81 个已锁定 HTTP 响应和本地 SHA-256，缺失时按 config/stage02_requests.lock.json 请求恢复。
2. 预算检查、缓存、限定重试与断点续传；服务原生 ID 列表、服务器计数与分页结果完全比较。
3. Census 样本检查后全分区归档；完整 GDB 字节保留，按实际市界空间选择。矢量统一稳定 ID、来源、年代和分块。
4. DEM / 建筑 / 官方清单 / 分类覆盖各有独立内容缓存，新地标资料不会重建百万轮廓。
5. 几何修复、孔洞保留、独立结构分类、精确重复排除和新旧建筑对应；候选高度不会写成核实 height_m。
6. 生成覆盖/缺口图、Downtown 建筑道路真实地形叠加；Blender 独立进程保存、退出，再以新进程重开并渲染。
7. 保存统计、验收、日志及 manifest；相同输入重跑验证所有输出并直接复用 .blend 和 PNG。

标准全市建筑是 `buildings.geojsonl.gz`，逐行 GeoJSON Feature；同名 `buildings.geojson` 是索引，空 features 不表示城市没有建筑。
使用 `scripts/stage02_dataset.py` 的 iter_model_buildings(root) 自动排除太阳能独立结构与 3 个精确重复旧轮廓。
Downtown 可直接读取 downtown_buildings.geojson，市区道路读取 roads.geojson。

## 恢复边界

已保存 raw 文件是精确复现的权威输入，不能静默替换为服务器的新版本。请求 URL、参数、下载日期与 SHA-256 均保留。
ArcGIS 临时 exportImage URL 可能过期；缺失树冠 TIFF 时，用 canopy/export.json.receipt.json 保存的稳定 exportImage 参数申请新导出，
对新字节建立新版本后复核，不改旧哈希冒充原文件。动态 ArcGIS 元数据/计数重新请求也可能变化，须登记新版本。
直接校验/恢复命令：`.venv/bin/python scripts/stage02_acquire.py`。
少量早期调查响应保留为研究证据；正式矢量/栅格均有下载凭据。原始 Completeness JSON 是计数核对派生报告。
阶段02请求锁不能恢复当时未取得的OSM、点云、建筑分部、车道与立面照片。阶段04的OSM PBF及请求凭据另存data/raw/stage04；其余缺口继续登记。

## 保护、退出码和后续门禁

已有自动输出与 manifest 不符时停止，先将用户编辑另存独立文件。输入变化时原输出复制到 work/history 后重建。
阶段 01 的全部 94 个交付文件有冻结快照 work/history/stage01_before_stage02；历史检查使用当时保存的配置。
不要为验证阶段 02 重新运行阶段 01 构建来替代历史证据。

实际执行并登记的检查通过返回0；运行错误1；参数错误2；阶段05–10、未支持的阶段04区域/质量和GLB export返回3。并发run因构建锁被拒绝时返回75，未写入模型。
阶段 02 状态 complete_with_documented_gaps 表示所选真实数据流水线已通过，同时保留语义、精度、年代和许可缺口。
并不表示 2026 城市全要素/高度/立面研究已完整。缺核心输入时不会返回成功。

第一阶段浏览器截图和 SwiftShader WebGL2 证据保留；第二阶段主要预览为 Matplotlib 与 Blender 真实生成图。
本地报告页不是第九阶段交互城市查看器，也不对外发布 localhost 链接。
成果仅在当前工作区保存，未提交、推送或公开发布；新云任务恢复尚未独立验收。

## 第三阶段补充

实际分块底座和完整操作见 docs/stage03.md；补充来源见 docs/stage03_sources.md。第三阶段主检查点为 scenes/stage03_city_medium.blend。
地形分块1000米和未来GLB250米约定分开管理；LOD几何已烘焙并验证混合接缝，运行时查看器切换仍未实现。
独立科学剖面导出命令为 `.venv/bin/python scripts/plot_river_sections.py`，使用保存的原始1米DEM调查剖面。

阶段04当前支持并实际验收的任务是`./project run --stage 4 --region city --quality medium`与对应check。
其他阶段04区域/质量任务明确返回未实现；阶段05–10和所有export仍退出3。
阶段四主工程目标文件为`scenes/stage04_city_medium.blend`，当前结果及验证边界以STATUS.md为准。详见docs/stage04.md。
