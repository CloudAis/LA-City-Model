# GitHub私有交付

目标仓库为`CloudAis/LA-City-Model`，私有。现有公开仓库`CloudAis/Base`不变。Git保存源码、依赖锁、配置和说明；大模型、纹理、最终交付和本地查看器保存在`v1.0.0` Release附件，避免将多GB二进制加入Git历史。

完整交付包含实际`LA_Master.blend`、两个关联城市工程、独立地标、分块GLB、纹理、来源/坐标元数据、最终查看器构建、图和视频。数据/外观的部分通过状态不因上传改变。原始约9GB采集数据及阶段01–09全部历史缓存不在最终交付包内，重建旧阶段仍需原工作区或依来源登记重新取得输入；本包提供已实际验证的最终工程、样本修改和本地查看能力。

## 只使用本地查看器

登录有仓库访问权的GitHub账号，在Releases中下载`LA_Local_Private_Viewer_1.0.zip`，完整解压后执行：

```bash
python start.py --port 8090
```

同机浏览器打开`http://127.0.0.1:8090`。需要Python3.10+和WebGL2，运行时无需Node、Blender和互联网。此ZIP是含实际模型的查看副本，不包含完整Blender编辑主工程。

## 恢复完整编辑交付

登录GitHub后从Release下载全部`LA_Delivery_1.0.tar.gz.part*`以及`LA_Delivery_1.0_MANIFEST.json`到`downloads`目录。可在已认证的GitHub CLI中运行：

```bash
gh release download v1.0.0 --repo CloudAis/LA-City-Model --pattern 'LA_Delivery_1.0*' --dir downloads
python scripts/restore_delivery.py --parts-dir downloads --output outputs
```

恢复脚本只依赖Python3.10+标准库；先核对每卷SHA256，再流式解包并核对完整交付清单。无需再拼接一份大型中间压缩文件，已有同内容文件会核对并保留，用户修改文件会使脚本停止。恢复需要约4GB目录空间和已下载分卷空间；请预留至少6GB。普通解压工具也可先按编号拼接各卷，再解压tar.gz。

Blender4.3.2打开`outputs/LA_Delivery/LA_Master.blend`，保持整个`assets`目录的相对位置。查看器从`outputs/LA_Delivery`运行`python start.py`。独立地标在`landmarks`，展示在`previews/index.html`，视频在`video/city_tour.mp4`。

## 许可、检查与源代码

私有存放不会为市/县/LA Times数据补充公开再分发授权。完整来源、准确依赖和未确认条款见交付内`docs/LICENSES_AND_DEPENDENCIES.md`；OSM署名和数据库义务保留。上传不改变项目原有近似与数据年代声明，不启用公开GitHub Pages。

最终查看器源代码在`outputs/LA_Delivery/viewer/source`，历史阶段09源码在`viewer`。前者使用锁定版本，运行`npm ci`后`npm run build`；将新构建接入模型前需要重新执行对应交互/性能和文件清单检查。冻结的原始阶段10交付保持不变。

Release分卷清单记录各卷字节数、SHA256和完整压缩流SHA；上传后按GitHub返回的附件逐卷回读，并逐文件比对最终交付清单。实际发布和核对结果写入工作区`work/reports/github_publication`。
