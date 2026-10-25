# 使用与维护 ·1.0.0

完整本地交付目录：outputs/LA_Delivery。它是本任务的私有本地工作副本，含许可尚未明确的市/县派生资料，不能据此推定可公开/商业再分发。许可明确的代码/原创材质另有单独资源包，未明确条款的数据只保留来源、获取方法和依赖说明。详见LICENSES_AND_DEPENDENCIES.md。

## 打开完整主工程

Blender4.3.2打开LA_Master.blend，保留整个assets目录，尤其assets/linked/stage07_city_medium.blend和stage07_final.blend。它是完整可编辑城市的关联组织，不是六样本检查场景。默认HistoricCore约1409177三角形、米制、材质色实体视图，渲染使用CPU Cycles。99_FINAL_CHECK_CAMERAS保存十二个检查机位。

不要只复制主文件而遗漏关联库。相同工作区为节约磁盘对未修改文件使用硬链接；另存为新文件再编辑，避免改动冻结来源。拷贝到别的磁盘/机器时普通复制文件即可，不依赖原始绝对工作区路径。独立地标landmarks/*.blend已逐个保存/关闭/重开，包含三LOD及打包PBR纹理，不需要原工程库；它们均保持有资料的近似状态。

## 启动实际本地查看器

从交付目录运行：

```bash
python start.py --port 8090
```

同机浏览器打开http://127.0.0.1:8090。若端口已被旧阶段服务占用可改为8093。Python3.10+与WebGL2即可，运行时无需Node/Blender/互联网。云环境localhost不是用户电脑localhost；下载本地查看器工作副本或复制交付目录到本机后启动。

鼠标左键环绕，右键平移，滚轮缩放；F飞行、O环绕、G概览、H说明；飞行时WASD、QE升降、Shift加速，左键调整朝向。单击模型查看ID、来源、年份和高度证据。可切换图层、四光照、三质量、两个近景区和十地标。自由飞行没有实体碰撞，不是行人导航系统。/previews/index.html展示检查图，/video/city_tour.mp4为巡游。

云端低配优先低档；中档内部960×540实测巡游20.73FPS，复杂HistoricCore约9–10FPS；原生1080p街景3.78FPS。高档600k局部目标、PBR映射、阴影关闭、玻璃不透射兼容，原始物理材质保留在原生/GLB中。详见PERFORMANCE.md，不将图像输出15FPS当作实时测试。

## 修改配置并重建样本区域

本包包含HistoricCore两栋真实建筑的源数组与元数据，配置config/sample.json。重建使用实际测试的Python3.12.14与锁定NumPy；仅浏览查看器的Python3.10+要求与重建环境分开。可使用原工作区.venv，或创建Python3.12环境：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r scripts/requirements-sample.txt
.venv/bin/python scripts/rebuild_sample.py --config config/sample.json --output tiles/rebuild/my_sample.glb
```

Windows相应Python为.venv\Scripts\python.exe。样本依赖锁定实际NumPy版本；不要求安装全套地理依赖。include_window_frames和roughness_multiplier可调整，随机种子固定。此命令已实际执行：68725面→18469面、SHA改变、原点不变，并实际导入空场景复查。样本不是整个城市全联网冷构建，也不会覆盖已验收分块。

GLB为局部坐标，旁边JSON记录origin_city_m与稳定ID。独立地标GLB为标准可直接导入版本；实时tiles为带Meshopt的版本，查看器已含本地解码器。要将新模型接入查看器，登记局部原点、轴向、范围、LOD、来源/精度、属性包、SHA及字节数，并按稳定ID替换旧主体，避免追加重复代理。

## 编辑、导出、扩展

主工程中的链接几何应在新副本的关联库编辑，或MakeLocal后另存。近景按r2_building/source_uid组织，地标按stable_id与近/中/远集合组织。不要为构图移动地理位置。新增街区先选真实多边形，核对城市归属，取得有使用依据的轮廓/地形/交通并登记年代、单位和许可；缺失尺寸推断要单列。新增地标先建资料卡与体量、核对高度定义/朝向，再细化，保留未观察部分。

scripts/inspect_scene.py支持固定机位/光照和按稳定ID导出，Blender调用示例与实际命令检查见metadata/acceptance/command_checks.json。渲染输出1920×1080/16采样CPU；不要覆盖LA_Master.blend或已登记分块。完整地理处理/城市再生成仍使用原项目scripts与config及原始数据档案；本交付不声称已作新机器全联网冷重建。原始县/城市资料若缺失，按来源登记获取并自行确认使用条款，不能用空文件替代成功。

修改查看器：viewer/source中npm ci、npm run build；package-lock固定Three0.179.1、meshoptimizer1.3.0、TypeScript7.0.2、Vite8.3.5。生产目录viewer/dist的实际依赖包含本地解码器/WASM和MIT许可；运行时不能只复制HTML而丢弃tiles。开发node_modules链接只是当前工作区便利，不属于可移植运行依赖，公开包与本地查看器包均不携带该链接。

完整工程需要足够内存/磁盘；本次CPU4核、32GiB、GPU/显存未知。Blender后台打开约9–12GiB工作集；全部最高LOD同时显示会增加开销。磁盘紧张采用完整目录加相对关联，最低操作保留0.75GiB；全城冷重建需要另行预算空间，未以本次余量认证。不要删除来源缓存和旧正式检查点来隐藏缺口。
