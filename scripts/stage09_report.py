"""Report only actual final browser, geometry and compression evidence."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,math,statistics
ROOT=Path(__file__).resolve().parents[1]
def read(path):return json.loads((ROOT/path).read_text())
def write(path,value):
 p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def percentile(values,p):
 values=sorted(values);return values[min(len(values)-1,int((len(values)-1)*p))] if values else None
browser=read('work/reports/stage09/browser_check.json');assert browser['status']=='passed','Do not report failed browser checks as accepted'
catalog=read('outputs/stage09/resources/manifest.json');baseline=read('work/reports/stage09/baseline_authoring.json');exported=read('work/reports/stage09/export.json');comparison=read('work/reports/stage09/indexing_comparison.json');spatial=read('work/reports/stage09/spatial_validation.json')
samples=browser['tour_samples'];times=[v for v in browser['tour_frame_times_ms'] if v>0];duration=samples[-1]['elapsed_s'];frames=samples[-1]['snapshot']['frame_count'];fps=frames/duration
native=browser['native_1080p_sample'];native_pass=native['fps']>=30 and native['frame_ms_p95']<=50
limits=['Actual test uses installed Chromium and explicit software WebGL2/SwiftShader on a4-core CPU quota. Hardware GPU and VRAM are unknown.',
'Default medium uses a1920x1080 CSS viewport and960x540 internal render target; it is not native1080p. Native1080p was separately sampled for6s in Historic Core, not certified for the entire tour.',
'Frame times are measured render-loop intervals, not physical display scanout or hardware GPU timing.',
'Geometry buffer bytes are actual CPU arrays; decoded texture RGBA/mipmap bytes are estimates and are not measured VRAM.',
'Three36s tour loops and explicit release were checked. This does not establish unlimited-duration or all-device leak freedom.',
'Existing mixed source dates, unverified heights, simplified façades/vegetation and site-interface limitations remain.',
'Close-up LODs omit some small detail at medium distance. Low/medium use simplified diffuse shading; high keeps PBR/normal/ORM/transmission and has no30FPS guarantee.',
'City overview omits most low-rise buildings and shows major roads as cartographic lines. Complete retained local building data are loaded in nearer LODs.']
steady=[]
for row in browser['steady_views']:
 s=row['snapshot'];r=s['resources'];steady.append({'view':row['view'],'seconds':row['measurement_seconds'],'fps':s['fps'],'frame_ms_p95':s['frame_ms_p95'],'draw_triangles':s['render']['triangles'],'draw_calls':s['render']['calls'],'cached_geometries':r['tracked_geometries'],'cached_materials':r['tracked_materials'],'cached_textures':r['texture_pool_entries'],'texture_dimensions':r.get('texture_dimensions',[]),'geometry_bytes':r['geometry_bytes'],'texture_bytes_estimated':r.get('decoded_texture_estimated_rgba_mip_bytes'),'js_heap_bytes':s['js_heap']['used'] if s['js_heap'] else None})
last=samples[-1]['snapshot'];loads=last['resources']['loads'];load_ms=[v['ms'] for v in loads]
report={'status':'actual_performance_measured','actual_measurement_completed':True,'created_at':datetime.now(ZoneInfo('Asia/Singapore')).isoformat(),'browser':browser['browser'],'rendering_backend':last['gpu_renderer'],'hardware_gpu_proven':False,'vram_bytes':None,
 'test':{'viewport':[1920,1080],'quality':'medium','internal_render_resolution':last['render_resolution'],'duration_s':duration,'cycles':3,'route_seconds':36,'frame_samples':len(times)},
 'tour':{'actual_frames':frames,'fps':fps,'frame_ms_mean':statistics.mean(times),'frame_ms_median':statistics.median(times),'frame_ms_p95':percentile(times,.95),'frame_ms_max':max(times),'peak_draw_triangles':max(s['snapshot']['render']['triangles'] for s in samples),'peak_cache_entries':max(s['snapshot']['resources']['cache_entries'] for s in samples),'peak_geometry_bytes':max(s['snapshot']['resources']['geometry_bytes'] for s in samples),'peak_js_heap_bytes':max(s['snapshot']['js_heap']['used'] for s in samples if s['snapshot']['js_heap']),
 'same_phase_cycle_ends':[{'cycle':i//6+1,'cache_entries':samples[i]['snapshot']['resources']['cache_entries'],'geometries':samples[i]['snapshot']['gpu_resources']['geometries'],'textures':samples[i]['snapshot']['gpu_resources']['textures']} for i in [5,11,17]]},
 'steady_views':steady,'initial_load_seconds':browser['initial_loaded_seconds'],'recent_asset_load_parse_ms':{'count':len(load_ms),'median':statistics.median(load_ms),'p95':percentile(load_ms,.95)},
 'native_1080p_sample':native,'target_30_fps_met':native_pass,'adjusted_medium_15fps_tour_met':fps>=15,'native1080p_30fps_tour_certified':False,
 'source_authoring':{k:baseline[k] for k in ['objects','mesh_objects','materials','textures','source_model_bytes','source_mesh_polygons_including_exclusive_lods']},
 'runtime':{'catalog_resources':len(catalog['resources']),'catalog_glb_bytes':sum(r['bytes'] for r in catalog['resources']),'vertices_before_indexing':sum(r.get('vertices_before_indexing',0) for r in catalog['resources']),'indexed_vertices':sum(r.get('indexed_vertices',0) for r in catalog['resources']),'building_attribute_records':exported['metadata_features']['buildings'],'raw_glb_bytes_before_meshopt':exported['raw_glb_bytes_before_compression'],'meshopt_bytes_for_same_base_exports':exported['compressed_glb_bytes']},
 'indexing_comparison':comparison,'resource_release':browser['release'],'limits':limits}
if (ROOT/'work/reports/stage09/object_census.json').exists():report['runtime_object_census']=read('work/reports/stage09/object_census.json')
if (ROOT/'work/reports/stage09/streaming_check.json').exists():report['distance_lod_and_automatic_eviction']=read('work/reports/stage09/streaming_check.json')
write('work/reports/stage09/performance.json',report)
rows=[]
for s in steady:rows.append(f"|{s['view']}|{s['fps']:.1f}|{s['frame_ms_p95']:.1f}|{s['draw_triangles']:,}|{s['draw_calls']}|{s['cached_geometries']}/{s['cached_materials']}/{s['cached_textures']}|")
medium='达到' if report['adjusted_medium_15fps_tour_met'] else '未达到';initial='达到（仅该6秒样本）' if native_pass else '未达到'
md=f'''# 阶段09实际性能报告

测试日期：{report['created_at']}。浏览器：{browser['browser']}。后端：{last['gpu_renderer']}。CPU有效配额4核、内存32GiB；GPU硬件与显存未知。

功能检查、十个地标实际加载、错误注入/重试、固定巡游与资源释放均有真实浏览器证据。初始“原生1080p约30FPS”目标在单独Historic Core样本中{initial}；完整原生1080p巡游没有达标认证。当前软件设备调整为1920×1080窗口、960×540内部渲染、中档150000三角形目标预算与简化漫反射材质，固定巡游15FPS的调整目标{medium}。调整原因是本机软件后端的实测开销，完整原始编辑工程与高档资源均保留。

## 固定巡游

路线36秒一轮，实际运行3轮、{duration:.2f}秒，共{frames}次实际渲染循环。平均{fps:.2f}FPS，帧时间平均{statistics.mean(times):.2f}ms、中位{statistics.median(times):.2f}ms、P95 {percentile(times,.95):.2f}ms。这些是浏览器循环统计，不是物理显示器刷新率。

## 固定机位稳态采样

每个机位在加载完成并预热后采样6秒；缓存列包括离屏保留对象，不能当作当前屏幕唯一对象数。绘制三角形在透射/阴影环境可能重复计次。

|机位|FPS|P95帧时间ms|实际绘制三角形|绘制调用|缓存网格/材质/纹理|
|---|---:|---:|---:|---:|---|
'''+ '\n'.join(rows)+f'''

原生1920×1080的Historic Core单独采样：{native['fps']:.2f}FPS，P95 {native['frame_ms_p95']:.2f}ms，实际绘制{native['render']['triangles']:,}三角形。高档只验证切换、解析与实际绘制，不保证高档帧率。

## 文件与组织

源工程实际读取到{baseline['objects']:,}对象、{baseline['materials']}材质、{baseline['textures']}被引用纹理。作者工程含互斥LOD、模块点与链接源，不能把这个总数直接除以某机位绘制调用来声称优化倍率。

最终清单共有{len(catalog['resources']):,}个资源，GLB合计{report['runtime']['catalog_glb_bytes']/1024**2:.2f}MiB；建筑属性保留{exported['metadata_features']['buildings']:,}份基础记录，另有独立精修建筑/地标属性。三档不一次加载整城最高细节。

同批基础GLB在量化/索引后、Meshopt前为{exported['raw_glb_bytes_before_compression']/1024**2:.2f}MiB，Meshopt后为{exported['compressed_glb_bytes']/1024**2:.2f}MiB，逐缓冲区实际解码比较通过。额外LOD和概览资源另计。索引前后City Hall样本的实际三角形与包围盒相同，固定相机浏览器图像的通道平均绝对差为{comparison['pixel_comparison']['mean_absolute_channel_difference']}；这只证明该样本和此次索引变换，不代替全部简化LOD的视觉检查。

初次页面至需求资源就绪耗时{browser['initial_loaded_seconds']:.2f}秒。最近{len(load_ms)}次成功资源加载/解析耗时中位{statistics.median(load_ms):.2f}ms、P95 {percentile(load_ms,.95):.2f}ms，包含本地HTTP与解析/图片准备，不等于全城加载时间。

## 缓存与释放

巡游峰值几何CPU缓冲{report['tour']['peak_geometry_bytes']/1024**2:.2f}MiB，JS堆峰值{report['tour']['peak_js_heap_bytes']/1024**2:.2f}MiB。GPU资源数量来自renderer.info；纹理RGBA+mipmap字节是估算，未测量VRAM。三轮相同阶段的缓存数量见原始JSON，没有把累计加载次数当成内存泄漏。

显式离开/释放检查已实际执行：缓存、跟踪网格、材质和共享纹理归零；JS堆不要求立即回收至零，没有强制GC来伪造下降。完整证据在work/reports/stage09/browser_check.json和performance.json。

## 验证范围

已运行的对象是当前本地构建与真实导出资源；不是占位演示或截图背景。当前仅测本浏览器/软件设备及上述时长。低/中档材质简化、远景省略低矮建筑、地形LOD误差、混合数据年份、近景接口和建筑资料缺口都保留；不以本报告认证所有设备、无限时长或最终照片写实质量。
'''
if 'runtime_object_census' in report:
 md+='\n## 实际对象数量补充\n\n另在相同中档窗口实际查询可见加载组，数量包含随后可能被逐对象视锥剔除的节点，不能与绘制调用等同。重复设施/树另以InstancedMesh绘制。\n\n|机位|可见加载组|组内GLB网格节点|组内材质槽合计|\n|---|---:|---:|---:|\n'
 for row in report['runtime_object_census']['views']:md+=f"|{row['view']}|{row['visible_loaded_groups']}|{row['visible_group_gltf_mesh_nodes_before_per_object_frustum_culling']}|{row['visible_group_declared_material_slots']}|\n"
if report.get('distance_lod_and_automatic_eviction',{}).get('status')=='passed':md+='\n另行实际滚轮缩放达到City Hall的LOD2、LOD1、LOD0；为避开中档预算限制，该项以高档独立地标层验证。离开区域14.5秒后，旧City Hall缓存自动释放，没有调用releaseAll或切换质量清空。该项与完整中档巡游为分开运行的检查。\n'
(ROOT/'docs/stage09_performance.md').write_text(md)
views=catalog['views'];route=[]
for ident in ['overview','historic_street','civic_street','landmark-griffith_observatory','landmark-us_bank_tower','overview']:
 if ident=='overview':r={'id':ident,**catalog['config']['city_overview']}
 elif ident.startswith('landmark-'):
  landmark=next(l for l in catalog['landmarks'] if 'landmark-'+l['id']==ident);p=landmark['origin_city_m'];r={'id':ident,'position_m':[p[0]+500,p[1]-650,p[2]+320],'target_m':[p[0],p[1],p[2]+70]}
 else:r=next(v for v in views if v['id']==ident)
 route.append(r)
write('config/stage09_tour.json',{'duration_seconds':36,'repetitions_for_test':3,'segment_seconds':7.2,'hold_fraction':.333,'ease':'smoothstep','travel_lift_m':'clamp(distance*.25,250,6000)*4*t*(1-t)','coordinate_axes':'source city east/north/up metres','waypoints':route})
print(json.dumps({'status':report['status'],'tour_fps':fps,'native1080p_fps':native['fps'],'resources':len(catalog['resources'])}),flush=True)
