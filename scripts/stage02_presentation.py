"""Real building-road-terrain overlay and geographic coverage/gap evidence."""
import json
import math
import os
from pathlib import Path
os.environ['MPLCONFIGDIR']=str(Path(__file__).resolve().parents[1]/'work/cache/matplotlib')
os.environ['XDG_CACHE_HOME']=str(Path(__file__).resolve().parents[1]/'work/cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import LightSource,ListedColormap
import numpy as np
import rasterio
from pyproj import Transformer
from shapely.geometry import shape,mapping
from shapely.ops import transform
from stage02_enrich import read_refs
from stage02_preview import lines
from stage02_io import write_json


def present(root,quality):
    base=root/'data/processed/stage02';out=root/'work/previews/stage02';refs,city,origin=read_refs(root)
    tx=Transformer.from_crs(4326,32611,always_xy=True);inv=Transformer.from_crs(32611,4326,always_xy=True)
    load=lambda n:json.loads((base/n).read_text())
    build=load('downtown_buildings.geojson')['features'];excluded=load('model_selection.json')['excluded_duplicate_ids']
    build=[f for f in build if f['properties']['feature_type']=='building_roofline' and f['properties']['id'] not in excluded]
    buildings=[transform(tx.transform,shape(f['geometry'])) for f in build]
    roads=[transform(tx.transform,shape(f['geometry'])) for f in load('downtown_roads.geojson')['features']]
    trees=[transform(tx.transform,shape(f['geometry'])) for f in load('trees.geojson')['features']]
    b=refs['downtown'].bounds;extent=[b[0]-origin[0],b[2]-origin[0],b[1]-origin[1],b[3]-origin[1]]
    def local(gs):return [[(x-origin[0],y-origin[1]) for x,y,*_ in line] for g in gs for line in lines(g)]
    def style(ax,title,bounds):
        ax.set_facecolor('#162532');ax.set_title(title,color='white',loc='left',fontsize=12)
        ax.set_aspect('equal');ax.set_xlim(bounds[0]-origin[0],bounds[2]-origin[0]);ax.set_ylim(bounds[1]-origin[1],bounds[3]-origin[1])
        ax.tick_params(colors='#b4c6d3',labelsize=8);ax.set_xlabel('Grid east / m',color='#b4c6d3');ax.set_ylabel('Grid north / m',color='#b4c6d3')
    with rasterio.open(base/'downtown_1m_dem_navd88_m.tif') as d:
        full=d.read(1);elev=d.read(1,out_shape=(1000,1000));affine=d.transform
    with rasterio.open(base/'downtown_canopy_2023_1m.tif') as d:canopy=d.read(1,out_shape=(1000,1000))
    hill=LightSource(azdeg=315,altdeg=40).hillshade(elev,vert_exag=1,dx=4,dy=4)
    fig,ax=plt.subplots(figsize=(12,11),facecolor='#101d2b');style(ax,'DOWNTOWN / ACTUAL BUILDINGS + ROADS + BARE-EARTH DEM',b)
    ax.imshow(hill,extent=extent,cmap='gray',vmin=0,vmax=1,alpha=.85)
    ax.imshow(np.ma.masked_where(canopy!=1,canopy),extent=extent,cmap=ListedColormap(['#46a864']),alpha=.65,interpolation='nearest')
    ax.add_collection(LineCollection(local(buildings),colors='#4bbfe9',linewidths=.28))
    ax.add_collection(LineCollection(local(roads),colors='#f4d69c',linewidths=.6))
    inside=[p for p in trees if p.intersects(refs['downtown'])]
    ax.scatter([p.x-origin[0] for p in inside],[p.y-origin[1] for p in inside],s=8,c='#6ae0a5',edgecolors='#183b2d',linewidths=.25)
    ax.add_collection(LineCollection(local([refs['historic_core'],refs['civic_center']]),colors='#ffffff',linewidths=1.2))
    ax.plot([-1800,-1300],[-1820,-1820],color='white',lw=3);ax.text(-1800,-1740,'500 m',color='white',fontsize=9)
    ax.text(1750,1700,'N ↑',color='white',fontsize=12)
    fig.text(.08,.035,'Blue: 2020-release rooflines (mixed capture years) | Gold: 2025 roads | Green: 2023 canopy + archival park tree points',color='#c8d6df',fontsize=9)
    fig.text(.08,.014,'DEM: 1 m bare earth, acquisition 2023–2024, NAVD88 meters. Rooflines are plan geometry, not verified facade/roof elevations.',color='#f2c67b',fontsize=9)
    fig.tight_layout(rect=(0,.06,1,1));fig.savefig(out/'downtown_overlay.png',dpi=160);fig.savefig(out/'downtown_partial_overlay.png',dpi=160);plt.close(fig)
    # Enrich the already-generated coverage grid with actual footprint observations.
    coverage=load('coverage.geojson');counts=load('building_coverage_counts_1km.json')
    for f in coverage['features']:
        p=f['properties'];key=p['id'].removeprefix('coverage_1km_');p['counts']['building_or_structure_centroids']=counts.get(key,0)
        p.update(buildings='2020_archive_full_city_downloaded_and_audited',terrain='observed_10m_city; 1m_Downtown',
                 landcover='NLCD_2021_30m',trees='partial_archival_parks_inventory; 2023_canopy_Downtown',
                 height_semantics='HEIGHT interpretation unresolved; inferred candidate retained separately',landmarks='official_HCM_plus_Census_reference_names')
    write_json(base/'coverage.geojson',coverage)
    gaps=[]
    for key,g,reason in [('verified_height_semantics',city,'Raw HEIGHT present, field meaning not confirmed by a field dictionary; candidate separate'),
                         ('independent_building_parts',city,'No independent architectural part segmentation in chosen source'),
                         ('fine_terrain_outside_downtown',city.difference(refs['downtown']),'10m observed terrain available; 1m only Downtown'),
                         ('complete_current_tree_inventory',city,'75 archival parks-tree points in sample; not all city/street trees'),
                         ('road_operational_attributes',city,'Lane, one-way, bridge/tunnel layer semantics missing; no inferred planar connections')]:
        gaps.append({'type':'Feature','properties':{'id':key,'reason':reason,'gap_type':'semantic_or_resolution_gap_not_absent_geometry'},'geometry':mapping(transform(inv.transform,g))})
    write_json(base/'gaps.geojson',{'type':'FeatureCollection','features':gaps})
    fig,axs=plt.subplots(1,2,figsize=(14,10),facecolor='#101d2b')
    style(axs[0],'ACQUIRED / city-wide observed geometry and DEM',city.bounds)
    style(axs[1],'GAPS / field meaning, detail and currentness',city.bounds)
    for ax in axs:ax.add_collection(LineCollection(local([city]),colors='#e5b46f',linewidths=.8));ax.add_collection(LineCollection(local([refs['downtown']]),colors='white',linewidths=1.2))
    axs[0].add_collection(LineCollection(local([transform(tx.transform,shape(f['geometry'])) for f in load('roads.geojson')['features']]),colors='#8cb3ce',linewidths=.1))
    audit=json.loads((root/'work/reports/stage02/building_output_audit.json').read_text())
    axs[0].text(.04,.06,f"{audit['buildings']:,} building observations\n{len(excluded)} exact duplicates have model-selection exclusions\nDEM: ~10m city / 1m Downtown\nLand cover: NLCD 2021 / 30m",transform=axs[0].transAxes,color='#c4dfd2',fontsize=10,linespacing=1.5)
    axs[1].text(.04,.1,'HEIGHT field meaning: unresolved\nFloors / architectural parts: missing\nLanes / one-way / cross-layer topology: unknown\nTree inventory: partial and archival\nAppearance is NOT one-date city truth',transform=axs[1].transAxes,color='#ffbcb1',fontsize=10,linespacing=1.5)
    fig.suptitle('LOS ANGELES / STAGE 02 / COVERAGE AND DATA LIMITS',color='white',fontsize=15)
    fig.tight_layout(rect=(0,.03,1,.96));fig.savefig(out/'coverage_and_gaps.png',dpi=150)
    for ax,name in zip(axs,['coverage_map.png','gap_map.png']):
        fig.canvas.draw();bbox=ax.get_tightbbox(fig.canvas.get_renderer()).transformed(fig.dpi_scale_trans.inverted()).expanded(1.03,1.03)
        fig.savefig(out/name,dpi=160,bbox_inches=bbox,facecolor=fig.get_facecolor())
    plt.close(fig)
    # Prepare local-meter geometry and genuine NAVD88 ground Z for Blender data review.
    with rasterio.open(base/'city_10m_dem_navd88_m.tif') as d:
        city_dem=d.read(1);city_affine=d.transform;city_nodata=d.nodata
    def sample(x,y):
        row,col=rasterio.transform.rowcol(affine,x+origin[0],y+origin[1])
        if 0<=row<full.shape[0] and 0<=col<full.shape[1]:return float(full[row,col])
        row,col=rasterio.transform.rowcol(city_affine,x+origin[0],y+origin[1])
        z=float(city_dem[row,col]) if 0<=row<city_dem.shape[0] and 0<=col<city_dem.shape[1] else city_nodata
        if z==city_nodata:raise ValueError('No observed ground for preview vertex; cannot invent elevation')
        return z
    road_lines=local(roads);building_lines=local(buildings)
    grid_rows=np.linspace(0,full.shape[0]-1,101).astype(int);grid_cols=np.linspace(0,full.shape[1]-1,101).astype(int)
    grid=full[np.ix_(grid_rows,grid_cols)]
    job={'origin_utm_m':origin,'quality':quality,'road_lines':road_lines,
         'road_feature_ids':[f['properties']['id'] for f,g in zip(load('downtown_roads.geojson')['features'],roads) for _ in lines(g)],
         'road_z':[[sample(x,y)+.4 for x,y in line] for line in road_lines],
         'building_lines':building_lines,'building_z':[[sample(x,y)+.7 for x,y in line] for line in building_lines],
         'building_feature_ids':[f['properties']['id'] for f,g in zip(build,buildings) for _ in lines(g)],
         'terrain_grid':grid.tolist(),'terrain_extent_m':[-1999.5,1999.5,-1999.5,1999.5],
         'terrain_grid_x':((grid_cols+.5)*affine.a+affine.c-origin[0]).tolist(),
         'terrain_grid_y':((grid_rows+.5)*affine.e+affine.f-origin[1]).tolist(),
         'vertical_datum':'NAVD88','z_status':'observed DEM meters; vector strokes have explicit 0.4/0.7m display offsets, not measured roof height',
         'water_lines':[],'closeup_lines':local([refs['historic_core'],refs['civic_center']]),
         'blend_path':str(root/'scenes/stage02_data_review.blend'),'render_path':str(out/'blender_data_review.png'),
         'check_path':str(root/'work/reports/stage02/blender_check.json')}
    write_json(root/'work/reports/stage02/blender_job.json',job)
    print('REAL_BUILDING_ROAD_TERRAIN_OVERLAY_PREPARED',len(build),'building observations',len(roads),'roads',flush=True)
    return job
