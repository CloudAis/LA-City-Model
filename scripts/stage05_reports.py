"""Source statistics, geographic maps and independent source/model sample audits."""
import json,sqlite3,collections,csv,gzip,math,time
from pathlib import Path
import numpy as np,shapely
from shapely.geometry import Polygon
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection,LineCollection
from stage03_common import references,polygon_parts
from stage02_io import write_json
from stage05_preserve import sha
ROOT=Path(__file__).resolve().parents[1]
def outline(ax,g,color='#333333',lw=.5):
 for p in polygon_parts(g):
  x,y=p.exterior.xy;ax.plot(x,y,color=color,lw=lw)
  for hole in p.interiors:x,y=hole.xy;ax.plot(x,y,color=color,lw=lw)
def source_reports(root=ROOT):
 root=Path(root);db=sqlite3.connect(root/'data/processed/stage05/buildings.sqlite');_,origin,city,regions=references(root);height=collections.Counter();types=collections.Counter();eras=collections.Counter();roofs=collections.Counter();stats=collections.Counter();xx=[];yy=[];zz=[];methods=[];candidates={};special={};downtown=[];lineage_diff=[];start=time.monotonic();batch=[]
 for i,uid,wkb,astr,x,y,h,visual in db.execute('SELECT i,uid,geom,attrs,cx,cy,height,visual FROM buildings WHERE active=1 ORDER BY i'):
  a=json.loads(astr);method=a['height_evidence'];height[method]+=1;types[a['building_type']]+=1;eras[str(a.get('acquisition_year'))]+=1;roofs[a['roof_shape']]+=1;xx.append(x);yy.append(y);zz.append(h);methods.append(0 if method.startswith('inferred') else 2 if method.startswith('verified') else 1);batch.append(wkb);stats['active']+=1;stats['null_height']+=h is None;stats['material_tagged']+='building:material' in a['tags'];stats['colour_tagged']+='building:colour' in a['tags'];stats['parts']+=bool(a['parts']);stats['named']+=bool(a.get('name'));stats['minimum_height_gt_zero']+=a['minimum_height_m']>0
  if len(batch)==10000:geoms=shapely.from_wkb(batch);stats['invalid_geometries']+=int((~shapely.is_valid(geoms)).sum());batch=[]
  if a.get('height_candidate_m') and a.get('OSM_county_lineage_not_independent') and a['height_candidate_m']>0:lineage_diff.append(h-a['height_candidate_m'])
  info={'i':i,'id':uid,'cell':db.execute('SELECT cell FROM buildings WHERE i=?',(i,)).fetchone()[0] if visual else None,'building_type':a['building_type'],'visual_level':visual,'height_m':h,'height_evidence':method,'parts':len(a['parts']),'name':a.get('name')}
  score=visual*100+(10 if a.get('name') else 0)+(5 if a.get('reference') else 0)
  kind=a['building_type']
  if kind not in candidates or score>candidates[kind][0]:candidates[kind]=(score,info,wkb)
  if visual or len(special)<40:
   g=shapely.from_wkb(wkb);holes=sum(len(p.interiors) for p in polygon_parts(g));parts=len(polygon_parts(g))
   for key,condition in [('courtyard',holes>0),('multipart',parts>1),('parts',bool(a['parts'])),('offset',a['minimum_height_m']>0),('roof',a['roof_shape'] not in ['flat','terrace']),('highrise',h>=100)]:
    if condition:
     ids=[k for k in special if k.startswith(key+':')]
     if len(ids)<3:special[key+':'+uid]=(score,info,wkb)
   if a.get('reference'):special['reference:'+uid]=(1000,info,wkb)
   if visual:downtown.append((i,uid,g,a))
  if stats['active']%200000==0:print('SOURCE_BUILDING_STATS',stats['active'],flush=True)
 if batch:stats['invalid_geometries']+=int((~shapely.is_valid(shapely.from_wkb(batch))).sum())
 chosen={r[1]['i']:r[1] for r in [*candidates.values(),*special.values()]}
 for item in chosen.values():
  if item['cell'] is None:item['cell']=db.execute('SELECT cell FROM buildings WHERE i=?',(item['i'],)).fetchone()[0]
 write_json(root/'work/reports/stage05/audit_selection.json',{'buildings':list(chosen.values()),'selection':'all13 available types plus explicit parts, courtyards, true multipart, min-height, pitched roofs, highrises and both published references; slope samples appended after placement','not_a_survey_accuracy_test':True})
 result={'status':'executed','counts':dict(stats),'height_sources':dict(height),'types':dict(types),'roof_shapes':dict(roofs),'source_acquisition_years':dict(eras),'geometry_valid_fraction':1-stats['invalid_geometries']/stats['active'],'numeric_height_missing_fraction':stats['null_height']/stats['active'],'independently_published_reference_count':height['verified_published_reference'],'source_reported_values_are_not_verified_measurements':True,'OSM_county_lineage_height_minus_candidate_p01_p50_p99_m':np.percentile(lineage_diff,[1,50,99]).tolist(),'seconds':time.monotonic()-start};write_json(root/'work/reports/stage05/source_statistics.json',result)
 folder=root/'work/previews/stage05';folder.mkdir(parents=True,exist_ok=True);x=np.array(xx)/1000;y=np.array(yy)/1000;z=np.array(zz);meth=np.array(methods)
 fig,ax=plt.subplots(figsize=(12,12));plot=ax.hexbin(x,y,C=z,reduce_C_function=np.max,gridsize=360,cmap='magma',vmin=0,vmax=150,mincnt=1);outline(ax,shapely.transform(city,lambda xy:xy/1000));ax.set_aspect('equal');ax.set(xlabel='Local grid east (km)',ylabel='Local grid north (km)',title='Los Angeles building height distribution\nReported and inferred heights; maximum per display bin, not a current survey');fig.colorbar(plot,ax=ax,label='Relative building height (m), display clipped at150');fig.tight_layout();fig.savefig(folder/'building_heights_city.png',dpi=150);plt.close(fig)
 colors=['#d8972b','#4c85aa','#b22538'];labels=['Inferred field/levels/type','Source-reported (mostly county lineage)','Published reference']
 fig,ax=plt.subplots(figsize=(12,12))
 for k in [1,0,2]:
  keep=meth==k;ax.scatter(x[keep],y[keep],s=1 if k<2 else 24,c=colors[k],label=labels[k],rasterized=True,alpha=.6 if k<2 else 1)
 outline(ax,shapely.transform(city,lambda xy:xy/1000));ax.set_aspect('equal');ax.legend(loc='upper right');ax.set(xlabel='Local grid east(km)',ylabel='Local grid north(km)',title='Height evidence, not a map of survey accuracy\nOriginal rooflines1992–2020 + OSM database state2026-10-20');fig.tight_layout();fig.savefig(folder/'height_evidence_city.png',dpi=150);plt.close(fig)
 fig,axes=plt.subplots(1,2,figsize=(16,8));polys=[];evidence=[];values=[]
 for i,uid,g,a in downtown:
  for poly in polygon_parts(g):polys.append(np.asarray(poly.exterior.coords));values.append(a['height_m']);evidence.append(colors[0 if a['height_evidence'].startswith('inferred') else 2 if a['height_evidence'].startswith('verified') else 1])
 for ax,title in zip(axes,['Downtown source height(m)','Downtown height evidence']):
  outline(ax,regions['downtown']);outline(ax,regions['historic_core'],'#be2a31',1.2);outline(ax,regions['civic_center'],'#be2a31',1.2);ax.set_xlim(-2200,2200);ax.set_ylim(-2200,2200);ax.set_aspect('equal');ax.set_title(title);ax.set(xlabel='Grid east(m)',ylabel='Grid north(m)')
 pc=PolyCollection(polys,array=np.array(values),cmap='viridis',edgecolor='#222222',linewidth=.08);axes[0].add_collection(pc);fig.colorbar(pc,ax=axes[0],label='Relative height(m)');axes[1].add_collection(PolyCollection(polys,facecolor=evidence,edgecolor='#222222',linewidth=.08));fig.tight_layout();fig.savefig(folder/'downtown_height_evidence.png',dpi=150);plt.close(fig)
 for name,counter in [('height_sources',height),('building_types',types),('source_years',eras),('roof_shapes',roofs)]:
  path=root/'work/reports/stage05'/f'{name}.csv'
  with path.open('w') as f:w=csv.writer(f);w.writerow(['category','count','fraction']);w.writerows((k,n,n/stats['active']) for k,n in counter.items())
 db.close();print('SOURCE_STATS_AND_MAPS_COMPLETE',stats['active'],'AUDIT_SAMPLE',len(chosen),flush=True)

def model_reports(root=ROOT):
 root=Path(root);index=json.loads((root/'data/processed/stage05/mesh_index.json').read_text());db=sqlite3.connect(root/'data/processed/stage05/buildings.sqlite');allcounts=collections.Counter();seen=set();duplicates=0;selected=json.loads((root/'work/reports/stage05/audit_selection.json').read_text());samples={x['i']:x for x in selected['buildings']};slopes=[];records={};gaps=[];counts=collections.Counter();total=0
 for i,uid,cell,astr,visual in db.execute('SELECT i,uid,cell,attrs,visual FROM buildings WHERE active=1 AND visual>0 ORDER BY height DESC LIMIT 24'):
  a=json.loads(astr);samples.setdefault(i,{'i':i,'id':uid,'cell':cell,'building_type':a['building_type'],'visual_level':visual,'height_m':a['height_m'],'height_evidence':a['height_evidence'],'parts':len(a['parts']),'name':a.get('name'),'selection_extra':'Downtown skyline top24 heights for actual same-camera source/model comparison'})
 reviewpath=root/'work/reports/stage05/height_type_review.json'
 if reviewpath.exists():
  changes=json.loads(reviewpath.read_text())['changes'];extra=[r for r in changes if r['old_height_m']!=r['new_height_m']];reported=[r for r in changes if r['geometry_changed'] and r['old_height_m']==r['new_height_m']]
  if reported:extra.append(max(reported,key=lambda r:r['new_height_m']))
  for rec in extra:
   i=rec['i'];uid,cell,astr,visual=db.execute('SELECT uid,cell,attrs,visual FROM buildings WHERE i=?',(i,)).fetchone();a=json.loads(astr);samples.setdefault(i,{'i':i,'id':uid,'cell':cell,'building_type':a['building_type'],'visual_level':visual,'height_m':a['height_m'],'height_evidence':a['height_evidence'],'parts':len(a['parts']),'name':a.get('name'),'selection_extra':'height/type review: estimate or reported height preserved with unknown use'})
 for cell in index['cells']:
  if not cell.get('placements'):continue
  with gzip.open(root/cell['placements'],'rt') as f:rows=json.load(f)['placements']
  for r in rows:
   i=r['i'];duplicates+=i in seen;seen.add(i);total+=1
   if not r['built']:gaps.append(r);continue
   if r['ground_relief_m']>=2 and len(slopes)<3:slopes.append(r)
   if i in samples:records[i]=r
   counts['base_embeds_below_lowest_sample']+=r['bottom_navd88_m']<r['ground_min_max_m'][0];counts['floor_clears_highest_sample']+=r['floor_navd88_m']>r['ground_min_max_m'][1];counts['area_change_within2percent']+=abs(r['model_area_m2']-r['geometry_area_m2'])<=r['geometry_area_m2']*.0200001
   if r['ground_unresolved'] or r['floor_navd88_m']-r['bottom_navd88_m']>8 or r.get('entrance',{} ) and r['entrance'].get('connection_unresolved'):gaps.append(r)
 for r in slopes:
  if r['i'] in samples:continue
  uid,cell,a=db.execute('SELECT uid,cell,attrs FROM buildings WHERE i=?',(r['i'],)).fetchone();a=json.loads(a);samples[r['i']]={'i':r['i'],'id':uid,'cell':cell,'building_type':a['building_type'],'visual_level':r['visual_level'],'height_m':r['height_m'],'height_evidence':r['height_evidence'],'parts':r['parts'],'name':r['name'],'selection_extra':'hillside ground relief >=2m'};records[r['i']]=r
 write_json(root/'work/reports/stage05/audit_selection.json',{'buildings':list(samples.values()),'placements':records,'not_a_survey_accuracy_test':True});write_json(root/'work/reports/stage05/placement_audit.json',{'status':'executed','records':total,'duplicate_feature_ownership':duplicates,'checks':dict(counts),'gap_and_warning_count':len(gaps),'ground_treatment_is_inferred':True,'sample_records':records});write_json(root/'data/processed/stage05/building_gaps.json',{'features':gaps,'note':'ground relief, unknown samples and entrance connections; not all buildings certified visually'})
 _,_,city,regions=references(root);fig,ax=plt.subplots(figsize=(12,12));outline(ax,city);px=[];py=[]
 for r in gaps:
  x,y=db.execute('SELECT cx,cy FROM buildings WHERE i=?',(r['i'],)).fetchone();px.append(x);py.append(y)
 ax.scatter(px,py,s=3,c='#bf4b34',alpha=.65,label='Foundation height>8m / unresolved entry or sample');outline(ax,regions['downtown'],'#267d91',1);ax.set_aspect('equal');ax.set(xlabel='Grid east(m)',ylabel='Grid north(m)',title='Building placement review gaps\nInferred plinths are not surveyed foundations');ax.legend();fig.tight_layout();fig.savefig(root/'work/previews/stage05/building_placement_gaps.png',dpi=150);plt.close(fig);db.close();assert duplicates==0;assert len(samples)>=20;print('PLACEMENT_AND_SAMPLE_AUDIT_READY',total,len(samples),len(gaps),flush=True)

def compare_saved_samples(root=ROOT):
 root=Path(root);report=json.loads((root/'work/reports/stage05/blender_check.json').read_text());db=sqlite3.connect(root/'data/processed/stage05/buildings.sqlite');placement=json.loads((root/'work/reports/stage05/audit_selection.json').read_text())['placements'];rows=[];failures=[]
 for b in report['samples']:
  i=b['i'];g,a=db.execute('SELECT geom,attrs FROM buildings WHERE i=?',(i,)).fetchone();g=shapely.from_wkb(g);a=json.loads(a)
  with np.load(root/f'work/reports/stage05/audit_meshes/{i}.npz') as d:v=d['v'];f=d['f'];mi=d['m']
  xy=v[f,:2];cross=(xy[:,1,0]-xy[:,0,0])*(xy[:,2,1]-xy[:,0,1])-(xy[:,1,1]-xy[:,0,1])*(xy[:,2,0]-xy[:,0,0]);polygons=shapely.polygons(xy[abs(cross)>1e-8]);raw_projection=shapely.union_all(polygons);numerical_holes=[Polygon(h).area for p in polygon_parts(raw_projection) for h in p.interiors if Polygon(h).area<1e-10];projected=shapely.MultiPolygon([Polygon(p.exterior,[h for h in p.interiors if not (Polygon(h).area<1e-10 and 2*Polygon(h).area/max(h.length,1e-30)<1e-8)]) for p in polygon_parts(raw_projection)]);intersection=g.intersection(projected).area;iou=intersection/g.union(projected).area;hole_expected=sum(len(p.interiors) for p in polygon_parts(g));hole_actual=sum(len(p.interiors) for p in polygon_parts(projected));edges=np.vstack([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]);_,edgecounts=np.unique(np.sort(edges,axis=1),axis=0,return_counts=True);nonmanifold=int((edgecounts!=2).sum());pl=placement[str(i)];expected_top=pl['floor_navd88_m']+a['height_m'];parapet_allowance=.7 if b['expected_record']['visual_level']>0 and a['roof_shape'] in ['flat','terrace'] and not a['parts'] and a['height_m']>2 else 0
  if a.get('reference') and a['reference'].get('spire'):expected_top=pl['floor_navd88_m']+a['reference']['total_m'];parapet_allowance=0
  height_delta=float(b['actual_maximum_z_including_shared_modules']-expected_top);expected_bottom=pl['floor_navd88_m']+a['minimum_height_m'] if a['minimum_height_m'] else pl['bottom_navd88_m'];bottom_delta=float(v[:,2].min()-expected_bottom);height_ok=abs(height_delta)<=.005 and abs(bottom_delta)<=.005;record={'id':b['id'],'building_type':a['building_type'],'height_evidence':a['height_evidence'],'source_model_footprint_iou':iou,'footprint_hausdorff_m':g.hausdorff_distance(projected),'courtyard_holes_source_model':[hole_expected,hole_actual],'actual_world_bbox_m':b['actual_bbox_m'],'height_m':a['height_m'],'actual_top_including_modules_minus_selected_height_target_m':height_delta,'actual_body_roof_top_m':float(v[:,2].max()),'actual_top_with_modules_m':b['actual_maximum_z_including_shared_modules'],'actual_bottom_minus_placement_m':bottom_delta,'height_and_ground_placement_check':height_ok,'effective_authoring_body_cells':1 if b['present_in_exactly_one_authoring_cell'] else 0,'material_indices':b['materials'],'normal_counts':b['normal_counts'],'nonmanifold_or_T_junction_edges':nonmanifold,'topology_note':'closeup wall recess grids may contain T junctions; not marked watertight when nonzero','passed_footprint_holes_materials_normals':iou>=.975 and hole_expected==hole_actual and b['present_in_exactly_one_authoring_cell'] and len(b['materials'])>=2 and height_ok};rows.append(record)
  record['projection_computational_grid_m']=None;record['projection_numerical_ring_filter']={'maximum_area_m2':1e-10,'maximum_effective_width_m':1e-8,'only_measurement_union_changed':True};record['raw_GEOS_numerical_holes_below1e-10m2']=numerical_holes;record['mesh_vertices_changed_by_projection_check']=False
  if not record['passed_footprint_holes_materials_normals']:failures.append(b['id'])
 write_json(root/'work/reports/stage05/building_sample_audit.json',{'status':'passed' if not failures else 'failed','sample_count':len(rows),'failures':failures,'buildings':rows,'calculated_model_alignment_not_source_survey_accuracy':True});db.close();assert not failures,str(failures);print('SAVED_MODEL_SOURCE_SAMPLE_COMPARISON_PASSED',len(rows),flush=True)
if __name__=='__main__':
 import sys
 {'sources':source_reports,'model':model_reports,'compare':compare_saved_samples}[sys.argv[1]]()
