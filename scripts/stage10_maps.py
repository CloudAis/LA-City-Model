"""Actual geographic coverage/detail and field-provenance maps, not a basemap."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Patch,Rectangle
import numpy as np,shapely
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
from stage10_common import *
forward=Transformer.from_crs(4326,32611,always_xy=True);origin=np.array(read('data/processed/origin.json')['origin_utm_m'][:2]);citydoc=read('data/processed/stage02/city_boundary_2025.geojson');city=shapely.union_all([transform(forward.transform,shape(f['geometry'])) for f in citydoc['features']]);scopes=read('data/processed/scopes.geojson');refined=read('data/processed/stage07_final/index.json');geo=read('work/reports/stage10/geography.json')
footprints=shapely.union_all([shape(b['source_geometry']) for b in refined['buildings']]);research=shapely.union_all([shape(b['source_geometry']) for b in refined['buildings'] if b['reference_guided']]);geo['coverage'].update(actual_refined_building_footprint_union_m2=footprints.area,reference_guided_five_building_footprint_union_m2=research.area,fully_survey_verified_facades=0);write('work/reports/stage10/geography.json',geo)
plt.rcParams.update({'font.size':11,'axes.facecolor':'#eff3f1','figure.facecolor':'#f7f8f5','axes.spines.top':False,'axes.spines.right':False})
def polygons(g):return list(g.geoms) if hasattr(g,'geoms') else [g]
def draw(ax,g,color,edge=None,alpha=1):
 for p in polygons(g):
  if p.geom_type!='Polygon':continue
  a=np.array(p.exterior.coords);ax.fill((a[:,0]-origin[0])/1000,(a[:,1]-origin[1])/1000,color=color,edgecolor=edge or color,alpha=alpha,linewidth=.5)
  for hole in p.interiors:
   a=np.array(hole.coords);ax.fill((a[:,0]-origin[0])/1000,(a[:,1]-origin[1])/1000,color='#f7f8f5',linewidth=.4)
def axes(ax):ax.set_aspect('equal');ax.set_xlabel('Grid east from project origin / km');ax.set_ylabel('Grid north / km');ax.grid(alpha=.12)
fig,(ax,zoom)=plt.subplots(1,2,figsize=(16,9),dpi=120,gridspec_kw={'width_ratios':[1,1.1]});draw(ax,city,'#b9cdc2','#6b867c');axes(ax);ax.set_title('Los Angeles city · model scope (2025 boundary)')
for f in scopes['features']:
 if f['properties']['id'] in ('downtown','historic_core','civic_center'):
  g=transform(forward.transform,shape(f['geometry']));draw(ax,g,'#d2ad53' if f['properties']['id']=='downtown' else '#bf634e',alpha=.8);draw(zoom,g,'#f2e4b9' if f['properties']['id']=='downtown' else '#d89b84',edge='#865b3d',alpha=.65)
for p in polygons(footprints):
 a=np.array(p.exterior.coords);zoom.fill(a[:,0]/1000,a[:,1]/1000,color='#355f64',alpha=.65,linewidth=0)
for lm in read('data/processed/stage06/landmark_index.json')['landmarks']:
 x,y=lm['origin_city_m'][:2];ax.scatter(x/1000,y/1000,s=15,c='#3d647b');
 if abs(x)<2500 and abs(y)<3500:zoom.scatter(x/1000,y/1000,s=20,c='#3d647b')
axes(zoom);zoom.set_xlim(-2.3,2.3);zoom.set_ylim(-2.3,2.8);zoom.set_title('Downtown 4×4 km; two close-up work windows')
fig.suptitle('Measured coverage and visual detail levels · phase 10',fontsize=19)
fig.text(.05,.04,f"City/tile domains: {city.area/1e6:.3f} km²  |  Downtown work window:16 km²  |  close-up work windows:0.28 km²\nActual100-building detailed footprint union:{footprints.area/1e6:.4f} km²; five reference-guided footprints:{research.area/1e6:.4f} km². Windows are not fully surveyed/detail-complete areas.\nBlue points:10 approximate landmarks at actual positions. Santa Monica and Beverly Hills are separate cities and excluded. EPSG:32611, metres.",fontsize=10)
fig.subplots_adjust(bottom=.19,top=.88,wspace=.27);fig.savefig(DELIVERY/'previews/coverage_detail.png');plt.close(fig)
fig,(ax,bar)=plt.subplots(1,2,figsize=(16,9),dpi=120,gridspec_kw={'width_ratios':[1.25,1]});draw(ax,city,'#dce4de','#859b90');grid=read('work/reports/stage10/height_grid.json');norm=matplotlib.colors.Normalize(0,1);cmap=matplotlib.colormaps['YlOrBr']
for row in grid:
 total=sum(row.get(k,0) for k in ('verified','unverified_report','estimated'));ratio=row.get('estimated',0)/max(1,total);x,y=row['ij'];ax.add_patch(Rectangle((x,y),1,1,facecolor=cmap(norm(ratio)),edgecolor='none',alpha=.9))
axes(ax);ax.set_title('Per1 km cell: fraction of estimated building heights');fig.colorbar(matplotlib.cm.ScalarMappable(norm=norm,cmap=cmap),ax=ax,shrink=.65,label='estimated height / active buildings')
h=geo['buildings']['height_evidence'];groups={'Unverified source reports':sum(v for k,v in h.items() if k.startswith('source_reported')),'Explicit estimates':sum(v for k,v in h.items() if k.startswith('inferred')),'Published reference':h.get('verified_published_reference',0)};keys=list(groups);values=list(groups.values());bar.barh(keys,values,color=['#7c9b9a','#b7833e','#416e8b']);bar.invert_yaxis();bar.set_xlabel('Active source building records');bar.set_title('Height evidence denominator:1,096,502 source records')
for i,v in enumerate(values):bar.text(v+max(values)*.018,i,f'{v:,} ({v/sum(values)*100:.4f}%)',va='center',fontsize=10)
bar.set_xlim(0,max(values)*1.38);bar.grid(axis='x',alpha=.15);fig.suptitle('Data sources and estimated attributes · no same-day city snapshot',fontsize=18)
fig.text(.05,.04,'Geometry: dated County roofline proxies and OSM. Most County acquisition years are2008; later records and2026 OSM database dates are separate.\nReported County/OSM heights are NOT independently verified measurements. Façade patterns, roofs, materials and many transport dimensions remain inferred/authored.\nThis map classifies HEIGHT fields, not an overall percentage of observed pixels, geometry accuracy or all visual content. ©OpenStreetMap contributors · County/LARIAC · USGS · Census.',fontsize=10)
fig.subplots_adjust(bottom=.19,top=.88,wspace=.38);fig.savefig(DELIVERY/'previews/source_estimate_distribution.png');plt.close(fig)
print('ACTUAL_GEOGRAPHIC_MAPS_SAVED_1920x1080',footprints.area,research.area,flush=True)
