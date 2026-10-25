"""Explicit static LOD selection for saved authoring views; no runtime streaming claim."""
import json,math
import numpy as np,bpy
from mathutils import Vector
from stage07_views import bounds
def views(root):return json.loads((root/'config/stage07_final_views.json').read_text())
def show(scene,root,focus,radius,detail,batch=False):
 index=json.loads((root/'data/processed/stage07_final/index.json').read_text());active=index['terrain_active_lod'];hidden={o.name for c in bpy.data.collections if c.hide_render for o in c.all_objects};objs=list(bpy.data.objects);shows={};tri=0
 for o in objs:
  visible=True
  if o.type=='MESH':
   lo,hi=bounds(o);near=lo[0]<=focus[0]+radius and hi[0]>=focus[0]-radius and lo[1]<=focus[1]+radius and hi[1]>=focus[1]-radius;visible=near
   if o.get('r2_building') is not None:
    origin=np.array(o['r2_origin_city_m']);distance=np.linalg.norm(origin[:2]-focus);visible=near and o['r2_lod']==('near' if distance<detail else 'far')
   elif o.get('building_lod') is not None:visible=near and int(o['building_lod'])==2
   elif o.get('landmark_lod'):
    distance=np.linalg.norm(np.array(o.parent.location)[:2]-focus);wanted='near' if distance<200 else 'mid' if distance<700 else 'far';visible=near and o['landmark_lod']==wanted
   elif o.get('tile_id') and o.get('lod') is not None and not o.get('traffic_role') and not o.get('instance_kind'):visible=near and int(o['lod'])==active.get(o['tile_id'],0)
   elif o.get('traffic_role') or o.get('instance_kind'):visible=near and bool(o.get('stage04_full_view_visible',True))
   if o.name in hidden:visible=False
   if o.get('stage08_export_only'):visible=False
   if visible:tri+=int(o.get('instance_triangles_07',o.get('instance_triangles_05',len(o.data.polygons))))
  shows[o.name]=bool(visible)
 if batch:
  a=np.array([not shows[o.name] for o in objs],bool);bpy.data.objects.foreach_set('hide_render',a);bpy.data.objects.foreach_set('hide_viewport',a)
 else:
  for o in objs:
   if o.hide_render==shows[o.name]:o.hide_render=not shows[o.name]
 return tri
def aim(scene,v):
 c=scene.camera;c.location=v['position_m'];c.rotation_euler=(Vector(v['target_m'])-c.location).to_track_quat('-Z','Y').to_euler();c.data.clip_start=.05;c.data.clip_end=50000;c.data.type='ORTHO' if 'ortho_scale_m' in v else 'PERSP'
 if c.data.type=='ORTHO':c.data.ortho_scale=v['ortho_scale_m']
 else:c.data.lens=v.get('lens_mm',32)
