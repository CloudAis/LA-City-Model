"""Source/geometry coverage and limits; small numerical error is not survey accuracy."""
import collections,json
from pathlib import Path
import numpy as np,shapely
from shapely.geometry import shape
from stage02_io import write_json,digest
ROOT=Path(__file__).resolve().parents[1]
def build(root=ROOT):
 bs=json.loads((root/'data/processed/stage07/buildings.json').read_text());ground=json.loads((root/'data/processed/stage07/ground_index.json').read_text());ge=json.loads((root/'data/processed/stage07/geometry_index.json').read_text());r=json.loads((root/'data/processed/stage07/research_registry.json').read_text());entry=json.loads((root/'work/reports/stage07/entry_review.json').read_text());fixtures=json.loads((root/'data/processed/stage07/street_features.json').read_text());seams=[]
 for t in ground['tiles']:
  with np.load(root/t['file']) as a:v=a['v'];f=a['f'];m=a['m']
  with np.load(root/t['source_file']) as a:
   if 'v' in a:sv=a['v'];sf=a['f']
   else:lod=ge['terrain_active_lod'][t['id']];sv=a['v'+str(lod)];sf=a['f'+str(lod)]
  assert np.array_equal(v[:,:2],sv[:,:2]) and np.array_equal(f,sf);boundary=(v[:,0]<1e-5)|(v[:,0]>1000-1e-5)|(v[:,1]<1e-5)|(v[:,1]>1000-1e-5);error=float(np.max(abs(v[boundary,2]-sv[boundary,2]))) if boundary.any() else 0;assert error==0;area0=np.abs(np.linalg.det(np.stack([sv[sf[:,1],:2]-sv[sf[:,0],:2],sv[sf[:,2],:2]-sv[sf[:,0],:2]],axis=1))).sum()/2;area1=np.abs(np.linalg.det(np.stack([v[f[:,1],:2]-v[f[:,0],:2],v[f[:,2],:2]-v[f[:,0],:2]],axis=1))).sum()/2;assert area1==area0;seams.append({'tile':t['id'],'boundary_vertices_checked':int(boundary.sum()),'new_boundary_difference_m':error,'xy_and_faces_exactly_equal':True,'road_cut_plan_area_difference_m2':float(area1-area0),'max_visual_z_edit_m':t['max_visual_z_edit_m']})
 write_json(root/'work/reports/stage07/terrain_seams.json',{'status':'passed_new_boundaries_unchanged','tiles':seams,'inherited_stage06_max_numeric_boundary_delta_m':json.loads((root/'data/processed/stage06/ground_index.json').read_text())['max_boundary_numeric_delta_m'],'source_accuracy':'inherited USGS1m/10m original resolution and provenance; no improved survey precision from grading','vertical_datum':'NAVD88 metres, unchanged; inferred edits in separate NPZ files'})
 report={'status':'computed_with_documented_gaps','regions':dict(collections.Counter(b['region'] for b in bs)),'source_buildings':len(bs),'near_buildings_with_missing_entry':sum(b['entry'] is None for b in bs),'entry_unresolved':sum(e['unresolved'] for e in entry['buildings']),'floor_corrections':len(entry['floor_corrections']),'height_evidence':dict(collections.Counter(b['height_evidence'] for b in bs)),'building_type_evidence':dict(collections.Counter(b['attrs']['type_basis'] for b in bs)),'source_acquisition_years':dict(collections.Counter(str(b['attrs']['acquisition_year']) for b in bs)),'mapped_street_features':fixtures['counts'],'placed_street_features':len(ge['street_instances']),'new_door_and_window_shapes':'inferred; old source-footprint apertures are inherited procedural positions, not a survey schedule','verified_complete_facades':0,'research_buildings':len(r['appearance']),'selected_licensed_photo_references':sum(p['status'].startswith('viewed_selected') for a in r['appearance'] for p in a['photos']),'explicit_gaps':['Most near facades and entries lack complete measured elevation/door/window/fixture schedules; detailed modules are approximate','83 source heights are unverified county-import reports;20 are explicitly inferred; no independently verified height in this103-building subset','Alexandria source-derived17 levels conflict with roughly8 visible reference rows; no unsupported height or floor count correction asserted','One building has no entry; one inherited entry floor is below nearby sampled grade by2.835m and remains unresolved','New grading is inferred visual adjustment, not measured engineering earthworks or accessibility design','Older full-city terrain, transportation and height issues remain outside07 correction set','Curbs, intersections and tactile ramps retain stage04 source/inference limits; some local interfaces remain approximate','Mapped trees5 only; no imagined complete planting inventory, exact species/height mostly unknown','Spring Arcade official page endpoints404; photo references limited, no current full elevation source','Real-time automatic LOD/streaming/viewer and GPU FPS not implemented or measured']};write_json(root/'work/reports/stage07/coverage_statistics.json',report)
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.patches import Polygon as Patch,Patch as Legend
 regions=json.loads((root/'data/processed/stage07/work_regions.geojson').read_text())['features'];fig,axes=plt.subplots(1,2,figsize=(13,8),layout='constrained')
 for ax,region in zip(axes,regions):
  name=region['properties']['id'];g=shape(region['geometry']);x0,y0,x1,y1=g.bounds
  for b in bs:
   if b['region']!=name:continue
   gg=shape(b['geometry']);polys=list(gg.geoms) if hasattr(gg,'geoms') else [gg]
   for p in polys:
    ax.add_patch(Patch(np.array(p.exterior.coords),facecolor='#d78337' if b['floor_delta_m'] else '#718a9c',edgecolor='#354655',linewidth=.4))
    for hole in p.interiors:ax.add_patch(Patch(np.array(hole.coords),facecolor='white',edgecolor='#354655',linewidth=.4))
   if b['entry']:x,y=b['entry']['xy_m'];ax.plot(x,y,'s',color='#c72c40' if b['entry']['unresolved'] else '#173922',markersize=2)
  for q in ge['street_instances']:
   if q['region']==name:ax.plot(*q['xyz'][:2],'^' if q['kind'].startswith('tree') else '.',color='#337d2f' if q['kind'].startswith('tree') else '#e5b900',markersize=5)
  ax.plot(*g.exterior.xy,color='#b42e48',linestyle='--');ax.set_xlim(x0-100,x1+100);ax.set_ylim(y0-100,y1+100);ax.set_aspect('equal');ax.set_title(name.replace('_',' ').title()+' | source XY retained');ax.set_xlabel('City local grid east (m)');ax.set_ylabel('City local grid north (m)');ax.grid(alpha=.15)
 fig.legend(handles=[Legend(color='#718a9c',label='Generic detailed facade modules; height unverified'),Legend(color='#d78337',label='Inferred floor/grade correction'),Legend(color='#e5b900',label='Mapped fixture position'),Legend(color='#337d2f',label='Mapped tree position')],loc='outside lower center',ncol=2);fig.suptitle('Stage07 near-street coverage | mixed source dates | not a survey or complete facade reconstruction');path=root/'work/previews/stage07/detail_coverage.png';fig.savefig(path,dpi=140);plt.close(fig);print('STAGE07_COVERAGE_AND_BOUNDARY_CHECKS_SAVED',len(bs),len(seams),flush=True)
if __name__=='__main__':build()
