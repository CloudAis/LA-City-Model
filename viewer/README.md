# 洛杉矶本地三维查看器

```bash
cd /workspace/Base
./viewer/start.sh --port 8090
```

在服务所在机器的浏览器打开 `http://127.0.0.1:8090`。仅浏览已构建版本需要Python3.10+及WebGL2浏览器，运行时无CDN依赖。云环境的localhost并非用户电脑的localhost；便携包可解压后在自己的电脑运行 `python start.py`。

源码：`src/`。构建：`dist/`。模型和元数据：`../outputs/stage09/resources/`，不能只复制dist而丢失这些资源。

开发时执行 `npm ci`、`npm run build`，依赖由package-lock锁定。主场景编辑仍使用第八阶段Blender工程；运行时合并资产按稳定ID保留选择能力。具体操作、坐标、质量取舍、来源及限制见 [阶段09说明](../docs/stage09.md)，实测结果见 [性能报告](../docs/stage09_performance.md)。
