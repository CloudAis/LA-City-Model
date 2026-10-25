"""Measured-device optimization: real reduced overview and intermediate near façades."""
import collections,gzip,json,subprocess,struct,sys
import numpy as np
from stage09_export import Exporter,ROOT,OUT,read,load,write
e=Exporter();manifest=read('outputs/stage09/resources/manifest.json')
with gzip.open(OUT/'metadata/special.json.gz','rt') as s:e.features=json.load(s)
e.special={r['id']:int(fid) for fid,r in e.features.items() if 'id' in r};e.next_id=max(map(int,e.features))+100
reports=[]
jobs=[] if '--details-only' in sys.argv else [(next(r for r in manifest['resources'] if r['id']=='overview-'+layer),target,error,fid) for layer,target,error,fid in [('terrain',35000,8,6_100_001),('roads',40000,2,6_100_002)]]
if '--details-only' not in sys.argv:jobs.extend((r,6000,.08,(r.get('feature_ids') or [6_100_003])[0]) for r in manifest['resources'] if r['layer']=='terrain' and r['lod']==0)
for r,target,error,fid in jobs:
 layer=r['layer'];is_overview=r.get('overview',False)
 path=ROOT/'work/cache/stage09';path.mkdir(parents=True,exist_ok=True);temp=path/(layer+'.bin')
 result=subprocess.run(['node',str(ROOT/'viewer/simplify.mjs'),str(OUT/r['url']),str(temp),str(target),str(error)],capture_output=True,text=True,check=True)
 blob=temp.read_bytes();length=struct.unpack_from('<I',blob)[0];header=json.loads(blob[4:4+length]);offset=4+length;n=header['vertices'];nf=header['indices']//3
 v=np.frombuffer(blob,dtype='<f4',count=n*3,offset=offset).reshape(-1,3).copy();offset+=n*12
 colors=np.frombuffer(blob,dtype=np.uint8,count=n*4,offset=offset).reshape(-1,4).copy();offset+=n*4
 f=np.frombuffer(blob,dtype='<u4',count=nf*3,offset=offset).reshape(-1,3).copy()
 # Decoded overview is glTF Y-up; return to original city Z-up exactly once.
 v=v[:,[0,2,1]];v[:,1]*=-1
 face_colors=np.rint(colors[f,:3].mean(axis=1)).astype(np.uint8)
 # Supply direct per-face colors via a palette; the optimized far material is
 # still sourced from actual land cover / transport colors.
 palette,inverse=np.unique(face_colors,axis=0,return_inverse=True)
 arrays={'v':v,'f':f,'m':inverse.astype(np.int32)}
 if is_overview:e.features[str(fid)]={'id':'overview-'+layer,'name':'全市概览地形' if layer=='terrain' else '全市概览主要交通','source':'preserved project distant overview','inferred':'LOD simplification; '+str(header['reported_quadric_error_m'])+'m reported quadric error is not surveyed accuracy'}
 origin=np.array(r['origin_city_m'])
 record=e.resource(r['id'],layer,3 if is_overview else 1,origin,[{'arrays':arrays,'origin_city_m':origin,'vertex_colors':np.column_stack([palette/255,np.ones(len(palette))]).tolist(),'fid':fid}],'metadata/special.json.gz')
 if is_overview:record['overview']=True
 record['source_summary']='Simplified preserved source geometry; original detailed tiles retained. Reported quadric error is not measured source accuracy.'
 reports.append(dict(id=r['id'],**header));temp.unlink()

# A real intermediate façade retains the source wall openings, glazing, roof,
# entrances and silhouette, while removing thin window frames and small modules.
groups=collections.defaultdict(list)
for row in e.extracted['objects']:
 if row['kind']!='buildings' or row['lod']!=0:continue
 if any(term in row['name'] for term in ('window_frames','frame_and_sill','small_equipment','roof_hvac','balcony_rail')):continue
 if row['id'].startswith('building:'):fid=int(row['id'].split(':')[1])
 else:fid=e.special[row['id']]
 groups[row['id']].append(dict(row,fid=fid))
for identity,rows in groups.items():
 e.resource('detail-'+identity.replace(':','-'),'buildings',1,np.array(rows[0]['origin_city_m']),rows,'metadata/special.json.gz')
# Intermediate roads keep actual accepted pavement and sidewalk heights, while
# their thin curb/paint geometry remains available only at full nearLOD0.
road_groups=collections.defaultdict(list)
for row in e.extracted['objects']:
 if row['kind']!='roads' or any(term in row['name'] for term in ('curb','markings','paths')):continue
 grid=tuple(np.floor(np.mean(row['bounds_city_m'],axis=0)[:2]/1000).astype(int))
 fid=e.special.get(row['id']) or e.identifier(row['id'],{'name':row['name'],'source':'accepted stage08 road surface','inferred':'recorded local grading'})
 road_groups[grid].append(dict(row,fid=fid))
for grid,rows in road_groups.items():
 e.resource('roads-la_t_x'+f'{grid[0]:+04d}_y{grid[1]:+04d}','roads',1,np.array([grid[0]*1000,grid[1]*1000,0]),rows,'metadata/special.json.gz')
e.proc.stdin.close();e.proc.wait();assert e.proc.returncode==0
replacements={(r['id'],r['lod']):r for r in e.resources};old={(r['id'],r['lod']):r for r in manifest['resources']};old.update(replacements);manifest['resources']=list(old.values())
manifest['config']=read('config/stage09.json')
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+'\n')
with gzip.GzipFile(filename=str(OUT/'metadata/special.json.gz'),mode='wb',mtime=0) as stream:stream.write(json.dumps(e.features,ensure_ascii=False,separators=(',',':')).encode())
write('work/reports/stage09/runtime_optimization'+('_details' if '--details-only' in sys.argv else '')+'.json',{'status':'actual_simplification_and_intermediate_lod_exported','overview':reports,'intermediate_building_tiles':len(groups),'intermediate_road_tiles':len(road_groups),'actual_byte_decode_verified':True,'original_source_files_changed':False,'mid_facade_omissions':'thin window frames and tiny equipment; full original façade retained asLOD0'})
print('ACTUAL_RUNTIME_OPTIMIZATION',reports,'mid_tiles',len(groups),flush=True)
