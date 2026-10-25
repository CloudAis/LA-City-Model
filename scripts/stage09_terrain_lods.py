"""LOD1/2 from the final graded terrain, with locked shared outer tile samples."""
import gzip,json,struct,subprocess
import numpy as np
from stage09_export import Exporter,ROOT,OUT,read,write
e=Exporter();manifest=read('outputs/stage09/resources/manifest.json')
reports=[]
for source in [r for r in manifest['resources'] if r['layer']=='terrain' and r['lod']==0]:
 for lod,target,error in [(1,6000,.025),(2,2000,.15)]:
  path=ROOT/'work/cache/stage09/terrain-lod.bin';path.parent.mkdir(parents=True,exist_ok=True)
  result=subprocess.run(['node',str(ROOT/'viewer/simplify.mjs'),str(OUT/source['url']),str(path),str(target),str(error)],check=True,capture_output=True,text=True)
  blob=path.read_bytes();njson=struct.unpack_from('<I',blob)[0];header=json.loads(blob[4:4+njson]);offset=4+njson;n=header['vertices'];nf=header['indices']//3
  v=np.frombuffer(blob,dtype='<f4',count=n*3,offset=offset).reshape(-1,3).copy();offset+=n*12;colors=np.frombuffer(blob,dtype=np.uint8,count=n*4,offset=offset).reshape(-1,4).copy();offset+=n*4
  f=np.frombuffer(blob,dtype='<u4',count=nf*3,offset=offset).reshape(-1,3).copy();v=v[:,[0,2,1]];v[:,1]*=-1
  face=np.rint(colors[f,:3].mean(axis=1)).astype(np.uint8);palette,mi=np.unique(face,axis=0,return_inverse=True);a={'v':v,'f':f,'m':mi.astype(np.int32)}
  origin=np.array(source['origin_city_m']);fid=(source.get('feature_ids') or [6_100_003])[0]
  row=e.resource(source['id'],'terrain',lod,origin,[{'arrays':a,'origin_city_m':origin,'vertex_colors':np.column_stack([palette/255,np.ones(len(palette))]).tolist(),'fid':fid}],'metadata/special.json.gz')
  row['source_summary']='Final accepted graded/cut terrain; shared outer tile vertices locked; interior/hole-border simplification with recorded error. OriginalLOD0 retained.'
  reports.append(dict(id=source['id'],lod=lod,**header));path.unlink()
e.proc.stdin.close();e.proc.wait();assert e.proc.returncode==0
new={(r['id'],r['lod']):r for r in e.resources};manifest['resources']=[new.get((r['id'],r['lod']),r) for r in manifest['resources']]
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+'\n')
write('work/reports/stage09/graded_terrain_lods.json',{'status':'passed_actual_exports','tiles':len(reports)//2,'outer_tile_boundary_samples_locked':True,'quadric_error_is_not_source_accuracy':True,'lods':reports})
print('ACTUAL_GRADED_TERRAIN_LODS',[(r['id'],r['lod'],r['output_triangles']) for r in reports if r['input_triangles']>10000],flush=True)
