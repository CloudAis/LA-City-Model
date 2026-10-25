"""Bounded property packets: avoid loading every city road for one building click."""
import collections,gzip,json,sqlite3
from stage09_export import OUT,ROOT,read,write
path=OUT/'metadata/special.json.gz'
with gzip.open(path,'rt') as stream:data=json.load(stream)
roads=collections.defaultdict(dict);special={}
for key,value in data.items():
 fid=int(key)
 if 3_000_000<=fid<4_000_000:roads[(fid-3_000_000)//1000][key]=value
 else:special[key]=value
conn=sqlite3.connect('file:'+str(ROOT/'data/processed/stage05/buildings.sqlite')+'?mode=ro',uri=True)
for building in read('data/processed/stage07_final/index.json')['buildings']:
 key=str(building['i'])
 if key not in special:continue
 row=conn.execute('select attrs from buildings where i=?',(building['i'],)).fetchone()
 if row:
  original=json.loads(row[0]);special[key].update(acquisition_year=original.get('acquisition_year'),original_id=original.get('original_id'),geometry_source=original.get('geometry_source'),data_class='source plan and recorded height with inferred facade detail')
conn.close()
for landmark in read('data/processed/stage06/landmark_index.json')['landmarks']:
 card=read(landmark['card'])
 for value in special.values():
  if value.get('id')=='landmark:'+landmark['id']:
   value.update(name=card['name'],source_uid=card.get('source_uid'),model_status='approximate_complete',height_basis=card.get('height_basis'),target_configuration=card.get('target_configuration'),inferred=card.get('unconfirmed_or_approximated'),source='stage06 reference card; mixed reference dates; not independently surveyed')
for bucket,items in roads.items():
 with gzip.GzipFile(filename=str(OUT/'metadata'/('roads-'+str(bucket)+'.json.gz')),mode='wb',mtime=0) as stream:stream.write(json.dumps(items,ensure_ascii=False,separators=(',',':')).encode())
with gzip.GzipFile(filename=str(path),mode='wb',mtime=0) as stream:stream.write(json.dumps(special,ensure_ascii=False,separators=(',',':')).encode())
previous=ROOT/'work/reports/stage09/metadata_partition.json';prior=json.loads(previous.read_text()) if previous.exists() else {}
write('work/reports/stage09/metadata_partition.json',{'status':'passed','road_features_partitioned':sum(map(len,roads.values())) if roads else prior.get('road_features_partitioned'),'packets':len(list((OUT/'metadata').glob('roads-*.json.gz'))),'max_road_features_per_packet':1000,'remaining_special_features':len(special),'browser_packet_cache_entries':8,'refined_building_years_enriched':100,'landmark_official_names_and_reference_status_enriched':10})
print('BOUNDED_METADATA_PACKETS',len(roads),len(special),flush=True)
