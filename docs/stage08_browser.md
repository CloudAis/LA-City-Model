# 阶段08浏览器材质样本检查

这是五个独立 GLB 的技术兼容性检查。它不会建立阶段09城市查看器，也不会测试全城流式加载、自动 LOD 或实际硬件 GPU 帧率。

入口为 `scripts/stage08_browser.py`。协调入口应在阶段07验收后、五个真实样本导出后调用 `stage08_browser.run(root)`。样本固定为：

- `outputs/stage08/glb/building.glb`
- `outputs/stage08/glb/road.glb`
- `outputs/stage08/glb/vegetation.glb`
- `outputs/stage08/glb/water.glb`
- `outputs/stage08/glb/landmark.glb`

仅准备本地页面并核对依赖，不启动浏览器：

```sh
.venv/bin/python scripts/stage08_browser.py --prepare
```

实际检查命令（必须由阶段协调器在门禁通过后执行）：

```sh
.venv/bin/python scripts/stage08_browser.py --check
```

实际运行使用项目锁定的 Playwright 与 `/usr/bin/chromium`，只监听临时 `127.0.0.1` 端口。Chromium 明确选择 SwiftShader 软件 WebGL2，因此成功结果不能证明存在硬件 GPU。`--no-sandbox` 只用于此隔离云环境的可信本地样本，不用于浏览外部网页。

浏览器用真实 GLTFLoader 加载五个 GLB，解码全部声明纹理，使用 PBR 环境和灯光渲染。报告记录每个样本的加载状态、材质类型和参数、纹理数量/尺寸/颜色空间、glTF 扩展和压缩扩展、网格数量、三角形、包络、绘制调用、可见像素和 WebGL 错误。程序断言纹理声明数与加载数一致；基础色/自发光贴图使用 sRGB，法线/粗糙度/金属度/AO 使用数据颜色空间。材质共享或克隆会使源材质数与运行时实例数不同，因此分别登记，不能简单断言两者相等。程序检查 GLB2 头、拒绝未嵌入的外部图片/缓冲依赖，记录输入 SHA-256 并在检查后确认输入未改变。纹理采用 GLB 自带数据，运行期间不访问 CDN。成功表示上述加载、颜色空间和绘制检查通过；与 Blender 的视觉一致性仍须查看实际图片。

产物为 `work/previews/stage08/browser_samples.png`、同目录实际页面 DOM 和 `work/reports/stage08/browser_check.json`。截图必须来自本次浏览器执行；截图尺寸与内容方差也会核对。JavaScript、资源、着色器、WebGL 或输入加载失败时返回失败，报告保留真实错误。准备命令只写 `not_run` 报告，不能算浏览器检查通过。

## 锁定依赖与使用条件

本地缓存位于 `assets/browser_dependencies/stage08/three/`，版本 Three.js **0.179.1**。`vendor.lock.json` 登记每个上游 URL、下载日期、大小和 SHA-256；每次准备和检查先核对缓存完整性。导入链仅包含 Three.js 核心、GLTFLoader、BufferGeometryUtils 和 RoomEnvironment。文件原样保存，版权与 MIT 许可文本在 `three/LICENSE`。

上游为 [Three.js](https://github.com/mrdoob/three.js)，固定版本下载源为 `https://cdn.jsdelivr.net/npm/three@0.179.1/`。MIT 允许使用和再分发，须随副本保留版权与许可通知。浏览器未引入 Draco、Meshopt 或 KTX2 解码器；如果后续导出要求这些压缩扩展，真实加载会明确失败，届时应锁定并登记相应解码器再重新检查。报告会列出样本实际扩展，不能将未使用的压缩能力记为已验证。

当前脚本与依赖准备完成不等于样本已生成或实际兼容性通过。真实运行状态以协调入口本次生成的 `browser_check.json` 为准。
