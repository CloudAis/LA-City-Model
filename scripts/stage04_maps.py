"""Actual vector-data maps; distinct from Blender rendered previews."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from shapely.geometry import LineString
from stage04_data import lines as line_parts
from stage03_common import references,local_features
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def maps(root=ROOT):
 folder=root/'data/processed/stage04';roads=json.loads((folder/'roads.json').read_text());a=np.load(folder/'road_profiles.npz');v=a['v'];_,o,city,refs=references(root);out=root/'work/previews/stage04';out.mkdir(parents=True,exist_ok=True);cross=json.loads((root/'work/reports/stage04/crossings.json').read_text());summary=json.loads((root/'work/reports/stage04/profile_refinement.json').read_text());lines=[];colors=[]
 palette={'motorway':'#bc633e','trunk':'#bc633e','ramp':'#c48b62','primary':'#485e72','secondary':'#607789','tertiary':'#7b8e9c','residential':'#9aa6b0','service':'#c2c7c8','parking_aisle':'#c9cecf','pedestrian':'#b9c7b6','cycleway':'#619c71'}
 for r in roads:
  k=r['profile_start'];n=r['profile_count'];g=LineString(v[k:k+n,:2]);g=g if city.covers(g) else g.intersection(city)
  for part in line_parts(g):lines.append(np.asarray(part.coords));colors.append(palette[r['parameters']['class']])
 def base(ax):
  parts=list(city.geoms) if hasattr(city,'geoms') else [city]
  for p in parts:
   x,y=p.exterior.xy;ax.plot(x,y,color='#303e4b',lw=.55)
   for hole in p.interiors:x,y=hole.xy;ax.plot(x,y,color='#303e4b',lw=.4)
  ax.add_collection(LineCollection(lines,colors=colors,linewidths=.25,rasterized=True));ax.set_aspect('equal');ax.set_xlabel('Project grid east (m)');ax.set_ylabel('Project grid north (m)');ax.set_facecolor('#f4f2ec')
 fig,ax=plt.subplots(figsize=(13,13));base(ax);b=city.bounds;ax.set_xlim(b[0]-1000,b[2]+1000);ax.set_ylim(b[1]-1000,b[3]+1000);ax.set_title(f'Los Angeles complete acquired transport network | {len(roads):,} ways\nOSM state2026-10-20; city boundary2025; mixed acquisition dates, not a survey');fig.text(.1,.025,'© OpenStreetMap contributors / ODbL1.0; Geofabrik | Census city boundary. No raster map tiles downloaded.',fontsize=9);fig.savefig(out/'all_city_network.png',dpi=150);plt.close(fig)
 fig,ax=plt.subplots(figsize=(12,10));base(ax);b=refs['downtown'].bounds;ax.set_xlim(b[0],b[2]);ax.set_ylim(b[1],b[3]);ax.set_title('Downtown | actual road centerlines and source grade tags');fig.savefig(out/'downtown_network.png',dpi=150);plt.close(fig)
 fig,ax=plt.subplots(figsize=(13,13));base(ax);ax.set_xlim(city.bounds[0]-1000,city.bounds[2]+1000);ax.set_ylim(city.bounds[1]-1000,city.bounds[3]+1000)
 for status,color,label in [('unresolved','#a4273f','Unresolved non-shared XY crossings'),('clearance_warning_source_conflict','#ef8e23','Inferred clearance conflicts')]:
  xy=np.array([c['xy_m'] for c in cross if c['status']==status]);
  if len(xy):ax.scatter(xy[:,0],xy[:,1],s=12,c=color,label=f'{label}: {len(xy)}',zorder=6)
 if (folder/'transport_gaps.geojson').exists():
  gaps=local_features(root,'data/processed/stage04/transport_gaps.geojson');ax.add_collection(LineCollection([np.asarray(g.coords) for _,g in gaps if g.geom_type=='LineString'],colors='#772c91',linewidths=1,label='Older Census midpoint >40m from OSM'))
 ax.legend(loc='upper right',fontsize=8);ax.set_title('Transport evidence gaps | numerical conflicts retained for review\nMarkers identify uncertainty; they are not verified road closures');fig.savefig(out/'transport_gaps.png',dpi=150);plt.close(fig)
 write_json(root/'work/reports/stage04/maps.json',{'status':'generated_from_actual_saved_data','images':['all_city_network.png','downtown_network.png','transport_gaps.png'],'not_Blender_renders':True,'data_time':'mixed vintage; OSM database state2026-10-20T20:23:47Z'})
 print('VECTOR_MAPS_GENERATED',flush=True)
if __name__=='__main__':maps()
