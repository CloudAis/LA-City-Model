"""Build a small city-wide overview; detailed tiles remain independently available."""
from pathlib import Path
import collections,gzip,json,sqlite3
import numpy as np
import yaml
from stage09_export import Exporter,ROOT,OUT,read,load,write

def compact(a,mask):
    f=a['f'][mask];ids,inverse=np.unique(f,return_inverse=True)
    return {'v':a['v'][ids],'f':inverse.reshape(-1,3),'m':a['m'][mask],'fid':a.get('fid',np.zeros(len(a['f']),np.int32))[mask]}

exporter=Exporter();manifest=read('outputs/stage09/resources/manifest.json')
with gzip.open(OUT/'metadata/special.json.gz','rt') as stream:exporter.features=json.load(stream)
exporter.next_id=max(map(int,exporter.features))+100
colors=list(yaml.safe_load((ROOT/'config/stage03.yaml').read_text())['surface']['colors'].values())
items=[]
for tile in read('data/processed/stage03/medium/tile_index.json')['tiles']:
    a=load('data/processed/stage03/medium/'+tile['id']+'.npz')
    fid=exporter.identifier('overview-terrain:'+tile['id'],{'name':'概览地形 '+tile['id'],'source':'USGS bare earth / NLCD2021','inferred':'distant terrain LOD, not higher source precision'})
    items.append({'arrays':{'v':a['v2'],'f':a['f2'],'m':a['m2']},'origin_city_m':tile['blender_object_translation_m'],'fid':fid,'vertex_colors':colors})
exporter.resource('overview-terrain','terrain',3,np.zeros(3),items,'metadata/special.json.gz');del items
index=read('data/processed/stage05/mesh_index.json');colors=[m[1] for m in index['materials']]
conn=sqlite3.connect('file:'+str(ROOT/'data/processed/stage05/buildings.sqlite')+'?mode=ro',uri=True)
tall={i for (i,) in conn.execute('select i from buildings where active=1 and height>=70')} - exporter.excluded
items=[]
for row in index['meshes']:
    if row['lod']!=2:continue
    a=load(row['file']);mask=np.isin(a['fid'],list(tall))
    if mask.any():items.append({'arrays':compact(a,mask),'origin_city_m':row['origin_m'],'vertex_colors':colors})
exporter.resource('overview-buildings','buildings',3,np.zeros(3),items,'metadata/special.json.gz');del items
for fid in tall:
    row=conn.execute('select uid,height,attrs from buildings where i=?',(fid,)).fetchone();attrs=json.loads(row[2])
    exporter.features[str(fid)]={'id':row[0],'name':attrs.get('name') or '高层建筑 '+str(fid),'height_m':row[1],'source':attrs.get('source_id'),'acquisition_year':attrs.get('acquisition_year'),'height_evidence':attrs.get('height_evidence'),'inferred':attrs.get('height_inferred')}
conn.close()
roads=read('data/processed/stage04/roads.json');major={r['feature_index'] for r in roads if r['parameters']['class'] in ('motorway','motorway_link','trunk','primary')}
index=read('data/processed/stage04/mesh_index.json');colors=[m[1] for m in index['materials']];items=[]
for row in index['meshes']:
    if row['role'] not in ('overview_far','airport_surface','airport_apron','rail_corridor'):continue
    a=load(row['file']);mask=np.isin(a['fid'],list(major)) if row['role']=='overview_far' else np.ones(len(a['f']),bool)
    if not mask.any():continue
    a=compact(a,mask);ids=np.where(a['fid']>=0,a['fid']+3_000_000,0)
    if np.any(ids==0):ids=np.where(ids==0,exporter.identifier('overview-transport:'+row['id'],{'name':row['role'],'source':'stage04 actual transport','inferred':'recorded width and elevations'}),ids)
    items.append({'arrays':a,'origin_city_m':row['origin_m'],'vertex_colors':colors,'ids':ids})
exporter.resource('overview-roads','roads',3,np.zeros(3),items,'metadata/special.json.gz')
exporter.proc.stdin.close();exporter.proc.wait();assert exporter.proc.returncode==0
for row in exporter.resources:row['overview']=True;row['source_summary']='City-wide distant overview: terrain sourceLOD2, source buildings>=70m, major highways/primary roads/rail/airport. Small buildings remain available in near tiles.'
manifest['resources']=[r for r in manifest['resources'] if not r.get('overview')]+exporter.resources
with gzip.GzipFile(filename=str(OUT/'metadata/special.json.gz'),mode='wb',mtime=0) as stream:stream.write(json.dumps(exporter.features,ensure_ascii=False,separators=(',',':')).encode())
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+'\n')
write('work/reports/stage09/overview_export.json',{'status':'actual_export_completed','resources':exporter.resources,'compression':exporter.metrics,'selected_source_highrise_ids':len(tall),'omission':'Distant overview intentionally omits source buildings below70m; all retained ordinary buildings remain in local LOD1 resources.'})
print('ACTUAL_CITY_OVERVIEW',[(r['layer'],r['triangles']) for r in exporter.resources],flush=True)
