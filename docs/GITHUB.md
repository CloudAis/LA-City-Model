# GitHub私有交付

仓库为[CloudAis/LA-City-Model](https://github.com/CloudAis/LA-City-Model)，私有。默认main分支保存源码、依赖锁、配置和说明；大模型与查看器通过Git LFS保存在[delivery-v1.0.0分支](https://github.com/CloudAis/LA-City-Model/tree/delivery-v1.0.0/deliveries/v1.0.0)。v1.0.0 Release页面提供对应下载入口。现有公开仓库CloudAis/Base未改动。

当前连接可以推送Git和Git LFS，但uploads.github.com附件端点返回401，因此采用已实际测试的LFS传输。大文件不写入普通Git对象；默认源码分支不会自动拉取全部模型。完整交付包含LA_Master.blend、两个关联城市工程、独立地标、8919分块GLB、纹理、来源/坐标元数据、最终查看器构建、图和视频。原始约9GB采集资料及阶段01–09全部历史缓存保留原云工作区，不在最终交付包中；旧阶段全量冷重建仍需原工作区或依来源登记取得输入。

## 只使用本地查看器

使用有仓库访问权的GitHub账号，打开[查看器ZIP文件页](https://github.com/CloudAis/LA-City-Model/blob/delivery-v1.0.0/deliveries/v1.0.0/LA_Local_Private_Viewer_1.0.zip)，点击下载原文件。完整解压后执行：

```bash
python start.py --port 8090
```

同机浏览器打开http://127.0.0.1:8090。需要Python3.10+和WebGL2；运行时无需Node、Blender和互联网。查看器ZIP含实际模型，不含完整Blender编辑主工程。

## 恢复完整编辑交付

安装Git及Git LFS，使用有仓库访问权的GitHub账号认证后执行：

```bash
git lfs install
git clone --branch delivery-v1.0.0 --single-branch https://github.com/CloudAis/LA-City-Model.git LA-City-Model
cd LA-City-Model
python scripts/restore_delivery.py --parts-dir deliveries/v1.0.0 --output outputs
```

模型分支使用LFS自动取得实际分卷和ZIP。如果本机配置了跳过LFS下载，可在克隆后执行git lfs pull取得内容。也可从分支文件页逐一下载全部LA_Delivery_1.0.tar.gz.part*及LA_Delivery_1.0_MANIFEST.json到downloads，再运行：

```bash
python scripts/restore_delivery.py --parts-dir downloads --output outputs
```

恢复脚本只依赖Python3.10+标准库；先核对每卷SHA256，再流式解包并核对完整交付清单，无需另存拼接压缩文件。已有同内容文件会核对并保留，用户修改文件会使脚本停止。恢复需要约4GB目录空间加下载分卷和ZIP空间，建议预留至少6GB。GitHub自动生成的源码压缩包可能只含LFS指针，模型获取请使用Git LFS或文件页原文件下载。

Blender4.3.2打开outputs/LA_Delivery/LA_Master.blend，保持整个assets目录的相对位置。查看器从outputs/LA_Delivery运行python start.py。独立地标在landmarks，展示在previews/index.html，视频在video/city_tour.mp4。

## 许可、检查与源代码

私有存放不补充市/县/LA Times数据的公开再分发授权。完整来源、准确依赖和未确认条款见交付内docs/LICENSES_AND_DEPENDENCIES.md；OSM署名和数据库义务保留。上传不改变项目原有部分通过、近似与混合年代声明，不启用公开GitHub Pages。

最终查看器源码在outputs/LA_Delivery/viewer/source，历史阶段09源码在viewer。前者使用锁定版本，运行npm ci后npm run build；将新构建接入模型前需重新执行交互/性能及文件清单检查。冻结的原始阶段10交付不因发布修改。

发布工具scripts/github_lfs_delivery.py使用独立Git索引维护模型分支，不检出或覆盖作者文件；128MiB分卷上传后从全新LFS缓存实际下载核对SHA，再登记Git指针。完整归档另从GitHub逐卷流式回读，逐文件核对交付清单。实际发布和检查证据位于原工作区work/reports/github_publication。
