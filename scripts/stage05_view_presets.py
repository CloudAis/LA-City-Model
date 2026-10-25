"""Portable saved-scene static alternatives. Select and Run Script in Blender.

This loads a fixed focus; it is not a runtime LOD/streaming viewer.
"""
import bpy,numpy as np
from mathutils import Matrix,Vector
preset='historic_core' # historic_core, civic_center, downtown, city_overview
scene=bpy.context.scene;centers={'historic_core':(-463,770),'civic_center':(220,1660),'downtown':(0,0)};focus=centers.get(preset,(0,0));radius=100000 if preset=='city_overview' else 2350 if preset=='downtown' else float(scene.get('stage05_default_radius_m',150));local={};hidden={o.name for c in bpy.data.collections if c.hide_render for o in c.objects}
for o in scene.objects:
 show=bool(o.get('stage04_full_view_visible',not o.hide_render));near=True
 if o.type=='MESH':
  if o.get('stage05_bounds_m') is not None:b=np.array(o['stage05_bounds_m']);lo=b[:3];hi=b[3:]
  else:
   key=o.data.as_pointer()
   if key not in local:
    v=np.empty(len(o.data.vertices)*3,np.float32);o.data.vertices.foreach_get('co',v);v=v.reshape(-1,3);local[key]=(v.min(axis=0),v.max(axis=0)) if len(v) else (np.zeros(3),np.zeros(3))
   a,b=local[key];matrix=Matrix.LocRotScale(o.location,o.rotation_euler.to_quaternion(),o.scale)
   if o.parent:matrix=o.parent.matrix_world@matrix
   corners=np.array([matrix@Vector((x,y,z)) for x in [a[0],b[0]] for y in [a[1],b[1]] for z in [a[2],b[2]]]);lo=corners.min(axis=0);hi=corners.max(axis=0)
  near=lo[0]<=focus[0]+radius and hi[0]>=focus[0]-radius and lo[1]<=focus[1]+radius and hi[1]>=focus[1]-radius;lod=o.get('building_lod')
  if lod is not None:show=int(lod)==(2 if preset=='city_overview' or not o['visual_level_05'] else 0)
  if o.get('instance_kind_05'):show=preset!='city_overview'
  if preset=='city_overview':
   if o.get('traffic_role'):show=o['traffic_role'] in ['overview_far','bridge_road','tunnel_road','downtown_road','rail_corridor','airport_surface','airport_apron','airport_marking','profiled_priority_road','inferred_retaining_bank']
   if o.get('instance_kind'):show=False
 show=show and near and o.name not in hidden
 if o.hide_render==show:o.hide_render=not show
 if o.hide_viewport==show:o.hide_viewport=not show
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.clip_end=500000;area.spaces.active.region_3d.view_location=Vector((*focus,100));area.spaces.active.region_3d.view_distance=50000 if preset=='city_overview' else 3000 if preset=='downtown' else 600
print('STAGE05_STATIC_VIEW_APPLIED',preset,'runtime LOD/GLB/streaming not implemented')
