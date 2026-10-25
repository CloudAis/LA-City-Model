"""Embedded, portable Blender Text Editor script. Select a preset below and Run Script."""
import bpy
import numpy as np
from mathutils import Matrix,Vector
preset='historic_core'  # city_overview, historic_core, civic_center, interchange
scene=bpy.context.scene
centers={'historic_core':tuple(scene['stage04_initial_focus_xy_m']),
         'civic_center':(200,1750),'interchange':tuple(scene['stage04_interchange_xy_m'])}
objects=list(scene.objects);local={};bounds={}
for o in objects:
 if o.type!='MESH':continue
 key=o.data.as_pointer()
 if key not in local:
  v=np.empty(len(o.data.vertices)*3,np.float32);o.data.vertices.foreach_get('co',v);v=v.reshape(-1,3);a=v.min(axis=0);b=v.max(axis=0)
  local[key]=[Vector((x,y,z)) for x in [a[0],b[0]] for y in [a[1],b[1]] for z in [a[2],b[2]]]
 matrix=Matrix.LocRotScale(o.location,o.rotation_euler.to_quaternion(),o.scale)
 if o.parent:matrix=o.parent.matrix_world@matrix
 p=[matrix@v for v in local[key]];bounds[o.name]=(min(q.x for q in p),max(q.x for q in p),min(q.y for q in p),max(q.y for q in p))
for o in objects:
 show=bool(o.get('stage04_full_view_visible',False));role=o.get('traffic_role')
 if preset=='city_overview':
  if role:show=role in ['overview_far','bridge_road','tunnel_road','downtown_road','rail_corridor','airport_surface','airport_apron','airport_marking','profiled_priority_road','inferred_retaining_bank']
  if o.get('instance_kind'):show=False
 else:
  x,y=centers[preset]
  if o.type=='MESH':
   a,b,c,d=bounds[o.name];show=show and a<=x+1000 and b>=x-1000 and c<=y+1000 and d>=y-1000
 # Use RNA setters for changed flags, so Blender refreshes its visibility graph.
 if o.hide_render==show:o.hide_render=not show
 if o.hide_viewport==show:o.hide_viewport=not show
if preset=='city_overview':
 ground=[bounds[o.name] for o in objects if o.get('lod') is not None and o.get('stage04_full_view_visible')]
 x=(min(a for a,b,c,d in ground)+max(b for a,b,c,d in ground))/2
 y=(min(c for a,b,c,d in ground)+max(d for a,b,c,d in ground))/2
 distance=max(max(b for a,b,c,d in ground)-min(a for a,b,c,d in ground),max(d for a,b,c,d in ground)-min(c for a,b,c,d in ground))*.65
else:x,y=centers[preset];distance=1100
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.clip_end=500000;area.spaces.active.region_3d.view_location=Vector((x,y,90));area.spaces.active.region_3d.view_distance=distance
print('STATIC_VIEW_PRESET_APPLIED',preset,'offline/static visibility; runtime streaming not implemented')
