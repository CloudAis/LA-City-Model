import statistics
from datetime import datetime
from zoneinfo import ZoneInfo
from stage10_common import *
b=read('work/reports/stage10/browser_check.json');assert b['status']=='passed'
samples=b['tour_samples'];times=sorted(t for t in b['tour_frame_times_ms'] if t>0);duration=samples[-1]['elapsed_s'];frames=samples[-1]['snapshot']['frame_count'];fps=frames/duration;native=b['native_1080p_sample'];catalog=read('outputs/LA_Delivery/tiles/manifest.json')
steady=[{'view':r['view'],'fps':r['snapshot']['fps'],'p95_ms':r['snapshot']['frame_ms_p95'],'triangles':r['snapshot']['render']['triangles'],'calls':r['snapshot']['render']['calls'],'geometry_bytes':r['snapshot']['resources']['geometry_bytes'],'textures':r['snapshot']['resources']['texture_dimensions']} for r in b['steady_views']]
report={'status':'actual_measurement_completed','created_at':datetime.now(ZoneInfo('Asia/Singapore')).isoformat(),'browser':b['browser'],'backend':b['actual_rendering_backend'],'quality':'medium','viewport':[1920,1080],'internal_render_resolution':[960,540],'test_seconds':duration,'route_cycles':3,'route_cycle_seconds':36,'tour_fps':fps,'frames':frames,'mean_frame_ms':statistics.mean(times),'p95_frame_ms':times[int((len(times)-1)*.95)],'max_frame_ms':max(times),'native1080p_street_fps':native['fps'],'native1080p_initial30fps_target_passed':False,'adjusted_mean_tour15fps_target_passed':fps>=15,'stable30fps_certified':False,'steady_views':steady,'peak_geometry_bytes':max(s['snapshot']['resources']['geometry_bytes'] for s in samples),'peak_js_heap_bytes':max(s['snapshot']['js_heap']['used'] for s in samples if s['snapshot']['js_heap']),'vram_measured_bytes':None,'initial_loaded_seconds':b['initial_loaded_seconds'],'resource_release_passed':b['release']['after']['resources']['tracked_geometries']==0 and b['release']['after']['resources']['texture_pool_entries']==0,'final_catalog_sha256':sha(DELIVERY/'tiles/manifest.json'),'final_build_fingerprint':b['viewer_build_fingerprint'],'all_browser_checks':len(b['checks']),'limits':['Software WebGL2 on4effectiveCPUcores and32GiB; no hardwareGPU/VRAM telemetry.','FPS is measured render-loop timing; frame capture and encoded video output rates are separate.','Medium uses960×540 internal pixels at1080p CSS window. Native1080p was sampled separately for6s, not full-tour certified.','Source overview terrain is an additional71181 triangles outside local-detail target; this prevents floating contextual landmarks at added draw cost.','High mode:600k local target,PBRmaps retained,shadows disabled,opaque glass compatibility. OriginalGLB and native transmission retained.','Only3tour cycles/thisbrowser tested; release checks do not prove unlimited-duration or every-device leak freedom.']}
write('work/reports/stage10/performance.json',report)
rows='\n'.join(f"|{r['view']}|{r['fps']:.2f}|{r['p95_ms']:.2f}|{r['triangles']:,}|{r['calls']}|" for r in steady)
md=f'''# 最终性能实测

{report['created_at']}；Chromium{b['browser']}，{b['actual_rendering_backend']}。有效CPU4核、内存32GiB；显卡与显存无法可靠测量。当前用户允许降低云环境帧率目标，沿用软件中档巡游平均15FPS目标；本次实际{'达到' if fps>=15 else '未达到'}，不要求原生1080p稳定30FPS。

固定1920×1080窗口、中档、内部960×540、36秒路线重复3轮，实际{duration:.2f}秒/{frames}帧，平均{fps:.2f}FPS，帧时间平均{report['mean_frame_ms']:.2f}ms、P95 {report['p95_frame_ms']:.2f}ms、最大{report['max_frame_ms']:.2f}ms。复杂街景低于巡游平均，不能写成稳定30FPS。

|固定机位（预热后6秒）|FPS|P95帧时间ms|绘制三角形|调用|
|---|---:|---:|---:|---:|
{rows}

原生1920×1080 HistoricCore单独6秒：{native['fps']:.2f}FPS。初始原生1080p30FPS未通过，未认证完整原生1080p巡游。云端优先低档，街景优先降低分辨率；高档用于静态检查和有余量的设备，未保证高档实时帧率。

首次需求资源加载就绪{b['initial_loaded_seconds']:.2f}秒。三轮峰值CPU几何缓冲{report['peak_geometry_bytes']/1024**2:.2f}MiB、JS堆{report['peak_js_heap_bytes']/1024**2:.2f}MiB。纹理RGBA/mipmap字节为估算，显存未知。缓存、网格、材质和纹理实际释放归零；同阶段缓存数量没有持续无界增长，仍不认证无限时长。

最终查看器修复了道路/细节预算压过地面的问题，增加真实来源的远景地形回退并对局部分块作显示掩码。它增加约71181个三角形与着色开销；此次平均帧率低于阶段09约30.49FPS的旧测量，换取更完整的地理环境显示。局部150k目标不是全部绘制的硬上限；实际绘制数见表。

低/中使用简化漫反射和256/512px纹理。高档局部目标600k、512px、PBR法线/ORM、阴影关闭、玻璃为不透射反射兼容版。物理透射和完整编辑材质仍在原生工程与GLB。完整原始最高LOD保留，细节是否常驻仍受档位预算影响。

展示PNG来自实际1920×1080模型帧；截图为完成渲染后暂停重复刷新再截取，不能据其耗时推算FPS。24秒视频为实际360帧视口序列、1280×720、输出15FPS，也不是实时帧率证明。四张原生CPU图为1920×1080/16采样，包含噪声。

实际完整证据：metadata/acceptance/browser_check.json、performance.json；开发工作区原始日志在work/logs/stage10/。本次只测该浏览器/软件设备，Windows、macOS和硬件GPU未实测。
'''
(DELIVERY/'docs/PERFORMANCE.md').write_text(md);print('FINAL_ACTUAL_PERFORMANCE',round(fps,2),'native',round(native['fps'],2),flush=True)
