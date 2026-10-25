# 阶段08材质样本的GLB兼容检查

本说明由`stage08_export.py`的实际执行记录配合使用；文件存在和语法检查不能替代实际导出、回载或浏览器检查。阶段08模型构建和验收须在阶段07验收后进行。

## 样本与坐标

`scripts/stage08_export.py`提供`export_samples(root, scene, cfg)`，由阶段08 Blender工作脚本在保存并重新打开阶段08检查点后调用。选取五类已有城市网格，不另造展示模型替代城市成果：

| 类别 | 来源选择 | GLB路径 |
| --- | --- | --- |
| 建筑 | Los Angeles Theatre的`r2_building=1080188`、near外观组件；缺失时选Alexandria960933 | `outputs/stage08/glb/building.glb` |
| 道路 | Historic Core附近已有`traffic_role=downtown_road`真实道路网格块 | `outputs/stage08/glb/road.glb` |
| 植被 | `S8_Export_tree_realised`实际树木几何；否则已有真实枝干/叶片原型 | `outputs/stage08/glb/vegetation.glb` |
| 水面 | Downtown附近已有`Water_*`来源水面网格 | `outputs/stage08/glb/water.glb` |
| 地标 | City Hall的near实际组件 | `outputs/stage08/glb/landmark.glb` |

每类临时复制网格并保留实际材质和世界变换，随后把样本包围盒中心XY及最低Z作为临时原点。原城市网格和地理位置不移动。报告保留`temporary_rebase_city_origin_m`、来源对象名与稳定ID、原城市包围盒、回载局部包围盒，可还原地理位置。GLB采用米、Y-up，Blender回载恢复Z-up。

优先使用已保存PBR场景的UV。若某个历史网格没有UV，仅对导出临时副本按面主轴建立局部米制平面UV，并在`uv_fallback_source_objects`逐项记录。该兼容UV不伪装成原始实测展UV，也不修改主工程。材质尺度与纹素密度仍以阶段08材质配置和已保存场景为准。

## 实际检查流程

1. 记录当前已保存阶段08工程的SHA256，读取五类实际对象。
2. 在临时独立场景复制所选对象，解除父级但保留世界变换，应用临时原点偏移。GLB导出只使用所选网格，应用修改器，包含UV、法线、切线和材质，PNG等纹理嵌入GLB。
3. 解析实际GLB2头、JSON块和二进制块。每个图片必须通过bufferView嵌入；PNG签名、尺寸、字节长度和SHA记录在报告，不允许依靠丢失的外部文件。
4. 核对真实导出primitive存在POSITION/NORMAL，以及所有实际纹理引用的TEXCOORD。记录材质数、贴图槽、alphaMode、doubleSided、金属/粗糙度因子、发光值和扩展。每个样本必须至少有一种同时包含BaseColor、Normal及MetallicRoughness贴图的真实材质，纯色或丢失法线/ORM的降级不计作完整纹理兼容通过。植被样本另强制检查叶片为双面MASK及实际cutoff，不把不透明叶片矩形计作通过。
5. 在另一个空场景通过Blender glTF导入器真正重新加载该GLB；检查网格和顶点数量、非数值坐标、法线有限性及单位长度、材质及图片数据、缺失纹理。回载包围盒与临时偏移后的来源包围盒比较，最大计算误差须≤0.02m。
6. 删除临时副本与回载场景，恢复原阶段08场景。重新核对已保存文件SHA，确保导出检查没有重写主工程。

通过后生成`work/reports/stage08/export_check.json`，顶层状态为`passed`，绑定`saved_model_sha256`，五类样本均记录`actual_export=true`、`actual_reimport=true`、`missing_textures=0`及`nonfinite_vertices=0`。任何一步失败即抛出异常，不写虚假的通过结果。计算回载误差不是地理源资料精度或测绘精度。

## 材质语义与渲染差异

glTF2采用metallic-roughness PBR。BaseColor和Emissive纹理按sRGB解码；Normal、Occlusion及MetallicRoughness是线性数据。金属度在B、粗糙度在G、遮蔽可共用同一ORM图的R；导出JSON中的真实连接必须与材质库约定一致。法线采用glTF/OpenGL的切线空间+Y方向，不反转绿色通道。UV原点、切线与Y-up变换交由实际导出/导入器处理，不能手动再翻转一次。

透明模式、双面和发光强度扩展均逐项登记。`KHR_materials_transmission`、`KHR_materials_ior`、`KHR_materials_emissive_strength`等依赖具体查看器支持。实时环境对玻璃的透射、遮挡排序、阴影、大气与色调映射可能与Blender Cycles不同；即使数值回载通过，也不能宣称像素完全一致。

本脚本只完成实际GLB与Blender回载检查。五类样本的真实浏览器加载、截图、透明排序和外观观察是另一份实际验收证据；没有运行浏览器时须明确记录未检查，不能根据上述PBR图谱检查推断浏览器表现通过。五个样本不构成整城分块导出、流式加载或运行时LOD实现。

法线验证以GLB的NORMAL向量和Blender回载后的分裂角点法线为准，两者必须有限且单位长度。屋檐等相对面上的平均顶点法线可能互相抵消；它们不是实际渲染法线，报告以informational单列，不能据此误判GLB法线损坏。检查器已用实际建筑样本和原始NORMAL访问器作过对照。道路样本含真实映射位置的路灯，设施图集的GLB采样器明确为LINEAR/CLAMP无mip，其余大面积纹理保留mipmap。
