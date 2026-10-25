"""Read-only inventory and runtime extraction from the accepted stage08 scene."""
from pathlib import Path
import collections, hashlib, json, time
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/processed/stage09/extracted'
OUT.mkdir(parents=True,exist_ok=True)
start=time.perf_counter()
scene=bpy.context.scene
source=ROOT/'scenes/stage08_city_medium.blend'
def sha(p):
    with p.open('rb') as s:return hashlib.file_digest(s,'sha256').hexdigest()
before=sha(source)
world_cache={}
def source_world(ob):
    # Hidden linked objects may retain a stale serialized matrix_world after
    # background open. Resolve the actual static parent chain for every object.
    key=ob.as_pointer()
    if key not in world_cache:
        basis=ob.matrix_basis.copy()
        world_cache[key]=source_world(ob.parent)@ob.matrix_parent_inverse@basis if ob.parent else basis
    return world_cache[key]
materials={}
def material(m):
    if not m:return None
    if m.name in materials:return m.name
    bs=next((n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None) if m.use_nodes else None
    base=list(bs.inputs['Base Color'].default_value) if bs else list(m.diffuse_color)
    row={'name':m.name,'family':m.get('stage08_material',''),'base_color':base,
         'metallic':float(bs.inputs['Metallic'].default_value) if bs else 0,
         'roughness':float(bs.inputs['Roughness'].default_value) if bs else .8,
         'transmission':float(bs.inputs['Transmission Weight'].default_value) if bs else 0,
         'ior':float(bs.inputs['IOR'].default_value) if bs else 1.5,
         'emission':list(bs.inputs['Emission Color'].default_value) if bs else [0,0,0,1],
         'emission_strength':float(m.get('night_emission_strength',bs.inputs['Emission Strength'].default_value if bs else 0)),
         'night':bool(m.get('stage08_night_emission',False)),
         'tile_m':list(m.get('physical_tile_metres',[1,1])), 'maps':{}}
    if m.use_nodes:
        for node in m.node_tree.nodes:
            if node.type!='TEX_IMAGE' or not node.image:continue
            image=node.image
            path=Path(bpy.path.abspath(image.filepath,library=image.library))
            role=next((r for r in ('base_color','normal','orm') if r in path.stem),None)
            if role and path.exists():row['maps'][role]=str(path.relative_to(ROOT))
    if row['maps']:
        row['base_color']=[1,1,1,1];row['metallic']=row['roughness']=1
    materials[m.name]=row
    return m.name

rows=[];visible=collections.Counter();counts=collections.Counter();instances=[]
all_objects=list(scene.objects)
for i,ob in enumerate(all_objects):
    counts[ob.type]+=1
    if ob.type!='MESH':continue
    data=ob.data
    if not ob.hide_render:
        visible['objects']+=1;visible['source_faces']+=len(data.polygons)
    kind=None;lod=None;ident=None
    if ob.get('r2_building') is not None:
        kind='buildings';lod=0 if ob.get('r2_lod')=='near' else 2;ident='building:'+str(ob['r2_building'])
    elif ob.get('r2_skybridge'):
        kind='buildings';lod=0;ident='skybridge:425993596'
    elif ob.get('landmark_id') and ob.get('landmark_lod'):
        kind='landmarks';lod={'near':0,'mid':1,'far':2}[ob['landmark_lod']];ident='landmark:'+ob['landmark_id']
    elif ob.get('r2_public_surface'):
        kind='roads';lod=0;ident='surface:'+ob.name
    elif ob.get('stage07_kind') and ob.get('stage07_instances') is not None:
        attrs={}
        for name in ('module_rotation','module_scale','building_index'):
            a=data.attributes.get(name)
            if not a:continue
            values=np.empty((len(data.vertices),3) if a.data_type=='FLOAT_VECTOR' else len(data.vertices),np.float32 if a.data_type=='FLOAT_VECTOR' else np.int32)
            a.data.foreach_get('vector' if a.data_type=='FLOAT_VECTOR' else 'value',values.ravel());attrs[name]=values.tolist()
        p=np.empty((len(data.vertices),3),np.float32);data.vertices.foreach_get('co',p.ravel())
        matrix=source_world(ob)
        p=p@np.array(matrix,np.float64)[:3,:3].T+np.array(matrix.translation)
        instances.append({'name':ob.name,'kind':ob['stage07_kind'],'points_city_m':p.tolist(),'attributes':attrs})
    elif ob.name.startswith('LA07_Module_') and len(data.polygons):
        kind='prototype';lod=0;ident='prototype:'+ob.name.removeprefix('LA07_Module_')
    elif ob.get('r2_ground_variant') and ob.get('lod')==0:
        kind='terrain';lod=0;ident='terrain:'+ob['tile_id']
    elif ob.get('r2_ordinary_transport_z_inferred'):
        kind='roads';lod=0;ident='road:'+ob.name
    if kind is None or not len(data.polygons):continue
    data.calc_loop_triangles()
    v=np.empty((len(data.vertices),3),np.float32);data.vertices.foreach_get('co',v.ravel())
    matrix=np.array(source_world(ob),np.float64)
    world=v@matrix[:3,:3].T+matrix[:3,3]
    origin=matrix[:3,3]
    f=np.array([t.vertices[:] for t in data.loop_triangles],np.int32)
    m=np.array([t.material_index for t in data.loop_triangles],np.uint16)
    arrays={'v':(world-origin).astype(np.float32),'f':f,'m':m}
    if data.uv_layers:
        uv=np.empty((len(data.loops),2),np.float32);data.uv_layers.active.data.foreach_get('uv',uv.ravel())
        loops=np.array([t.loops[:] for t in data.loop_triangles],np.int32)
        arrays['uv']=uv[loops]
    path=OUT/(str(len(rows)).zfill(4)+'.npz')
    np.savez_compressed(path,**arrays)
    row={'name':ob.name,'kind':kind,'lod':lod,'id':ident,'file':str(path.relative_to(ROOT)),
         'origin_city_m':origin.tolist(),'bounds_city_m':[world.min(axis=0).tolist(),world.max(axis=0).tolist()],
         'triangles':len(f),'materials':[material(s.material) for s in ob.material_slots]}
    rows.append(row)
    if len(rows)%200==0:print('EXTRACTED',len(rows),flush=True)

all_materials={s.material.name:s.material for ob in all_objects if ob.type=='MESH' for s in ob.material_slots if s.material}
textures={n.image.name:n.image for m in all_materials.values() if m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image}
report={'stage':9,'status':'actual_saved_stage08_inventory_and_extraction_completed','source_model_sha256':before,
        'source_model_bytes':source.stat().st_size,'object_types':dict(counts),'objects':len(all_objects),
        'mesh_objects':counts['MESH'],'unique_mesh_datablocks':len({o.data.as_pointer() for o in all_objects if o.type=='MESH'}),
        'source_mesh_polygons_including_exclusive_lods':sum(len(o.data.polygons) for o in all_objects if o.type=='MESH'),
        'saved_default_visibility':dict(visible),'materials':len(all_materials),'textures':len(textures),
        'texture_dimensions':[{'name':n,'size_px':list(im.size)} for n,im in textures.items()],
        'device':'CPU; GPU/VRAM unknown','seconds':time.perf_counter()-start,
        'saved_default_scene_metadata':{k:scene[k] for k in scene.keys() if 'triangles' in k},
        'original_file_unchanged':sha(source)==before,'geometry_was_resampled':False,
        'hidden_parent_transforms_resolved_explicitly':True,
        'exported_objects':len(rows),'exported_triangles':sum(r['triangles'] for r in rows)}
assert report['original_file_unchanged']
(OUT/'index.json').write_text(json.dumps({'objects':rows,'materials':materials,'instances':instances},ensure_ascii=False,indent=2)+'\n')
(ROOT/'work/reports/stage09/baseline_authoring.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('READ_ONLY_BASELINE_COMPLETED',len(rows),report['seconds'],flush=True)
