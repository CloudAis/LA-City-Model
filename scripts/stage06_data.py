"""Landmark source cards, exact selected plans, identity replacement and georeferencing."""
import json,math,sqlite3,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np,shapely
from shapely import affinity
from shapely.geometry import Point,LineString,mapping
from pyproj import Transformer
from stage02_io import write_json,digest
from stage04_geometry import Ground
from stage03_surface import Surface
ROOT=Path(__file__).resolve().parents[1]
FEATURES={
 'us_bank_tower':(['stepped cruciform/cylindrical shaft','pale stone piers and dark recessed glazing','circular tiered lantern/crown','Fifth Street podium/entry'],['exact stone coursing and service facade','current lobby and roof equipment','commercial marks omitted; no obsolete Skyslide']),
 'wilshire_grand':(['curved glass shaft distinct from large low podium','asymmetric sail crown and needle','floor bands and vertical mullions','curved entry atrium/plaza'],['crown control points and exact roof/antenna height definitions','unseen rear podium equipment','glass coating and lighting states']),
 'city_hall':(['source lower-building courtyards','three-tier civic composition','vertical window rhythm and setbacks','pyramidal crown, observation colonnade and arched civic entry'],['historic sculpted reliefs/inscriptions','precise crown profiles and recess dimensions','courtyard service entrances']),
 'disney_hall':(['multiple curved stainless-steel sails with distinct orientations','main acoustic volume and lower glass foyer','metal panel seam organization','Grand Avenue entry stairs/terraces'],['no original CATIA/NURBS construction surfaces','individual6000+ panel layout and back-of-house junctions','shells are sampled editable approximations; not fabrication geometry']),
 'the_broad':(['porous diagonal veil surrounding dark vault','central concave oculus','lifted entrance corner and glass lobby','roof daylight grid'],['exact2500-panel unique fabrication geometry','roof layout partly inferred: no confirmed overhead photo','expansion work/status and unseen back facade']),
 'union_station':(['Mission Moderne long west facade with arched glazing','clock tower/belfry and red tile roof','waiting-hall/ticket-hall differentiated roof volumes','court/patio connections'],['east/rear roofs and exact patio boundaries','clock face design, inscriptions and reliefs','no interior or full platform rebuild']),
 'griffith_observatory':(['central planetarium and two smaller telescope domes','cream Art Deco wings and fluted entrance','copper dome ribs/slit and upper terraces','real Mount Hollywood slope and south retaining platform'],['exact dome rise and post2006 underground layout','Art Deco sculptural panels','site elevation text and source ele are not height control']),
 'hollywood_sign':(['nine actual letter line locations and directions','custom editable block letter outlines with real holes','rear steel posts and triangulated braces','terrain-following separate letter baselines'],['steel member sections/anchor depths and precise corrugation','letter outlines estimated from photos, not original shop drawings','supports inferred except broad observed structure']),
 'dodger_stadium':(['baseball diamond and northeast outfield opening','horseshoe decks with differentiated seat colors','pavilions, hexagonal scoreboards and canopy','concourse piers, light towers and outer circulation'],['seating aisles/row counts and exact structural spans','2025/26 renovation geometry not fully verified','retaining bowl/field datum photo-estimated from ground']),
 'memorial_coliseum':(['real oval footprint and field void','east peristyle arches and central Olympic cauldron','post2019 south Scholarship Club Tower','cardinal seating tiers, circulation openings and exterior colonnade'],['exact club facade dimensions/seat counts','sculptures, inscriptions and sponsor graphics','bowl/field ground offsets inferred; not structural survey'])}
def prepare(root=ROOT):
 cfg=json.loads((root/'config/stage06.json').read_text());origin=np.array(cfg['origin_utm_m']);tx=Transformer.from_crs(32611,4326,always_xy=True);forward=Transformer.from_crs(4326,32611,always_xy=True)
 research=json.loads((root/'data/processed/stage06/research_registry.json').read_text());osmdb=sqlite3.connect(root/'data/processed/stage05/osm_buildings.sqlite');db=sqlite3.connect(root/'data/processed/stage05/buildings.sqlite');ground=Ground(root);surface=None;items=[];all_replacements={};features=[]
 for p in cfg['landmarks']:
  ident=p['id'];refs=next(r for r in research['landmarks'] if r['id']==ident);letters=[]
  if ident=='hollywood_sign':
   tree=ET.parse(root/'data/raw/stage06/research/hollywood_sign.osm').getroot();nodes={n.attrib['id']:n for n in tree.findall('node')};ways={w.attrib['id']:w for w in tree.findall('way')};rel=next(r for r in tree.findall('relation') if r.attrib['id']=='1706337')
   for member in rel.findall('member'):
    if member.attrib['type']!='way':continue
    w=ways[member.attrib['ref']];tags={x.attrib['k']:x.attrib['v'] for x in w.findall('tag')};coords=[]
    for n in w.findall('nd'):
     a=nodes[n.attrib['ref']].attrib;x,y=forward.transform(float(a['lon']),float(a['lat']));coords.append([x-origin[0],y-origin[1]])
    letters.append({'uid':'osm:way:'+w.attrib['id'],'letter':tags['inscription'],'xy_m':coords,'source_tags':tags,'last_edit':w.attrib['timestamp']})
   g=shapely.union_all([LineString(a['xy_m']) for a in letters]).buffer(.3);tags={'name':'Hollywood Sign','source':'small OSM API map2026-10-23, not the stage04 PBF snapshot'};edited=rel.attrib['timestamp'];source_kind='source_line_locations_letter_shapes_inferred'
  else:
   blob,tags,edited=osmdb.execute('select geom,tags,edited from features where uid=?',(p['osm_uid'],)).fetchone();g=shapely.from_wkb(blob);tags=json.loads(tags);source_kind='OSM source building/roofline plan; not independently surveyed ground walls'
  center=np.array(g.centroid.coords[0]);rect=np.array(g.minimum_rotated_rectangle.exterior.coords)[:4];ds=np.roll(rect,-1,axis=0)-rect;angles=[math.atan2(d[1],d[0]) for d in ds];theta=min([((a+math.pi/2)%math.pi)-math.pi/2 for a in angles],key=abs)
  if ident=='hollywood_sign':theta=0.
  def local(h):return affinity.rotate(affinity.translate(h,xoff=-center[0],yoff=-center[1]),-math.degrees(theta),origin=(0,0))
  localg=local(g);samples=shapely.get_coordinates(shapely.segmentize(g,8));samples=np.vstack([samples,center]);zz=ground(samples[:,0],samples[:,1]);miss=~np.isfinite(zz)
  if miss.any():
   if surface is None:surface=Surface(root)
   zz[miss]=surface(samples[miss,0],samples[miss,1])
  assert np.isfinite(zz).all(),ident+' missing terrain'
  # Stadium playing fields and sign letter anchors require a separate local terrain solution.
  if ident in ['hollywood_sign','dodger_stadium','memorial_coliseum','griffith_observatory']:
   if surface is None:surface=Surface(root)
   z=float(surface(center[:1],center[1:])[0])+.16
   for letter in letters:
    xy=np.asarray(letter['xy_m']);zletter=surface(xy[:,0],xy[:,1]);letter['baseline_NAVD88_m']=float(max(zletter))+.22;letter['height_m']=p['height_m'];letter['anchor_method']='maximum native10m bare-earth samples at source line endpoints +0.22m, inferred footings'
  else:
   if surface is None:surface=Surface(root)
   z=float(surface(center[:1],center[1:])[0])+.16
  replacements=[];candidate_rows=[];b=g.bounds
  for i,uid,blob,attrs,cell in db.execute('select b.i,b.uid,b.geom,b.attrs,b.cell from buildings b join spatial s on s.i=b.i where b.active=1 and s.minx<? and s.maxx>? and s.miny<? and s.maxy>?',(b[2]+1,b[0]-1,b[3]+1,b[1]-1)):
   h=shapely.from_wkb(blob);inter=h.intersection(g).area;coverage=inter/max(h.area,1e-9);iou=inter/max(h.union(g).area,1e-9);a=json.loads(attrs);rawids=str(tags.get('lacounty:bld_id','')).split(';');explicit=uid=='lariac6:'+rawids[0] or uid==p['osm_uid'] or (uid.startswith('lariac6:') and uid.split(':')[1] in rawids)
   chosen=bool(explicit or coverage>.55 or iou>.30)
   if inter>1 or explicit:candidate_rows.append({'i':i,'uid':uid,'cell':cell,'source_area_m2':h.area,'intersection_area_m2':inter,'coverage':coverage,'iou':iou,'explicit_source_identity':explicit,'replace':chosen})
   if chosen:
    assert i not in all_replacements,(ident,uid,'duplicate landmark selection');all_replacements[i]=ident;replacements.append({'i':i,'uid':uid,'cell':cell,'basis':'explicit source identity' if explicit else 'source plan overlap >55% of proxy or IoU>30%','intersection_coverage':coverage})
  parts=[]
  for uid,blob,t,k in osmdb.execute('select f.uid,f.geom,f.tags,f.kind from features f join spatial s on s.i=f.i where f.kind="part" and s.minx<? and s.maxx>? and s.miny<? and s.maxy>?',(b[2],b[0],b[3],b[1])):
   h=shapely.from_wkb(blob);a=json.loads(t)
   if h.intersection(g).area/max(h.area,1e-9)>.55:parts.append({'uid':uid,'geometry':mapping(local(h)),'tags':a})
  lonlat=list(tx.transform(*(center+origin)));matrix=[[math.cos(theta),-math.sin(theta),0,float(center[0])],[math.sin(theta),math.cos(theta),0,float(center[1])],[0,0,1,z],[0,0,0,1]]
  selected=[dict(photo,reference_number=j+1) for j,photo in enumerate(refs['reference_photos']) if j+1 in p['selected_reference_numbers']];confirmed,unknown=FEATURES[ident]
  card=dict(p,name=refs['name'],status='approximate_complete_pending_model_checks',longitude_latitude=lonlat,origin_city_m=[*center,z],rotation_z_radians=theta,rotation_from_grid_east_degrees=math.degrees(theta),asset_to_city_matrix=matrix,local_plan_bounds_m=list(localg.bounds),source_plan_area_m2=g.area,source_uid=p['osm_uid'],source_plan_kind=source_kind,source_last_edit=edited,source_tags=tags,local_plan=mapping(localg),parts=parts,letters=letters,replaces=replacements,replacement_candidates=candidate_rows,ground={'datum':'NAVD88','source':'selected stage03/04 terrain + USGS bare-earth fallback','footprint_min_m':float(zz.min()),'footprint_max_m':float(zz.max()),'asset_origin_z_m':z,'method':'median for stadium/sign, maximum sampled8m boundary for other sites; inferred site foundation, not survey','road_or_plaza_interface':'local foreground site patches inferred; existing traffic XY unchanged'},confirmed_identifying_features=confirmed,unconfirmed_or_approximated=unknown,reference_photographs=selected,official_pages=refs['official_pages'],view_coverage={'front':'selected licensed photographs','side':'oblique photos; not complete measured orthographic survey','rear':'explicit blind spot unless selected image shows it','top':'source plan available; overhead photo available for Disney/Dodger/Coliseum; others partial/unknown'},model_data_class='processed_observed plan + source-reported/published heights + inferred editable architectural detail; no third-party models',photo_license_policy='Only linked image-specific CC/PD photographs copied; attribution retained; photographs not used as textures; other web photos linked only',target_era_policy=refs['model_vintage_policy'])
  folder=root/'data/processed/stage06/cards';write_json(folder/(ident+'.json'),card);items.append(card);features.append({'type':'Feature','properties':{'id':'landmark:'+ident,'name':refs['name'],'source_uid':p['osm_uid'],'status':'approximate','region':'downtown' if abs(center[0])<=2000 and abs(center[1])<=2000 else 'independent_'+ident},'geometry':mapping(g)})
  print('SOURCE_IDENTITY',ident,'replacements',len(replacements),'parts',len(parts),'origin',card['origin_city_m'],'angle',card['rotation_from_grid_east_degrees'],flush=True)
 write_json(root/'data/processed/stage06/landmarks_city_local.geojson',{'type':'FeatureCollection','crs':{'type':'name','properties':{'name':'project-local EPSG32611 minus origin; metres'}},'features':features})
 write_json(root/'data/processed/stage06/landmark_index.json',{'landmarks':[{'id':a['id'],'card':'data/processed/stage06/cards/'+a['id']+'.json','origin_city_m':a['origin_city_m'],'rotation_z_radians':a['rotation_z_radians'],'replaces':a['replaces']} for a in items],'replaced_source_buildings':len(all_replacements),'source_checkpoint_sha256':digest(root/cfg['source_checkpoint']),'actual_independent_positions_preserved':True})
 write_json(root/'work/reports/stage06/identity_review.json',{'status':'source_overlap_rules_executed','replacements':len(all_replacements),'per_landmark':{a['id']:a['replacement_candidates'] for a in items},'unknown':'county roofline proxies and present building-wall plans may disagree; nonselected neighbors retained'})
 return items
if __name__=='__main__':prepare()
