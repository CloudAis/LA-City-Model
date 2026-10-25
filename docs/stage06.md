# 第六阶段：独立地标、近似精修与整合

工程`/workspace/Base`。本阶段按用户第六部分覆盖原先将地标放在第八阶段的规划。十个目标均已建立具有专项建筑几何的原创参数化资产，逐项标记为**近似完成**；没有把它们计作逐处核实的写实精修完成。

## 可查看成果

- 城市检查点：`scenes/stage06_city_medium.blend`，包含原完整城市和本阶段独立地标；米制、原始真实地理距离、全部本地可编辑。
- 体量检查点：`scenes/stage06_massing.blend`；先建立体量，侧视发现Wilshire窄带问题后补正，再以官网修正天文台顶部。初次未验收体量保存在`work/history/stage06_initial_massing_before_wilshire_side_correction`。
- 十个独立资产：`assets/landmarks/stage06/<id>.blend`；各有near/mid/far集合，参数和来源JSON文本。对象/材质有语义命名，部分硬边体块保留Bevel修改器。
- 三十个GLB：`outputs/stage06/glb/<id>/{near,mid,far}.glb`。实际导出、在新Blender进程中重新导入；可编辑作者版本与烘焙实时版本分开。程序噪声微表面没有烘成实物纹理，GLB采用可导出的PBR颜色/粗糙度。
- 每栋正面、侧面、俯视和环境图：`work/previews/stage06/<id>/`，1200×900、真实CPU Cycles渲染；另有带日期/许可的参考对比，**不同相机，非摄影测量比对**。
- 十个真实邻域工程：`scenes/stage06_context_<id>.blend`。邻域半径430m或650m，按同一地理矩阵转到资产局部坐标；普通建筑/道路来自已有真实资料，同时加入范围内其他精修地标。边界是离线提取窗，不代表运行时加载。
- 逐栋资料卡和差异：`docs/landmarks/<id>.md`、`data/processed/stage06/cards/<id>.json`。完整来源/照片署名/许可/采集年代说明在`source_registry.json`；不能把网页日期当作城市外观年代。

## 资料与几何取舍

U.S. Bank Tower以物业公布1018国际英尺作为舍入顶部参考，保留来源阶梯体量，增加石材窗格和环形冠顶。Wilshire Grand采用工程师1100英尺含针塔总高，联合三个73层分部恢复塔身厚度；冠顶根据照片与次级928英尺屋顶参考插值。OSM245m、255.5m和不同屋顶定义仍有冲突，未伪称已获施工剖面。

市政厅保留低层庭院、来源塔楼分层、观察层柱列、金字塔顶和入口拱。音乐厅使用11片不同朝向的采样曲面与板缝；原Gehry CATIA曲面与6000余块钢板的逐片拓扑并未取得。The Broad有连续斜格栅、凹入眼窗、玻璃底层和入口角；屋顶、独特GFRC孔型和扩建工地仍有缺口。

联合车站有分区红瓦屋顶、西立面拱窗、钟塔和推断庭院；后方观察不足。天文台官网尺寸为墙到墙236×176英尺，中央/两侧穹顶顶部距前草坪77/55英尺；选用的来源平面与公布包络接近，未缩放/移动真实足迹去凑尺寸。 dome曲率、铜饰、浮雕和地下扩建未逐处复刻。

Hollywood Sign九个字母使用独立OSM线段的位置和朝向，自制带孔字形和钢架；支撑截面、锚固、字形小曲线仍推断。Dodger Stadium有NNE外场开口、彩色层级看台、水平波形罩棚、六角计分牌和灯塔。Coliseum有东柱廊/火炬、椭圆看台和2019后南侧俱乐部楼。两座体育场的座位/通道数量、精确结构剖面、场地标高仍为资料指导估计；标准球场尺寸是配置值，不冒充现场测量。

## 地理、地形和代理替换

13个普通建筑来源代理由稳定ID替换；作者与简化块中的对应FACE building_index均移除，属于这些建筑的GN门窗/屋顶模块POINT也移除。邻居三角形坐标逐项比较保持完全相同。独立重开后，旧代理面/模块点残留为0。十个地标的局部原点、矩阵、方向和45组相对距离另有报告；计算误差不等于OSM/县数据的测绘精度。

17块地形建立局部版本。山区从已取得的10m裸地DEM采样细化，Downtown新增5m采样点；不是获得更高原始精度。保留原有道路切孔，三角形平面面积数值差最大不足0.01m²；分块边界高程数值差约4.6e-7m，原始DEM自身精度另论。坡地、体育场与城市建筑的局部整平有明确记录，最大与旧粗网格的差异约53.45m同时包含粗网格误差和局部修整，**不能称为实测土方量**。全部原DEM及阶段03/04底座保留。

Sign下方的NLCD水面类别小岛与授权干燥山坡参考冲突，显示改为推断干坡，原类别在`source_m`保留；这不是新增现时测绘判读，也未增删真实水体几何。具体证据见surface_conflict_review.json。

场地平台/台阶/基础与材料均有推断；没有得到工程标高、无障碍设计或逐块真实铺装资料。基础可能深于地表，建筑门窗未构建真实室内。全部场景并非统一日期的完整城市快照。

## 执行和复现

```bash
cd /workspace/Base
./project env
./project check --stage 6 --region city --quality medium
./project run --stage 6 --region city --quality medium
```

最后两条对已验收的相同输入执行内容哈希验证；不会重写用户模型。尚未验证的区域/质量返回3。完整冷联网获取、不同硬件性能、实时浏览帧率未验证。当前全部离线渲染使用4线程CPU；GPU和显存未知。

本地重建顺序为stage06_research.py缓存校验、stage06_data.py、stage06_geometry.py --massing、Blender massing-build/massing-check、实际查看体量图；然后stage06_geometry.py、assets-build、逐资产asset-check-render；stage06_context.py、contexts-build/context-render、integrate/main-check、glb-check；最后stage06_reports.py、实际逐图审阅、stage06.register。独立Blender进程保存、关闭和重开是必要步骤。未登记的模型不会被统一入口静默覆盖；新输入应先冻结旧成果，按受影响地标/区域重建。`./project export`仍返回未实现，30个个体GLB是本阶段实际产物，不是全市分块导出功能。

实际命令/失败及修正保留在`work/logs/stage06`、`work/reports/stage06`。物理磁盘从9.6GiB余量预算增加约2.8GiB，最低余量设为4GiB；全市作者场景仍需约9–12GiB内存，不能以默认可见三角形预算冒充全场景常驻RAM或FPS结果。运行时自动LOD和流送留待第九阶段。

用户已追加授权：本阶段验收和冻结后自动进入第七阶段，按PROJECT_SPEC中的Historic Core与Civic Center近景精修执行；不自动推进第八阶段。
