"""Bounded stage04 investigation: receipts include exact requests and hashes."""
from pathlib import Path
import sys,json,concurrent.futures
from stage02_io import Client,write_json
ROOT=Path(__file__).resolve().parents[1]
def client():
 c=Client(ROOT,{'request':{'max_json_mib':256,'retries':2,'timeout_seconds':200,'retry_statuses':[429,500,502,503,504],'disk_headroom_gib':8}})
 c.log=ROOT/'work/logs/stage04/requests.jsonl';return c
TASKS={
 'osm_sample':('https://overpass-api.de/api/interpreter',{'data':'[out:json][timeout:70];(way["highway"](34.045,-118.255,34.055,-118.24);way["railway"](34.045,-118.255,34.055,-118.24););out body geom;'}),
 'osm_boundary':('https://overpass-api.de/api/interpreter',{'data':'[out:json][timeout:60];rel(207359);out tags;'}),
 'street_service':('https://maps.lacity.org/lahub/rest/services/Street_Information/MapServer',{'f':'pjson'}),
 'metro_service':('https://maps.lacity.org/lahub/rest/services/Metro_Bus_and_Rail/MapServer',{'f':'pjson'}),
 'ladot_service':('https://maps.lacity.org/lahub/rest/services/LADOT/MapServer',{'f':'pjson'}),
 'camutcd':('https://dot.ca.gov/programs/safety-programs/camutcd',None),
}
def main(keys):
 def run(key):
  u,p=TASKS[key]
  try:
   path=client().get(u,'data/raw/stage04/research/'+key+'.response',p)
   try:
    d=json.loads(path.read_text()); result={'elements':len(d.get('elements',[])),'layers':d.get('layers'),'error':d.get('error')}
    if d.get('elements'):result['sample']=d['elements'][:2]
   except:result={'bytes':path.stat().st_size}
   print(key,json.dumps(result)[:6500],flush=True)
  except Exception as e:print(key,'FAILED',str(e),flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run,keys))
if __name__=='__main__':main(sys.argv[1:] or list(TASKS))
