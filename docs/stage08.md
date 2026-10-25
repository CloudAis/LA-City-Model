# 阶段08：PBR材质、光照与兼容性

本阶段在阶段07实际视觉验收通过后执行，为已接受的几何增加可编辑PBR材质、四套日期/时间光照及五类实时材质兼容性样本。阶段07尚未注册通过时，统一入口返回4，不能据已生成的纹理配置宣称阶段08场景已完成。实际状态以 `STATUS.md` 和 `outputs/stage08_city_medium_acceptance.json` 为准。

2026-10-24最终检查：材质、米制UV、独立重开、实际烘焙、四种光照渲染和五类GLB回载/浏览器兼容性已执行通过，按明确近似范围交付。它是可继续编辑的材质与光照检查点，尚未达到整个城市最终照片写实质量。四图集中查看入口为 `work/previews/stage08/lighting_review.html`。

主材质库实际独立追加得到40个材质、45张图像。14类原创材质共126张1024/512/256px PNG，压缩文件合计约27.16MiB；另有3张512px设施图集和3张实际Blender烘焙图。1291份带UV网格完成检查，来源地理顶点不改变。576个水面使用水材质，水的IOR为1.333；27个实际使用的体育场座椅材质槽保留四种来源配色，避免通用材质替换丢失原色。

## 文件与链接依赖

- 主工程：`scenes/stage08_city_medium.blend`。
- 两个必须随附的源工程：`scenes/stage07_final.blend`、`scenes/stage07_city_medium.blend`。将三者保存在同一 `scenes` 目录。新场景链接既有几何；新UV副本应保持原XY/Z不变。链接网格在来源工程修改，或明确Make Local后修改。
- 材质库：`assets/materials/stage08/material_library.blend`，使用 File → Append → Material 追加；不是独立城市场景。
- 来源程序材质的实际Blender烘焙校准样本：`assets/materials/stage08/baked_brick.blend` 与 `assets/textures/stage08/bakes/brick_reference_*.png`，详见 `docs/stage08_bake.md`。它只证明一份来源砖材质完成真实烘焙，不把14类原创采样纹理统称为Blender烘焙结果。
- 原创纹理清单：`assets/materials/stage08/registry.json`；实际各级PNG位于 `assets/textures/stage08/<输入指纹>/`，生成配置 `config/stage08_materials.json`。交付必须保留清单所列PNG目录。
- 光照：`config/stage08_lighting.json`；构建、固定对比机位及渲染参数 `config/stage08.json`。
- 实际图：`work/previews/stage08/{clear_day,golden_hour,blue_hour,night}.png`，同一已配置机位、不同光照。
- 五个实际导出样本：`outputs/stage08/glb/{building,road,vegetation,water,landmark}.glb`。
- 检查与真实运行记录：`work/reports/stage08/`、`work/logs/stage08/`；最终SHA登记于 `outputs/stage08_city_medium.manifest.json`。

## 材质与数据含义

14类材质为沥青、混凝土、石材铺装、砖、灰泥、油漆、玻璃、裸露金属、屋顶、土壤、草、叶片、水和标线。它们使用固定种子生成的原创通用图像，不是逐栋拍摄取样，也不把研究照片作为贴图。纹理的真实米制重复尺寸见配置；近/中/远分别1024、512、256像素，降低分辨率不增加资料精度。

Base Color使用sRGB；法线和ORM使用Non-Color。法线为glTF/OpenGL切线空间+Y约定。ORM的R=1是未烘焙几何遮蔽的占位，G为粗糙度，B为金属度。玻璃和水使用介电材质，不能用金属度模拟玻璃；透射扩展不受支持时的外观差异必须说明。叶片使用MASK透明裁切和双面几何；它们仍是通用推断树种。微表面法线不改变原地形或建筑空间位置。

纹理清单保存文件SHA、尺寸、色彩空间和生成参数；110MiB配置预算表示压缩纹理文件/缓存字节，不等于GPU实际占用。GPU、显存及实时帧率必须依实际环境报告，不因浏览器成功运行就认定存在硬件GPU。

## 四套光照

晴朗白天、日落前暖光、蓝调时刻和夜景使用同一固定地理机位。太阳计算使用来源原点经纬度、带时区的America/Los_Angeles时间及UTM子午线收敛角，区分真北与网格北。系统主机时区不作为洛杉矶太阳时间。

`scripts/stage08_solar.py --check`实际重算保存配置，检查季节时差、夏令时折叠/不存在时间、太阳方位和欧拉旋转一致性。计算相符不是实测太阳或照度精度。天空、云量、曝光和人工光强是明确设计的视觉参数；不声称准确复现指定日期的真实天气或全城灯光开关状态。

## 运行与验收

集成后的统一入口使用 `./project run --stage 8 --region city --quality medium`；复核使用 `./project check --stage 8 --region city --quality medium`。仅支持city/medium；其他组合返回3“未实现”。也可直接调用：

```sh
.venv/bin/python scripts/stage08.py execute
.venv/bin/python scripts/stage08.py textures
.venv/bin/python scripts/stage08.py library
.venv/bin/python scripts/stage08.py register
.venv/bin/python scripts/stage08.py check
```

已登记且哈希一致的成果复用；有编辑或变化时停止，不静默覆盖。既有未注册工程保留，待实际检查与审查完成。缺少实际浏览器或目视证据返回4，真实失败或哈希冲突返回1，完整真实验收通过才返回0。

正式登记要求：

1. 阶段07验收清单与实际输入/成果哈希校验返回0。
2. 主文件实际保存后由另一Blender进程重开；`scene_check.json`绑定当前场景SHA，并检查米制、有限坐标、来源几何不变、UV、PBR节点、贴图色彩空间及依赖存在。
3. 四张配置尺寸的真实CPU Cycles最终PNG；`renders.json`绑定当前场景SHA、相机与光照方案。逐图实际打开后，`visual_inspection.json`记录 `accepted_with_documented_approximations`、`stage_gate_passed=true`、当前场景SHA、四图路径/SHA及 `actual_view_image_inspection=true`。脚本不自动生成视觉通过。
4. 五类GLB实际导出，再于该导出进程中新建的独立临时场景重新导入。`export_check.json`记录当前场景SHA、文件SHA、实际导出/导入、纹理缺失及有限坐标检查；这不冒充另起进程的GLB导入。登记工具还直接读取GLB二进制，验证嵌入图像和Base Color/Normal/ORM绑定，检查植被MASK及玻璃/水的介电关系。
5. 实际浏览器/WebGL加载当前五类样本，记录 `browser_check.json`、各样本SHA、控制台/页面错误和真实截图。该兼容性结果只适用于所测浏览器和样本；软件WebGL结果不能当作GPU实测。
6. 材质库由独立factory-startup Blender进程实际追加，检查图像已打包或路径存在，输出 `library_check.json`。纹理注册SHA和实际像素尺寸检查通过。
7. `scripts/stage08_bake.py`在阶段07通过后实际调用Blender烘焙来源程序砖材质的Base Color、切线Normal和Roughness，`bake_check.json`绑定来源场景/脚本及三张重载PNG、兼容材质库SHA。源程序材质保留；校准块不主张无缝重复、几何AO或全城所有程序材质均已烘焙。烘焙兼容库也实际追加检查。

这些GLB是材质兼容性样本。全市分块导出、交互查看器、自动LOD、流式加载和性能测试具有独立后续验收，不从本阶段样本推导为已完成。既有多年代几何、估算高度、外观盲区和场地接口近似继续保留。

## 小设施图集与数值修订

已实际使用512px共享饰面图集替换路灯、消防栓、垃圾桶和防撞柱的常用漆面/金属饰面；四个常量象限共用BaseColor/Normal/ORM三张PNG，UV留32px保护带。图集登记为assets/materials/stage08/atlas_registry.json，材质包含在主库，实际检查为atlas_check.json。常量饰面没有纹理细节频率，实时GLB使用LINEAR无mip及CLAMP，防止远处金属/油漆跨象限平均；大面积重复纹理仍使用正常mipmap。道路兼容样本另含真实映射点位的路灯实例，不改变地理相对位置。

水体UV采用主法向投影，并逐三角面减去整数个12m周期，保持共面分块纹理相位，避免极细源三角面的float32 UV坍缩；地理顶点不改变。雾体朝外法线已检查。真实投光灯选择最近24个已映射灯位并匹配既有6.6m灯头，42个灯头可发光；入口灯10个和亮窗为明确模拟。灯光日期是可复现的太阳可视化参考，不表示混合年代城市资料属于2025-09-21同日快照。

图集把四种饰面合并为一个共享PBR材质；与四套独立图像材质所需12张相比使用3张。原小设施曾使用常量材质，因此不声称图集比原零贴图方案更节省纹理内存。它主要合并材质分组；大面积米制重复贴图继续复用。原始程序砖烘焙与原创通用材质不是逐栋实测的材料取样。

## 最终图像的验证边界

四张正式图全部由同一已保存场景独立重开后执行CPU Cycles渲染：1280×960、48采样、4线程、固定种子20261021、间接光钳制3、关闭不可用的降噪。Blender采用AgX、Look=None；浏览器样本采用Three.js ACESFilmic、曝光1和RoomEnvironment，并不共用Blender的完整天空、雾和离线间接光。材质参数与贴图连接可核验，两个环境不承诺像素相同。

实际逐图观察：白天可检查基础颜色、玻璃和表面尺度；暖光改变受光方向与色温；蓝调保留冷环境及稳定亮窗；夜景保留入口照明，Records储藏翼没有被虚构成整面发光窗。暖光与夜景仍有明显48采样噪声，树冠为简化叶片模板，部分立面节奏重复。地面可见继承场地接口的深色边缝/楔形边缘，局部铺装坡面及基础仍为视觉近似；本阶段没有将这些现象判作已经修复。建筑高度、年代和未观测立面缺口沿用阶段07登记。上述缺口限制最终写实程度，不能从本阶段技术通过推导出全城最终视觉验收通过。

浏览器实际加载5/5样本、解码27个纹理，控制台/页面错误为0；Chromium使用SwiftShader软件WebGL2。透明叶片、水面介电参数、法线与嵌入贴图已检查。道路样本是较大的真实路网块，画廊缩放后路灯与纹理很小；画廊只证明相应加载与材质兼容，不证明全部道路近景细节或实时帧率。
