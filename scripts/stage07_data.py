"""Select the two existing work windows, preserve real XY and record every inference."""
from pathlib import Path
import collections,gzip,json,math,sqlite3,xml.etree.ElementTree as ET
import numpy as np,shapely
from shapely.geometry import Point,LineString,Polygon,shape,mapping
from shapely.ops import nearest_points
from pyproj import Transformer
from stage03_common import references,local_features,polygon_parts
from stage04_geometry import Ground
from stage03_surface import Surface
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
class WorkingGround:
 def __init__(self,root=ROOT):
  self.root=root;self.base=Ground(root);self.surface=Surface(root);self.overrides={tuple(t['ij']):t for t in json.loads((root/'data/processed/stage06/ground_index.json').read_text())['tiles']};self.cache={}
 def __call__(self,x,y):
  x=np.asarray(x,float);y=np.asarray(y,float);z=self.base(x,y);ij=np.floor(np.column_stack([x,y])/1000).astype(int)
  for key in set(map(tuple,ij)):
   if key not in self.overrides:continue
   if key not in self.cache:
    t=self.overrides[key]
    with np.load(self.root/t['file']) as a:v=a['v'].astype(float);f=a['f'].copy()
    tris=shapely.polygons(v[f,:2]);self.cache[key]=(v,f,shapely.STRtree(tris),tris)
   v,f,tree,tri=self.cache[key];ids=np.flatnonzero(np.all(ij==key,axis=1));xy=np.column_stack([x[ids]-key[0]*1000,y[ids]-key[1]*1000]);pairs=tree.query(shapely.points(xy),predicate='intersects');found={int(a):int(b) for a,b in zip(*pairs)}
   if found:
    ii=np.array(list(found));jj=np.array(list(found.values()));a=v[f[jj,0]];ab=v[f[jj,1]]-a;ac=v[f[jj,2]]-a;aq=xy[ii]-a[:,:2];den=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0];good=np.abs(den)>1e-10;ii=ii[good];ab=ab[good];ac=ac[good];a=a[good];aq=aq[good];den=den[good];u=(aq[:,0]*ac[:,1]-aq[:,1]*ac[:,0])/den;w=(ab[:,0]*aq[:,1]-ab[:,1]*aq[:,0])/den;z[ids[ii]]=a[:,2]+u*ab[:,2]+w*ac[:,2]
  missing=~np.isfinite(z)
  if missing.any():z[missing]=self.surface(x[missing],y[missing])
  return z
def prepare(root=ROOT):
 cfg=json.loads((root/'config/stage07.json').read_text());_,origin,_,refs=references(root);tx=Transformer.from_crs(4326,32611,always_xy=True);excluded={r['i'] for a in json.loads((root/'data/processed/stage06/landmark_index.json').read_text())['landmarks'] for r in a['replaces']};db=sqlite3.connect(root/'data/processed/stage05/buildings.sqlite');rows=db.execute('select i,uid,cell,geom,attrs from buildings where visual=2 and active=1 order by i').fetchall();wanted={i for i,*_ in rows}-excluded;idx=json.loads((root/'data/processed/stage05/mesh_index.json').read_text());placements={};oldinstances=[]
 for cell in idx['cells']:
  if cell['id'] not in {row[2] for row in rows}:continue
  with gzip.open(root/cell['placements'],'rt') as f:a=json.load(f)
  placements.update({x['i']:x for x in a['placements'] if x['i'] in wanted});oldinstances.extend(x for x in a['instances'] if x['fid'] in wanted)
 ground=WorkingGround(root);furniture=[];entrances=[];counters=collections.Counter();seen=set()
 for region in cfg['regions']:
  path=root/'data/raw/stage07/osm'/(region+'.osm');tree=ET.parse(path).getroot()
  for n in tree.findall('node'):
   tags={a.attrib['k']:a.attrib['v'] for a in n.findall('tag')};x,y=tx.transform(float(n.attrib['lon']),float(n.attrib['lat']));x-=origin[0];y-=origin[1]
   if not refs[region].covers(Point(x,y)):continue
   uid='osm:node:'+n.attrib['id']
   if tags.get('entrance') and tags['entrance']!='no':entrances.append({'id':uid,'xy_m':[x,y],'tags':tags,'last_edit':n.attrib['timestamp']})
   kind=None
   if tags.get('natural')=='tree':kind='tree_palm' if any(q in str(tags).lower() for q in ['washingtonia','phoenix','palm']) else 'tree_broadleaf'
   elif tags.get('highway')=='street_lamp':kind='street_lamp'
   elif tags.get('amenity')=='bench':kind='bench'
   elif tags.get('amenity')=='waste_basket':kind='waste_bin'
   elif tags.get('emergency')=='fire_hydrant':kind='hydrant'
   elif tags.get('barrier')=='bollard':kind='bollard'
   elif tags.get('highway') in ['traffic_signals','crossing']:counters['mapped_'+tags['highway']]+=1
   if not kind or uid in seen:continue
   z=float(ground(np.array([x]),np.array([y]))[0]);assert np.isfinite(z);height=cfg['trees']['palm_height_m'] if kind=='tree_palm' else cfg['trees']['unknown_height_m'] if kind=='tree_broadleaf' else None;source_height=tags.get('height');reported_height=None
   try:
    if source_height:
     reported_height=float(source_height.lower().replace('m','').strip())
     if not 1<reported_height<80:reported_height=None
   except ValueError:reported_height=None
   if reported_height is not None and kind.startswith('tree'):height=reported_height
   seen.add(uid);counters[kind]+=1;furniture.append({'id':uid,'kind':kind,'region':region,'xyz_m':[x,y,z+.04],'source':'small OSM map snapshot2026-10-23','original_id':n.attrib['id'],'source_last_edit':n.attrib['timestamp'],'tags':tags,'height_m':height,'height_evidence':'source_reported_unverified' if reported_height else 'inferred_config_default' if kind.startswith('tree') else 'inferred_asset_dimensions','position_evidence':'OSM mapped point; source numeric accuracy unknown','source_file':str(path.relative_to(root)),'appearance_evidence':'generic source-class template; exact manufacturer/species/fixture geometry unknown'})
 buildings=[];newinstances=[];entry_rows=[];changes=[];entry_window_conflicts=[]
 for i,uid,cell,blob,attrs in rows:
  if i not in wanted:continue
  g=shapely.orient_polygons(shapely.from_wkb(blob));a=json.loads(attrs);p=placements[i];e=p['entrance'];region='historic_core' if 'historic_core' in a['regions'] else 'civic_center'
  if e is None:
   buildings.append({'i':i,'uid':uid,'cell':cell,'region':region,'name':a.get('name'),'building_type':a['building_type'],'geometry':mapping(g),'attrs':a,'source_floor_navd88_m':p['floor_navd88_m'],'floor_navd88_m':p['floor_navd88_m'],'floor_delta_m':0.,'height_m':a['height_m'],'height_evidence':a['height_evidence'],'old_placement':p,'entry':None,'entry_gap':'No inherited or corroborated entrance; no doorway or floor adjustment invented'})
   entry_rows.append({'uid':uid,'region':region,'unresolved':True,'reason':'No inherited entrance; retained building, no invented doorway','delta_m':0.})
   for ins in oldinstances:
    if ins['fid']==i and ins['kind']=='window_frame':
     item=dict(ins);item.update(kind='window_masonry_reveal',region=region,source='stage05 actual recessed aperture; neutral frame geometry inferred');newinstances.append(item)
   continue
  xy=np.array(e['position_xy_m']);closest=min(polygon_parts(g),key=lambda q:q.exterior.distance(Point(xy))).exterior;point=closest.interpolate(closest.project(Point(xy)));d=closest.project(point);pa=np.array(closest.interpolate(max(0,d-.08)).coords[0]);pb=np.array(closest.interpolate(min(closest.length,d+.08)).coords[0]);tangent=pb-pa;tangent/=max(np.linalg.norm(tangent),1e-9);out=np.array([tangent[1],-tangent[0]]);angle=math.atan2(tangent[1],tangent[0]);xy=np.array(point.coords[0]);walkxy=xy+out*3.0;walkz=float(ground(walkxy[:1],walkxy[1:])[0]);oldfloor=p['floor_navd88_m'];oldrise=oldfloor-walkz;delta=-min(cfg['entry']['max_floor_lowering_m'],oldrise-cfg['entry']['target_corrected_rise_m']) if oldrise>cfg['entry']['max_existing_rise_before_visual_floor_correction_m'] else 0.;floor=oldfloor+delta;rise=floor-walkz;steps=math.ceil(max(0,rise)/cfg['entry']['step_max_rise_m']);unresolved=steps>32 or rise<-.25;source=e['source'];matches=[q for q in entrances if g.boundary.distance(Point(q['xy_m']))<1.5 and Point(q['xy_m']).distance(Point(xy))<8]
  if matches:source=min(matches,key=lambda q:Point(q['xy_m']).distance(Point(xy)))['id']+' (corroborates existing entry vicinity; doorway not relocated)'
  building={'i':i,'uid':uid,'cell':cell,'region':region,'name':a.get('name'),'building_type':a['building_type'],'geometry':mapping(g),'attrs':a,'source_floor_navd88_m':oldfloor,'floor_navd88_m':floor,'floor_delta_m':delta,'height_m':a['height_m'],'height_evidence':a['height_evidence'],'old_placement':p,'entry':{'xy_m':xy.tolist(),'outward_xy':out.tolist(),'rotation_z':angle,'walk_xy_m':walkxy.tolist(),'walk_navd88_m':walkz,'rise_m':rise,'steps':steps,'unresolved':unresolved,'source':source,'field_class':'mapped entrance vicinity if OSM ID; otherwise inferred street-facing position; all doorway forms inferred','accessibility_compliance':'not established by geometry screening'}};buildings.append(building);entry_rows.append({'uid':uid,'name':a.get('name'),'region':region,'old_floor_m':oldfloor,'new_floor_m':floor,'delta_m':delta,'walk_m':walkz,'old_rise_m':oldrise,'new_rise_m':rise,'source':source,'unresolved':unresolved,'basis':'explicit visual floor correction to inherited road/terrain interface; no XY shift or building height randomization'})
  if delta:changes.append({'i':i,'uid':uid,'floor_delta_m':delta,'height_unchanged':True,'footprint_xy_unchanged':True,'class':'inferred_visual_site_adjustment'})
  # Reuse real existing aperture positions; upgraded frame prototypes stay shared.
  for ins in oldinstances:
   if ins['fid']!=i or ins['kind'] not in ['window_frame']:continue
   # An inherited procedural window must not put a frame across a new door.
   relative=np.array(ins['xyz'][:2])-xy;along=float(np.dot(relative,tangent));normal=float(np.dot(relative,out));bottom=ins['xyz'][2]+delta-ins['scale'][2]/2;top=ins['xyz'][2]+delta+ins['scale'][2]/2
   if abs(along)<.95+ins['scale'][0]/2 and abs(normal)<.45 and bottom<floor+2.35 and top>floor:
    entry_window_conflicts.append({'i':i,'window_xyz':ins['xyz'],'reason':'suppress inferred frame crossing inferred/mapped doorway; source footprint/body retained'});continue
   item=dict(ins);item['kind']='window_metal_reveal' if a['building_type'] in ['office_highrise','parking_structure'] else 'window_masonry_reveal';item['xyz']=list(ins['xyz']);item['xyz'][2]+=delta;item['region']=region;item['source']='stage05 actual recessed aperture location; frame detail inferred';newinstances.append(item)
  for kind,xyz,scale in [('entry_glazed_double',[*xy,floor+1.15],[1.8,.14,2.3]),('canopy_brackets',[*(xy+out*.65),floor+2.65],[2.5,1.6,.18])]:newinstances.append({'kind':kind,'xyz':xyz,'scale':scale,'rotation':angle,'fid':i,'region':region,'source':source+'; shape inferred'})
 write_json(root/'data/processed/stage07/buildings.json',buildings);write_json(root/'data/processed/stage07/module_placements.json',{'instances':newinstances,'prototype_geometry_inferred':True,'entry_window_conflicts_suppressed':entry_window_conflicts});write_json(root/'data/processed/stage07/street_features.json',{'features':furniture,'counts':dict(counters),'unmapped_features_not_invented':True,'source_snapshot_date_not_collection_date':True});write_json(root/'work/reports/stage07/entry_review.json',{'status':'calculated_inferred_adjustments_pending_saved_model_check','buildings':entry_rows,'floor_corrections':changes,'numeric_source_accuracy_unknown':True});write_json(root/'data/processed/stage07/work_regions.geojson',{'type':'FeatureCollection','crs':{'type':'name','properties':{'name':'project-local metres EPSG32611 minus fixed origin'}},'features':[{'type':'Feature','properties':{'id':r,'area_m2':refs[r].area},'geometry':mapping(refs[r])} for r in cfg['regions']]});print('NEAR_BUILDINGS',len(buildings),dict(collections.Counter(b['region'] for b in buildings)),'MODULES',len(newinstances),'SOURCE_STREET_FEATURES',dict(counters),'FLOOR_CORRECTIONS',len(changes),'UNRESOLVED_ENTRIES',sum(x['unresolved'] for x in entry_rows),'DOOR_WINDOW_CONFLICTS_REMOVED',len(entry_window_conflicts),flush=True)
if __name__=='__main__':prepare()
