# Los Angeles City Exterior · 1.0.0

> GitHub私有仓库：[CloudAis/LA-City-Model](https://github.com/CloudAis/LA-City-Model)。完整工程与本地查看器通过[v1.0.0 Release](https://github.com/CloudAis/LA-City-Model/releases/tag/v1.0.0)下载。大模型不放入Git历史；恢复方法见[GitHub下载与恢复](docs/GITHUB.md)。需要有访问该私有仓库的账号。

工程：`/workspace/Base`。第十阶段总核查、修复、展示与本地交付已整理。**整体部分通过**：工程与查看功能通过，数据年代、推断高度、地标细部、场地接口及照片写实仍有明确缺口。开始工作先读 [PROJECT_SPEC.md](PROJECT_SPEC.md) 和 [STATUS.md](STATUS.md)。

完整交付位于 [outputs/LA_Delivery](outputs/LA_Delivery/README.md)。用Blender4.3.2打开 [LA_Master.blend](outputs/LA_Delivery/LA_Master.blend)，保留整个`assets`目录，尤其`assets/linked`下两个关联工程。默认打开Historic Core，米制、CPU渲染；十个独立地标见`landmarks/*.blend`。本工作区部分资源使用硬链接，编辑前应另存新副本。

从最终交付目录启动：

```bash
cd /workspace/Base/outputs/LA_Delivery
python start.py --port 8090
```

同机浏览器访问`http://127.0.0.1:8090`，需要Python3.10+与WebGL2；运行时不需要Node、Blender、CDN或互联网。端口占用可改为8093。云环境的localhost不等于用户电脑的localhost。

也可将 [本地查看器工作副本ZIP](outputs/LA_Local_Private_Viewer_1.0.zip) 完整解压到本机后执行`python start.py`。此ZIP含模型、贴图、页面、展示图和视频，不包含完整可编辑主工程及关联库。只在本次Linux环境实际启动测试，未认证Windows/macOS。完整目录与查看器ZIP是私有任务工作资料，含再分发条款尚未明确的市/县派生数据；[原创材质与工具子集](outputs/LA_Original_Materials_And_Tools_1.0.zip) 单独提供，详见[许可与依赖](outputs/LA_Delivery/docs/LICENSES_AND_DEPENDENCIES.md)。

行政分块域约1299.693km²，Downtown工作窗16km²。最细的Historic Core与Civic Center两个350×400m窗合计0.28km²，100栋细化足迹并集约0.1530km²，其中5栋有重点外观研究。工作窗不等于全部完成精修。十地标均是有资料的近似；Santa Monica和Beverly Hills未作为洛杉矶市背景启用。

- [最终十阶段验收表](outputs/LA_Delivery/docs/FINAL_ACCEPTANCE.md)
- [打开、操作、修改、重建与扩展](outputs/LA_Delivery/docs/DELIVERY.md)
- [十二机位×四光照及四张CPU渲染](outputs/LA_Delivery/previews/index.html)
- [十地标预览索引](outputs/LA_Delivery/previews/landmarks/index.html)
- [24秒实际模型视口视频](outputs/LA_Delivery/video/city_tour.mp4)
- [实测性能](outputs/LA_Delivery/docs/PERFORMANCE.md)

本次4核/32GiB、SwiftShader软件WebGL2，中档1920×1080窗口/960×540内部渲染，三轮巡游平均20.73FPS；Historic Core约9.67FPS，原生1080p街景约3.78FPS。按用户允许调整后的巡游平均15FPS目标通过，初始原生1080p30FPS未通过，硬件GPU/显存未知。高档保留PBR映射但关闭阴影与透射以兼容软件设备；原生物理材质保留。

统一入口：

```bash
./project env
./project check --stage 10 --region city --quality medium
./project run --stage 10 --region city --quality medium
./project export --stage 10 --region city --quality medium
```

第十阶段流水线只接受`city/medium`，按清单SHA验证并增量复用。其他组合明确返回未实现；查看器内部三档另行切换。交付目录独立核对使用Python3.12执行`python scripts/check_delivery.py`。样本修改重建的实际命令及依赖见维护说明。输入或冻结成果改变时停止，保留用户编辑。未执行清空全部缓存后的全联网冷重建。

原始数据和阶段01–09工程、清单、预览及阶段09便携包均保留。最终源代码在`outputs/LA_Delivery/viewer/source`，生产构建在相邻`dist`，实际模型/纹理/属性在`tiles`；不能只复制`dist`。
