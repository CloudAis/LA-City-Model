"""Blender static inspection presets; no runtime loading or distance-switch claim."""
import json,math
import numpy as np
import bpy
from mathutils import Matrix,Vector
_cache={}
def views(root):return json.loads((root/'config/stage07_views.json').read_text())
def bounds(o):
 if o.name in _cache:return _cache[o.name]
 for key in ['stage07_bounds_m','stage05_bounds_m']:
  if o.get(key) is not None:a=np.array(o[key]);_cache[o.name]=(a[:3],a[3:]);return _cache[o.name]
 m=o.data;key=m.as_pointer()
 if key not in _cache:
  v=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',v);v=v.reshape(-1,3);_cache[key]=(v.min(axis=0),v.max(axis=0)) if len(v) else (np.zeros(3),np.zeros(3))
 a,b=_cache[key];M=Matrix.LocRotScale(o.location,o.rotation_euler.to_quaternion(),o.scale)
 if o.parent:M=Matrix.LocRotScale(o.parent.location,o.parent.rotation_euler.to_quaternion(),o.parent.scale)@M
 p=np.array([M@Vector((x,y,z)) for x in [a[0],b[0]] for y in [a[1],b[1]] for z in [a[2],b[2]]]);_cache[o.name]=(p.min(axis=0),p.max(axis=0));return _cache[o.name]
def count_visible(scene):
 hidden={o.name for c in bpy.data.collections if c.hide_render for o in c.all_objects}
 return sum(int(o.get('instance_triangles_07',o.get('instance_triangles_05',len(o.data.polygons)))) for o in scene.objects if o.type=='MESH' and not o.hide_render and o.name not in hidden)
def set_visibility(scene,root,focus,radius,batch=False):
 hidden={o.name for c in bpy.data.collections if c.hide_render for o in c.all_objects};active=json.loads((root/'data/processed/stage07/geometry_index.json').read_text())['terrain_active_lod'];shows={};objects=list(bpy.data.objects)
 for o in objects:
  if o.type!='MESH':shows[o.name]=True;continue
  lo,hi=bounds(o);near=lo[0]<=focus[0]+radius and hi[0]>=focus[0]-radius and lo[1]<=focus[1]+radius and hi[1]>=focus[1]-radius;lod=o.get('building_lod');show=near
  if lod is not None:show=near and (int(lod)==(0 if int(o.get('visual_level_05',0)) else 2))
  elif o.get('landmark_lod'):
   origin=np.array(o.parent.location);d=np.linalg.norm(origin[:2]-focus);want='near' if d<180 else 'mid' if d<700 else 'far';show=near and o['landmark_lod']==want
  elif o.get('tile_id') and o.get('lod') is not None and not o.get('traffic_role') and not o.get('instance_kind'):show=near and int(o['lod'])==active.get(o['tile_id'],0)
  elif o.get('traffic_role'):show=near and bool(o.get('stage04_full_view_visible',True))
  elif o.get('instance_kind'):show=near and bool(o.get('stage04_full_view_visible',True))
  if o.name in hidden:show=False
  shows[o.name]=bool(show)
 if batch:
  flags=np.array([not shows[o.name] for o in objects],bool);bpy.data.objects.foreach_set('hide_render',flags);bpy.data.objects.foreach_set('hide_viewport',flags)
 else:
  for o in objects:
   if o.hide_render==shows[o.name]:o.hide_render=not shows[o.name]
 return sum(int(o.get('instance_triangles_07',o.get('instance_triangles_05',len(o.data.polygons)))) for o in objects if o.type=='MESH' and shows[o.name])
def aim_view(scene,view):
 c=scene.camera;c.location=view['position_m'];c.rotation_euler=(Vector(view['target_m'])-c.location).to_track_quat('-Z','Y').to_euler();c.data.clip_start=.05;c.data.clip_end=100000;c.data.type='ORTHO' if 'ortho_scale_m' in view else 'PERSP'
 if c.data.type=='ORTHO':c.data.ortho_scale=view['ortho_scale_m']
 else:c.data.lens=view.get('lens_mm',28)
