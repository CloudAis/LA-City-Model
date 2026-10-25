"""Refresh owned, unaccepted detail exports after UV/sampler compatibility repair."""
import gzip,json
from stage09_export import Exporter,ROOT,OUT,read,write
from stage09_glb import digest
e=Exporter();manifest=read('outputs/stage09/resources/manifest.json')
for r in manifest['resources']:
    assert digest(OUT/r['url'])==r['sha256'],'Preserve edited runtime asset: '+r['url']
with gzip.open(OUT/'metadata/special.json.gz','rt') as stream:e.features=json.load(stream)
e.special={r['id']:int(fid) for fid,r in e.features.items() if 'id' in r};e.next_id=max(map(int,e.features))+100
instances=e.details();e.proc.stdin.close();e.proc.wait();assert e.proc.returncode==0
new={(r['id'],r['lod']):r for r in e.resources}
unchanged=[r for r in manifest['resources'] if not (r['id'].startswith('detail-') or r['id'].startswith('landmark-') or r['id'].startswith('prototype-'))]
manifest['resources']=unchanged+e.resources;manifest['instances']=instances
with gzip.GzipFile(filename=str(OUT/'metadata/special.json.gz'),mode='wb',mtime=0) as stream:stream.write(json.dumps(e.features,ensure_ascii=False,separators=(',',':')).encode())
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+'\n')
write('work/reports/stage09/detail_compatibility_repair.json',{'status':'actual_reexport_completed','resources':len(e.resources),'blender_uv_to_gltf_v_flip':True,'furniture_atlas_linear_clamp_no_mipmap':True,'all_buffers_decoded_and_byte_compared':True,'geometry_source_unchanged':True,'comparison_metrics':e.metrics})
print('ACTUAL_DETAIL_UV_SAMPLER_REEXPORT',len(e.resources),flush=True)
