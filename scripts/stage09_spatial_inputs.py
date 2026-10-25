"""Independent source positions/bounds, before looking at exported model bytes."""
import json,numpy as np
from stage09_export import ROOT,read,load,write
source=read('data/processed/stage09/extracted/index.json');landmarks=[]
for landmark in read('data/processed/stage06/landmark_index.json')['landmarks']:
 rows=[r for r in source['objects'] if r['id']=='landmark:'+landmark['id'] and r['lod']==2]
 bounds=np.array([r['bounds_city_m'] for r in rows]);landmarks.append({'id':landmark['id'],'origin_city_m':landmark['origin_city_m'],'bounds_city_m':[bounds[:,0].min(axis=0).tolist(),bounds[:,1].max(axis=0).tolist()]})
v=load('data/processed/stage04/road_profiles.npz')['v'];roads=[]
for r in read('data/processed/stage04/roads.json'):
 if r['parameters']['class'] not in ('motorway','motorway_link','trunk','primary'):continue
 start=r['profile_start'];count=r['profile_count'];a=v[start];b=v[start+count-1]
 if np.linalg.norm(b[:2]-a[:2])<1000:continue
 roads.append({'id':r['id'],'name':r['name'],'feature_id':3000000+r['feature_index'],'first_city_m':a.tolist(),'last_city_m':b.tolist()})
 if len(roads)==3:break
near={r['i']:r['origin_city_m'] for r in read('data/processed/stage07_final/index.json')['buildings']};errors=[]
for r in source['objects']:
 if r['id'].startswith('building:'):errors.append(float(np.max(abs(np.array(r['origin_city_m'])-near[int(r['id'].split(':')[1])]))))
write('work/reports/stage09/spatial_expected.json',{'landmarks':landmarks,'roads':roads,'parent_checks':len(errors),'max_parent_origin_numeric_delta_m':max(errors),'source_accuracy':'Original source geometry/heights and dated references retain their recorded uncertainty; these are computational checks, not surveying control.'})
