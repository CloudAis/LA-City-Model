"""Cache-first public reference acquisition; preserve URLs, TLS, bytes, dates and unknowns."""
from pathlib import Path
import urllib.request,urllib.parse,urllib.error,json,time,datetime,sqlite3
from html.parser import HTMLParser
from stage05_preserve import sha
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def fetch(url,name,root=ROOT,limit=16*1024*1024):
 p=root/'data/raw/stage05/research'/name;receipt=Path(str(p)+'.receipt.json');p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():
  r=json.loads(receipt.read_text());assert r['url']==url and r['sha256']==sha(p);return p
 for attempt in range(2):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Los-Angeles-Geographic-Model/Stage05 (data-research)'})
   with urllib.request.urlopen(req,timeout=30) as r:
    payload=r.read(limit+1)
    if len(payload)>limit:raise ValueError('Reference exceeds size budget')
    meta={'url':url,'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'http_status':r.status,'content_type':r.headers.get('Content-Type'),'last_modified_http':r.headers.get('Last-Modified'),'capture_year':None,'numeric_accuracy':None}
   p.write_bytes(payload);meta.update({'bytes':len(payload),'sha256':sha(p)});write_json(receipt,meta);return p
  except Exception as e:
   with (root/'work/logs/stage05/reference_requests.jsonl').open('a') as f:f.write(json.dumps({'url':url,'attempt':attempt+1,'error':str(e)})+'\n')
   if isinstance(e,urllib.error.HTTPError) and e.code in [401,403,404]:break
   if attempt==0:time.sleep(1)
 return None
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.skip=0
 def handle_starttag(self,t,a):
  if t in ['script','style']:self.skip+=1
 def handle_endtag(self,t):
  if t in ['script','style']:self.skip=max(self.skip-1,0)
 def handle_data(self,s):
  if not self.skip and s.strip():self.parts.append(s.strip())
def investigate(root=ROOT):
 queries={'lariac_webscenes':'LARIAC type:"Web Scene"','county_building_scenes':'"Los Angeles" building type:"Scene Service"','county_building_maps':'"Countywide Building" type:"Web Map"'}
 for key,q in queries.items():fetch('https://www.arcgis.com/sharing/rest/search?'+urllib.parse.urlencode({'f':'json','q':q,'num':30}),key+'.json',root)
 urls={'osm_height':'https://wiki.openstreetmap.org/wiki/Key:height','osm_levels':'https://wiki.openstreetmap.org/wiki/Key:building:levels','osm_roof':'https://wiki.openstreetmap.org/wiki/Key:roof:shape','us_bank_property':'https://www.usbanktower.com/','wilshire_grand_architect':'https://www.acmartin.com/portfolio/wilshire-grand-center','wilshire_grand_property':'https://www.wilshiregrandcenter.com/','city_hall_conservancy':'https://www.laconservancy.org/learn/historic-places/los-angeles-city-hall/','grand_la_architect':'https://www.gensler.com/projects/the-grand-la'}
 for key,url in urls.items():
  p=fetch(url,key+'.html',root)
  if p:
   parser=Text();parser.feed(p.read_text(errors='replace'));text='\n'.join(parser.parts);out=root/'data/processed/stage05/research'/f'{key}.txt';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(text)
 print('REFERENCE_INVESTIGATION_FINISHED',flush=True)
if __name__=='__main__':investigate()
