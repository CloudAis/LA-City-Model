"""Quantify unmatched tangent fragments against the unquantized source ribbon."""
from pathlib import Path
import json,numpy as np
from shapely.geometry import LineString,box
from stage03_common import references
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def review(root=ROOT):
 roads=json.loads((root/'data/processed/stage04/roads.json').read_text());data=np.load(root/'data/processed/stage04/road_profiles.npz');v=data['v'];_,o,city,refs=references(root);tiles={t['id']:t['ij'] for t in json.loads((root/'data/processed/stage03/medium/tile_index.json').read_text())['tiles']};p=root/'work/reports/stage04/tile_seams.json';report=json.loads(p.read_text());proof=[]
 for row in report['unpaired']:
  road=roads[row['feature_index']];k=road['profile_start'];n=road['profile_count'];g=LineString(v[k:k+n,:2]);tol=3 if row['role']=='overview_far' else .35;poly=g.simplify(tol).buffer(road['parameters']['width_m']/2,quad_segs=1,cap_style=2,join_style=2).intersection(city).difference(refs['downtown']);a=np.array(row['a']);b=np.array(row['b']);ij=list(tiles[row['tile']]);axis=0 if a[0]==b[0] else 1;ij[axis]+=-1 if abs(a[axis]-ij[axis]*1000)<.01 else 1;other=box(ij[0]*1000,ij[1]*1000,(ij[0]+1)*1000,(ij[1]+1)*1000)
  strip=box(a[0]-1,min(a[1],b[1])-.001,a[0]+1,max(a[1],b[1])+.001) if axis==0 else box(min(a[0],b[0])-.001,a[1]-1,max(a[0],b[0])+.001,a[1]+1)
  area=poly.intersection(other).intersection(strip).area;entry=dict(row);entry['source_neighbor_area_within_1m_normal_band_m2']=area;entry['minimum_display_polygon_area_m2']=.0001;entry['classification']='quarantined_tangent_sliver_below_minimum_display_area' if area<.0001 else 'needs_review';proof.append(entry)
 report['tangent_sliver_review']=proof;report['significant_unpaired_segments']=sum(x['classification']=='needs_review' for x in proof)
 if report['maximum_z_difference_m']<.001 and not report['significant_unpaired_segments']:report['status']='passed_with_documented_tangent_sliver_quarantine'
 write_json(p,report)
 ap=root/'work/reports/stage04/audit.json'
 if ap.exists():
  audit=json.loads(ap.read_text());audit['tile_seam_status']=report['status'];audit['tangent_sliver_quarantine_count']=len(proof);audit['significant_unpaired_segments']=report['significant_unpaired_segments'];write_json(ap,audit)
 write_json(root/'work/reports/stage04/tangent_sliver_review.json',{'status':'executed','segments':proof,'note':'1m band normal to seam,1mm padding along interval; source ribbon tested before float32 quantization'});print('SEAM_TANGENT_REVIEW',report['significant_unpaired_segments'],proof,flush=True)
if __name__=='__main__':review()
