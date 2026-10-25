"""Use areal hydrography where TIGER linear water omits the Downtown river."""
import json
import numpy as np
import rasterio
from pyproj import Transformer
from shapely.geometry import LineString,Point,box
from stage03_common import references,local_features,to_geographic
from stage02_io import write_json


def prepare(root,quality):
    cfg,o,city,refs=references(root);parents=[(f,g) for f,g in local_features(root,cfg['water']['polygon_source']) if 'Los Angeles Riv' in (f['properties'].get('name') or '')]
    sections=[];path=root/'data/raw/stage02/dem/usgs_1m_downtown_B23.tif'
    with rasterio.open(path) as source:
        tx=Transformer.from_crs(32611,source.crs,always_xy=True)
        for y in np.arange(-1500,1501,500):
            search=LineString([(1000,y),(4000,y)]);hits=[]
            for f,g in parents:
                cross=g.intersection(search)
                lines=[cross] if cross.geom_type=='LineString' else [a for a in getattr(cross,'geoms',[]) if a.geom_type=='LineString']
                for line in lines:
                    if line.length>1:hits.append((f,line))
            if not hits:continue
            f,line=min(hits,key=lambda item:item[1].distance(Point(2200,y)));mid=line.interpolate(.5,normalized=True);half=int(max(80,np.ceil(line.length/2+20)));offsets=np.arange(-half,half+1)
            xy=np.column_stack([mid.x+offsets,np.full(len(offsets),y)]);xx,yy=tx.transform(xy[:,0]+o[0],xy[:,1]+o[1]);z=np.array([a[0] for a in source.sample(zip(xx,yy))],dtype=float)
            good=np.isfinite(z)&(z!=source.nodata)
            if not good.all():continue
            sections.append({'source_water_area_id':f['properties']['id'],'center_local_xy_m':[mid.x,mid.y],
                'center_lon_lat':Transformer.from_crs(32611,4326,always_xy=True).transform(mid.x+o[0],mid.y+o[1]),
                'offsets_east_west_m':offsets.tolist(),'ground_NAVD88_m':z.tolist(),'hydrographic_polygon_width_along_transect_m':line.length,
                'source_file':str(path.relative_to(root)),'source_crs':str(source.crs),'horizontal_conversion':'EPSG32611 to sourceEPSG26911, always_xy, PROJ installed operation',
                'source_sample_spacing_m':1,'sampling':'nearest native 1m bare-earth DEM samples; no source precision claim',
                'scope':'Actual river beside Downtown work window; original 4x4km work window and city origin unchanged',
                'cross_section_type':'terrain investigation, not surveyed hydraulic/engineering section','current_flow_width_m':None,'bank_material':'unverified'})
    index=json.loads((root/f'data/processed/stage03/{quality}/tile_index.json').read_text());reaches=[]
    for f,g in parents:
        for t in index['tiles']:
            x,y,_=t['blender_object_translation_m'];piece=g.intersection(box(x,y,x+cfg['tile_size_m'],y+cfg['tile_size_m']))
            if piece.area<1:continue
            reaches.append({'type':'Feature','properties':{'id':f['properties']['id']+'__'+t['id'],'parent_id':f['properties']['id'],'tile_id':t['id'],
                'name':'Los Angeles River areal reach','source_geometry_type':'Census2025 areal hydrography, not inferred centerline buffer',
                'bank_material':'unknown_by_reach','bridge_decks':'unavailable','current_wetted_extent':'not_observed','detail_source':'USGS bare-earth DEM,1m only within acquired tile footprint,10m elsewhere'},'geometry':to_geographic(piece,o)})
    write_json(root/'data/processed/stage03/la_river_adjacent_1m_sections.json',sections)
    write_json(root/'data/processed/stage03/la_river_area_reaches.geojson',{'type':'FeatureCollection','features':reaches})
    report={'status':'actual_bare_earth_sections_extracted','section_count':len(sections),'areal_reach_count':len(reaches),
        'linear_water_gap':'Linear TIGER LosAngelesRiver segments omit the nearby Downtown areal water stretch. Full areal hydrography is used; no river relocation or assumed buffer widths.',
        'materials_and_bridges':'Unknown by reach; terrain sections do not identify concrete versus natural material or bridge decks'}
    write_json(root/'work/reports/stage03/river_sections.json',report);print('ACTUAL_RIVER_SECTIONS',len(sections),'AREAL_REACHES',len(reaches),flush=True)
    return report


if __name__=='__main__':
    from pathlib import Path
    prepare(Path(__file__).resolve().parents[1],'medium')
