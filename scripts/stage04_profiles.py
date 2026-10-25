"""Global grade-bounded road profiles; inferred clearance loses priority on contradictory data."""
from pathlib import Path
import json,heapq,collections,time
import numpy as np
from pyproj import Transformer
from stage03_surface import Surface
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def refine(root=ROOT):
 started=time.monotonic();folder=root/'data/processed/stage04';roads=json.loads((folder/'roads.json').read_text());a=np.load(folder/'road_profiles.npz');v=a['v'];s=a['s'];surface=Surface(root);origin=surface.origin;N=len(v);ground=surface(v[:,0],v[:,1]);ground=np.where(np.isfinite(ground),ground,v[:,2]-.06);z=ground+.06
 byid={r['source_id']:i for i,r in enumerate(roads)};tx=Transformer.from_crs(4326,32611,always_xy=True);firstnode={};eq_src=[];eq_dst=[];source=[];dest=[];cost=[];limits=np.zeros(N);native_index={}
 for row in (folder/'source_ways.jsonl').open():
  w=json.loads(row);i=byid.get(w['id'])
  if i is None:continue
  r=roads[i];k=r['profile_start'];n=r['profile_count'];ss=s[k:k+n];xy=np.array(w['lonlat']);x,y=tx.transform(xy[:,0],xy[:,1]);xy=np.column_stack([x-origin[0],y-origin[1]]);native=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))];idx=np.searchsorted(ss,native);idx=np.clip(idx,0,n-1);prev=np.maximum(0,idx-1);idx=np.where(abs(ss[idx]-native)<abs(ss[prev]-native),idx,prev)+k
  native_index[i]=idx
  for node,j in zip(w['node_ids'],idx):
   if node in firstnode:eq_src.append(firstnode[node]);eq_dst.append(int(j))
   else:firstnode[node]=int(j)
  p=r['parameters'];gg=p['max_grade'];limits[k:k+n]=gg
  ds=np.diff(ss);ii=np.arange(k,k+n-1);source.extend([ii,ii+1]);dest.extend([ii+1,ii]);cc=ds*gg
  if p['class'] in ['pedestrian','cycleway']:
   # Preserve real steep steps/path grades; these are not a vehicle design criterion.
   cc=np.maximum(cc,abs(np.diff(ground[k:k+n]))+.001)
  cost.extend([cc,cc])
  rank=p['vertical_rank']
  if p['bridge'] or rank>0:z[k:k+n]=np.maximum(ground[k:k+n],np.interp(ss,[ss[0],ss[-1]],[ground[k],ground[k+n-1]]))+.06
  elif p['tunnel'] or rank<0:
   depth=7;fade=np.minimum.reduce([ss-ss[0],ss[-1]-ss,np.full(n,80)])/80;z[k:k+n]-=depth*fade
 # Equality links have zero grade distance. CSR adjacency has ~5 million directed arcs.
 eq_src=np.array(eq_src,int);eq_dst=np.array(eq_dst,int);source.extend([eq_src,eq_dst]);dest.extend([eq_dst,eq_src]);cost.extend([np.zeros(len(eq_src)),np.zeros(len(eq_src))]);src=np.concatenate(source);dst=np.concatenate(dest);cc=np.concatenate(cost);order=np.argsort(src,kind='stable');dst=dst[order];cc=cc[order];ptr=np.r_[0,np.cumsum(np.bincount(src,minlength=N))];del src,source,dest,cost,order
 print('GRADE_GRAPH',N,len(dst),flush=True)
 cross=json.loads((root/'work/reports/stage04/crossings.json').read_text());relations=[];contradictions=[]
 def vertex(i,dist):
  r=roads[i];k=r['profile_start'];n=r['profile_count'];j=int(np.searchsorted(s[k:k+n],dist));j=min(j,n-1)
  if j and abs(s[k+j-1]-dist)<abs(s[k+j]-dist):j-=1
  return k+j
 def bound(start,target,limit=6):
  heap=[(0.,start)];seen={start:0.}
  while heap:
   d,i=heapq.heappop(heap)
   if i==target:return d
   if d>seen[i]+1e-9:continue
   for j,c in zip(dst[ptr[i]:ptr[i+1]],cc[ptr[i]:ptr[i+1]]):
    new=d+c
    if new<limit and new<seen.get(int(j),float('inf'))-1e-8:seen[int(j)]=new;heapq.heappush(heap,(new,int(j)))
  return float('inf')
 for ci,c in enumerate(cross):
  if c['upper'] is None:continue
  u=c['upper'];lo=c['b'] if u==c['a'] else c['a'];su=c['s_a'] if u==c['a'] else c['s_b'];sl=c['s_b'] if u==c['a'] else c['s_a'];ui=vertex(u,su);li=vertex(lo,sl);budget=bound(ui,li)
  if budget<5.85:
   c['constraint_status']='infeasible_5_2m_clearance_with_grade_limits_and_actual_connected_network';c['grade_feasible_vertical_difference_m']=budget;contradictions.append(ci)
  else:c['constraint_status']='feasible_clearance_estimate';relations.append((ui,li,ci))
 print('CLEARANCE_FEASIBILITY',len(relations),'contradictions',len(contradictions),flush=True)
 # A max-heap computes the smallest upper grade envelope, preserving XY and common nodes.
 relaxations=0
 def propagate(heap):
  nonlocal relaxations
  heapq.heapify(heap)
  while heap:
   neg,i=heapq.heappop(heap);val=-neg
   if val<z[i]-1e-7:continue
   js=dst[ptr[i]:ptr[i+1]];values=val-cc[ptr[i]:ptr[i+1]];good=values>z[js]+1e-7
   for j,new in zip(js[good],values[good]):
    j=int(j);z[j]=new;heapq.heappush(heap,(-float(new),j));relaxations+=1
 propagate([(-float(val),i) for i,val in enumerate(z)])
 # Enforce feasible crossing inequalities; retain an explicit finite correction budget for source contradictions.
 accepted=[];rejected=[]
 for iteration in range(10):
  heap=[];maxraise=0
  for ui,li,ci in relations:
   need=z[li]+6-z[ui]
   if need>1e-5:
    if z[li]+6-ground[ui]>30:
     cross[ci]['constraint_status']='network_conflict_or_over_30m_unsurveyed_correction';rejected.append(ci);continue
    z[ui]+=need;heap.append((-float(z[ui]),ui));maxraise=max(maxraise,need)
  propagate(heap);print('GRADE_CLEARANCE_PASS',iteration,'max_raise',maxraise,flush=True)
  if maxraise<1e-5:break
 v[:,2]=z;np.savez_compressed(folder/'road_profiles.npz',v=v,s=s)
 grade=[]
 for i,r in enumerate(roads):
  k=r['profile_start'];n=r['profile_count'];slope=np.abs(np.diff(z[k:k+n])/np.maximum(np.diff(s[k:k+n]),1e-9));mx=float(slope.max()) if len(slope) else 0.;r['maximum_estimated_grade']=mx;r['profile_method']='global_grade_bounded_DTM_and_shared_nodes_with_feasible_OSM_layer_clearance_constraints';grade.append({'feature_id':r['id'],'class':r['parameters']['class'],'maximum_estimated_grade':mx,'limit':r['parameters']['max_grade'],'status':'warning' if mx>r['parameters']['max_grade']+1e-4 else 'within_profile_limit','note':'steps/footpaths may legitimately exceed vehicle grade budgets; numeric road Z remains inferred'})
 for c in cross:
  za=float(z[vertex(c['a'],c['s_a'])]);zb=float(z[vertex(c['b'],c['s_b'])]);c['z_a_m']=za;c['z_b_m']=zb
  if c['upper'] is not None:
   signed=za-zb if c['upper']==c['a'] else zb-za;c['estimated_deck_clearance_m']=signed-.65;c['status']='pass_estimated_clearance' if signed>=5.85-.001 else 'clearance_warning_source_conflict'
 write_json(folder/'roads.json',roads);write_json(root/'work/reports/stage04/road_grades.json',grade);write_json(root/'work/reports/stage04/crossings.json',cross)
 graph=json.loads((folder/'road_graph.json').read_text())
 for key,n in graph['nodes'].items():
  if n['source_node_id'] in firstnode:n['xyz_m'][2]=float(z[firstnode[n['source_node_id']]])
 write_json(folder/'road_graph.json',graph)
 report={'status':'executed','vertices':N,'grade_relaxations':relaxations,'clearance_constraints_tested':len(relations)+len(contradictions),'grade_infeasible_clearance_constraints':len(contradictions),'constraint_correction_budget_rejections':len(set(rejected)),'crossing_status':dict(collections.Counter(c['status'] for c in cross)),'grade_warnings_by_class':dict(collections.Counter(g['class'] for g in grade if g['status']=='warning')),'maximum_profile_minus_ground_m':float((z-ground).max()),'elapsed_seconds':time.monotonic()-started,'priority':'source XY and source-node connectivity > bounded vehicle grades > inferred5.2m clearance. Source conflicts retained for review, never fabricated as passed.'}
 write_json(root/'work/reports/stage04/profile_refinement.json',report);print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':refine()
