# 原程序材质的实际烘焙检查

`scripts/stage08_bake.py` 提供 Blender 中可导入的 `bake_reference(root, source_scene='scenes/stage07_final.blend')`，也可独立运行：

```sh
blender --factory-startup -b --python scripts/stage08_bake.py -- --root /workspace/Base
```

执行前必须已经存在阶段07通过验收记录，且来源 `.blend` 的SHA与该验收完全一致。脚本只追加原 `LA07R2_brick` 材质及依赖，不打开或修改整座城市。未通过07时明确报错，不生成虚假烘焙成果。

在独立临时场景创建3.84×1.20m的竖直XZ平面，U沿+X、V沿+Z、几何法线−Y，与原材质 `Object.X+Object.Y` 和 `Object.Z` 的砖纹理投影一致。原程序材质和节点保留，可编辑副本用于实际Cycles CPU烘焙。三个1024×1024 PNG分别通过真实 `bpy.ops.object.bake` 生成：

- `DIFFUSE` 的COLOR-only基础颜色；关闭直接和间接光照，避免将日间照明烧进材料。
- `NORMAL` 的Tangent切线法线；POS_X/POS_Y/POS_Z，OpenGL +Y。原着色器Bump节点的响应参与烘焙。
- `EMIT` 的粗糙度；只在临时克隆中将原粗糙度输入连接到强度1的Emission，不改动源材质。即使原粗糙度是常数，也实际执行烘焙，不以手填常数PNG代替。

基础颜色以sRGB读取；法线和粗糙度使用Non-Color数据。实际PNG保存后重新加载，核对尺寸、有限像素、非黑、法线正Z及程序凹凸非平坦响应。日志记录每次操作结果和时间；结果与来源 `.blend` SHA、脚本SHA、输出PNG SHA登记在 `work/reports/stage08/bake_check.json`。

烘焙图位于 `assets/textures/stage08/bakes/`；兼容Principled材质及带UV的校准平面保存为可Append对象库 `assets/materials/stage08/baked_brick.blend`，原程序源材质也保留在该库。使用时需保留相对纹理目录。调用完成后恢复原调用者场景；实际旧工程不会保存或覆盖。

该烘焙是原程序材质的单个校准补片，**不声称14类原创PBR贴图都经Blender烘焙**。原程序Noise不是周期函数，因此此补片采用EXTEND寻址，不能直接称为无缝重复贴图。主要材质库的周期PBR资源另由 `stage08_textures.py` 生成和验证。对象库重开、实时GLB导出和回载差异仍须单独实际测试，烘焙文件存在并不替代那些验收。

如果既有烘焙登记与当前来源、脚本或输出不符，脚本停止以保护编辑。需要修订时应先归档旧成果；不能静默覆盖已登记资源。
