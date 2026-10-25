"""Four actual CPU Cycles1080p lighting renders from the delivered master."""
from pathlib import Path
import sys,json,time,math
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from stage10_common import *
from stage10_scene import apply_view,apply_light
scene=bpy.context.scene;cfg=read('config/stage10.json');lighting=read('config/stage08_lighting.json')
# Adapt the city top bookmark to the final16:9 output aspect without cropping
# the administrative north/south extents. This changes the camera, not geography.
cfg['views']['city_overview']['ortho_scale_m']=180000
write('config/stage10.json',cfg);write('outputs/LA_Delivery/config/stage10.json',cfg)
for ident,view in cfg['views'].items():
 ob=bpy.data.objects.get('CHECK_'+ident)
 if not ob:continue
 ob.location=view['position_m'];ob.rotation_euler=(Vector(view['target_m'])-ob.location).to_track_quat('-Z','Y').to_euler()
 if 'ortho_scale_m' in view:ob.data.ortho_scale=view['ortho_scale_m']
view=dict(cfg['views']['historic_street'],detail_radius_m=65);terrain=read('data/processed/stage07_final/index.json')['terrain_active_lod'];tri=apply_view(scene,view,terrain);apply_light(scene,lighting,'clear_day');bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(DELIVERY/'LA_Master.blend'),compress=True,relative_remap=False)
checkpoint_sha=sha(DELIVERY/'LA_Master.blend');rows=[]
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.use_denoising=False;scene.cycles.max_bounces=4;scene.cycles.sample_clamp_indirect=3;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100
for name in cfg['lights']:
 started=time.perf_counter();apply_light(scene,lighting,name);file=DELIVERY/'previews/native_lighting'/(name+'.png');file.parent.mkdir(parents=True,exist_ok=True);scene.render.filepath=str(file);bpy.ops.render.render(write_still=True)
 rows.append({'light':name,'path':str(file.relative_to(DELIVERY)),'sha256':sha(file),'width':1920,'height':1080,'samples':16,'engine':'CPU Cycles','actual_render':True,'seconds':time.perf_counter()-started,'local_datetime':lighting['presets'][name]['solar']['local_datetime'],'camera':view,'visible_triangles_including_instances':tri});write('work/reports/stage10/native_lighting.in_progress.json',{'status':'in_progress','images':rows});print('NATIVE1080P_ACTUAL_RENDER',name,flush=True)
write('work/reports/stage10/native_lighting.json',{'status':'actual_four_cpu_renders_completed','master_sha256':checkpoint_sha,'lights_config_sha256':sha(ROOT/'config/stage08_lighting.json'),'images':rows,'color_management':'AgX; source exposure presets; no unsupported denoising','no_fog_hull':'Original local atmosphere hull disabled for geographic camera consistency; no city geometry changed for framing.'})
