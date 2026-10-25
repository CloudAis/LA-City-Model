"""Incremental local GLB tiles from preserved project geometry, not replacement demo data."""
from pathlib import Path
import collections,gzip,hashlib,itertools,json,math,shutil,sqlite3,subprocess,time
import numpy as np
import yaml
from PIL import Image
from stage09_glb import GLB,digest,linear_rgba

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/stage09/resources'
def read(path):return json.loads((ROOT/path).read_text())
def write(path,value):
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n')
def load(path):
    with np.load(ROOT/path) as z:return {k:z[k] for k in z.files}

class Exporter:
    def __init__(self):
        self.cfg=read('config/stage09.json');self.extracted=read('data/processed/stage09/extracted/index.json')
        for d in ('tiles','textures','textures-low','metadata'): (OUT/d).mkdir(parents=True,exist_ok=True)
        self.proc=subprocess.Popen(['node',str(ROOT/'viewer/compress.mjs')],cwd=ROOT/'viewer',stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
        self.resources=[];self.metrics=[];self.features={};self.metadata={};self.next_id=6_000_000
        self.texture_map={};self.input_files=set();self.lm=read('data/processed/stage06/landmark_index.json')
        self.refined=read('data/processed/stage07_final/index.json')
        self.excluded={r['i'] for a in self.lm['landmarks'] for r in a['replaces']}|set(self.refined['replaced_source_indices'])
        self.special={};self.raw_kept=0
    def texture(self,path):
        if path in self.texture_map:return self.texture_map[path]
        p=(ROOT/path).resolve();key=digest(p)[:14]+'.png'
        for folder,size in [('textures',512),('textures-low',256)]:
            target=OUT/folder/key
            if not target.exists():
                with Image.open(p) as image:
                    image.thumbnail((size,size),Image.Resampling.LANCZOS);image.save(target,optimize=True)
        self.texture_map[path]='../textures/'+key;return self.texture_map[path]
    def spec(self,name):
        source=self.extracted['materials'].get(name)
        if source is None:return {'name':'runtime_neutral','base_color':[.5,.5,.5,1]}
        result=dict(source);result['maps']={k:self.texture(v) for k,v in source['maps'].items()}
        # Foliage and the original furniture atlas use their existing normalized
        # UVs. Other scene UVs are metres and are divided by each material tile.
        return result
    def identifier(self,key,properties):
        if key in self.special:return self.special[key]
        self.next_id+=1;fid=self.next_id;self.special[key]=fid
        self.features[str(fid)]=dict(id=key,**properties);return fid
    def resource(self,ident,layer,lod,origin,inputs,metadata=None,keep_raw=False):
        """Merge by effective material; per-corner ID remains available for selection."""
        groups={};bounds=[];input_objects=0
        for item in inputs:
            arrays=item.get('arrays')
            if arrays is None:
                self.input_files.add(item['file']);arrays=load(item['file'])
            v=np.asarray(arrays['v'],np.float64)+np.asarray(item.get('origin_city_m',[0,0,0]))-origin
            f=arrays['f'];ids=item.get('ids',arrays.get('fid',np.full(len(f),item.get('fid',0),np.int32)))
            mask=item.get('mask')
            if mask is not None:f=f[mask];ids=np.asarray(ids)[mask]
            if not len(f):continue
            bounds.append(v[np.unique(f)]);input_objects+=1
            mi=arrays.get('m',np.zeros(len(arrays['f']),np.uint8));mi=mi[mask] if mask is not None else mi
            uv=arrays.get('uv');uv=uv[mask] if uv is not None and mask is not None else uv
            if item.get('vertex_colors') is not None:
                spec=item.get('material',{'name':layer+'_shared_vertex_pbr','base_color':[1,1,1,1],'roughness':.85,'metallic':0})
                colors=np.array([linear_rgba(c) for c in item['vertex_colors']],np.uint8)[np.clip(mi,0,len(item['vertex_colors'])-1)]
                batches=[(np.ones(len(f),bool),spec,colors,None)]
            else:
                batches=[]
                for slot in np.unique(mi):
                    subset=mi==slot
                    names=item.get('materials',[]);spec=self.spec(names[int(slot)] if int(slot)<len(names) else '')
                    local_uv=uv[subset] if uv is not None else None
                    if local_uv is not None and spec.get('maps'):
                        tile=spec.get('tile_m',[1,1]);tile=np.array(tile if len(tile)==2 else [tile[0],tile[0]])
                        local_uv=local_uv/np.maximum(tile,1e-9)
                    if local_uv is not None:
                        local_uv=local_uv.copy();local_uv[...,1]=1-local_uv[...,1]
                    if not spec.get('maps'):
                        local_uv=None
                    elif local_uv is None:
                        points=v[f[subset]];normal=np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0]);axis=np.argmax(abs(normal),axis=1);local_uv=np.empty((len(points),3,2),np.float32)
                        for ax in range(3):
                            take=axis==ax;axes=[k for k in range(3) if k!=ax];local_uv[take]=points[take][:,:,axes]
                        tile=np.array(spec.get('tile_m',[1,1]));local_uv/=tile[:2];local_uv[...,1]=1-local_uv[...,1]
                    batches.append((subset,spec,None,local_uv))
            for subset,spec,colors,local_uv in batches:
                # Source transport includes single-sheet pavement whose winding
                # can face down. Blender displays both sides by default; retain
                # that contract in glTF instead of culling the road from above.
                if layer=='roads':spec=dict(spec,double_sided=True)
                key=json.dumps(spec,sort_keys=True);group=groups.setdefault(key,{'v':[],'f':[],'ids':[],'colors':[],'uv':[],'spec':spec,'count':0})
                group['v'].append(v);group['f'].append(f[subset]+group['count']);group['count']+=len(v);group['ids'].append(np.asarray(ids)[subset])
                if colors is not None:group['colors'].append(colors[subset])
                if local_uv is not None:group['uv'].append(local_uv)
        if not bounds:return None
        writer=GLB(ident)
        for group in groups.values():
            writer.add(np.concatenate(group['v']),np.concatenate(group['f']),np.concatenate(group['ids']),group['spec'],
                       np.concatenate(group['colors']) if group['colors'] else None,np.concatenate(group['uv']) if group['uv'] else None)
        if not writer.triangles:return None
        name=ident+'-l'+str(lod);temporary=OUT/'tiles'/(name+'.raw.tmp')
        target=OUT/'tiles'/(name+'.glb');writer.save(temporary)
        self.proc.stdin.write(json.dumps({'input':str(temporary),'output':str(target)})+'\n');self.proc.stdin.flush()
        answer=json.loads(self.proc.stdout.readline());assert answer['status']=='passed',answer
        if keep_raw:
            comparison=OUT/'tiles'/(name+'-uncompressed.glb');temporary.replace(comparison)
            answer['gzip_raw_bytes']=len(gzip.compress(comparison.read_bytes(),mtime=0));answer['uncompressed_comparison']='tiles/'+comparison.name
        else:temporary.unlink()
        all_bounds=np.concatenate(bounds)+origin
        record={'id':ident,'layer':layer,'lod':lod,'url':'tiles/'+target.name,'bytes':target.stat().st_size,'sha256':digest(target),
                'origin_city_m':list(map(float,origin)),'bounds_city_m':[all_bounds.min(axis=0).tolist(),all_bounds.max(axis=0).tolist()],
                'triangles':writer.triangles,'objects':len(writer.doc['nodes']),'materials':len(writer.doc['materials']),
                'vertices_before_indexing':writer.vertices_before_indexing,'indexed_vertices':writer.indexed_vertices,
                'feature_count':len(writer.feature_ids),'metadata_url':metadata,'feature_ids':sorted(writer.feature_ids) if len(writer.feature_ids)<150 else None,
                'source_summary':'Preserved LA project source geometry; original acquisition years and inferred heights retained in metadata.',
                'position_quantization_error_bound_m':writer.quantization_error_m,'build_version':'stage09-v1'}
        self.resources.append(record);self.metrics.append(dict(id=ident,lod=lod,input_objects=input_objects,**answer))
        if len(self.resources)%200==0:print('ACTUAL_GLB_TILES',len(self.resources),'free_GiB',round(shutil.disk_usage(ROOT).free/1024**3,2),flush=True)
        return record
    def buildings(self):
        index=read('data/processed/stage05/mesh_index.json');colors=[m[1] for m in index['materials']]
        conn=sqlite3.connect('file:'+str(ROOT/'data/processed/stage05/buildings.sqlite')+'?mode=ro',uri=True)
        heights=np.zeros(1_200_000,np.float32)
        for fid,height in conn.execute('select i,height from buildings where active=1'):heights[fid]=height
        groups=collections.defaultdict(list)
        for row in index['meshes']:groups[row['owner']].append(row)
        for cell,rows in groups.items():
            origin=np.array(rows[0]['origin_m'],float);meta='metadata/'+cell+'.json.gz'
            for row in rows:
                if row['lod']==0 and row['visual_level']==0:continue
                a=load(row['file']);keep=~np.isin(a['fid'],list(self.excluded))
                item={'file':row['file'],'arrays':a,'mask':keep,'origin_city_m':origin,'vertex_colors':colors}
                self.resource('buildings-'+cell,'buildings',0 if row['lod']==0 else 1,origin,[item],meta)
                if row['lod']==2:
                    far=keep&(heights[np.clip(a['fid'],0,len(heights)-1)]>=self.cfg['far_building_min_height_m'])
                    # Dated source height is used for significance, not randomized.
                    self.resource('buildings-'+cell,'buildings',2,origin,[dict(item,mask=far)],meta)
        conn.close()
        # Stream metadata in cell order without rewriting the frozen source DB.
        conn=sqlite3.connect('file:'+str(ROOT/'data/processed/stage05/buildings.sqlite')+'?mode=ro',uri=True);conn.execute('PRAGMA temp_store=MEMORY')
        cursor=conn.execute('select cell,i from buildings where active=1 order by cell')
        metadata_count=0
        for cell,items in itertools.groupby(cursor,key=lambda r:r[0]):
            ids=[r[1] for r in items];records={}
            for begin in range(0,len(ids),800):
                part=ids[begin:begin+800]
                for fid,uid,height,bottom,raw in conn.execute('select i,uid,height,min_height,attrs from buildings where i in ('+','.join('?' for _ in part)+')',part):
                    if fid in self.excluded:continue
                    a=json.loads(raw);records[str(fid)]={'id':uid,'name':a.get('name') or a.get('tags',{}).get('name') or '建筑 '+str(fid),'source':a.get('source_id'),
                        'original_id':a.get('original_id'),'acquisition_year':a.get('acquisition_year'),'height_m':height,'bottom_height_m':bottom,
                        'height_evidence':a.get('height_evidence'),'height_source':a.get('height_source'),'building_type':a.get('building_type'),
                        'geometry_source':a.get('geometry_source'),'inferred':a.get('height_inferred'),'confidence':'Source-reported or inferred; not independently surveyed'}
            p=OUT/'metadata'/(cell+'.json.gz')
            with gzip.GzipFile(filename=str(p),mode='wb',mtime=0) as stream:stream.write(json.dumps(records,ensure_ascii=False,separators=(',',':')).encode())
            metadata_count+=len(records)
        conn.close();self.metadata['buildings']=metadata_count
    def terrain(self):
        index=read('data/processed/stage03/medium/tile_index.json');colors=list(yaml.safe_load((ROOT/'config/stage03.yaml').read_text())['surface']['colors'].values())
        # Use preserved road-cut and landmark-graded versions close to the camera.
        overrides={r['id']:r for r in read('data/processed/stage06/ground_index.json')['tiles']}
        overrides.update({r['id']:r for r in self.refined['ground']})
        overrides.update({r['id'].split(':',1)[1]:r for r in self.extracted['objects'] if r['kind']=='terrain'})
        for n,tile in enumerate(index['tiles']):
            ident=tile['id'];origin=np.array(tile['blender_object_translation_m'],float);fid=self.identifier('terrain:'+ident,{'name':'地形 '+ident,'source':'USGS bare-earth / NLCD2021','datum':'NAVD88','inferred':'resampling and recorded local grading; no precision improvement'})
            a=load('data/processed/stage03/medium/'+ident+'.npz')
            for lod in [1,2]:
                arrays={'v':a['v'+str(lod)],'f':a['f'+str(lod)],'m':a['m'+str(lod)]}
                self.resource('terrain-'+ident,'terrain',lod,origin,[{'arrays':arrays,'vertex_colors':colors,'fid':fid,'origin_city_m':origin}],'metadata/special.json.gz')
            if ident in overrides:
                row=overrides[ident];aa=load(row['file'])
                self.resource('terrain-'+ident,'terrain',0,origin,[{'arrays':aa,'vertex_colors':colors,'fid':fid,'origin_city_m':origin}],'metadata/special.json.gz')
    def roads(self):
        index=read('data/processed/stage04/mesh_index.json');colors=[m[1] for m in index['materials']];groups=collections.defaultdict(list)
        source_roads=read('data/processed/stage04/roads.json')
        for r in source_roads:
            fid=3_000_000+r['feature_index']
            self.features[str(fid)]={'id':'road:'+str(r['id']),'name':r.get('name') or '未命名道路','source':r.get('source_id'),'acquisition_year':r.get('capture_year'),
                                    'parameters':r.get('parameters'),'source_edit_date':r.get('edit_timestamp'),'inferred':'width and vertical profile as recorded in stage04'}
        for row in index['meshes']:
            role=row['role']
            if role in ('markings','rail_detail'):continue
            groups[(row['tile_id'],2 if role=='overview_far' else 1)].append(row)
            if role in ('airport_surface','airport_apron','rail_corridor'):
                groups[(row['tile_id'],2)].append(row)
        for (tile,lod),rows in groups.items():
            origin=np.array(rows[0]['origin_m'],float);items=[]
            for row in rows:
                a=load(row['file']);ids=np.where(a['fid']>=0,a['fid']+3_000_000,0)
                if np.any(ids==0):ids=np.where(ids==0,self.identifier('transport-surface:'+row['id'],{'name':row['role'],'source':'stage04 actual road mesh','inferred':'unioned surface cannot be assigned to one original way'}),ids)
                items.append({'arrays':a,'origin_city_m':row['origin_m'],'vertex_colors':colors,'ids':ids})
            self.resource('roads-'+tile,'roads',lod,origin,items,'metadata/special.json.gz')
        # Closest street surfaces use the actual final source08 geometry.
        rows=[r for r in self.extracted['objects'] if r['kind']=='roads'];grouped=collections.defaultdict(list)
        for row in rows:
            center=np.mean(row['bounds_city_m'],axis=0);key=tuple(np.floor(center[:2]/1000).astype(int));grouped[key].append(row)
        for key,rows in grouped.items():
            origin=np.array([key[0]*1000,key[1]*1000,0],float);items=[]
            for row in rows:
                fid=self.identifier(row['id'],{'name':row['name'],'source':'accepted stage08 / stage07 refined road or paving','inferred':'local surface grading and interfaces'})
                items.append(dict(row,fid=fid))
            self.resource('roads-la_t_x'+f'{key[0]:+04d}_y{key[1]:+04d}','roads',0,origin,items,'metadata/special.json.gz')
    def water(self):
        index=read('data/processed/stage03/medium/water_index.json');parents={p['id']:p for p in index['parents']};groups=collections.defaultdict(list)
        for row in index['pieces']:groups[row['tile_id']].append(row)
        for tile,rows in groups.items():
            origin=np.array(rows[0]['object_translation_m'],float);items=[]
            for row in rows:
                parent=parents[row['parent_source_id']];fid=self.identifier(row['parent_source_id'],{'name':parent.get('name') or '水体','source':'Census2025 hydrographic extent','height_source':parent['level_source'],'inferred':'water Z and instantaneous wetted extent unmeasured'})
                items.append({'file':row['file'],'origin_city_m':row['object_translation_m'],'fid':fid,'vertex_colors':[[.045,.17,.22,1]],'material':{'name':'water_reference','family':'water','base_color':[1,1,1,1],'roughness':.24,'metallic':0,'transmission':.10,'ior':1.333}})
            self.resource('water-'+tile,'water',2,origin,items,'metadata/special.json.gz')
    def details(self):
        groups=collections.defaultdict(list)
        for row in self.extracted['objects']:
            if row['kind'] not in ('buildings','landmarks'):continue
            if row['id'].startswith('building:'):
                fid=int(row['id'].split(':')[1]);b=next(b for b in self.refined['buildings'] if b['i']==fid)
                self.features[str(fid)]={'id':b['uid'],'name':b['name'] or '建筑 '+str(fid),'source':'stage07 final / original LARIAC and OSM','height_m':b['height_input_m'],'height_evidence':b['height_source'],'inferred':'reference-guided or neutral facade, not surveyed'}
            else:
                fid=self.identifier(row['id'],{'name':row['id'],'source':'stage06 landmark card or mapped OSM skybridge','inferred':'reference-guided approximation; see source cards'})
            if row['kind']=='landmarks':key=(row['id'],row['lod']);origin=np.array(next(a['origin_city_m'] for a in self.lm['landmarks'] if row['id']=='landmark:'+a['id']),float)
            else:
                # All components and LODs of one building share its original
                # parent origin, even when a cornice crosses the cell edge.
                # Whole-building streaming avoids having to load several dense
                # façades together just because they share a125m source cell.
                key=('detail-'+row['id'].replace(':','-'),row['lod']);origin=np.array(row['origin_city_m'],float)
            groups[key].append(dict(row,fid=fid,runtime_origin=origin))
        for (ident,lod),rows in groups.items():
            layer='landmarks' if ident.startswith('landmark:') else 'buildings';name=ident.replace(':','-')
            self.resource(name,layer,lod,rows[0]['runtime_origin'],rows,'metadata/special.json.gz',keep_raw=ident=='landmark:city_hall' and lod in [0,1])
        prototypes={r['id'].split(':',1)[1]:r for r in self.extracted['objects'] if r['kind']=='prototype'}
        prototype_records={}
        for kind in {r['kind'] for r in self.extracted['instances']}:
            row=prototypes.get(kind)
            if not row:continue
            fid=self.identifier('prototype:'+kind,{'name':kind,'source':'preserved source08 shared module','inferred':'generic template, not measured species or fixture'})
            rec=self.resource('prototype-'+kind,'vegetation' if kind=='tree_broadleaf' else 'furniture',0,np.zeros(3),[dict(row,fid=fid,origin_city_m=[0,0,0])],'metadata/special.json.gz')
            prototype_records[kind]=rec
        return {'prototypes':prototype_records,'fields':self.extracted['instances']}
    def run(self):
        start=time.perf_counter();self.details();self.terrain();self.roads();self.water();self.buildings()
        instances=self.instances if hasattr(self,'instances') else None
        self.proc.stdin.close();self.proc.wait();assert self.proc.returncode==0
        with gzip.GzipFile(filename=str(OUT/'metadata/special.json.gz'),mode='wb',mtime=0) as stream:stream.write(json.dumps(self.features,ensure_ascii=False,separators=(',',':')).encode())
        tilemap=collections.defaultdict(list)
        for row in self.resources:tilemap[row['id']].append(row)
        landmarks=[]
        for row in self.lm['landmarks']:
            card=read(row['card']);landmarks.append({'id':row['id'],'name':card['name'],'origin_city_m':row['origin_city_m'],'source_ids':[r['uid'] for r in row['replaces']],'status':'approximate_complete','card':row['card']})
        presets=read('config/stage07_final_views.json');views=[]
        for ident,label in [('historic_street','Historic Core 街景'),('civic_street','Civic Center 街景'),('records_facade','Hall of Records'),('alexandria_facade','Alexandria Hotel')]:
            if ident in presets:views.append(dict(id=ident,name=label,**presets[ident]))
        origin=read('data/processed/origin.json')
        manifest={'schema':1,'stage':9,'source_scene_sha256':digest(ROOT/self.cfg['source_scene']),'seed':self.cfg['seed'],
            'coordinate_system':{'horizontal':'EPSG:32611','vertical':'NAVD88 ground; water display estimates separate','origin_utm_m':origin['origin_utm_m'],
                'source_city_axes':'X east,Y grid north,Z up','glb_axes':'X east,Y up,Z grid south','city_to_glb_matrix':[[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]],'grid_convergence_deg':-.69748006434},
            'resources':self.resources,'landmarks':landmarks,'views':views,'instances':self.instance_output,'config':self.cfg,
            'layers':['terrain','roads','buildings','landmarks','vegetation','furniture','water'],
            'attributions':['© OpenStreetMap contributors · ODbL 1.0 · openstreetmap.org/copyright','USGS 3DEP bare-earth DEM · US public domain','U.S. Census TIGER/Line 2025 · US public domain','LA County / LARIAC dated roofline archive; height definitions and redistribution limits retained in project sources','NLCD2021 / MRLC land cover; LA City GIS; mixed years, not a same-day city snapshot','Project original synthetic PBR; Three.js and meshoptimizer MIT licenses included'],
            'source_precision_summary':'Source rooftop plans, reported/inferred heights and local visual grading retain documented uncertainty. Runtime quantization bound is computational error, not survey accuracy.',
            'lod_policy':'Tile source geometry and stable IDs preserved. City far LOD2 omits low-rise buildings only for distant overview. LOD1 contains retained complete source buildings; detailed regions add LOD0. Landmarks have independent0/1/2.',
            'cross_tile_policy':'Stable source-cell ownership; overhanging whole buildings remain with source owner. Never duplicate a body in neighbors. Terrain shared boundaries retain source samples.'}
        (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+'\n')
        texturebytes=sum(p.stat().st_size for folder in ('textures','textures-low') for p in (OUT/folder).glob('*'))
        report={'status':'actual_glb_export_completed','resources':len(self.resources),'triangles_by_lod':dict(collections.Counter({str(k):sum(r['triangles'] for r in self.resources if r['lod']==k) for k in (0,1,2)})),
                'resource_bytes':sum(r['bytes'] for r in self.resources),'texture_bytes':texturebytes,'metadata_features':self.metadata,
                'merged_material_primitives':sum(r['objects'] for r in self.resources),'max_quantization_position_bound_m':max(r['position_quantization_error_bound_m'] for r in self.resources),
                'actual_lossless_meshopt_buffer_decode_verified':all(m['actual_lossless_decode_byte_comparison'] for m in self.metrics),
                'raw_glb_bytes_before_compression':sum(m['raw_bytes'] for m in self.metrics),'compressed_glb_bytes':sum(m['compressed_bytes'] for m in self.metrics),
                'compression_comparisons':[m for m in self.metrics if 'uncompressed_comparison' in m],'seconds':time.perf_counter()-start,
                'limits':self.cfg['limits'],'input_files_count':len(self.input_files),'original_geometry_files_modified':False}
        write('work/reports/stage09/export.json',report);print('STAGE09_EXPORT_COMPLETED',json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':
    exporter=Exporter()
    # Details returns original prototype meshes plus mapped instance transforms.
    original=exporter.details
    def details_once():
        exporter.instance_output=original()
    exporter.details=details_once
    exporter.run()
