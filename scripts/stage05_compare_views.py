"""Same-camera source envelopes vs actual geometry extracted from the saved blend.

Source envelopes are deliberately coarse: a full footprint with selected relative
height is a data constraint, not a verified facade, roof profile or street photo.
"""
from pathlib import Path
import json,sqlite3,numpy as np,shapely
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection,PolyCollection
from PIL import Image
from stage03_common import polygon_parts
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def project(v,view):
 pos=np.array(view['position_m']);target=np.array(view['target_m']);forward=target-pos;forward/=np.linalg.norm(forward);right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward);q=np.asarray(v)-pos;depth=q@forward
 if 'ortho_scale_m' in view:return np.column_stack([q@right/(view['ortho_scale_m']/2),q@up/(view['ortho_scale_m']*3/8)]),depth
 lens=view.get('lens_mm',35);return np.column_stack([q@right/np.maximum(depth,.01)*lens/18,q@up/np.maximum(depth,.01)*lens/13.5]),depth
def comparisons(root=ROOT):
 root=Path(root);views=json.loads((root/'config/stage05_views.json').read_text());audit=json.loads((root/'work/reports/stage05/audit_selection.json').read_text());db=sqlite3.connect(root/'data/processed/stage05/buildings.sqlite');targets=[b for b in audit['buildings'] if b['visual_level']>0 and b['height_m']>=100];outputs={}
 for name in ['skyline_northwest','skyline_northeast','skyline_south']:
  view=views[name];lines=[];source_names=[];actual=[];bboxmatches=[]
  for b in targets:
   i=b['i'];g,a=db.execute('SELECT geom,attrs FROM buildings WHERE i=?',(i,)).fetchone();g=shapely.from_wkb(g);a=json.loads(a);base=audit['placements'][str(i)]['floor_navd88_m'];height=a['height_m'];model=root/f'work/reports/stage05/audit_meshes/{i}.npz'
   if not model.exists():continue
   for p in polygon_parts(g):
    for ring in [p.exterior,*p.interiors]:
     xy=np.asarray(ring.coords)[:,:2];bottom=np.column_stack([xy,np.full(len(xy),base)]);top=bottom+[0,0,height];pr0,d0=project(bottom,view);pr1,d1=project(top,view)
     if np.all(d0>0):lines.extend([pr0,pr1]);lines.extend(np.array([pr0[j],pr1[j]]) for j in range(0,len(xy)-1,max(1,(len(xy)-1)//6)))
   if a.get('reference') and a['reference'].get('spire'):
    part=max(a['parts'],key=lambda p:p['height_m']);pg=shapely.from_wkb(bytes.fromhex(part['geometry_wkb_hex']));q=pg.representative_point();tipline=np.array([[q.x,q.y,base+height],[q.x,q.y,base+a['reference']['total_m']]]);tip_projection,depth=project(tipline,view)
    if np.all(depth>0):lines.append(tip_projection)
   with np.load(model) as d:v=d['v'];f=d['f']
   projected,depth=project(v,view);tri=projected[f];cross=(tri[:,1,0]-tri[:,0,0])*(tri[:,2,1]-tri[:,0,1])-(tri[:,1,1]-tri[:,0,1])*(tri[:,2,0]-tri[:,0,0]);keep=(depth[f]>.1).all(axis=1)&(np.abs(tri).min(axis=(1,2))<10)&(abs(cross)>1e-10);tri=tri[keep]
   if len(tri):
    silhouette=shapely.union_all(shapely.polygons(tri));actual.extend([np.asarray(p.exterior.coords) for p in polygon_parts(silhouette)]);bboxmatches.append({'id':b['id'],'name':a.get('name'),'selected_height_m':height,'actual_mesh_bbox_m':[v.min(axis=0).tolist(),v.max(axis=0).tolist()],'same_camera_parameters':True,'source_envelope_is_not_expected_facade_shape':True})
  im=Image.open(root/'work/previews/stage05'/f'{name}.png');fig,axes=plt.subplots(1,2,figsize=(16,6.5));axes[0].imshow(im,extent=[-1,1,-1,1],aspect='auto');axes[0].add_collection(LineCollection(lines,colors='#efb146',linewidths=.45,alpha=.75));axes[1].add_collection(PolyCollection(actual,facecolors='#397e9b',edgecolors='#1c425b',linewidths=.25,alpha=.55));axes[1].add_collection(LineCollection(lines,colors='#ce8d27',linewidths=.45,alpha=.8))
  for ax in axes:ax.set(xlim=(-1,1),ylim=(-1,1),xlabel='Same camera normalized horizontal coordinate',ylabel='Normalized vertical coordinate');ax.set_aspect(.75)
  axes[0].set_title('Actual CPU render + selected source height envelopes');axes[1].set_title('Saved .blend mesh silhouettes + source envelopes');fig.suptitle(name+' | fixed geographic camera; foreground occlusion differs from wire envelopes');fig.tight_layout();path=root/'work/previews/stage05'/f'{name}_comparison.png';fig.savefig(path,dpi=150);plt.close(fig);outputs[name]={'comparison':str(path.relative_to(root)),'camera':view,'buildings':bboxmatches,'scope':'selected tallest Downtown targets only, not a comparison to independent street photography','published_height_accuracy_unknown':True}
 write_json(root/'work/reports/stage05/same_camera_comparison.json',{'status':'executed','views':outputs,'all_geometry_extracted_from_saved_reopened_model':True,'published_spire_total_drawn_separately_from_full_footprint_envelope':True,'source_data_and_inferred_heights_not_current_photographic_ground_truth':True});db.close();print('THREE_SAME_CAMERA_SAVED_MODEL_COMPARISONS_COMPLETE',flush=True)
if __name__=='__main__':comparisons()
