"""Continuous DEM sampling, explicit repairs and categorical ground materials."""
import json
import numpy as np
import rasterio
from rasterio.features import geometry_mask,shapes
from shapely.geometry import mapping,shape
from shapely.ops import unary_union
from shapely.strtree import STRtree
import shapely
from stage03_common import references,local_features,to_geographic
from stage02_io import write_json


class Surface:
    def __init__(self,root):
        self.root=root;self.cfg,self.origin,self.city,self.refs=references(root);self.sources={};self.repairs={}
        for key,path in [('city',self.cfg['terrain']['city_dem']),('fine',self.cfg['terrain']['downtown_dem'])]:
            with rasterio.open(root/path) as d:
                self.sources[key]=(d.read(1),d.transform,d.nodata)
        with rasterio.open(root/self.cfg['surface']['landcover']) as d:self.cover=d.read(1);self.cover_affine=d.transform
        self.classes=list(self.cfg['surface']['colors']);self.class_index={s:i for i,s in enumerate(self.classes)}
        self.facilities=[];self.override=[]
        for f,g in local_features(root,self.cfg['surface']['facilities']):
            code=f['properties']['raw_attributes'].get('MTFCC')
            category='airport' if code=='K2457' else 'industrial' if code=='K2362' else 'park_green' if code.startswith('K218') else None
            if category:self.facilities.append(g);self.override.append(self.class_index[category])
        plan=root/'data/processed/stage03/selected_plan_landuse.geojson'
        if plan.exists():
            for f,g in local_features(root,str(plan.relative_to(root))):self.facilities.append(g);self.override.append(self.class_index[f['properties']['class']])
        self.tree=STRtree(self.facilities)
        self.coast=unary_union([g for _,g in local_features(root,self.cfg['water']['coastline_source'])])
        self.marine=unary_union([g for f,g in local_features(root,self.cfg['water']['polygon_source']) if f['properties']['raw_attributes']['MTFCC'] in ['H2053','H2051']])

    def _sample(self,key,x,y):
        a,t,nodata=self.sources[key];px=(x+self.origin[0]-t.c)/t.a-.5;py=(y+self.origin[1]-t.f)/t.e-.5
        ix=np.floor(px).astype(int);iy=np.floor(py).astype(int);fx=px-ix;fy=py-iy;num=np.zeros(x.shape);den=np.zeros(x.shape)
        for dx,dy,w in [(0,0,(1-fx)*(1-fy)),(1,0,fx*(1-fy)),(0,1,(1-fx)*fy),(1,1,fx*fy)]:
            cx=ix+dx;cy=iy+dy;inside=(cx>=0)&(cx<a.shape[1])&(cy>=0)&(cy<a.shape[0]);z=a[np.clip(cy,0,a.shape[0]-1),np.clip(cx,0,a.shape[1]-1)]
            valid=inside&np.isfinite(z)&(z!=nodata);ww=np.where(valid,w,0);num+=ww*np.where(valid,z,0);den+=ww
        return np.divide(num,den,out=np.full(x.shape,np.nan),where=den>1e-12)

    def __call__(self,x,y):
        x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float);z=self._sample('city',x,y)
        missing=~np.isfinite(z)
        if missing.any():
            a,t,nd=self.sources['city'];radius=self.cfg['terrain']['nodata_max_nearest_repair_m'];maxr=int(radius/abs(t.a))
            for i in np.flatnonzero(missing):
                px=int(np.rint((x[i]+self.origin[0]-t.c)/t.a-.5));py=int(np.rint((y[i]+self.origin[1]-t.f)/t.e-.5));best=None
                for dy in range(-maxr,maxr+1):
                    for dx in range(-maxr,maxr+1):
                        rr,cc=py+dy,px+dx
                        if 0<=rr<a.shape[0] and 0<=cc<a.shape[1] and a[rr,cc]!=nd:
                            cx=t.c+(cc+.5)*t.a-self.origin[0];cy=t.f+(rr+.5)*t.e-self.origin[1];distance=np.hypot(cx-x[i],cy-y[i])
                            if distance<=radius and (best is None or distance<best[0]):best=(distance,float(a[rr,cc]))
                if best:
                    z[i]=best[1];self.repairs[(round(float(x[i]),4),round(float(y[i]),4))]={'method':'nearest_valid_city_DEM_within_30m','distance_m':best[0],'height_m':best[1]}
        b=np.round(self.refs['downtown'].bounds,6);distance=np.minimum.reduce([x-b[0],b[2]-x,y-b[1],b[3]-y]);inside=distance>0
        if inside.any():
            zz=self._sample('fine',x[inside],y[inside]);w=np.clip(distance[inside]/self.cfg['terrain']['fine_transition_band_m'],0,1);w=np.where(np.isfinite(zz),w,0)
            z[inside]=np.where(w>0,z[inside]*(1-w)+np.nan_to_num(zz)*w,z[inside])
        return z

    def material_indices(self,x,y):
        a=self.cover;t=self.cover_affine;cc=np.floor((x+self.origin[0]-t.c)/t.a).astype(int);rr=np.floor((y+self.origin[1]-t.f)/t.e).astype(int)
        valid=(cc>=0)&(cc<a.shape[1])&(rr>=0)&(rr<a.shape[0]);v=np.where(valid,a[np.clip(rr,0,a.shape[0]-1),np.clip(cc,0,a.shape[1]-1)],0)
        out=np.zeros(v.shape,dtype=np.int32)
        for values,name in [([11],'inland_water'),([21,22,23,24],'built'),([31],'barren'),([41,42,43],'forest'),([52,71,81,82],'dry_slope'),([90,95],'wetland')]:out[np.isin(v,values)]=self.class_index[name]
        points=shapely.points(x,y)
        if len(self.facilities):
            pairs=self.tree.query(points,predicate='within')
            # Park override first; explicit use polygons airport/industry take priority.
            for category in ['park_green','industrial','port','airport']:
                keep=np.array(self.override)[pairs[1]]==self.class_index[category];out[pairs[0][keep]]=self.class_index[category]
        coastal=(v==31)&(shapely.distance(points,self.coast)<=self.cfg['surface']['beach_inference_max_coast_distance_m'])
        out[coastal]=self.class_index['beach']
        marine=shapely.covers(self.marine,points);out[marine]=self.class_index['ocean']
        return out

    def audit(self):
        results={};cfg=self.cfg
        for key,(a,t,nd) in self.sources.items():
            g=self.city if key=='city' else self.refs['downtown'];global_g=shapely.transform(g,lambda xy:xy+self.origin)
            inside=geometry_mask([mapping(global_g)],a.shape,t,invert=True);valid=inside&np.isfinite(a)&(a!=nd)
            bad=inside&~valid;lo,hi=cfg['terrain']['valid_height_range_m'];jumps=[]
            for axis in [0,1]:
                dz=np.diff(a,axis=axis);ok=np.take(valid,range(a.shape[axis]-1),axis=axis)&np.take(valid,range(1,a.shape[axis]),axis=axis)
                jumps.append(np.abs(dz[ok]))
            jumps=np.concatenate(jumps)
            results[key]={'kind':'bare_earth_DTM_not_DSM','shape':list(a.shape),'source_spacing_m':[abs(t.a),abs(t.e)],
                'affine_pixel_corner_to_UTM':list(t)[:6],'pixel_centers':'pixel index +0.5','vertical_datum':'NAVD88','vertical_unit':'meter',
                'inside_pixels':int(inside.sum()),'nodata_pixels':int(bad.sum()),'valid_fraction':float(valid.sum()/inside.sum()),
                'minimum_m':float(a[valid].min()),'maximum_m':float(a[valid].max()),
                'outside_configured_height_range_count':int((valid&((a<lo)|(a>hi))).sum()),
                'neighbor_height_difference_p95_p99_max_m':np.percentile(jumps,[95,99,100]).tolist(),
                'numeric_source_accuracy_m':None,'accuracy_note':'pixel spacing and numerical precision do not establish survey accuracy'}
            if bad.any():
                fs=[{'type':'Feature','properties':{'source':key,'gap_type':'original_DEM_NoData','repair_policy':'only nearest valid sample within30m, otherwise omit invalid faces'},'geometry':geom} for geom,val in shapes(bad.astype('uint8'),mask=bad,transform=t) if val==1]
                from pyproj import Transformer
                from shapely.ops import transform
                inv=Transformer.from_crs(32611,4326,always_xy=True)
                for f in fs:f['geometry']=mapping(transform(inv.transform,shape(f['geometry'])))
                write_json(self.root/f'data/processed/stage03/{key}_source_nodata.geojson',{'type':'FeatureCollection','features':fs})
        b=np.round(self.refs['downtown'].bounds,6);xx,yy=np.meshgrid(np.arange(b[0]+5,b[2],10),np.arange(b[1]+5,b[3],10));x,y=xx.ravel(),yy.ravel()
        delta=self._sample('fine',x,y)-self._sample('city',x,y);delta=delta[np.isfinite(delta)]
        results['fine_coarse_overlap']={'samples':len(delta),'fine_minus_coarse_p05_median_p95_m':np.percentile(delta,[5,50,95]).tolist(),
            'maximum_absolute_difference_m':float(abs(delta).max()),'transition_band_m':cfg['terrain']['fine_transition_band_m'],
            'treatment':'deterministic blend weight=min(distance to Downtown boundary /100m,1). Exact common source at border; original rasters untouched. Blend is resampling, not improved source precision.'}
        write_json(self.root/'work/reports/stage03/dem_audit.json',results);return results
