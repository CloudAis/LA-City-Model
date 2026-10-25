"""Incremental terrain-following near/far foundations and inferred roof plant.

Rebuild these two derived components from the source wall plan each time. A
repeated run must not append another foundation to the previous far mesh.
"""
import numpy as np,shapely
from stage07_final_data import ROOT,Grade,read,OUT,save,Mesh,polys
from shapely.geometry import shape,Point
from shapely import affinity
from stage02_io import write_json
def run():
 ix=read(OUT+'index.json');grade=Grade();cfg=read('config/stage07_final.json');spacing=float(cfg.get('foundation_boundary_sampling_max_m',4.0));assert 0<spacing<=4.0
 for b in ix['buildings']:
  center=np.array(b['origin_city_m'][:2]);floor=b['floor_navd88_m'];g=affinity.translate(shape(b['wall_plan']),-center[0],-center[1]);m=Mesh();m.extrude(g,-.22,0,'concrete');actual_spacing=0.;foundation_edges=0
  # Long roofline edges can span a changing road slope. Sample all exterior and
  # courtyard boundaries at<=4m so the skirt follows the same global grade used
  # by the sidewalk, instead of one straight bottom edge between distant ends.
  for p in polys(shapely.orient_polygons(shapely.segmentize(g,spacing))):
   for ring in [p.exterior,*p.interiors]:
    xy=np.array(ring.coords);z=np.minimum(grade(xy[:,0]+center[0],xy[:,1]+center[1])-floor-.25,-.23);actual_spacing=max(actual_spacing,float(np.linalg.norm(np.diff(xy,axis=0),axis=1).max(initial=0)));foundation_edges+=len(xy)-1
    for a,c,za,zc in zip(xy[:-1],xy[1:],z[:-1],z[1:]):
     m.quad([[*a,za],[*c,zc],[*c,-.22],[*a,-.22]],'concrete')
  if not b['reference_guided'] and g.area>250 and b['height_input_m']>15:
   c=g.representative_point();m.box([c.x,c.y,b['height_input_m']+.55],[2.8,1.8,1.1],'silver');m.cylinder([c.x,c.y,b['height_input_m']+1.1],.55,.55,.10,'dark_metal',16)
  ar,removed=m.arrays();file=save(OUT+'buildings/'+str(b['i'])+'/terrain_foundation_and_inferred_plant.npz',ar);b['near']=[r for r in b['near'] if r['name']!='terrain_foundation_and_inferred_plant'];b['near'].append({'name':'terrain_foundation_and_inferred_plant','file':file,'triangles':len(ar['f']),'degenerate_filtered':removed,'foundation_boundary_max_segment_m':actual_spacing,'foundation_boundary_edges':foundation_edges,'evidence':'foundation follows inferred street grade with<=4m boundary sampling; roof plant original generic approximation, not inventory'})
  # Regenerate a fresh coarse body, then attach the identical graded skirt.
  # Both mutually exclusive static LODs must meet the ground at the same place.
  coarse=Mesh();coarse.extrude(g,0,b['height_input_m'],'concrete');coarse_ar,coarse_removed=coarse.arrays();offset=len(coarse_ar['v']);far={'v':np.concatenate([coarse_ar['v'],ar['v']]),'f':np.concatenate([coarse_ar['f'],ar['f']+offset]),'m':np.concatenate([coarse_ar['m'],ar['m']])};b['far']=save(OUT+'buildings/'+str(b['i'])+'/far.npz',far);b['far_triangles']=len(far['f']);b['far_degenerate_filtered']=removed+coarse_removed;b['foundation_in_near_and_far']=True;b['foundation_boundary_sampling_max_m']=spacing
 write_json(ROOT/(OUT+'index.json'),ix);print('NEAR_AND_FAR_GRADED_FOUNDATIONS_REBUILT',len(ix['buildings']),'MAX_BOUNDARY_SEGMENT_M',spacing,flush=True)
if __name__=='__main__':run()
