"""Texture-backed PBR, solar presets and saved stage08 authoring checkpoint.

Runs only after the coordinator has accepted07. Geometry stays in its real city
coordinates; local copies add UVs and material slots, not new survey precision.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage06_blender import *
cfg8=read('config/stage08.json')
lights_cfg=read('config/stage08_lighting.json')
scene=bpy.context.scene

def sha(path):
 with open(path,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def classify(name):
 n=name.lower()
 if any(w in n for w in ['ballast','sleeper']):return 'soil'
 if 'runway' in n:return 'asphalt'
 if any(w in n for w in ['dark_metal','pole','frame','paint']):return 'paint'
 for words,key in [(['glass','glazing'],'glass'),(['asphalt','road_surface','road_asphalt'],'asphalt'),(['marking','yellow_line','white_line'],'road_marking'),(['brick'],'brick'),(['terracotta','stucco','paint','white'],'stucco'),(['metal','silver','rail','iron','steel'],'metal'),(['leaf','leaves'],'leaf'),(['grass','park','forest','vegetation','shrub'],'grass'),(['water','ocean','river','lake','reservoir'],'water'),(['roof'],'roof'),(['soil','earth','bare','sand','beach','dry'],'soil'),(['paving','limestone','sidewalk','stone'],'paving_stone')]:
  if any(w in n for w in words):return key
 return 'concrete'

def registry():return read('assets/materials/stage08/registry.json')['materials']
def linear_color(c):return tuple(x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in c[:3])+(1,)

def materials():
 reg=registry();result={};images={}
 for key,r in reg.items():
  for textured in [False,True]:
   m=bpy.data.materials.new('S8_'+key+('_PBR_maps' if textured else '_PBR_far'));m.use_nodes=True;m['stage08_material']=key;m['texture_backed']=textured;m['physical_tile_metres']=r['tile_size_m'];m['normal_convention']='OpenGL +Y tangent space';n=m.node_tree.nodes;l=m.node_tree.links;b=n.get('Principled BSDF');b.inputs['Base Color'].default_value=linear_color(r['base_color_srgb']);b.inputs['Roughness'].default_value=r['roughness'];b.inputs['Metallic'].default_value=r['metallic'];b.inputs['IOR'].default_value=r.get('ior',1.5)
   if key=='glass':b.inputs['Transmission Weight'].default_value=r.get('transmission',.35)
   if key=='water':b.inputs['Transmission Weight'].default_value=.18;b.inputs['IOR'].default_value=1.333
   if textured:
    uv=n.new('ShaderNodeUVMap');uv.uv_map='PBR_Meters';mapping=n.new('ShaderNodeMapping');tile=r['tile_size_m'];tile=tile if isinstance(tile,list) else [tile,tile];mapping.inputs['Scale'].default_value=(1,1,1) if key=='leaf' else (1/tile[0],1/tile[1],1);l.new(uv.outputs['UV'],mapping.inputs[0]);maps=r['maps'][cfg8['texture_quality']]
    for role in ['base_color','normal','orm']:
     file=maps[role];cache=(file,role=='base_color')
     if cache not in images:
      img=bpy.data.images.load(str(root/file),check_existing=False);img.colorspace_settings.name='sRGB' if role=='base_color' else 'Non-Color';images[cache]=img
     tex=n.new('ShaderNodeTexImage');tex.image=images[cache];tex.extension='REPEAT';tex.interpolation='Linear';tex.label=role;l.new(mapping.outputs[0],tex.inputs[0])
     if role=='base_color':
      l.new(tex.outputs['Color'],b.inputs['Base Color'])
      if key=='leaf':
       clip=n.new('ShaderNodeMath');clip.operation='GREATER_THAN';clip.inputs[1].default_value=r.get('alpha_cutoff',.4);l.new(tex.outputs['Alpha'],clip.inputs[0]);l.new(clip.outputs[0],b.inputs['Alpha']);m.use_backface_culling=False
     elif role=='normal':
      normal=n.new('ShaderNodeNormalMap');normal.space='TANGENT';normal.uv_map='PBR_Meters';normal.inputs['Strength'].default_value=1;l.new(tex.outputs['Color'],normal.inputs['Color']);l.new(normal.outputs[0],b.inputs['Normal'])
     else:
      split=n.new('ShaderNodeSeparateColor');split.mode='RGB';l.new(tex.outputs['Color'],split.inputs[0]);l.new(split.outputs['Green'],b.inputs['Roughness']);l.new(split.outputs['Blue'],b.inputs['Metallic'])
   result[(key,textured)]=m
 for key,parent,color,rough,trans in [('paint_dark','paint',[.075,.085,.095],.55,0),('paint_void','paint',[.018,.025,.030],.85,0),('paving_red','paving_stone',[.48,.18,.11],.65,0),('glass_office','glass',[.20,.32,.38],.18,.30),('glass_retail','glass',[.32,.43,.46],.09,.72),('marking_yellow','road_marking',[1,.72,.035],.65,0),('copper_patina','paint',[.30,.44,.35],.62,0)]:
  m=result[(parent,False)].copy();m.name='S8_'+key+'_authored_variant';m['variant_evidence']='authored material-type/tint distinction, not a measured optical sample';b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=linear_color(color);b.inputs['Roughness'].default_value=rough;b.inputs['Transmission Weight'].default_value=trans;result[(key,False)]=m
 for key,color in cfg8['legacy_seat_colors_linear'].items():
  m=result[('paint',False)].copy();m.name='S8_'+key+'_authored_variant';m['variant_evidence']='preserved source06 model palette, not measured paint reflectance';m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=color;result[(key,False)]=m
 return result

def metre_uv(data):
 """Dominant-normal triangle projection in metres, with consistent handedness."""
 v=np.empty(len(data.vertices)*3,np.float32);data.vertices.foreach_get('co',v);v=v.reshape(-1,3);ids=np.empty(len(data.loops),np.int32);data.loops.foreach_get('vertex_index',ids);p=v[ids].reshape(-1,3,3);normal=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);axis=np.argmax(abs(normal),axis=1);uv=np.empty((len(p),3,2),np.float32)
 for ax in [0,1,2]:
  take=axis==ax;q=p[take];sign=np.where(normal[take,ax]<0,-1.,1.)[:,None]
  if ax==0:uv[take,:,0]=q[:,:,1]*sign;uv[take,:,1]=q[:,:,2]
  elif ax==1:uv[take,:,0]=-q[:,:,0]*sign;uv[take,:,1]=q[:,:,2]
  else:uv[take,:,0]=q[:,:,0]*sign;uv[take,:,1]=q[:,:,1]
 layer=data.uv_layers.get('PBR_Meters') or data.uv_layers.new(name='PBR_Meters');layer.data.foreach_set('uv',uv.ravel());data.uv_layers.active=layer
 return {'vertex_sha256':hashlib.sha256(v.tobytes()).hexdigest(),'vertex_count':len(v),'triangles':len(p),'uv_finite':bool(np.isfinite(uv).all()),'projection':'dominant face normal; metres; consistent tangent handedness; discontinuities at hard corners are intentional UV seams'}

def water_uv(data,origin):
 """Preserve Repeat phase while keeping skinny clipped triangles precise."""
 v=np.empty(len(data.vertices)*3,np.float32);data.vertices.foreach_get('co',v);v=v.reshape(-1,3);ids=np.empty(len(data.loops),np.int32);data.loops.foreach_get('vertex_index',ids);p=v[ids].astype(np.float64).reshape(-1,3,3)+np.array(origin,np.float64);normal=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);axis=np.argmax(abs(normal),axis=1);xy=np.empty((len(p),3,2),np.float64)
 for ax in [0,1,2]:
  take=axis==ax;q=p[take];sign=np.where(normal[take,ax]<0,-1.,1.)[:,None]
  if ax==0:xy[take,:,0]=q[:,:,1]*sign;xy[take,:,1]=q[:,:,2]
  elif ax==1:xy[take,:,0]=-q[:,:,0]*sign;xy[take,:,1]=q[:,:,2]
  else:xy[take,:,0]=q[:,:,0]*sign;xy[take,:,1]=q[:,:,1]
 pairs=np.array([[0,1],[1,2],[2,0]]);delta=xy[:,pairs[:,1]]-xy[:,pairs[:,0]];short=np.argmin(np.sum(delta*delta,axis=2),axis=1);edge=pairs[short];anchor=(xy[np.arange(len(xy)),edge[:,0]]+xy[np.arange(len(xy)),edge[:,1]])*.5;period=np.floor(anchor/12)*12;uv=(xy-period[:,None,:]).astype(np.float32);data.uv_layers['PBR_Meters'].data.foreach_set('uv',uv.ravel());return 'Dominant-plane projection; per-triangle integer12m translation anchored at shortest edge, shared Repeat phase on coplanar pieces'

def align_night_assets(focus):
 points=[]
 for ob in scene.objects:
  if ob.type!='MESH' or ob.get('stage07_kind')!='street_lamp' or ob.get('stage07_instances') is None:continue
  rot=ob.data.attributes['module_rotation'];fid=ob.data.attributes.get('building_index')
  for j,v in enumerate(ob.data.vertices):
   p=ob.matrix_world@v.co;d=np.linalg.norm(np.array(p[:2])-focus)
   if d<250:points.append((d,p.copy(),rot.data[j].vector.z,ob.name,j,fid.data[j].value if fid else None))
 points.sort(key=lambda r:r[0]);records=[]
 for j,(_,p,angle,field,index,fid) in enumerate(points[:cfg8['max_real_road_lights']]):
  ob=bpy.data.objects.get('S8_road_light_'+str(j))
  if not ob:continue
  ob.location=p+Vector((1.2*math.cos(angle),1.2*math.sin(angle),6.49));records.append({'light':ob.name,'source_point_field':field,'point_index':index,'source_fid':fid,'position_city_m':list(ob.location),'fixture_local_emitter_m':[1.2,0,6.49],'orientation_evidence':'same inferred source07 module rotation as visible fixture'})
 proto=bpy.data.objects.get('LA07_Module_street_lamp');emitter=bpy.data.materials.get('S8_streetlamp_emitter')
 if proto:
  lens_slot=int(proto.get('stage08_atlas_lens_slot',7))
  if not emitter:
   emitter=proto.material_slots[lens_slot].material.copy();emitter.name='S8_streetlamp_emitter';emitter['stage08_night_emission']=True;emitter['night_emission_strength']=4.;b=emitter.node_tree.nodes.get('Principled BSDF');b.inputs['Emission Color'].default_value=(1,.75,.45,1);b.inputs['Emission Strength'].default_value=0
  proto.material_slots[lens_slot].link='OBJECT';proto.material_slots[lens_slot].material=emitter
 bark=bpy.data.materials.get('S8_bark_generic_brown')
 if not bark:
  bark=bpy.data.materials['S8_paint_dark_authored_variant'].copy();bark.name='S8_bark_generic_brown';bark['variant_evidence']='rough brown bark proxy, unmeasured species';b=bark.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=linear_color([.22,.12,.065]);b.inputs['Roughness'].default_value=.90
 for name in ['LA07_Module_tree_broadleaf','S8_Export_tree_realised']:
  ob=bpy.data.objects.get(name)
  if ob:ob.material_slots[5].link='OBJECT';ob.material_slots[5].material=bark
 path=root/'work/reports/stage08/night_distribution.json'
 if path.exists():
  report=json.loads(path.read_text());report.update(actual_road_light_positions=records,real_road_lights=len(records),all_mapped_lamp_heads_emissive=True,point_lights_use_nearest_source_fixtures=True);write('work/reports/stage08/night_distribution.json',report)

def lamp(name,kind,position,energy,color,radius=.6,target=None):
 d=bpy.data.lights.new(name,kind);d.energy=energy;d.color=color
 if kind=='POINT':d.shadow_soft_size=radius
 o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=position;o['stage08_night_light']=True;o['night_energy_w']=energy;o['evidence']='authored plausible illumination; not a lighting survey'
 if kind=='AREA':d.shape='DISK';d.size=radius*2
 if target is not None:o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
 return o

def night_setup(mats,focus):
 # Real openings use deterministic whole-window groups, never independently lit
 # triangle halves. Transparent interiors are not invented behind each window.
 glow={};window_stats=[]
 for name,color,strength in [('warm',(1,.62,.28,1),2.5),('cool',(.55,.72,1,1),1.8)]:
  m=mats[('glass',False)].copy();m.name='S8_window_'+name;m['stage08_night_emission']=True;m['night_emission_strength']=strength;b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Transmission Weight'].default_value=0;b.inputs['Emission Color'].default_value=color;b.inputs['Emission Strength'].default_value=0;glow[name]=m
 for ob in list(scene.objects):
  if ob.type!='MESH' or ob.get('r2_component')!='glazing':continue
  base=ob.material_slots[ob.data.polygons[0].material_index].material if len(ob.data.polygons) else mats[('glass',False)]
  data=ob.data.copy();ob.data=data;data.materials.clear()
  for m in [base,glow['warm'],glow['cool']]:data.materials.append(m)
  for slot in ob.material_slots:slot.link='DATA'
  v=np.empty(len(data.vertices)*3,np.float32);data.vertices.foreach_get('co',v);v=v.reshape(-1,3);ids=np.empty(len(data.loops),np.int32);data.loops.foreach_get('vertex_index',ids);f=ids.reshape(-1,3);centre=v[f].mean(axis=1);# Face pairs from the actual glazing quads share one ID.
  groups=np.full(len(v),len(f),np.int32);np.minimum.at(groups,f.ravel(),np.repeat(np.arange(len(f)),3));pair=groups[f].min(axis=1);seed=int(ob.get('r2_building',0))+cfg8['seed'];values=np.mod(np.sin((pair+seed)*12.9898)*43758.5453,1);mi=np.where(values<cfg8['night_window_fraction'],1+(values<cfg8['night_window_fraction']*.25),0).astype(np.int32);data.polygons.foreach_set('material_index',mi);window_stats.append({'object':ob.name,'faces':len(f),'emissive_faces':int((mi>0).sum()),'distribution':'stable source building ID and connected opening vertex group; simulated occupancy'})
 from mathutils import Vector
 road=[]
 for ob in scene.objects:
  if ob.type=='MESH' and ob.get('stage07_kind')=='street_lamp' and ob.get('stage07_instances') is not None:
   for v in ob.data.vertices:
    p=ob.location+v.co
    if (Vector((p.x,p.y))-Vector(focus)).length<250:road.append(tuple(p))
 for j,p in enumerate(road[:cfg8['max_real_road_lights']]):lamp('S8_road_light_'+str(j),'POINT',(p[0],p[1],p[2]+7.0),220,(1,.75,.43),.4)
 ix=read('data/processed/stage07_final/index.json');doors=[]
 for b in ix['buildings']:
  for d in b['doors']:
   if np.linalg.norm(np.array(d['xy_city_m'])-focus)<180:doors.append(d)
 for j,d in enumerate(doors[:cfg8['max_real_entrance_lights']]):
  p=np.array(d['xy_city_m'])+np.array(d['outward_xy'])*.4;lamp('S8_entrance_'+str(j),'POINT',[*p,d['floor_navd88_m']+2.4],35,(1,.67,.35),.3)
 for ob in scene.objects:
  if ob.type!='MESH' or ob.get('r2_component') not in ['blade','marquee']:continue
  for slot in ob.material_slots:
   if not slot.material:continue
   m=slot.material.copy();m.name='S8_sign_'+ob.name;m['stage08_night_emission']=True;m['night_emission_strength']=.7;b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Emission Color'].default_value=(1,.23,.045,1);slot.link='OBJECT';slot.material=m
 # Source traffic signal prototypes retain their actual inferred placement. Add
 # emissive lenses, rather than hundreds of shadow-casting traffic lamps.
 signal_mats={}
 for j in [2,3,4]:
  m=mats[('paint_dark',False)].copy();m.name='S8_signal_'+['red','amber','green'][j-2];m['stage08_night_emission']=True;m['night_emission_strength']=3.0 if j==2 else .08;b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Emission Color'].default_value=[(1,.025,.008,1),(1,.42,.01,1),(.01,1,.08,1)][j-2];b.inputs['Base Color'].default_value=linear_color([[.35,.01,.005],[.13,.07,.005],[.005,.10,.015]][j-2]);signal_mats[j]=m
 for ob in scene.objects:
  if ob.type!='MESH' or 'signal' not in ob.name.lower():continue
  for j,slot in enumerate(ob.material_slots):
   if j in signal_mats:slot.link='OBJECT';slot.material=signal_mats[j]
 for o in scene.objects:
  if o.get('stable_id')=='landmark:city_hall':
   c=np.array(o.location)
   for j,off in enumerate([[35,-45,4],[-30,-40,4]]):lamp('S8_city_hall_accent_'+str(j),'AREA',c+off,600,(1,.72,.44),4,c+[0,0,40])
 write('work/reports/stage08/night_distribution.json',{'seed':cfg8['seed'],'window_fraction_requested':cfg8['night_window_fraction'],'actual_window_meshes':window_stats,'real_road_lights':min(len(road),cfg8['max_real_road_lights']),'real_entrance_lights':min(len(doors),cfg8['max_real_entrance_lights']),'not_observed_occupancy':True,'emission_vs_lights_separate':True})
 align_night_assets(focus)

def preset(name):
 p=lights_cfg['presets'][name];s=p['solar'];sun=next(o for o in scene.objects if o.type=='LIGHT' and o.data.type=='SUN');sun.rotation_euler=[math.radians(a) for a in p['sun_rotation_euler_xyz_degrees']];sun.data.energy=p['sun_energy'];sun.data.color=p['sun_color_linear_rgb'];sun.data.angle=math.radians(p['sun_angle_deg']);world=scene.world;world.use_nodes=True;n=world.node_tree.nodes;l=world.node_tree.links;bg=n.get('Background');sky=n.get('S8_solar_sky')
 for other in scene.objects:
  if other.type=='LIGHT' and other!=sun and not other.get('stage08_night_light'):other.data.energy=0
 if p['world_model']=='nishita':
  if not sky:sky=n.new('ShaderNodeTexSky');sky.name='S8_solar_sky';sky.sky_type='NISHITA';sky.sun_disc=False
  sky.sun_elevation=math.radians(max(.1,s['altitude_geometric_deg']));direction=p['sun_direction_towards_sun_grid_xyz'];sky.sun_rotation=math.atan2(direction[1],direction[0]);l.new(sky.outputs[0],bg.inputs[0])
 else:
  for link in list(bg.inputs[0].links):l.remove(link)
  c=p.get('world_color_linear_rgb',[.04,.07,.16]);bg.inputs[0].default_value=(*c[:3],1)
 bg.inputs[1].default_value=p['world_strength'];scene.view_settings.exposure=p['exposure_stops'];on=p['artificial_lights_enabled']
 for o in scene.objects:
  if o.get('stage08_night_light'):o.data.energy=o['night_energy_w']*(.65 if name=='blue_hour' else 1) if on else 0
 for m in bpy.data.materials:
  if m.get('stage08_night_emission') and m.use_nodes:m.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=m['night_emission_strength']*(.5 if name=='blue_hour' else 1) if on else 0
 scene['stage08_active_lighting_preset']=name;scene['stage08_local_time']=s['local_datetime'];scene['stage08_solar_grid_azimuth_deg']=p['azimuth_grid_north_clockwise_deg'];scene['stage08_solar_altitude_deg']=s['altitude_geometric_deg']

def atmosphere(focus):
 # A weak finite volume provides depth only; no claim of a measured aerosol
 # profile. The same density is shared by all four lighting presets.
 m=bpy.data.materials.new('S8_authored_atmosphere');m.use_nodes=True;n=m.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputMaterial');v=n.new('ShaderNodeVolumeScatter');v.inputs['Color'].default_value=(.72,.79,.85,1);v.inputs['Density'].default_value=cfg8['atmosphere_density_per_m'];v.inputs['Anisotropy'].default_value=.2;m.node_tree.links.new(v.outputs[0],out.inputs['Volume']);data=bpy.data.meshes.new('S8_atmosphere_volume');data.from_pydata([(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)],[],[(2,6,4,0),(5,7,3,1),(4,5,1,0),(3,7,6,2),(1,3,2,0),(6,7,5,4)]);data.materials.append(m);o=bpy.data.objects.new('S8_finite_depth_atmosphere',data);scene.collection.objects.link(o);o.location=(*focus,170);o.scale=(1800,1800,300);o.display_type='WIRE';o['evidence']='authored weak depth haze, not observed atmospheric visibility';scene.cycles.volume_bounces=1

def build():
 global scene
 source=root/cfg8['source_scene']
 if bpy.data.filepath:
  assert Path(bpy.data.filepath)==source
  temp=root/'work/tmp/stage08_link_main_temporary.blend';bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(temp),compress=True)
 else:
  temp=None
  with bpy.data.libraries.load(str(source),link=False) as (src,dst):dst.scenes=src.scenes[:1]
  old=scene;scene=dst.scenes[0];bpy.context.window.scene=scene;bpy.data.scenes.remove(old)
 originals=[m for m in bpy.data.meshes if m.library is None];names={m.name for m in originals}
 with bpy.data.libraries.load(str(source),link=True) as (src,dst):dst.meshes=[n for n in src.meshes if n in names]
 linked={m.name:m for m in dst.meshes}
 for o in bpy.data.objects:
  if o.type=='MESH' and o.data.library is None and o.data.name in linked:o.data=linked[o.data.name]
 bpy.data.batch_remove(ids=[m for m in originals if not m.users])
 mats=materials();uv_records={};cache={};remapped=0
 for object_number,ob in enumerate(scene.objects):
  if object_number%20000==0:print('STAGE08_MATERIAL_OBJECT_PROGRESS',object_number,flush=True)
  if ob.type!='MESH':continue
  if ob.get('traffic_role')=='markings':ob.visible_shadow=False;ob['stage08_marking_shadow_note']='Inherited25mm display offset retained; paint decals do not cast an artificial raised-bar shadow. Engineering marking thickness is not represented.'
  # Highest geometry detail has real metre UVs. Distant cells use explicit
  # constant PBR variants: no procedural graph silently omitted in GLB.
  eligible=bool(ob.get('r2_component') in ['structure','roof','cornices','entry_recess','entry_steps','terrain_foundation_and_inferred_plant'] or ob.get('r2_public_surface') or ob.get('r2_ground_variant') or ob.get('landmark_lod')=='near' or ob.get('traffic_role') in ['downtown_road','markings'] or ob.name.startswith('Water_') or ob.name=='LA07_Module_tree_broadleaf')
  if eligible and len(ob.data.polygons):
   key=ob.data.as_pointer()
   if key not in cache:
    data=ob.data.copy();data.name='S8_UV_'+ob.data.name;cache[key]=data;uv_records[data.name]=metre_uv(data)
    if ob.name.startswith('Water_'):
     uv_records[data.name]['water_phase']=water_uv(data,ob.location)
    if ob.name=='LA07_Module_tree_broadleaf':
     mi=np.empty(len(data.polygons),np.int32);data.polygons.foreach_get('material_index',mi);leafslots=[j for j,m in enumerate(data.materials) if m and classify(m.name)=='grass'];mask=np.isin(mi,leafslots);uv=data.uv_layers['PBR_Meters'];a=np.empty(len(data.loops)*2,np.float32);uv.data.foreach_get('uv',a);a=a.reshape(-1,3,2);leafuv=np.array([[[0,0],[1,0],[1,1]],[[0,0],[1,1],[0,1]]],np.float32);a[mask]=leafuv[np.arange(int(mask.sum()))%2];uv.data.foreach_set('uv',a.ravel());uv_records[data.name]['leaf_uv']='each source leaf quad0..1; tile scale intentionally1'
   ob.data=cache[key]
  for slot in ob.material_slots:
   if slot.material is None:continue
   oldname=slot.material.name.lower();key=classify(oldname);variant=None
   if ob.name.startswith('Water_'):key='water'
   for seat in cfg8['legacy_seat_colors_linear']:
    if seat in oldname:variant=seat
   if ob.get('traffic_role')=='markings' and any(w in oldname for w in ['white','yellow']):key='road_marking'
   if key=='concrete' and (ob.get('r2_component')=='roof' or 'roof' in str(ob.get('component','')).lower()):key='roof'
   if key=='road_marking' and 'yellow' in oldname:variant='marking_yellow'
   if any(w in oldname for w in ['dark_metal','pole','frame','signal_case']):variant='paint_dark'
   if 'screen' in oldname:variant='paint_void'
   if 'terracotta' in oldname:variant='paving_red'
   if 'copper' in oldname:variant='copper_patina'
   if 'tactile' in oldname:variant='marking_yellow'
   if key=='glass' and (ob.get('landmark_lod') or ob.get('r2_building') in [974288,1065462,1044280,1044508]):variant='glass_office'
   if key=='glass' and ob.get('r2_component')=='entry_recess':variant='glass_retail'
   if ob.name=='LA07_Module_tree_broadleaf' and key=='grass':key='leaf'
   slot.link='OBJECT';slot.material=mats[(variant,False)] if variant else mats[(key,eligible)];remapped+=1
 proto=bpy.data.objects.get('LA07_Module_tree_broadleaf')
 if proto:
  inst=next(r for r in read('data/processed/stage07/geometry_index.json')['street_instances'] if r['kind']=='tree_broadleaf');field=bpy.data.objects['LA07_'+inst['region']+'_street_tree_broadleaf'];tree=proto.copy();tree.name='S8_Export_tree_realised';scene.collection.objects.link(tree);tree.location=field.location+field.data.vertices[0].co;tree.scale=inst['scale'];tree.rotation_euler.z=inst['rotation'];tree['stage08_export_only']=True;tree['stable_source_id']=inst['stable_source_id'];tree['evidence']='actual source-mapped7m instance of the original generic tree; species and crown inferred';tree.hide_render=True;tree.hide_viewport=True
 v=read('config/stage07_final_views.json')[cfg8['camera']['stage07_view']];from stage07_final_views import aim,show
 # Preserve07 default budget, with same real geographic camera for all presets.
 tri=show(scene,root,v['focus_xy_m'],v.get('radius_m',420),scene.get('stage07_final_default_detail_radius_m',65),True);aim(scene,v);night_setup(mats,np.array(v['focus_xy_m']))
 from stage08_atlas import install
 for rec in install(root,scene):uv_records[rec['mesh']]=rec
 align_night_assets(np.array(v['focus_xy_m']))
 setup_scene(cfg8['render']['width'],cfg8['render']['height'],cfg8['render']['samples']);scene.cycles.seed=cfg8['seed'];scene.view_settings.view_transform='AgX';atmosphere(v['focus_xy_m']);preset('clear_day');scene['stage']=8;scene['stage08_source_scene']=cfg8['source_scene'];scene['stage08_source_geometry_unchanged']=True;scene['stage08_default_triangles']=tri;scene['stage08_texture_registry']='assets/materials/stage08/registry.json';scene['stage08_camera']=json.dumps(v)
 # The texture-driven editable library contains both budget variants. External
 # project texture paths are retained and validated instead of duplicating PNGs.
 for m in mats.values():
  for node in m.node_tree.nodes:
   if node.type=='TEX_IMAGE' and node.image and not node.image.packed_file:node.image.pack()
 asset=root/'assets/materials/stage08/material_library.blend';bpy.data.libraries.write(str(asset),set(mats.values())|{bpy.data.materials['LA08_Furniture_Atlas_PBR']},fake_user=True,compress=True)
 for img in bpy.data.images:
  if img.source=='FILE' and img.filepath:img.filepath=bpy.path.relpath(bpy.path.abspath(img.filepath),start=str(root/'scenes'))
 for lib in bpy.data.libraries:lib.filepath=bpy.path.relpath(bpy.path.abspath(lib.filepath),start=str(root/'scenes'))
 bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=True,do_recursive=True);bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(root/cfg8['output_scene']),compress=True,relative_remap=False)
 if temp is not None:temp.unlink()
 write('work/reports/stage08/build.json',{'status':'saved_requires_independent_reopen','source_scene':cfg8['source_scene'],'output_scene':cfg8['output_scene'],'remapped_object_material_slots':remapped,'uv_meshes':uv_records,'source_geometry_unchanged':True,'default_visible_triangles':tri,'camera':v,'texture_bake_basis':'original textures directly drive Principled; far materials are explicit constant variants, not unsupported procedural exports'})

def check():
 assert Path(bpy.data.filepath)==root/cfg8['output_scene'];bad=0;seen=set();missing=[];uvbad=[];lib=[];build=read('work/reports/stage08/build.json');record=build['uv_meshes'];matched=set()
 for l in bpy.data.libraries:lib.append({'path':bpy.path.abspath(l.filepath),'exists':Path(bpy.path.abspath(l.filepath)).exists()})
 for image in bpy.data.images:
  if image.source=='FILE' and image.filepath and not image.packed_file and not Path(bpy.path.abspath(image.filepath)).exists():missing.append(image.filepath)
 for ob in scene.objects:
  if ob.type!='MESH' or ob.data.as_pointer() in seen or ob.data.library:continue
  m=ob.data;seen.add(m.as_pointer());v=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',v);bad+=int((~np.isfinite(v)).sum())
  if m.name in record:
   assert hashlib.sha256(v.tobytes()).hexdigest()==record[m.name]['vertex_sha256'],m.name;matched.add(m.name);uv=m.uv_layers.get('PBR_Meters');assert uv;arr=np.empty(len(m.loops)*2,np.float32);uv.data.foreach_get('uv',arr)
   if not np.isfinite(arr).all():uvbad.append(m.name)
 assert bad==0 and not missing and not uvbad and all(l['exists'] for l in lib);assert matched==set(record);assert scene.unit_settings.scale_length==1
 fog=bpy.data.objects['S8_finite_depth_atmosphere'];assert all(p.normal.dot(p.center)>0 for p in fog.data.polygons),'Atmosphere hull must have outward winding'
 water_objects=0
 for ob in scene.objects:
  if ob.type=='MESH' and ob.name.startswith('Water_'):
   assert all(slot.material and slot.material.get('stage08_material')=='water' for slot in ob.material_slots),ob.name+' must use water rather than a generic name fallback';water_objects+=1
 assert water_objects>0
 from stage08_material_audit import audit_materials
 material_checks=audit_materials(scene)
 write('work/reports/stage08/material_audit_candidate.json',material_checks)
 assert all(material_checks.get(k) for k in ['pbr_material_checks_passed','uv_checks_passed','color_space_checks_passed']),'Actual PBR/UV/color audit failed; inspect material_audit_candidate.json'
 from stage08_atlas import check as check_atlas
 check_atlas(root,scene)
 material_checks['atlas_checks_passed']=True
 write('work/reports/stage08/scene_check.json',{'status':'passed','saved_model_sha256':sha(bpy.data.filepath),'saved_checkpoint_reopened_independently':True,'units_metres_per_blender_unit':1,'nonfinite_vertices':bad,'missing_images':missing,'invalid_uv_meshes':uvbad,'uv_meshes_checked':len(matched),'source_geometry_unchanged':True,'libraries':lib,'color_management':{'view_transform':scene.view_settings.view_transform,'look':scene.view_settings.look,'working_space':'Blender linear scene-referred, sRGB base maps and Non-Color data maps'},'texture_color_spaces':{i.name:i.colorspace_settings.name for i in bpy.data.images if i.source=='FILE'},**material_checks})

def repair_candidate():
 """Incrementally repair the unregistered candidate, preserving source geometry."""
 import bmesh
 assert Path(bpy.data.filepath)==root/cfg8['output_scene']
 assert not (root/'outputs/stage08_city_medium.manifest.json').exists()
 before=sha(bpy.data.filepath);report=read('work/reports/stage08/build.json');fog=bpy.data.objects['S8_finite_depth_atmosphere'];dots=[p.normal.dot(p.center) for p in fog.data.polygons]
 archive=root/'work/history'/('stage08_candidate_'+before[:12]);archive.mkdir(parents=True,exist_ok=True)
 write(str((archive/'diagnostic.json').relative_to(root)),{'unregistered_candidate_sha256':before,'fog_outward_dots_before':dots,'source_scene_preserved':cfg8['source_scene'],'old_full_binary_not_duplicated':'Source geometry is retained in07; this owned candidate repair preserves diagnostics rather than a second284MiB binary.'})
 if any(d<=0 for d in dots):
  bm=bmesh.new();bm.from_mesh(fog.data);bmesh.ops.reverse_faces(bm,faces=list(bm.faces));bm.to_mesh(fog.data);bm.free();fog.data.update()
 assert all(p.normal.dot(p.center)>0 for p in fog.data.polygons)
 seen={};water_count=0
 for ob in scene.objects:
  if ob.type!='MESH' or not ob.name.startswith('Water_'):continue
  data=ob.data;key=data.as_pointer();phase=np.mod(np.array(ob.location[:2],np.float64),12).astype(np.float32)
  if key in seen:
   assert np.allclose(seen[key],phase,atol=.00001);continue
  assert data.library is None;seen[key]=phase;meta=metre_uv(data);meta['water_phase']=water_uv(data,ob.location);report['uv_meshes'][data.name]=meta;water_count+=1
 from stage08_atlas import install
 for rec in install(root,scene):report['uv_meshes'][rec['mesh']]=rec
 apply_semantic_materials()
 align_night_assets(np.array(json.loads(scene['stage08_camera'])['focus_xy_m']))
 for image in bpy.data.images:
  if image.source=='FILE' and image.filepath and image.library is None:image.filepath=bpy.path.relpath(bpy.path.abspath(image.filepath),start=str(root/'scenes'))
 save(cfg8['output_scene']);report['actual_candidate_repairs']={'outward_fog_winding':True,'water_uv_phase_precision_meshes':water_count,'original_building_road_terrain_vertices_unchanged':True};write('work/reports/stage08/build.json',report);write('work/reports/stage08/candidate_repair.json',{'status':'repaired_requires_independent_reopen','previous_sha256':before,'saved_model_sha256':sha(bpy.data.filepath),'fog_outward_dots_after':[p.normal.dot(p.center) for p in fog.data.polygons],'water_uv_meshes':water_count,'source_geometry_vertices_modified':False})

def apply_semantic_materials():
 water=bpy.data.materials['S8_water_PBR_maps'];seats={}
 for key,color in cfg8['legacy_seat_colors_linear'].items():
  m=bpy.data.materials.get('S8_'+key+'_authored_variant')
  if not m:
   m=bpy.data.materials['S8_paint_PBR_far'].copy();m.name='S8_'+key+'_authored_variant';m['variant_evidence']='preserved source06 model palette, not measured reflectance';m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=color
  seats[key]=m
 count=seat_slots=0
 for ob in scene.objects:
  if ob.type!='MESH':continue
  if ob.name.startswith('Water_'):
   for slot in ob.material_slots:slot.link='OBJECT';slot.material=water
   count+=1
  for j,original in enumerate(ob.data.materials):
   if not original:continue
   key=next((k for k in seats if k in original.name.lower()),None)
   if key:ob.material_slots[j].link='OBJECT';ob.material_slots[j].material=seats[key];seat_slots+=1
 library=root/'assets/materials/stage08/material_library.blend'
 with bpy.data.libraries.load(str(library),link=False) as (src,dst):names=list(src.materials);dst.materials=[n for n in names if bpy.data.materials.get(n) is None]
 bpy.data.libraries.write(str(library),{bpy.data.materials[n] for n in names}|set(seats.values()),fake_user=True,compress=True,path_remap='RELATIVE');write('work/reports/stage08/material_semantics.json',{'status':'applied_requires_independent_reopen','water_objects_using_actual_water_material':count,'preserved_seat_palette_slots':seat_slots,'source_geometry_changed':False})

def validate_semantic_materials():
 assert Path(bpy.data.filepath)==root/cfg8['output_scene'];water=seat_slots=0
 for ob in scene.objects:
  if ob.type!='MESH':continue
  if ob.name.startswith('Water_'):
   assert all(slot.material and slot.material.get('stage08_material')=='water' for slot in ob.material_slots);water+=1
  if not ob.get('landmark_lod'):continue
  used={p.material_index for p in ob.data.polygons}
  for j in used:
   old=ob.data.materials[j];key=next((k for k in cfg8['legacy_seat_colors_linear'] if k in old.name.lower()),None) if old else None
   if key:
    m=ob.material_slots[j].material;assert m.get('stage08_material')=='paint';assert np.max(abs(np.array(m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value)-cfg8['legacy_seat_colors_linear'][key]))<1e-6;seat_slots+=1
 assert water>0 and seat_slots>0
 write('work/reports/stage08/material_semantics.json',{'status':'passed','saved_model_sha256':sha(bpy.data.filepath),'independent_saved_model_check':True,'water_objects_using_actual_water_material':water,'used_landmark_seat_material_slots_verified':seat_slots,'original_seat_palette_retained':True,'source_geometry_changed':False})

def renders(draft=False):
 assert all(p.normal.dot(p.center)>0 for p in bpy.data.objects['S8_finite_depth_atmosphere'].data.polygons),'Atmosphere hull must have outward winding before rendering'
 v=json.loads(scene['stage08_camera']);from stage07_final_views import aim,show;tri=show(scene,root,v['focus_xy_m'],v.get('radius_m',420),v.get('detail_radius_m',150));aim(scene,v);setup_scene(640 if draft else cfg8['render']['width'],480 if draft else cfg8['render']['height'],12 if draft else cfg8['render']['samples']);scene.cycles.max_bounces=5;result={}
 scene.cycles.sample_clamp_indirect=cfg8['render'].get('indirect_clamp',3.0)
 for name in lights_cfg['presets']:
  if args.id!='all' and name not in args.id.split(','):continue
  preset(name);out='work/previews/stage08/'+('draft_' if draft else '')+name+'.png';render(out);result[name]={'output':out,'actual_cpu_cycles':True,'position_m':v['position_m'],'target_m':v['target_m'],'lens_mm':v.get('lens_mm',30),'lighting_preset':name,'local_datetime':lights_cfg['presets'][name]['solar']['local_datetime'],'sun_altitude_deg':lights_cfg['presets'][name]['solar']['altitude_geometric_deg'],'sun_grid_azimuth_deg':lights_cfg['presets'][name]['azimuth_grid_north_clockwise_deg'],'exposure':scene.view_settings.exposure}
 write('work/reports/stage08/'+('draft_' if draft else '')+'renders.json',{'status':'actual_render_completed','saved_scene':bpy.data.filepath,'saved_scene_sha256':sha(bpy.data.filepath),'lighting_config_sha256':sha(root/'config/stage08_lighting.json'),'build_config_sha256':sha(root/'config/stage08.json'),'offline_visible_triangles':tri,'render_parameters':{'engine':scene.render.engine,'device':scene.cycles.device,'samples':scene.cycles.samples,'width':scene.render.resolution_x,'height':scene.render.resolution_y,'seed':scene.cycles.seed,'threads':scene.render.threads,'max_bounces':scene.cycles.max_bounces,'indirect_clamp':scene.cycles.sample_clamp_indirect,'denoising':scene.cycles.use_denoising},'images':result})

if __name__=='__main__':
 if args.mode=='build-eight':build()
 elif args.mode=='check-eight':check()
 elif args.mode=='repair-eight':repair_candidate()
 elif args.mode=='render-eight':renders()
 elif args.mode=='draft-eight':renders(True)
 elif args.mode=='check-draft-eight':check();renders(True)
 elif args.mode=='check-render-eight':check();renders()
 elif args.mode=='check-semantics-eight':validate_semantic_materials()
 elif args.mode=='export-eight':
  from stage08_export import export_samples
  preset('night')
  export_samples(root,scene,cfg8)
 else:raise RuntimeError('未实现 / NOT IMPLEMENTED '+args.mode)
