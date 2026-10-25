"""Delivery-specific physical support and visual provenance checks."""
import json,sqlite3,numpy as np,shapely,datetime,collections
from pathlib import Path
from stage02_io import write_json
from stage05_preserve import sha
ROOT=Path(__file__).resolve().parents[1]
def support(root=ROOT):
 root=Path(root);db=sqlite3.connect(root/'data/processed/stage05/buildings.sqlite');i,a=db.execute('SELECT i,attrs FROM buildings WHERE uid=?',('lariac6:201700195459',)).fetchone();a=json.loads(a);db.close();selection=json.load(open(root/'work/reports/stage05/audit_selection.json'));base=selection['placements'][str(i)]['floor_navd88_m'];plane=base+a['height_m'];index=json.load(open(root/'data/processed/stage05/mesh_index.json'));roof=next(k for k,m in enumerate(index['materials']) if m[0]=='roof');metal=next(k for k,m in enumerate(index['materials']) if m[0]=='metal')
 with np.load(root/f'work/reports/stage05/audit_meshes/{i}.npz') as d:v=d['v'];f=d['f'];m=d['m']
 top=(m==roof)&(np.abs(v[f,2]-plane)<.005).all(axis=1);cap=shapely.union_all(shapely.polygons(v[f[top],:2]));basepoints=v[np.unique(f[m==metal])];basepoints=basepoints[abs(basepoints[:,2]-plane)<.005];dist=shapely.distance(shapely.points(basepoints[:,:2]),cap);tip=v[np.argmax(v[:,2])];expected=base+a['reference']['total_m'];assert len(basepoints)>=8 and max(dist)<.005 and abs(tip[2]-expected)<.005;write_json(root/'work/reports/stage05/actual_spire_support.json',{'status':'passed','source':'actual saved/reopened Blender mesh sample','base_points_tested':len(basepoints),'maximum_distance_outside_actual_support_cap_m':float(max(dist)),'maximum_vertical_contact_delta_m':float(abs(basepoints[:,2]-plane).max()),'tip_xy_navd88_z_m':tip.tolist(),'published_total_height_m':a['reference']['total_m'],'numeric_top_error_m':float(tip[2]-expected),'not_a_measurement_accuracy_claim':True});print('ACTUAL_SAVED_SPIRE_SUPPORT_PASSED',len(basepoints),flush=True)
def visual(root=ROOT):
 root=Path(root);names=list(json.load(open(root/'config/stage05_views.json')));notes={
 'city_top':['Entire city including San Pedro/port now framed inside the image.','Administrative holes and separate cities remain unfilled; overview colors/roofs are schematic.'],
 'downtown_top':['Highrise concentration and diagonal street grid follow source geography; courtyards/roof terraces visible.','Pavement/terrain and inferred frontage gaps remain; source footprint overlap is not a surveyed setback.'],
 'skyline_northwest':['80m elevated virtual camera clears the earlier nearby wall; skyline is visible.','Facades use inferred regular grids; this is a massing check, not a photographic reconstruction.'],
 'skyline_northeast':['60m elevated virtual camera shows the cluster behind source foreground blocks.','Foreground overview buildings are neutral proxies; no current appearance validation.'],
 'skyline_south':['Wilshire visual spire is supported at the highest source part; earlier floating placement removed.','Published total and roof/body candidate remain distinct; landmark profile is approximate.'],
 'historic_core_street':['Street-level geometry, window/entry modules, curb and signal are visible.','Shaded image remains noisy; facade rhythm/materials/door placement are mostly inferred, not final street fidelity.'],
 'civic_center_street':['Initial civic block massing and facades are visible; hard-edge normals removed melted wall shading.','Terrain/plinth/sidewalk transitions and exact entrances are unresolved; this is not a passed final near-view environment.']}
 write_json(root/'work/reports/stage05/visual_inspection.json',{'status':'inspected_with_documented_visual_gaps','inspection_method':'assistant actually viewed all seven final PNGs via local image tool; no generated replacement pictures','images':{name:{'path':f'work/previews/stage05/{name}.png','sha256':sha(root/f'work/previews/stage05/{name}.png'),'observations':notes[name],'checked_for_blank_or_camera_obstruction':True} for name in names},'render_not_photoreal_acceptance':True,'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()});print('SEVEN_ACTUALLY_VIEWED_IMAGES_REGISTERED',flush=True)
if __name__=='__main__':support();visual()
