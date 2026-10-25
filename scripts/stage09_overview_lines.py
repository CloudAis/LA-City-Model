"""Measured-software fallback: true major road profiles as distant line geometry."""
import json,numpy as np
from shapely.geometry import LineString
from stage09_export import Exporter,ROOT,OUT,read,write,load
from stage09_glb import GLB,digest
e=Exporter();manifest=read('outputs/stage09/resources/manifest.json');profiles=load('data/processed/stage04/road_profiles.npz')['v']
segments=[];ids=[];source_points=0
for road in read('data/processed/stage04/roads.json'):
 if road['parameters']['class'] not in ('motorway','motorway_link','trunk','primary'):continue
 p=profiles[road['profile_start']:road['profile_start']+road['profile_count']]
 if len(p)<2:continue
 source_points+=len(p);simplified=np.array(LineString(p).simplify(15,preserve_topology=False).coords)
 segments.extend(np.stack([simplified[:-1],simplified[1:]],axis=1));ids.extend([3_000_000+road['feature_index']]*(len(simplified)-1))
writer=GLB('overview-major-transport');writer.add_lines(np.array(segments),np.array(ids,np.int32))
raw=OUT/'tiles/overview-transport-lines.raw.tmp';target=OUT/'tiles/overview-transport-lines-l3.glb';writer.save(raw)
e.proc.stdin.write(json.dumps({'input':str(raw),'output':str(target)})+'\n');e.proc.stdin.flush();check=json.loads(e.proc.stdout.readline());assert check['status']=='passed';raw.unlink();e.proc.stdin.close();e.proc.wait()
points=np.array(segments).reshape(-1,3)
resource={'id':'overview-transport-lines','layer':'roads','lod':3,'overview':True,'url':'tiles/'+target.name,'bytes':target.stat().st_size,'sha256':digest(target),'origin_city_m':[0,0,0],'bounds_city_m':[points.min(axis=0).tolist(),points.max(axis=0).tolist()],
'triangles':0,'lines':writer.lines,'objects':1,'materials':1,'feature_count':len(set(ids)),'metadata_url':'metadata/special.json.gz','position_quantization_error_bound_m':writer.quantization_error_m,
'source_summary':'Source major road profile centerlines,15m planar Douglas-Peucker distant simplification,1px cartographic width; full source road surfaces are available near the camera. Distinct ways are never joined.'}
manifest['resources']=[r for r in manifest['resources'] if r['id'] not in ('overview-roads','overview-transport-lines')]+[resource]
manifest['config']=read('config/stage09.json');(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+'\n')
write('work/reports/stage09/overview_line_optimization.json',{'status':'actual_export_completed','source_profile_points':source_points,'segments':writer.lines,'source_ways':len(set(ids)),'actual_byte_decode_verified':True,'resource':resource,'visual_limit':'Distant1px road lines are cartographic LOD, not true road cross-section width. Near GLBs retain road surfaces and bridge levels.'})
print('ACTUAL_OVERVIEW_TRANSPORT_LINES',writer.lines,flush=True)
