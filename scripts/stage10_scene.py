"""Portable Blender view/light selection; no raw source data or network required."""
import math
import bpy,numpy as np
from mathutils import Vector
_bounds={}
def world_matrix(ob):return world_matrix(ob.parent)@ob.matrix_parent_inverse@ob.matrix_basis if ob.parent else ob.matrix_basis.copy()
def bounds(ob):
 if ob.name in _bounds:return _bounds[ob.name]
 for key in ('stage07_bounds_m','stage05_bounds_m'):
  if ob.get(key) is not None:
   a=np.array(ob[key]);_bounds[ob.name]=(a[:3],a[3:]);return _bounds[ob.name]
 key=ob.data.as_pointer()
 if key not in _bounds:
  a=np.empty((len(ob.data.vertices),3),np.float32);ob.data.vertices.foreach_get('co',a.ravel());_bounds[key]=(a.min(axis=0),a.max(axis=0)) if len(a) else (np.zeros(3),np.zeros(3))
 a,b=_bounds[key];m=world_matrix(ob);p=np.array([m@Vector((x,y,z)) for x in (a[0],b[0]) for y in (a[1],b[1]) for z in (a[2],b[2])]);_bounds[ob.name]=(p.min(axis=0),p.max(axis=0));return _bounds[ob.name]
def apply_view(scene,view,terrain_active):
 focus=np.array(view.get('focus_xy_m',view['target_m'][:2]));radius=view.get('radius_m',2000);detail=view.get('detail_radius_m',120);city=view.get('mode')=='city';tri=0
 hidden={o.name for c in bpy.data.collections if c.hide_render for o in c.all_objects};objects=list(bpy.data.objects);flags=[]
 for ob in objects:
  visible=True
  if ob.type=='MESH':
   lo,hi=bounds(ob);near=lo[0]<=focus[0]+radius and hi[0]>=focus[0]-radius and lo[1]<=focus[1]+radius and hi[1]>=focus[1]-radius;visible=near
   if ob.get('r2_building') is not None:
    d=np.linalg.norm(np.array(ob['r2_origin_city_m'])[:2]-focus);visible=near and ob['r2_lod']==('near' if d<detail and not city else 'far')
   elif ob.get('building_lod') is not None:visible=near and int(ob['building_lod'])==2
   elif ob.get('landmark_lod'):
    d=np.linalg.norm(np.array(ob.parent.location)[:2]-focus);wanted='near' if d<view.get('landmark_near_m',180) and not city else 'mid' if d<900 and not city else 'far';visible=near and ob['landmark_lod']==wanted
   elif ob.get('tile_id') and ob.get('lod') is not None and not ob.get('traffic_role') and not ob.get('instance_kind'):visible=near and int(ob['lod'])==terrain_active.get(ob['tile_id'],0)
   elif ob.get('traffic_role') or ob.get('instance_kind'):visible=near and bool(ob.get('stage04_full_view_visible',True))
   if ob.name in hidden or ob.get('stage08_export_only') or ob.name=='S8_finite_depth_atmosphere':visible=False
   if visible:tri+=int(ob.get('instance_triangles_07',ob.get('instance_triangles_05',len(ob.data.polygons))))
  flags.append(not visible)
 bpy.data.objects.foreach_set('hide_render',np.array(flags,bool));bpy.data.objects.foreach_set('hide_viewport',np.array(flags,bool))
 camera=scene.camera;camera.location=view['position_m'];camera.rotation_euler=(Vector(view['target_m'])-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.clip_start=.1;camera.data.clip_end=180000;camera.data.type='ORTHO' if 'ortho_scale_m' in view else 'PERSP'
 if camera.data.type=='ORTHO':camera.data.ortho_scale=view['ortho_scale_m']
 else:camera.data.lens=view.get('lens_mm',35)
 bpy.context.view_layer.update();return tri
def apply_light(scene,lighting,name):
 p=lighting['presets'][name];sun=next(o for o in scene.objects if o.type=='LIGHT' and o.data.type=='SUN');sun.rotation_euler=[math.radians(x) for x in p['sun_rotation_euler_xyz_degrees']];sun.data.energy=p['sun_energy'];sun.data.color=p['sun_color_linear_rgb'];sun.data.angle=math.radians(p['sun_angle_deg']);world=scene.world;world.use_nodes=True;nodes=world.node_tree.nodes;links=world.node_tree.links;bg=nodes.get('Background');sky=nodes.get('S8_solar_sky')
 if p['world_model']=='nishita':
  if not sky:sky=nodes.new('ShaderNodeTexSky');sky.name='S8_solar_sky';sky.sky_type='NISHITA';sky.sun_disc=False
  sky.sun_elevation=math.radians(max(.1,p['solar']['altitude_geometric_deg']));d=p['sun_direction_towards_sun_grid_xyz'];sky.sun_rotation=math.atan2(d[1],d[0]);links.new(sky.outputs[0],bg.inputs[0])
 else:
  for link in list(bg.inputs[0].links):links.remove(link)
  bg.inputs[0].default_value=(*p.get('world_color_linear_rgb',[.04,.07,.16])[:3],1)
 bg.inputs[1].default_value=p['world_strength'];scene.view_settings.exposure=p['exposure_stops'];on=p['artificial_lights_enabled']
 for ob in scene.objects:
  if ob.type=='LIGHT' and ob!=sun:ob.data.energy=ob.get('night_energy_w',0)*(.65 if name=='blue_hour' else 1) if on and ob.get('stage08_night_light') else 0
 for mat in bpy.data.materials:
  if mat.get('stage08_night_emission') and mat.use_nodes:mat.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=mat['night_emission_strength']*(.5 if name=='blue_hour' else 1) if on else 0
 scene['stage10_lighting']=name;scene['stage10_local_datetime']=p['solar']['local_datetime']
