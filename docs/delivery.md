# 第三阶段当前交付

主检查点 scenes/stage03_city_medium.blend，真实顶视/侧视/Downtown/线框位于 work/previews/stage03/stage03_city_medium。坐标/转换/分块/地形/水体/调查剖面和全部证据见 docs/stage03.md 与 STATUS.md。
阶段02的329个文件已完整冻结至 work/history/stage02_before_stage03，并实际复核SHA；以下早期说明作为历史保留。

# 交付与保存

工程 `/workspace/Base`。阶段 02 主要交付：

- `data/raw/stage02`：正式下载、原始服务页、调查记录、请求凭据和 SHA-256。
- `data/processed/stage02`：全市市界、流式建筑、道路、水体/设施/铁路/海岸线、DEM、NLCD、树冠、树点、地标，及选择表/年代修正/对应关系。
- `config/stage02_requests.lock.json`：81 个已取得 HTTP 响应的 URL、参数、大小与哈希；`config/stage02.yaml`：预算与规则。
- `scripts/stage02*.py`：请求、清洗、语义隔离、完整审计、独立缓存、预览与 Blender 检查。
- `scenes/stage02_data_review.blend`：可编辑实际建筑轮廓/道路线/真实地面数据检查点，没有挤出未核高度。
- `work/previews/stage02`：Downtown 叠加、覆盖图、缺口图及真实 Blender 渲染。
- `work/reports/stage02`、`work/logs/stage02`：实际数量、有效率、高度缺失率、DEM覆盖率、分页计数、运行/重开证据和请求日志。
- `outputs/stage02_acceptance.json`、`stage02.manifest.json`、`stage02_files.sha256`：验收、自动输出保护与最终文件完整性清单。
- `docs/stage02/sources.md`、`data_readiness.md`、`schema.md`：来源、年代/精度/许可、可用性及标准结构。

运行与恢复见 docs/usage.md。`buildings.geojson` 为指向完整 gzip JSON Lines 的索引，非空建筑数据在 `buildings.geojsonl.gz`。
公开再分发前须按 source_registry 检查县/市资料与照片权利，不将联邦公开数据许可扩张至所有来源。
阶段 03–10、正式地形/全市建筑网格、GLB 与交互查看器均未实施，等待第三部分。
文件保存在当前工作区；未自动 Git 提交、推送或公开发布。云环境草稿保存不等于应用、发布或新任务恢复验证。

## 阶段 01 冻结交付（保留）

原94个交付文件已在 work/history/stage01_before_stage02 完整保存；原模型和渲染仍在原位置。
以下第一阶段记录为历史说明，关于“未取得道路/DEM/建筑”的描述只适用于当时。

# 第一阶段交付说明

工程根目录 `/workspace/Base`。主检查点 `scenes/stage01_calibration_medium.blend` 可直接打开编辑。
低档补充检查点为 `scenes/stage01_historic_core_low.blend`，高档为 `scenes/stage01_calibration_high.blend`。
三个均为合成米制技术样板，差异为选区元数据和检查渲染参数，不是真实地理建筑模型。

## 主要文件

- PROJECT_SPEC.md：目标、范围、视觉等级与运行时 LOD 的区分、十阶段门禁和执行规则。
- STATUS.md：实际完成情况、报告路径、真实限制及下一阶段入口。
- config/project.yaml：可调参数；config/sources.lock.json：原始来源的不可变 URL 和 SHA-256。
- data/raw/：原始响应与下载凭据记录（receipt，不含身份密钥）；data/processed/：经纬度多边形、本地米制副本、原点和范围校验清单。
- scripts/project.py、project：统一入口；bootstrap.sh：锁定依赖安装；geo_scopes.py：范围派生；blender_stage01.py：建模、保存、重开测量与渲染；browser_probe.py：真实本地页面截图；validate_stage01.py：未实现门禁测试；fetch_stage01_sources.py：原始输入校验和恢复。
- work/previews/stage01_calibration_medium.png：真实 Cycles CPU 检查图。
- work/previews/stage01_calibration_medium_browser.png：真实 Chromium 页面截图。
- work/previews/scopes.svg：依真实投影位置绘制的范围图；没有为构图移动地标或背景城市。
- outputs/stage01_*.manifest.json：每个运行配置的模型、图像、报告与日志的文件哈希。
- outputs/stage01_acceptance.json、stage01_files.sha256：整体验收记录和交付文件清单。

完整目录另含 assets 分类占位、viewer 后续说明、work/cache、work/tmp、work/history、scenes 和 outputs。
缓存及失败诊断历史不属于最终城市资产，保留在当前环境中供复查。

## 复查

```bash
cd /workspace/Base
bash scripts/bootstrap.sh
./project env
./project check --stage 1 --region calibration --quality medium
./project run --stage 1 --region calibration --quality medium
```

同输入的 run 会验证并复用模型/渲染，仍启动新的浏览器探针；没有持久 HTTP 服务需要手工维护。
详见 docs/usage.md。阴影、流送、纹理、实时 LOD 的质量预算已保存，运行时实现留到后续阶段。

当前不交付真实全市建筑、DEM、道路、街道级近景、独立地标、GLB 或交互城市查看器。
全市范围是可追溯且按 GEOID 核对的官方 2020 年 1:500,000 归档版本，不是已核实的 2026 精细行政边界。
地图原始数据许可细节与再分发边界见 docs/sources.md。

所有工作已保存到当前工作区，未自动提交 Git、推送远程或公开发布。
云环境安装/启动说明和精确域名需求已保存为草稿，保存不等于执行、应用网络设置或发布。
如需固化当前云环境，在环境设置中审阅并保存草稿，再发布；新任务恢复尚未独立验证。
