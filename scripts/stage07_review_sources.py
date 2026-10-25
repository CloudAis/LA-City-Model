"""Persist the actual visual subject review; never auto-select search results by name."""
import json
from pathlib import Path
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def run(root=ROOT):
 p=root/'data/processed/stage07/research_registry.json';r=json.loads(p.read_text());supp=json.loads((root/'data/processed/stage07/hall_records_supplement.json').read_text());pages={x['id']:x for x in json.loads((root/'data/processed/stage07/official_supplement.json').read_text())}
 decisions={
 'alexandria_hotel':[(False,'Interview portrait, no exterior'),(True,'Actual exterior; beige pressed-brick/terracotta cornice, 2008 view'),(False,'Interview portrait, no exterior'),(False,'Banquet interior, not exterior')],
 'spring_arcade':[(True,'Roof radio towers and context only; facade blind spot'),(True,'Actual Spring Arcade arched entry, 2008 view')],
 'la_times':[(True,'Entrance and wall material only; full massing not visible'),(True,'Low-angle facade piers/window material; full massing not visible'),(True,'Portal detail only'),(True,'Inscription/cladding detail only')],
 'hall_records':[(False,'1956 cityscape predates1962 building'),(False,'City Hall is a different building'),(False,'Statue photograph, different subject'),(False,'Hall of Justice1924 construction is a different building')],
 'la_theatre':[(True,'Actual Los Angeles Theatre facade and marquee, 2006'),(False,'Los Angeles Theatre Center is a different venue')]}
 for a in r['appearance']:
  for photo,(keep,why) in zip(a['photos'],decisions[a['id']]):assert digest(root/photo['local_path'])==photo['sha256'];photo.update(status='viewed_selected_limited_exterior_evidence' if keep else 'viewed_rejected_subject',review_reason=why)
  if a['id'] in pages:a['official_supplement']=pages[a['id']]
  if a['id']=='hall_records':
   for q in supp:q.update(status='viewed_selected_limited_exterior_evidence',review_reason='Correct1962 Hall of Records; night/front and historic rear partial views; missing current complete elevations')
   a['photos'].extend(q for q in supp if q['local_path'] not in {p['local_path'] for p in a['photos']})
  a['model_use']='Qualitative material/identity review; no photo texture copying, no claim all architectural forms reproduced';a['blind_spots']='Incomplete/dated elevation coverage, no survey drawings or measured door/window schedules'
 r['actual_visual_curation_complete']=True;r['photos_as_textures']=False;r['all_facades_reference_matched']=False;write_json(p,r)
 source=[]
 for x in r['osm_samples']:
  source.append({'name':'OSM small map '+x['region'],'publisher':'OpenStreetMap contributors','original_page':'https://www.openstreetmap.org/copyright','download_url':x['url'],'downloaded_at_utc':x['downloaded_at_utc'],'collection_year':'unknown; object edit timestamps are not survey dates','content_update':'per XML timestamp/version, not an all-city date','page_update':'not applicable API','coverage':x['params']['bbox'],'horizontal_crs':'EPSG:4326 WGS84 numeric coordinates; source positional accuracy unknown','vertical_datum':'not supplied; ele not mixed with NAVD88','horizontal_unit':'degrees -> EPSG32611 metres -> city local origin','height_unit':'source tag retained; parsed simple numeric metre height only, otherwise inferred','accuracy':'unknown','terms':x['license'],'redistribution':'ODbL1.0 attribution/share-alike obligations; raw extracts retained separately','local_path':x['local_path'],'sha256':x['sha256']})
 for a in r['appearance']:
  for q in a['photos']:source.append(q|{'dataset':'appearance reference '+a['name'],'horizontal_crs':'image, not georectified','vertical_datum':'not applicable','accuracy':'not a measurement source','content_year':q['capture_date_description'],'webpage_update':'not equated with capture year','redistribution':'image-specific '+q['license']+'; author/source/license retained','not_used_as_texture':True})
 for p in sorted((root/'data/raw/stage07').rglob('*.receipt.json')):
  q=Path(str(p)[:-len('.receipt.json')]);a=json.loads(p.read_text());assert digest(q)==a['sha256']
 write_json(root/'data/processed/stage07/source_registry.json',{'datasets':source,'official_pages_in_research_registry':True,'copyright_html_internal_research_only':True,'mixed_dates_not_same_date_snapshot':True,'source_body_height_and_type_limits_inherited':True});print('STAGE07_ACTUAL_REFERENCE_REVIEW_SAVED',len(source),flush=True)
if __name__=='__main__':run()
