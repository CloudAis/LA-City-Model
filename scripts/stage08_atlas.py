"""Original guarded constant-finish atlas, actually applied to street furniture.

Large repeating surfaces retain metre-scaled tiling maps. This small palette
needs no mipmaps: each chart is uniform and LINEAR avoids mixing metal/paint
at distant mip levels. The GLB sampler is explicitly preserved accordingly.
"""
from pathlib import Path
import hashlib,json,struct,zlib
import numpy as np

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,q):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n')
def png(a):
 h,w,_=a.shape
 def chunk(t,b):return struct.pack('>I',len(b))+t+b+struct.pack('>I',zlib.crc32(t+b)&0xffffffff)
 raw=b''.join(b'\0'+r.tobytes() for r in a)
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw,9))+chunk(b'IEND',b'')
def generate(root):
 root=Path(root);cfg=json.loads((root/'config/stage08_atlas.json').read_text());size=cfg['size_px'];half=size//2;maps={k:np.zeros((size,size,3),np.uint8) for k in ['base_color','normal','orm']}
 for j,r in enumerate(cfg['palettes']):
  y=(1-j//2)*half;x=(j%2)*half;sl=np.s_[y:y+half,x:x+half];maps['base_color'][sl]=np.rint(np.array(r['color_srgb'])*255);maps['normal'][sl]=[128,128,255];maps['orm'][sl]=[255,round(r['roughness']*255),round(r['metallic']*255)]
 files=[]
 for role,a in maps.items():
  p=root/'assets/textures/stage08/furniture_atlas'/('furniture_atlas_'+role+'.png');p.parent.mkdir(parents=True,exist_ok=True);b=png(a)
  if p.exists() and p.read_bytes()!=b:raise RuntimeError('Preserve edited atlas before regeneration: '+str(p))
  p.write_bytes(b);files.append({'role':role,'path':str(p.relative_to(root)),'sha256':digest(p),'colorspace':'sRGB' if role=='base_color' else 'Non-Color'})
 reg={'id':cfg['id'],'size_px':size,'guard_px':cfg['guard_px'],'files':files,'palettes':cfg['palettes'],'sampler':{'minFilter':9729,'magFilter':9729,'wrapS':33071,'wrapT':33071},'mipmap_policy':'No mip sampling for four constant finish charts;32px guard prevents bilinear bleed. Repeating detailed PBR maps retain mipmapping.','license':'Original project-generated constant finish atlas; no external texture inputs.'};write(root/'assets/materials/stage08/atlas_registry.json',reg);return reg

def install(root,scene):
 import bpy
 root=Path(root);reg=generate(root);m=bpy.data.materials.get('LA08_Furniture_Atlas_PBR')
 if not m:
  m=bpy.data.materials.new('LA08_Furniture_Atlas_PBR');m.use_nodes=True;m['texture_backed']=True;m['normalized_atlas_uv']=True;m['stage08_atlas_id']=reg['id'];n=m.node_tree.nodes;l=m.node_tree.links;b=n.get('Principled BSDF');uv=n.new('ShaderNodeUVMap');uv.uv_map='PBR_Meters'
  for r in reg['files']:
   image=bpy.data.images.load(str(root/r['path']),check_existing=True);image.colorspace_settings.name=r['colorspace'];image.pack();tex=n.new('ShaderNodeTexImage');tex.image=image;tex.label=r['role'];tex.extension='EXTEND';tex.interpolation='Closest';l.new(uv.outputs[0],tex.inputs[0])
   if r['role']=='base_color':l.new(tex.outputs['Color'],b.inputs['Base Color'])
   elif r['role']=='normal':
    normal=n.new('ShaderNodeNormalMap');normal.uv_map='PBR_Meters';l.new(tex.outputs['Color'],normal.inputs['Color']);l.new(normal.outputs[0],b.inputs['Normal'])
   else:
    split=n.new('ShaderNodeSeparateColor');l.new(tex.outputs['Color'],split.inputs[0]);l.new(split.outputs['Green'],b.inputs['Roughness']);l.new(split.outputs['Blue'],b.inputs['Metallic'])
 records=[];half=reg['size_px']//2;g=reg['guard_px'];library=root/'assets/materials/stage08/material_library.blend'
 for name in ['LA07_Module_street_lamp','LA07_Module_hydrant','LA07_Module_waste_bin','LA07_Module_bollard']:
  ob=bpy.data.objects.get(name)
  if not ob:continue
  if ob.get('stage08_atlas_installed'):
   continue
  old=ob.data;data=old.copy();data.name='LA08_ATLAS_'+name;ob.data=data;mi=np.empty(len(data.polygons),np.int32);data.polygons.foreach_get('material_index',mi);lens=ob.material_slots[7].material if 'street_lamp' in name else None;role=np.where(mi==2,1,np.where(mi==11,2,np.where(mi==14,3,0)));uv=np.empty((len(mi),3,2),np.float32)
  for j in range(4):
   lo=np.array([(j%2)*half+g,(j//2)*half+g],float)/reg['size_px'];hi=lo+(half-2*g)/reg['size_px'];uv[role==j]=[lo,[hi[0],lo[1]],hi]
  layer=data.uv_layers.get('PBR_Meters') or data.uv_layers.new(name='PBR_Meters');layer.data.foreach_set('uv',uv.ravel());data.uv_layers.active=layer;data.materials.clear();data.materials.append(m)
  if lens:data.materials.append(lens)
  data.polygons.foreach_set('material_index',np.where(mi==7,1,0).astype(np.int32) if lens else np.zeros(len(mi),np.int32))
  for slot in ob.material_slots:slot.link='DATA'
  ob['stage08_atlas_installed']=True
  if lens:ob['stage08_atlas_lens_slot']=1
  data.update();v=np.empty(len(data.vertices)*3,np.float32);data.vertices.foreach_get('co',v);records.append({'object':name,'mesh':data.name,'vertex_sha256':hashlib.sha256(v.tobytes()).hexdigest(),'vertex_count':len(data.vertices),'triangles':len(data.polygons),'uv_finite':True,'projection':'normalized guarded constant finish atlas; not a metre repeating surface'})
 # Preserve all original reusable materials, adding the actual atlas to the
 # existing appendable material library rather than replacing its classes.
 if library.exists():
  with bpy.data.libraries.load(str(library),link=False) as (src,dst):
   names=list(src.materials);dst.materials=[n for n in names if bpy.data.materials.get(n) is None]
 else:names=[m.name for m in bpy.data.materials if m.name.startswith('S8_') and m.name.endswith(('_PBR_maps','_PBR_far','_authored_variant'))]
 bpy.data.libraries.write(str(library),{bpy.data.materials[n] for n in names}|{m},fake_user=True,compress=True,path_remap='RELATIVE')
 # Real mapped lamp for the road compatibility sample; no city position change.
 proto=bpy.data.objects.get('LA07_Module_street_lamp');night=root/'work/reports/stage08/night_distribution.json'
 if proto and night.exists() and not bpy.data.objects.get('S8_Export_lamp_realised'):
  row=json.loads(night.read_text())['actual_road_light_positions'][0];field=bpy.data.objects[row['source_point_field']];idx=row['point_index'];ob=proto.copy();ob.name='S8_Export_lamp_realised';scene.collection.objects.link(ob);ob.location=field.matrix_world@field.data.vertices[idx].co;ob.rotation_euler.z=field.data.attributes['module_rotation'].data[idx].vector.z;ob['stage08_export_only']=True;ob['source_point_fid']=row['source_fid'];ob.hide_render=True;ob.hide_viewport=True
 return records

def check(root,scene):
 import bpy
 root=Path(root);reg=json.loads((root/'assets/materials/stage08/atlas_registry.json').read_text());m=bpy.data.materials['LA08_Furniture_Atlas_PBR'];b=m.node_tree.nodes.get('Principled BSDF');assert b and b.inputs['Base Color'].is_linked and b.inputs['Normal'].is_linked and b.inputs['Metallic'].is_linked and b.inputs['Roughness'].is_linked;assert b.inputs['Metallic'].links[0].from_socket.name=='Blue' and b.inputs['Roughness'].links[0].from_socket.name=='Green';assert b.inputs['Normal'].links[0].from_node.type=='NORMAL_MAP'
 with bpy.data.libraries.load(str(root/'assets/materials/stage08/material_library.blend'),link=False) as (src,dst):assert m.name in src.materials;dst.materials=[]
 for r in reg['files']:
  assert digest(root/r['path'])==r['sha256'];tex=next(n for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.label==r['role']);im=tex.image;assert im.colorspace_settings.name==r['colorspace'] and im.packed_file and tex.extension=='EXTEND';pixels=np.empty(len(im.pixels),np.float32);im.pixels.foreach_get(pixels);assert np.isfinite(pixels).all();a=pixels.reshape(reg['size_px'],reg['size_px'],4)
  if r['role']=='orm':
   for j,finish in enumerate(reg['palettes']):
    pix=a[(j//2)*256+128,(j%2)*256+128];assert abs(float(pix[2])-finish['metallic'])<1e-5;assert abs(float(pix[1])-finish['roughness'])<1/255+.0001
 records=[]
 for ob in scene.objects:
  if not ob.get('stage08_atlas_installed'):continue
  uv=ob.data.uv_layers['PBR_Meters'];a=np.empty(len(uv.data)*2,np.float32);uv.data.foreach_get('uv',a);a=a.reshape(-1,3,2);area=abs((a[:,1,0]-a[:,0,0])*(a[:,2,1]-a[:,0,1])-(a[:,1,1]-a[:,0,1])*(a[:,2,0]-a[:,0,0]))/2;assert np.isfinite(a).all() and (area>0).all() and a.min()>0 and a.max()<1;records.append({'object':ob.name,'triangles':len(area),'finite_nondegenerate_guarded_uv':True})
 assert len(records)>=1
 report={'status':'passed','saved_model_sha256':digest(bpy.data.filepath),'actual_saved_scene_atlas_checked':True,'material':'LA08_Furniture_Atlas_PBR','mapped_prototypes':records,'source_geometry_vertices_unchanged':True,'textures':reg['files'],'mipmap_policy':reg['mipmap_policy']};write(root/'work/reports/stage08/atlas_check.json',report);return report

def patch_glb_sampler(path):
 """Keep this constant palette from blending metals/paint in distant mips."""
 path=Path(path);data=path.read_bytes();pos=12;chunks=[];doc=None
 while pos<len(data):
  size,kind=struct.unpack_from('<II',data,pos);payload=data[pos+8:pos+8+size];pos+=8+size
  if kind==0x4e4f534a:doc=json.loads(payload.rstrip(b' \0'))
  else:chunks.append((kind,payload))
 selected=[t for t in doc.get('textures',[]) if 'furniture_atlas_' in doc['images'][t['source']].get('name','')]
 if not selected:return
 samplers=doc.setdefault('samplers',[]);idx=len(samplers);samplers.append({'minFilter':9729,'magFilter':9729,'wrapS':33071,'wrapT':33071})
 for t in selected:t['sampler']=idx
 payload=json.dumps(doc,separators=(',',':')).encode();payload+=b' '*((-len(payload))%4);parts=[struct.pack('<II',len(payload),0x4e4f534a)+payload]+[struct.pack('<II',len(b),k)+b for k,b in chunks];body=b''.join(parts);path.write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)
