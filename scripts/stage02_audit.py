"""Stream the actual city output: classify non-building structures and validate counts/geometry."""
import collections
import gzip
import hashlib
import json
import math
import shutil
from pathlib import Path
import numpy as np
import pyogrio.raw
from shapely.geometry import shape
from shapely import normalize
from pyproj import Transformer
from shapely.ops import transform
from stage02_io import write_json,digest
from stage02_enrich import read_refs


def audit(root):
    base=root/'data/processed/stage02';path=base/'buildings.geojsonl.gz'
    gdb=next((root/'work/cache/lariac6').rglob('*.gdb'))
    meta,fids,_,arrays=pyogrio.raw.read(gdb,layer='LARIAC6_BUILDINGS_2020',columns=['CODE'],read_geometry=False,return_fids=True)
    lookup=np.empty(int(fids.max())+1,dtype=object);lookup[:]=None;lookup[fids]=arrays[0]
    refs,city,origin=read_refs(root);world=transform(Transformer.from_crs(32611,4326,always_xy=True).transform,city)
    import shapely
    shapely.prepare(world)
    forward=Transformer.from_crs(4326,32611,always_xy=True)
    seen=set();geometry_seen={};duplicates=[];cells=collections.Counter();stats=collections.Counter();dt=[]
    backup=root/'work/history/buildings_before_classification';backup.mkdir(parents=True,exist_ok=True)
    if not (backup/path.name).exists():shutil.copy2(path,backup/path.name)
    temporary=path.with_suffix('.tmp')
    with gzip.open(path,'rt') as source,gzip.open(temporary,'wt',compresslevel=5) as target:
        for line in source:
            f=json.loads(line);p=f['properties'];uid=p['id'];g=shape(f['geometry'])
            if uid in seen:raise ValueError('Duplicate stable building ID '+uid)
            seen.add(uid);stats['records_checked']+=1
            if not g.is_valid:raise ValueError('Invalid output building geometry '+uid)
            if g.is_empty:raise ValueError('Empty output building geometry '+uid)
            code=lookup[int(p['original_id'])];p['source_code']=str(code)
            p['feature_type']='building_roofline' if code=='Building' else 'solar_structure' if code=='Free Standing Solar Structure' else 'source_structure'
            if p['feature_type']=='building_roofline':stats['buildings']+=1
            else:stats['other_structures']+=1
            p['boundary_crossing']=not bool(shapely.covers(world,g))
            if p['boundary_crossing']:stats['boundary_crossing_features']+=1
            representative=g.representative_point();x,y=forward.transform(representative.x,representative.y)
            key=f'{math.floor((x-origin[0])/1000)}_{math.floor((y-origin[1])/1000)}';cells[key]+=1
            if g.geom_type=='MultiPolygon':stats['multipart_features']+=1
            stats['interior_rings_preserved']+=sum(len(v.interiors) for v in (g.geoms if g.geom_type=='MultiPolygon' else [g]))
            hg=hashlib.sha256(normalize(g).wkb).hexdigest()
            if hg in geometry_seen:duplicates.append({'first_id':geometry_seen[hg],'other_id':uid,'status':'exact_geometry_duplicate_review; source attributes retained'})
            else:geometry_seen[hg]=uid
            if p['height_m'] is not None:raise ValueError('Unexpected verified height without a confirmed field definition')
            if p.get('height_candidate_m') is not None and not (0<=p['height_candidate_m']<=1000):raise ValueError('Out-of-range height candidate')
            if p['feature_type']=='building_roofline' and p.get('source_HEIGHT') is None:stats['building_raw_height_missing']+=1
            target.write(json.dumps(f,separators=(',',':'),ensure_ascii=False)+'\n')
            if 'downtown' in p['regions']:dt.append(f)
            if stats['records_checked']%200000==0:print('BUILDING_OUTPUT_AUDITED',stats['records_checked'],flush=True)
    path.unlink();temporary.replace(path)
    write_json(base/'downtown_buildings.geojson',{'type':'FeatureCollection','features':dt})
    write_json(base/'building_coverage_counts_1km.json',dict(cells))
    write_json(base/'building_geometry_duplicate_review.json',duplicates)
    report={**dict(stats),'exact_geometry_duplicate_pairs':len(duplicates),'stable_ids_unique':True,
        'valid_geometry_rate':1.0,'building_raw_height_missing_rate':stats['building_raw_height_missing']/stats['buildings'],
        'verified_height_missing_rate':1.0,'verified_height_status':'unresolved official field definition; retain inferred candidate separately',
        'downtown_structures':len(dt),'downtown_buildings':sum(f['properties']['feature_type']=='building_roofline' for f in dt),
        'file_sha256':digest(path),'all_geometry_checked':True}
    write_json(root/'work/reports/stage02/building_output_audit.json',report)
    print('BUILDING_OUTPUT_AUDIT_PASSED',report,flush=True)
    return report
