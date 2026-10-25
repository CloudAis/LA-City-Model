"""Read-only clean-process inspection of the source authoring city."""
from pathlib import Path
import bpy,json,collections,os
ROOT=Path(__file__).resolve().parents[1]
scene=bpy.context.scene
def path_row(block):
 raw=block.filepath;actual=Path(bpy.path.abspath(raw,library=block.library)) if raw else None
 return {'name':block.name,'raw_path':raw,'resolved':str(actual) if actual else None,'exists':actual.is_file() if actual else None,'packed':bool(getattr(block,'packed_file',None)),'library':block.library.filepath if block.library else None}
objects=list(scene.objects);roles=collections.Counter();samples={}
for ob in objects:
 if ob.type!='MESH':continue
 keys={k:ob[k] for k in ob.keys() if isinstance(ob[k],(int,float,str,bool)) and any(w in k for w in ('role','kind','lod','stage','component','region','stable_id'))}
 key=next((str(keys[k]) for k in ['transport_role','stage04_role','building_lod','r2_component','stage07_kind','stage06_kind'] if k in keys),'other')
 roles[key]+=1
 if key not in samples:samples[key]={'name':ob.name,'props':keys,'hide_render':ob.hide_render,'hide_viewport':ob.hide_viewport,'collections':[c.name for c in ob.users_collection]}
report={'status':'inspected','actual_clean_blender_process':True,'source_file':bpy.data.filepath,'objects':len(objects),'mesh_objects':sum(o.type=='MESH' for o in objects),'libraries':[path_row(x) for x in bpy.data.libraries],'images':[path_row(x) for x in bpy.data.images if x.source=='FILE'],'fonts':[path_row(x) for x in bpy.data.fonts if x.filepath!='<builtin>'],'roles':dict(roles),'samples':samples,'collections':[{'name':c.name,'hide_render':c.hide_render,'hide_viewport':c.hide_viewport,'objects':len(c.objects)} for c in bpy.data.collections if len(c.objects)>300 or c.name.startswith(('00','10','20','30','40','50','60','70','80','90'))],'scene_properties':{k:str(scene[k]) for k in scene.keys()},'render_engine':scene.render.engine,'unit_scale_m':scene.unit_settings.scale_length,'camera':scene.camera.name if scene.camera else None}
p=ROOT/'work/reports/stage10/source_inventory.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('STAGE10_SOURCE_INVENTORY',len(objects),len(bpy.data.libraries),len(report['images']),flush=True)
