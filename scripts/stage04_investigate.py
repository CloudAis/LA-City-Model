from stage04_research import client,ROOT
import concurrent.futures,json,re
base='https://maps.lacity.org/lahub/rest/services/'
tasks={
 'bbbike_index':('https://download.bbbike.org/osm/bbbike/LosAngeles/',None),
 'bbbike_poly':('https://download.bbbike.org/osm/bbbike/LosAngeles/LosAngeles.poly',None),
 'bbbike_license':('https://download.bbbike.org/osm/bbbike/',None),
 'city_centerline':(base+'Street_Information/MapServer/36',{'f':'json'}),
 'city_surface':(base+'Street_Information/MapServer/34',{'f':'json'}),
 'city_bridge':(base+'Street_Information/MapServer/0',{'f':'json'}),
 'city_signal':(base+'LADOT/MapServer/30',{'f':'json'}),
 'metro_lines':(base+'Metro_Bus_and_Rail/MapServer/2',{'f':'json'}),
 'metro_stations':(base+'Metro_Bus_and_Rail/MapServer/1',{'f':'json'}),
 'osm_copyright':('https://www.openstreetmap.org/copyright',None),
}
def run(k):
 u,p=tasks[k]
 try:
  path=client().get(u,'data/raw/stage04/research/'+k+'.response',p)
  s=path.read_text()
  try:
   d=json.loads(s);print(k,{i:d.get(i) for i in ['name','description','capabilities','editingInfo','hasZ','copyrightText']},[f['name'] for f in d.get('fields',[])],flush=True)
  except:print(k,s[:1500] if k=='bbbike_poly' else re.findall(r'href=[\"\']([^\"\']+)',s)[:65],flush=True)
 except Exception as e:print(k,'FAILED',str(e),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(run,tasks))
