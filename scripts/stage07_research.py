"""Small, cached OSM map samples plus free-license appearance references."""
from pathlib import Path
import concurrent.futures,json,re
import numpy as np
from pyproj import Transformer
from stage03_common import references
from stage06_research import fetch,text_only,sha,write
ROOT=Path(__file__).resolve().parents[1]
def run():
 cached=ROOT/'data/processed/stage07/research_registry.json'
 if cached.exists() and json.loads(cached.read_text()).get('actual_visual_curation_complete'):
  for a in json.loads(cached.read_text())['appearance']:
   for p in a['photos']:assert sha(ROOT/p['local_path'])==p['sha256']
  print('STAGE07_CURATED_RESEARCH_CACHE_VERIFIED');return
 cfg=json.loads((ROOT/'config/stage07.json').read_text());_,origin,_,refs=references(ROOT);tx=Transformer.from_crs(32611,4326,always_xy=True);sources=[]
 for region in cfg['regions']:
  xy=np.array(refs[region].exterior.coords)+origin;x,y=tx.transform(xy[:,0],xy[:,1]);bbox=','.join(map(str,[min(x),min(y),max(x),max(y)]));path=ROOT/'data/raw/stage07/osm'/(region+'.osm');m=fetch('https://api.openstreetmap.org/api/0.6/map',path,{'bbox':bbox});assert path.exists(),m;sources.append(m|{'region':region,'local_path':str(path.relative_to(ROOT)),'license':'ODbL1.0 ©OpenStreetMap contributors https://www.openstreetmap.org/copyright','capture_year':'unknown; editing timestamps per element, download time not survey time','source_state':'live small map snapshot2026-10-23, distinct from stage04 frozen PBF2026-10-20'})
 def research(item):
  raw=ROOT/'data/raw/stage07/research'/item['id'];p=raw/'official.html';meta=fetch(item['official_page'],p)
  if p.exists():
   text=re.sub(r'\s+',' ',text_only(p.read_text(errors='replace')));q=ROOT/'data/processed/stage07/research'/item['id'];q.mkdir(parents=True,exist_ok=True);(q/'official.txt').write_text(text+'\n')
  query=raw/'commons.json';fetch('https://commons.wikimedia.org/w/api.php',query,{'action':'query','format':'json','generator':'search','gsrsearch':item['photo_query']+' filetype:bitmap','gsrnamespace':6,'gsrlimit':4,'prop':'imageinfo','iiprop':'url|extmetadata','iiurlwidth':1000});photos=[]
  if query.exists():
   for page in sorted(json.loads(query.read_text()).get('query',{}).get('pages',{}).values(),key=lambda x:x.get('index',0)):
    if not page.get('imageinfo'):continue
    info=page['imageinfo'][0];e=info.get('extmetadata',{});v=lambda k:text_only(e.get(k,{}).get('value','')).strip();lic=v('LicenseShortName')
    if not (lic.startswith(('CC BY','CC0','Public domain')) or v('Copyrighted')=='False'):continue
    target=raw/('reference_'+str(len(photos)+1)+'.jpg');m=fetch(info.get('thumburl',info['url']),target)
    if target.exists():photos.append({'title':page['title'],'author':v('Artist'),'credit':v('Credit'),'license':lic,'license_url':v('LicenseUrl'),'source_page':info['descriptionurl'],'local_path':str(target.relative_to(ROOT)),'sha256':sha(target),'capture_date_description':v('DateTimeOriginal') or 'unknown','downloaded_at_utc':m['downloaded_at_utc'],'status':'unselected_until_actual_visual_review'})
  return item|{'official_page_receipt':meta,'photos':photos,'copy_policy':'only image-specific free/PD photos downloaded; website remote images not copied'}
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:appearance=list(pool.map(research,cfg['appearance_research']))
 write(ROOT/'data/processed/stage07/research_registry.json',{'osm_samples':sources,'appearance':appearance,'same_day_snapshot_claim':False});print('STAGE07_REAL_RESEARCH_SAVED',[(a['id'],len(a['photos'])) for a in appearance],flush=True)
if __name__=='__main__':run()
