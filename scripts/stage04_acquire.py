"""Recorded stage04 acquisition. Cache first; small samples, then exact-ID batches."""
from pathlib import Path
import json,shutil,urllib.request
from stage04_research import client,ROOT
from stage02_io import write_json,digest
PBF_URL='https://download.geofabrik.de/north-america/us/california-latest.osm.pbf'
PBF_SHA='43741cb5381f7a78bffb7f704ee88482c22f89a79a983a9aa877d702fbcb0ff4'
def acquire(root=ROOT):
 c=client();p=root/'data/raw/stage04/osm/california-20261021.osm.pbf'
 if not p.exists():
  with urllib.request.urlopen(urllib.request.Request(PBF_URL,method='HEAD'),timeout=40) as r:size=int(r.headers['Content-Length']);headers=dict(r.headers)
  if size>2*1024**3 or shutil.disk_usage(root).free<size+11*1024**3:raise RuntimeError('PBF exceeds download/processing disk budget')
  write_json(root/'work/reports/stage04/download_budget.json',{'url':PBF_URL,'expected_bytes':size,'headers':headers,'minimum_free_bytes':8*1024**3,'decision':'within_disk_budget'})
 p=c.get(PBF_URL,'data/raw/stage04/osm/california-20261021.osm.pbf',limit=2*1024**3)
 if digest(p)!=PBF_SHA:raise RuntimeError('Remote latest differs from frozen2026-10-20 input. Preserve this response and create a new source version; do not call it a historical reconstruction.')
 base='https://maps.lacity.org/lahub/rest/services/'
 for key,service,oid in [('bridges','Street_Information/MapServer/0','ID'),('signals','LADOT/MapServer/30','ID'),('metro_stations','Metro_Bus_and_Rail/MapServer/1','OBJECTID'),('metro_lines','Metro_Bus_and_Rail/MapServer/2','OBJECTID')]:
  u=base+service;target='data/raw/stage04/'+key
  meta=c.json(u,target+'/layer.json',{'f':'json'});count=c.json(u+'/query',target+'/count.json',{'where':'1=1','f':'json','returnCountOnly':'true'})['count'];ids=sorted(set(c.json(u+'/query',target+'/ids.json',{'where':'1=1','f':'json','returnIdsOnly':'true'})['objectIds']));assert len(ids)==count
  got=[]
  for offset in range(0,len(ids),80):
   batch=ids[offset:offset+80];name='short_page_' if key in ['bridges','signals'] else 'stage04_small_page_';d=c.json(u+'/query',target+'/'+name+f'{offset:08d}.json',{'f':'json','objectIds':','.join(map(str,batch)),'outFields':'*','returnGeometry':'true','outSR':4326});assert not d.get('exceededTransferLimit') and set(x['attributes'][oid] for x in d['features'])==set(batch);got.extend(x['attributes'][oid] for x in d['features'])
  assert len(got)==len(set(got))==count and set(got)==set(ids)
  write_json(root/target/'completeness.json',{'server_count':count,'downloaded_count':len(got),'id_set_equal':True,'object_id_field':oid,'page_size':80})
 for k,part in [('markings_3a','3a'),('markings_3b','3b')]:c.get('https://dot.ca.gov/-/media/dot-media/programs/safety-programs/documents/ca-mutcd/2026/2026-camutcd-2026-'+part+'-a11y.pdf','data/raw/stage04/research/'+k+'.pdf')
 print('STAGE04_ACQUISITION_CACHE_AND_COUNTS_VERIFIED',flush=True)
if __name__=='__main__':acquire()
