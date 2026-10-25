"""Cached factual research and explicitly licensed reference photographs only."""
from pathlib import Path
import concurrent.futures,datetime,hashlib,html,json,re,time
from urllib.parse import urljoin
import requests
ROOT=Path(__file__).resolve().parents[1]
UA={'User-Agent':'LA-Urban-Model-Research/1.0 (non-commercial local architectural research)'}
LANDMARKS=[
 ('us_bank_tower','U.S. Bank Tower','U.S. Bank Tower Los Angeles',['https://www.usbanktower.com/']),
 ('wilshire_grand','Wilshire Grand Center','Wilshire Grand Center',['https://www.acmartin.com/portfolio/wilshire-grand-center','https://www.thorntontomasetti.com/project/wilshire-grand-center']),
 ('city_hall','Los Angeles City Hall','Los Angeles City Hall',['https://www.laconservancy.org/learn/historic-places/los-angeles-city-hall/','https://lacity.gov/government/history']),
 ('disney_hall','Walt Disney Concert Hall','Walt Disney Concert Hall exterior',['https://www.laphil.com/visit/walt-disney-concert-hall','https://www.musiccenter.org/visit-explore/visit-explore/campus/walt-disney-concert-hall/']),
 ('the_broad','The Broad','The Broad museum exterior',['https://www.thebroad.org/about','https://dsrny.com/project/the-broad']),
 ('union_station','Los Angeles Union Station','Los Angeles Union Station exterior',['https://www.unionstationla.com/history/']),
 ('griffith_observatory','Griffith Observatory','Griffith Observatory exterior',['https://griffithobservatory.org/about/','https://griffithobservatory.org/explore/exhibits/the-building/']),
 ('hollywood_sign','Hollywood Sign','Hollywood Sign',['https://www.hollywoodsign.org/history','https://www.hollywoodsign.org/the-sign-at-a-glance']),
 ('dodger_stadium','Dodger Stadium','Dodger Stadium aerial',['https://www.mlb.com/dodgers/ballpark','https://www.mlb.com/dodgers/ballpark/information/guide']),
 ('memorial_coliseum','Los Angeles Memorial Coliseum','Los Angeles Memorial Coliseum aerial',['https://www.lacoliseum.com/coliseum-history/','https://www.lacoliseum.com/venue-information/'])]
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def text_only(s):return html.unescape(re.sub('<[^>]+>',' ',re.sub(r'<(script|style)\b[^>]*>.*?</\1>',' ',s,flags=re.S|re.I)))
def fetch(url,path,params=None):
 receipt=Path(str(path)+'.receipt.json')
 if path.exists() and receipt.exists():
  meta=json.loads(receipt.read_text());assert sha(path)==meta['sha256'];return meta
 errors=[]
 for attempt in range(3):
  try:
   r=requests.get(url,params=params,headers=UA,timeout=45);r.raise_for_status();path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(r.content)
   meta={'requested_url':url,'url':r.url,'params':params,'downloaded_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'http_status':r.status_code,'bytes':len(r.content),'sha256':sha(path),'headers':{k:r.headers[k] for k in ['content-type','last-modified','etag'] if k in r.headers}};write(receipt,meta);return meta
  except Exception as e:errors.append(str(e));time.sleep(attempt+1)
 return {'requested_url':url,'status':'unavailable','errors':errors}
def research(item):
 ident,name,query,urls=item;raw=ROOT/'data/raw/stage06/research'/ident;processed=ROOT/'data/processed/stage06/research'/ident;pages=[]
 for j,u in enumerate(urls):
  p=raw/f'official_{j}.html';m=fetch(u,p)
  # Text/markup research cache contains no embedded remote image downloads.
  if p.exists():
   t=re.sub(r'\s+',' ',text_only(p.read_text(errors='replace'))).strip();processed.mkdir(parents=True,exist_ok=True);(processed/f'official_{j}.txt').write_text(t+'\n')
   links=[{'text':text_only(label).strip(),'url':urljoin(m['url'],url)} for url,label in re.findall(r'<a[^>]+href=[\"\x27]([^\"\x27]+)[\"\x27][^>]*>(.*?)</a>',p.read_text(errors='replace'),re.S|re.I)]
   write(processed/f'official_{j}_links.json',links)
  pages.append(m|{'local_path':str(p.relative_to(ROOT)) if p.exists() else None,'copy_policy':'HTML/text for internal factual research only; no remote copyright images copied or redistributed'})
 params={'action':'query','format':'json','generator':'search','gsrsearch':query+' filetype:bitmap -interior','gsrnamespace':6,'gsrlimit':6,'prop':'imageinfo','iiprop':'url|extmetadata|size','iiurlwidth':900}
 p=raw/'commons_query.json';meta=fetch('https://commons.wikimedia.org/w/api.php',p,params);photos=[]
 if p.exists():
  rows=json.loads(p.read_text()).get('query',{}).get('pages',{}).values()
  for row in sorted(rows,key=lambda x:x.get('index',0)):
   if not row.get('imageinfo'):continue
   info=row['imageinfo'][0];e=info.get('extmetadata',{});v=lambda k:text_only(e.get(k,{}).get('value','')).strip();license=v('LicenseShortName');licenseurl=v('LicenseUrl');allowed=license.startswith(('CC BY','CC0','Public domain')) or v('Copyrighted')=='False'
   if not allowed:continue
   url=info.get('thumburl',info['url']);photo=raw/('reference_'+str(len(photos)+1)+'.jpg');m=fetch(url,photo)
   if not photo.exists():continue
   photos.append({'title':row['title'],'author':v('Artist'),'credit':v('Credit'),'license':license,'license_url':licenseurl,'source_page':info['descriptionurl'],'download_url':url,'original_url':info['url'],'description':v('ImageDescription'),'date_description':v('DateTimeOriginal'),'local_path':str(photo.relative_to(ROOT)),'sha256':sha(photo),'downloaded_at_utc':m['downloaded_at_utc'],'allowed_copy_basis':'Commons image-specific free license or explicit public-domain metadata; metadata retained','view_class':'pending_actual_visual_review'})
 return {'id':ident,'name':name,'official_pages':pages,'reference_photos':photos,'query_receipt':meta,'model_vintage_policy':'mixed dated reference views; target permanent exterior configuration through frozen OSM2026-10-20; unverified 2026 changes remain unknown; not a same-date photogrammetric reconstruction'}
def run():
 cached=ROOT/'data/processed/stage06/research_registry.json'
 if cached.exists():
  rows=json.loads(cached.read_text())['landmarks']
  for r in rows:
   for photo in r['reference_photos']:assert sha(ROOT/photo['local_path'])==photo['sha256'],photo['local_path']
  for receipt in (ROOT/'data/raw/stage06/research').rglob('*.receipt.json'):
   target=Path(str(receipt)[:-len('.receipt.json')]);assert sha(target)==json.loads(receipt.read_text())['sha256']
  print('FROZEN_RESEARCH_CACHE_VERIFIED; curated supplements and image choices preserved',flush=True);return
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:rows=list(ex.map(research,LANDMARKS))
 write(ROOT/'data/processed/stage06/research_registry.json',{'landmarks':rows,'external_models_used':False,'photographs_used_as_textures':False,'osm_license':'ODbL 1.0; © OpenStreetMap contributors; https://www.openstreetmap.org/copyright','date_fields_not_equivalent':True})
 print('RESEARCH_CACHED',[(r['id'],len(r['reference_photos']),[p.get('http_status',p.get('status')) for p in r['official_pages']]) for r in rows],flush=True)
if __name__=='__main__':run()
