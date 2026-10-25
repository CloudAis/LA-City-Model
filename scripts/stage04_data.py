"""Observed OSM XY/node topology; separate configured cross-section and Z estimates."""
from pathlib import Path
import json,math,re,collections,csv
import numpy as np
import shapely
from shapely.geometry import LineString,Point,mapping,shape
from shapely.strtree import STRtree
from pyproj import Transformer
import yaml
from stage03_common import references,to_geographic
from stage03_surface import Surface
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def lines(g):
 if g.geom_type=='LineString':return [g] if g.length>.01 else []
 return [p for q in getattr(g,'geoms',[]) for p in lines(q)]
def number(v,unit='m'):
 if not v:return None
 v=str(v).strip().lower()
 try:
  if ';' in v or ',' in v:return None
  if "'" in v:
   a=re.fullmatch(r"(\d+(?:\.\d+)?)'\s*(\d+(?:\.\d+)?)?\"?",v)
   if a:return float(a[1])*.3048+float(a[2] or 0)*.0254
  m=re.fullmatch(r'([\d.]+)\s*(m|meter|meters|ft|feet)?',v)
  if m:return float(m[1])*(.3048 if m[2] in ['ft','feet'] else 1)
 except ValueError:pass
 return None

def classification(t):
 h=t.get('highway')
 if h:
  if h in ['construction','proposed','raceway']:return None
  if h.endswith('_link'):return 'ramp'
  if h in ['motorway','trunk','primary','secondary','tertiary','residential','service','cycleway']:return 'parking_aisle' if h=='service' and t.get('service')=='parking_aisle' else h
  if h=='busway':return 'secondary'
  if h in ['living_street','unclassified','road','track']:return 'residential' if h not in ['track'] else 'service'
  if h in ['footway','path','pedestrian','steps','bridleway']:return 'pedestrian'
 return None

def grade_rank(t):
 try:layer=int(t.get('layer','0'))
 except ValueError:layer=0
 b=t.get('bridge','no') not in ['no','false','0',''];tun=t.get('tunnel','no') not in ['no','false','0','','building_passage']
 return layer if layer else (1 if b else -1 if tun else 0),b,tun

def parameters(t,cfg,kind):
 p=cfg['road_classes'][kind];inferred=[];one=t.get('oneway');one=one if one in ['yes','no','1','-1','true','false','reversible','alternating'] else None
 if one is None:
  one='yes' if t.get('highway')=='motorway' or t.get('junction')=='roundabout' else 'no';inferred.append('oneway_default_OSM_semantics_not_explicit_tag')
 lanes=number(t.get('lanes'))
 if lanes is None or lanes!=int(lanes) or not 1<=lanes<=16:lanes=p['lanes_one_way'] if one in ['yes','1','-1','true'] else p['lanes_two_way'];inferred.append('lanes')
 lanes=int(lanes);width=number(t.get('width'))
 if width is None or not .5<=width<=80:width=lanes*p['lane_m']+2*p['shoulder_m']+p['median_m'];inferred.append('carriageway_width_m')
 sw=p['sidewalk_m'];stag=t.get('sidewalk')
 if stag=='no':sw=0
 else:inferred.append('sidewalk_width_and_side_presence_unless_explicit')
 rank,bridge,tunnel=grade_rank(t)
 return {'class':kind,'original_highway':t.get('highway'),'oneway':one,'oneway_tag':t.get('oneway'),'lanes':lanes,'lanes_tag':t.get('lanes'),'width_m':round(width,5),'width_tag':t.get('width'),'sidewalk_m':sw,'sidewalk_tag':stag,'lane_m':p['lane_m'],'shoulder_m':p['shoulder_m'],'median_m':p['median_m'],'bridge':bridge,'tunnel':tunnel,'layer_tag':t.get('layer'),'vertical_rank':rank,'max_grade':p['max_grade'],'inferred_fields':inferred+['longitudinal_elevation_NAVD88_from_DTM_plus_structure_offset','crossfall','curb_height','shoulder_and_median_width'],'grade_evidence':'OSM_relative_layer_or_bridge_tunnel_tag; numeric_Z_and_clearance_inferred','source_accuracy_m':None}

def prepare(root=ROOT):
 cfg=yaml.safe_load((root/'config/stage04.yaml').read_text());_,origin,city,refs=references(root);surface=Surface(root);tx=Transformer.from_crs(4326,32611,always_xy=True)
 target=root/'data/processed/stage04';roads=[];other=[];stats=collections.Counter();source=[]
 for row in (target/'source_ways.jsonl').open():
  w=json.loads(row);t=w['tags'];xy=np.array(w['lonlat']);x,y=tx.transform(xy[:,0],xy[:,1]);xy=np.column_stack([x-origin[0],y-origin[1]])
  g=LineString(xy);clip=g if city.covers(g) else g.intersection(city)
  if clip.is_empty or clip.length<.05:continue
  k=classification(t)
  if k and t.get('area')!='yes':
   r={'id':'osm:way:'+str(w['id']),'source_id':w['id'],'name':t.get('name'),'tags':t,'edit_timestamp':w['timestamp'],'capture_year':None,'data_class':'processed_observed_XY_inferred_parameters_Z','node_ids':w['node_ids'],'parameters':parameters(t,cfg,k),'geometry_source':'OSM_Geofabrik_2026-10-20T20:23:47Z','tile_ids':[], 'regions':['city']}
   r['_xy']=xy;r['_g']=g;r['_clip']=clip
   if clip.intersects(refs['downtown']):r['regions'].append('downtown')
   for key in ['historic_core','civic_center']:
    if clip.intersects(refs[key]):r['regions'].append(key)
   roads.append(r);stats[k]+=1
  elif t.get('railway') or t.get('aeroway') or t.get('public_transport')=='platform' or t.get('barrier') in ['guard_rail','noise_barrier']:
   other.append({'id':'osm:way:'+str(w['id']),'source_id':w['id'],'tags':t,'node_ids':w['node_ids'],'lonlat':w['lonlat'],'edit_timestamp':w['timestamp']})
 roads.sort(key=lambda r:r['source_id']);nodeuse=collections.defaultdict(list)
 for i,r in enumerate(roads):
  r['feature_index']=i
  for j,n in enumerate(r['node_ids']):nodeuse[n].append((i,j))
 shared={n:at for n,at in nodeuse.items() if len(at)>1};del nodeuse
 # Common graph-node heights. No 2D crossing becomes a graph node.
 anchor={};step=cfg['vertical']['clearance_m']+cfg['vertical']['bridge_deck_thickness_m']+.15
 ns=list(shared);axy=np.array([roads[shared[n][0][0]]['_xy'][shared[n][0][1]] for n in ns]);az=surface(axy[:,0],axy[:,1])
 for n,base in zip(ns,az):
  if not np.isfinite(base):continue
  ranks=[roads[a]['parameters']['vertical_rank'] for a,_ in shared[n] if roads[a]['parameters']['class'] not in ['pedestrian','cycleway']]
  if not ranks:ranks=[roads[a]['parameters']['vertical_rank'] for a,_ in shared[n]]
  rank=0 if 0 in ranks or min(ranks)<0<max(ranks) else min(ranks) if min(ranks)>0 else max(ranks)
  anchor[n]=float(base)+(rank*step if rank>=0 else rank*cfg['vertical']['tunnel_depth_m'])+cfg['vertical']['surface_offset_m']
 profiles=[]
 for i,r in enumerate(roads):
  xy=r['_xy'];ds=np.linalg.norm(np.diff(xy,axis=0),axis=1);s=np.r_[0,np.cumsum(ds)];r['_s_native']=s
  spacing=5 if 'downtown' in r['regions'] else 60
  dense=np.unique(np.r_[s,np.arange(0,s[-1],spacing)]);xx=np.interp(dense,s,xy[:,0]);yy=np.interp(dense,s,xy[:,1]);base=surface(xx,yy)
  if not np.isfinite(base).all():
   bad=~np.isfinite(base);inside=shapely.covers(city,shapely.points(xx[bad],yy[bad]))
   if inside.any() or not np.isfinite(base).any():raise ValueError('NoData road surface inside city '+r['id'])
   base[bad]=np.interp(dense[bad],dense[~bad],base[~bad]);r['outside_city_context_height_fill_count']=int(bad.sum())
  rank=r['parameters']['vertical_rank'];z=base+cfg['vertical']['surface_offset_m']
  if rank>0:
   # Straight bridge deck profile over a river depression; terrain is not a measured deck.
   support=np.linspace(base[0],base[-1],len(base));z=np.maximum(base,support)+rank*step+cfg['vertical']['surface_offset_m']
  elif rank<0:z+=rank*cfg['vertical']['tunnel_depth_m']
  ids=r['node_ids'];aidx=[j for j,n in enumerate(ids) if n in anchor]
  if aidx:
   ss=s[aidx];want=np.array([anchor[ids[j]] for j in aidx]);delta=want-np.interp(ss,dense,z)
   # Anchors plus distance-limited approach corrections avoid jumping at bridge ends.
   breaks=np.r_[0,ss,s[-1]];cor=np.r_[0,delta,0];unique,idx=np.unique(breaks,return_index=True)
   # Endpoint anchors have priority over zero falloff.
   dd={0.:0.,float(s[-1]):0.}
   for a,b in zip(ss,delta):dd[float(a)]=float(b)
   for a,b in zip(ss,delta):
    for q in [a-120,a+120]:
     if 0<q<s[-1] and min(abs(ss-q))>119:dd[float(q)]=0.
   ks=np.array(sorted(dd));z+=np.interp(dense,ks,[dd[q] for q in ks])
  profiles.append({'s':dense,'v':np.column_stack([xx,yy,z])})
 print('PROFILES',len(roads),'shared_nodes',len(shared),flush=True)
 # Independently enumerate crossing ways. Grade separation comes from source tags, not XY intersection.
 gs=[r['_clip'] for r in roads];tree=STRtree(gs);pairs=tree.query(gs,predicate='crosses');cross=[]
 for ai,bi in zip(*pairs):
  a,b=int(ai),int(bi)
  if a>=b:continue
  p=gs[a].intersection(gs[b]);pts=[p] if p.geom_type=='Point' else list(getattr(p,'geoms',[]))
  for q in pts:
   if q.geom_type!='Point':continue
   # Shared OSM node on both lines proves a junction even when geometries cross internally.
   common=set(roads[a]['node_ids'])&set(roads[b]['node_ids']);connected=False
   if common:
    amap={n:j for j,n in enumerate(roads[a]['node_ids'])}
    connected=any(Point(roads[a]['_xy'][amap[n]]).distance(q)<.02 for n in common)
   ra,rb=[roads[i]['parameters']['vertical_rank'] for i in [a,b]]
   known=ra!=rb and not connected
   upper=a if ra>rb else b
   cross.append({'a':a,'b':b,'xy_m':[q.x,q.y],'connected_by_source_node':connected,'kind':'verified_shared_OSM_node' if connected else 'relative_grade_from_OSM_tags' if known else 'unresolved_non_shared_planar_crossing','upper':upper if known else None,'s_a':roads[a]['_g'].project(q),'s_b':roads[b]['_g'].project(q)})
 # Exact crossing samples permit local constraints without changing known shared-node anchors.
 for i,p in enumerate(profiles):
  p['anchors']=np.unique(roads[i]['_s_native'][[j for j,n in enumerate(roads[i]['node_ids']) if n in anchor]])
 extra=collections.defaultdict(list)
 for c in cross:
  for k in ['a','b']:extra[c[k]].append(c['s_'+k])
 for i,ss in extra.items():
  p=profiles[i];dense=np.unique(np.r_[p['s'],ss]);p['v']=np.column_stack([np.interp(dense,p['s'],p['v'][:,k]) for k in range(3)]);p['s']=dense
 adjustments=collections.Counter()
 def getz(i,s):return float(np.interp(s,profiles[i]['s'],profiles[i]['v'][:,2]))
 for iteration in range(12):
  worst=0
  for c in cross:
   if c['upper'] is None:continue
   u=c['upper'];lo=c['b'] if u==c['a'] else c['a'];su=c['s_a'] if u==c['a'] else c['s_b'];sl=c['s_b'] if u==c['a'] else c['s_a']
   need=getz(lo,sl)+step-getz(u,su)
   if need>1e-5:
    p=profiles[u];anchors=p['anchors'];left=anchors[anchors<su-1e-5];right=anchors[anchors>su+1e-5]
    ll=max(0.,su-120,float(left[-1]) if len(left) else 0.);rr=min(p['s'][-1],su+120,float(right[0]) if len(right) else p['s'][-1])
    if ll>=su or rr<=su:continue
    weight=np.maximum(0,np.minimum((p['s']-ll)/(su-ll),(rr-p['s'])/(rr-su)))
    p['v'][:,2]+=need*weight;adjustments[u]+=1;worst=max(worst,need)
  print('ANCHOR_CONSTRAINED_CLEARANCE_ITER',iteration,'max_correction',worst,flush=True)
  if worst<1e-5:break
 # Reports retain residuals and all unknown crossings.
 for c in cross:
  za,zb=getz(c['a'],c['s_a']),getz(c['b'],c['s_b']);c['z_a_m']=za;c['z_b_m']=zb
  c['estimated_deck_clearance_m']=abs(za-zb)-cfg['vertical']['bridge_deck_thickness_m'] if c['upper'] is not None else None
  c['source_a']=roads[c['a']]['id'];c['source_b']=roads[c['b']]['id']
  c['status']='source_junction' if c['connected_by_source_node'] else 'unresolved' if c['upper'] is None else 'pass_estimated_clearance' if c['estimated_deck_clearance_m']>=cfg['vertical']['clearance_m']-.001 else 'clearance_warning'
 graph_nodes={};edges=[]
 def nodekey(r,dist,q,which,source_start,source_end):
  # Actual native endpoint at an interior split is preserved. City clips get distinct IDs.
  endpoint=source_start if which==0 else source_end
  if q.distance(Point(r['_xy'][endpoint]))<.001:return 'osm:node:'+str(r['node_ids'][endpoint])
  return f'clip:{r["source_id"]}:{round(dist*1000)}'
 for i,r in enumerate(roads):
  ids=r['node_ids'];cuts=sorted(set([0,len(ids)-1]+[j for j,n in enumerate(ids) if n in shared]))
  for a,b in zip(cuts[:-1],cuts[1:]):
   g=LineString(r['_xy'][a:b+1]);pieces=lines(g if city.covers(g) else g.intersection(city))
   for k,p in enumerate(pieces):
    ends=[Point(p.coords[0]),Point(p.coords[-1])];d=[r['_g'].project(q) for q in ends];keys=[nodekey(r,dist,q,w,a,b) for w,(dist,q) in enumerate(zip(d,ends))]
    for key,q,s in zip(keys,ends,d):
     xyz=[q.x,q.y,getz(i,s)];old=graph_nodes.get(key)
     if old is None:graph_nodes[key]={'xyz_m':xyz,'incident_edges':[],'source_node_id':int(key.split(':')[-1]) if key.startswith('osm:node:') else None}
    eid=f'osm:way:{r["source_id"]}:{a}-{b}:{k}';direction=r['parameters']['oneway'];arc=1 if direction in ['yes','1','-1','true'] else 2
    e={'id':eid,'way_index':i,'from':keys[0] if direction!='-1' else keys[1],'to':keys[1] if direction!='-1' else keys[0],'directed_arc_count':arc,'length_m':p.length,'source_node_range':[a,b],'access_tags':{k:v for k,v in r['tags'].items() if k in ['access','vehicle','motor_vehicle','foot','bicycle']}}
    edges.append(e)
    for key in keys:graph_nodes[key]['incident_edges'].append(len(edges)-1)
 # Connected components are topology diagnostics, not a claim all access restrictions implemented.
 remaining=set(graph_nodes);components=[]
 while remaining:
  start=remaining.pop();stack=[start];count=0
  while stack:
   n=stack.pop();count+=1
   for ei in graph_nodes[n]['incident_edges']:
    e=edges[ei];neighbor=e['to'] if n==e['from'] else e['from']
    if neighbor in remaining:remaining.remove(neighbor);stack.append(neighbor)
  components.append(count)
 write_json(target/'road_graph.json',{'crs':'EPSG32611_project_local_m','nodes':graph_nodes,'edges':edges,'junction_rule':'only shared original OSM node IDs, never planar intersections','turn_restrictions':'relations not extracted; routing restrictions not implemented','components_node_counts':sorted(components,reverse=True)})
 verts=[];chain=[];offset=0;geo=[];grade=[];est=[]
 for i,(r,p) in enumerate(zip(roads,profiles)):
  r['profile_start']=offset;r['profile_count']=len(p['s']);offset+=len(p['s']);verts.append(p['v']);chain.append(p['s']);g=r.pop('_clip');r.pop('_xy');r.pop('_g');r.pop('_s_native')
  slopes=np.abs(np.diff(p['v'][:,2])/np.maximum(np.diff(p['s']),1e-6));mx=float(slopes.max()) if len(slopes) else 0
  grade.append({'feature_id':r['id'],'class':r['parameters']['class'],'maximum_estimated_grade':mx,'limit':r['parameters']['max_grade'],'status':'warning' if mx>r['parameters']['max_grade'] else 'within_profile_limit','inference':'ground DTM plus inferred vertical structure; not surveyed road profile'})
  r['maximum_estimated_grade']=mx;r['elevation_adjustment_iterations']=adjustments[i]
  geo.append({'type':'Feature','properties':{k:r[k] for k in ['id','name','source_id','feature_index','regions','edit_timestamp','capture_year','parameters','data_class']},'geometry':to_geographic(g,origin)})
  est.append({'feature_id':r['id'],'class':r['parameters']['class'],'width_m':r['parameters']['width_m'],'width_source':'OSM_width_tag' if 'carriageway_width_m' not in r['parameters']['inferred_fields'] else 'class_estimate','lanes':r['parameters']['lanes'],'lanes_source':'OSM_lanes_tag' if 'lanes' not in r['parameters']['inferred_fields'] else 'class_estimate','sidewalk_m':r['parameters']['sidewalk_m'],'oneway':r['parameters']['oneway'],'bridge':r['parameters']['bridge'],'tunnel':r['parameters']['tunnel'],'layer_tag':r['parameters']['layer_tag'],'height_source':'DTM_plus_inferred_profile_not_measured_deck','inferred_fields':'|'.join(r['parameters']['inferred_fields'])})
 np.savez_compressed(target/'road_profiles.npz',v=np.concatenate(verts),s=np.concatenate(chain))
 write_json(target/'roads.json',roads);write_json(target/'roads.geojson',{'type':'FeatureCollection','features':geo});write_json(target/'other_transport.json',other)
 write_json(root/'work/reports/stage04/crossings.json',cross);write_json(root/'work/reports/stage04/road_grades.json',grade)
 with (root/'work/reports/stage04/estimated_parameters.csv').open('w') as f:
  out=csv.DictWriter(f,fieldnames=list(est[0]));out.writeheader();out.writerows(est)
 report={'roads':len(roads),'classes':dict(stats),'graph_nodes':len(graph_nodes),'graph_edges':len(edges),'directed_arcs':sum(e['directed_arc_count'] for e in edges),'components':len(components),'largest_components_nodes':sorted(components,reverse=True)[:10],'geometric_crossings':len(cross),'crossing_status':dict(collections.Counter(c['status'] for c in cross)),'grade_warnings':sum(g['status']=='warning' for g in grade),'source_xy_accuracy_m':None,'profile_vertices':offset,'stage02_roads_not_duplicated':'Census kept for independent coverage/match audit only; OSM authoritative construction geometry','building_entrance_interface':'no buildings built at stage04; sidewalk height contract0.15m, actual entrances pending stage05–07'}
 write_json(root/'work/reports/stage04/data_summary.json',report);print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':prepare()
