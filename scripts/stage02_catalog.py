"""Dataset-level provenance; web modified timestamps never become acquisition years."""
import csv
import datetime
import json
from pathlib import Path

from stage02_io import digest, write_json


def iso_ms(n):return datetime.datetime.fromtimestamp(n/1000,datetime.timezone.utc).isoformat() if n else None


def catalog(root):
    raw=root/'data/raw/stage02';rows=[]
    def row(key,name,publisher,page,download,status,**extra):
        d={'id':key,'name':name,'publisher':publisher,'original_page':page,'download_url':download,
           'status':status,'download_date':None,'acquisition_year':None,'data_content_updated_at':None,
           'page_item_updated_at':None,'reference_vintage':None,'spatial_coverage':None,
           'horizontal_crs':None,'vertical_datum':None,'horizontal_unit':None,'height_unit':None,
           'resolution':None,'nominal_horizontal_accuracy_m':None,'nominal_vertical_accuracy_m':None,
           'accuracy_status':'unknown_not_inferred_from_coordinate_digits','use_conditions':None,
           'attribution':None,'redistribution':'unknown','local_data_files':[],
           'local_metadata_files':[],'notes':[],**extra}
        rows.append(d);return d
    def file_info(p):
        return {'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':digest(p)}
    for name,url in json.loads((root/'config/stage02_census_sources.json').read_text()).items():
        p=raw/'census'/name;receipt=json.loads(Path(str(p)+'.receipt.json').read_text())
        d=row('census_'+name.removesuffix('.zip'),name.removesuffix('.zip').replace('_',' '),'U.S. Census Bureau',
              'https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html',url,'downloaded_verified',
              download_date=receipt.get('downloaded_at_utc'),reference_vintage=2025,
              horizontal_crs='EPSG:4269 / NAD83 (verified from .prj)',horizontal_unit='degree; reprojected to EPSG:32611 meters',
              spatial_coverage='California' if name.startswith('ca_') else 'United States' if name.startswith('us_') else 'Los Angeles County',
              use_conditions='Federal public-domain data; reproduce with Census attribution. Statistical geometry is not a legal land description; retain TIGER/Line trademark disclaimer.',
              attribution='U.S. Census Bureau, 2025 TIGER/Line® Shapefiles',redistribution='allowed_with_attribution_and_trademark_notice',
              local_data_files=[file_info(p)],local_metadata_files=[file_info(Path(str(p)+'.receipt.json')),
                  file_info(raw/'research/census_technical_doc.pdf')],
              notes=['Download HTTP Last-Modified is file publication evidence, not survey acquisition.',
                     'Census technical documentation says positional accuracy varies and cannot be specified uniformly.'])
        if 'places' in name:d['legal_reference_date']='2025-01-01'
        if 'roads' in name:d['notes'].append('No one-way, lane, bridge, tunnel, grade or elevation fields in this file.')
        if 'landmarks' in name:d['notes'].append('Census facilities are not exhaustive land cover or an official protected architectural landmark register.')
    items=[
        ('lariac6_buildings','Countywide Building Outlines (2020)','County of Los Angeles / LARIAC','county_buildings_item.response','buildings'),
        ('county_elevation','LA County Elevation','LA GeoHub / County GIS','research/county_elevation_item.json','terrain'),
        ('county_landcover','Los Angeles County Land Cover','Dudek / LA County canopy project','research/county_landcover_item.json','landcover'),
        ('county_trees','County maintained road trees','County of Los Angeles Public Works','research/trees_item.json','trees'),
        ('city_monuments','Historic Cultural Monuments','Los Angeles Department of City Planning','research/city_monuments_item.json','landmarks'),
        ('county_airports','Airports','County of Los Angeles','research/airports_item.json','transport'),
        ('county_metro','Metro Stations','County of Los Angeles','research/metro_item.json','transport')]
    for key,name,publisher,relative,kind in items:
        p=raw/relative
        if not p.exists():continue
        j=json.loads(p.read_text())
        d=row(key,name,publisher,'https://www.arcgis.com/home/item.html?id='+j['id'],j.get('url'),
              'metadata_only_not_selected',page_item_updated_at=iso_ms(j.get('modified')),
              spatial_coverage=j.get('extent'),horizontal_crs=j.get('spatialReference'),
              use_conditions=j.get('licenseInfo'),attribution=j.get('accessInformation'),
              local_metadata_files=[file_info(p)],notes=['Item modified is NOT observation/acquisition time.'])
        if key=='lariac6_buildings':
            d.update(reference_vintage=2020,acquisition_year=[2008,2014,2017,2020],
                     acquisition_year_basis='Item description: stereo capture 2008, updated with LARIAC4/5/6 imagery in 2014/2017/2020',
                     height_unit=None,notes=d['notes']+['Item says height included; fields, definitions and units NOT yet fetched. HEIGHT/ELEV must not be assumed to be relative meters.',
                                                     'Full hosted layer item size 2,657,910,784 bytes; use small spatial sample and ID paging rather than downloading county GDB blindly.'])
        if key=='county_elevation':
            d['status']='rejected_for_downtown_extent'
            d['notes'].append('Published extent latitude 34.482–34.572 does not intersect Downtown; source age/resolution/unit unresolved.')
        if key=='county_trees':d['notes'].append('Maintained county-road tree subset cannot stand in for all trees in LA city.')
        if key=='county_landcover':d['notes'].append('Published map tile layer is not yet a verified downloadable classified raster; acquisition date unknown.')
    row('la_city_buildings','LA official building footprints','City of Los Angeles',
        'https://maps.lacity.org/lahub/rest/services/Landbase_Information_WFS/MapServer/0',
        'https://maps.lacity.org/lahub/rest/services/Landbase_Information_WFS/MapServer/0/query',
        'metadata_and_data_blocked',notes=['Cannot establish fields, acquisition date, accuracy or units from service name.'])
    row('usgs_3dep','USGS 3DEP DEM/DTM and lidar inventory','USGS',
        'https://apps.nationalmap.gov/lidar-explorer/','https://tnmaccess.nationalmap.gov/api/v1/products',
        'catalog_blocked_no_terrain_downloaded',notes=['No DEM, DTM or LAS/LAZ acquired; acquisition years, resolution and vertical datum remain unknown.'])
    row('osm','OpenStreetMap vectors','OpenStreetMap contributors','https://www.openstreetmap.org/copyright',
        'https://overpass-api.de/api/interpreter','download_blocked',
        use_conditions='ODbL 1.0; attribution and database share-alike obligations apply; no standard map-tile scraping or offline prefetch.',
        attribution='© OpenStreetMap contributors',redistribution='ODbL_conditions_apply',
        local_metadata_files=[file_info(raw/'research/osm_tile_policy.txt'),file_info(raw/'research/osm_copyright_source.txt')],
        notes=['Official policy source obtained from OpenStreetMap GitHub repository; direct website blocked.',
               'OSM object edit timestamps would not establish building construction or survey dates.'])
    # Actual acquisitions replace the provisional network-blocked descriptions.
    by_id={d['id']:d for d in rows}
    bfile=raw/'buildings/LARIAC6_Buildings_2020.gdb.zip'
    if bfile.exists():
        d=by_id['lariac6_buildings'];receipt=json.loads(Path(str(bfile)+'.receipt.json').read_text())
        br=json.loads((root/'work/reports/stage02/buildings.json').read_text())
        layer=next(iter(sorted((raw/'network').glob('*/county_buildings/layer.json'))))
        lm=json.loads(layer.read_text())
        d.update(status='downloaded_full_county_standardized_city',download_date=receipt['downloaded_at_utc'],
                 horizontal_crs='EPSG:6424 NAD83(2011) / California zone 5 (ftUS), verified in GDB',
                 horizontal_unit='US survey foot; geometry normalized to meters',height_unit='raw HEIGHT/ELEV unit not independently field-dictionary verified; US survey foot candidate from product guide',
                 data_content_updated_at=iso_ms(lm.get('editingInfo',{}).get('dataLastEditDate')),
                 local_data_files=[file_info(bfile)],
                 local_metadata_files=d['local_metadata_files']+[file_info(layer),file_info(raw/'research/county_buildings_layer_metadata.xml'),file_info(raw/'research/lariac6_product_guide.pdf')],
                 per_feature_reported_year_counts=br['year_counts'],
                 notes=['2020 is archive reference vintage, NOT the acquisition year of every retained building.',
                        'DATE_ source-reported years include older 1992/2003/2008/2014/2017 records; exact flight dates not established.',
                        'LARIAC6 guide states all products delivered in US survey feet; no authoritative HEIGHT/ELEV field dictionary found.',
                        'height_m remains null; height_candidate_m is explicitly inferred. ELEV is not used as ground height.',
                        'Ground height is independently sampled from USGS NAVD88 DEM. Roofline, courtyard and solar-structure types are distinguished.',
                        'Internal/research use; original county terms retained. An explicit unrestricted redistribution grant has not been established.'])
        d['download_url']=receipt['url']
        d['acquisition_year']=sorted(int(x) for x in br['year_counts'])
        d['redistribution']='requires_original_county_terms_review_before_public_delivery'
    sample=next(iter(sorted((raw/'network').glob('*/la_city_buildings/page_00000000.json'))),None)
    if sample:
        d=by_id['la_city_buildings'];d.update(status='sample_acquired_older_source_not_primary',local_data_files=[file_info(sample)],
            notes=['82 features in the tested small window; server count and exact ID set verified.',
                   'Schema contains LARIAC_BUILDINGS_2014_AREA; related official City Planning item describes a 2014 dataset. Exact MapServer capture dates remain unverified.',
                   'Prefer the county 2020 archive; explicit OLD_BLD_ID links and geometric overlap are retained. No duplicate city/County building meshes.'])
    ufile=raw/'dem/usgs_1m_downtown_B23.tif'
    if ufile.exists():
        d=by_id['usgs_3dep'];d.update(name='USGS 3DEP 1m bare-earth DEM / CA_LosAngeles_B23',status='downloaded_verified',
            original_page='https://www.sciencebase.gov/catalog/item/689bf41fd4be0276bfcb20af',
            download_url=json.loads(Path(str(ufile)+'.receipt.json').read_text())['url'],
            download_date=json.loads(Path(str(ufile)+'.receipt.json').read_text())['downloaded_at_utc'],
            acquisition_year=[2023,2024],acquisition_start='2023-01-08',acquisition_end='2024-01-07',
            page_item_updated_at='2025-08-12',publication_date='2025-08-11',
            spatial_coverage=[-118.300367,33.973699,-118.190765,34.064963],horizontal_crs='EPSG:26911',
            horizontal_unit='m',vertical_datum='NAVD88',height_unit='m',resolution='1m bare-earth grid',
            local_data_files=[file_info(ufile)],local_metadata_files=[file_info(raw/'research/usgs_1m_metadata.xml')],
            use_conditions='3DEP public domain; acknowledge USGS, identify modifications, no USGS endorsement or accuracy warranty.',
            attribution='U.S. Geological Survey, 3D Elevation Program',redistribution='public_domain_with_attribution_and_modification_notice',
            notes=['Source XML time period verified; publication date does not replace acquisition period.',
                   'Numeric horizontal/vertical accuracy not supplied in this tile metadata; do not equate 1m pixels with 1m accuracy.'])
        tiles=sorted((raw/'dem').glob('usgs_10m_*.tif'))
        if tiles:
            d2=row('usgs_3dep_city_10m','USGS 3DEP 1/3 arc-second city overview DEM','USGS',
                'https://tnmaccess.nationalmap.gov/api/v1/products','see config/stage02_dem_sources.json',
                'downloaded_verified',reference_vintage='selected publication versions 2025; acquisition mixed/unknown',
                horizontal_crs='EPSG:4269 (verified GeoTIFF); normalized EPSG:32611',horizontal_unit='degree in source; meters in output',
                vertical_datum='NAVD88',height_unit='m',resolution='1/3 arc-second source; 10m normalized grid',
                local_data_files=[file_info(p) for p in tiles],local_metadata_files=[file_info(raw/'dem/city_10m_catalog_correct.json')],
                use_conditions=d['use_conditions'],attribution=d['attribution'],redistribution=d['redistribution'],
                notes=['Selected newest catalog publication per n34w119/n35w119 tile; source observation years unresolved.',
                       'Raster NoData and small residual coverage gaps retained, never replaced by invented relief.'])
            d2['download_date']=max(json.loads(Path(str(p)+'.receipt.json').read_text())['downloaded_at_utc'] for p in tiles)
    nfile=raw/'landcover/nlcd2021_city_30m.tif'
    if nfile.exists():
        row('nlcd2021','NLCD 2021 land cover / MRLC WCS','USGS / MRLC',
            'https://www.mrlc.gov/geoserver/mrlc_display/wcs?service=WCS&request=GetCapabilities&version=1.0.0',
            json.loads(Path(str(nfile)+'.receipt.json').read_text())['url'],'downloaded_verified_categorical_values',
            download_date=json.loads(Path(str(nfile)+'.receipt.json').read_text())['downloaded_at_utc'],reference_vintage=2021,
            spatial_coverage='Census LA city bounding region; see raster geotransform',horizontal_crs='EPSG:5070 served raster, verified',
            horizontal_unit='m',resolution='approximately 30m served grid; normalized to 30m UTM with nearest-neighbor',
            vertical_datum='not_applicable',height_unit='not_applicable',
            use_conditions='USGS/MRLC categorical land-cover product; attribution retained; does not establish actual parcel use or zoning.',
            attribution='USGS / Multi-Resolution Land Characteristics Consortium, NLCD 2021',redistribution='USGS_federal_data_attribution_retained',
            local_data_files=[file_info(nfile)],local_metadata_files=[file_info(raw/'research/nlcd_describe.xml'),file_info(raw/'research/mrlc_capabilities.xml')],
            notes=['Single uint8 band and actual category codes checked; not an RGB map screenshot.',
                   '2021 is classification reference year; exact contributing image dates unknown. Failed old website URL recorded, not cited as verified.'])
    canopy=raw/'canopy/downtown_canopy_2023_1m.tif'
    if canopy.exists():
        row('lariac7_canopy','LARIAC7 2023 canopy presence mask','Los Angeles County',
            'https://image.gis.lacounty.gov/image/rest/services/LARIAC7/TREE_CANOPY_2023/ImageServer',
            'https://image.gis.lacounty.gov/image/rest/services/LARIAC7/TREE_CANOPY_2023/ImageServer/exportImage',
            'downloaded_downtown_quality_limitations',download_date=json.loads(Path(str(canopy)+'.receipt.json').read_text())['downloaded_at_utc'],
            acquisition_year=2023,spatial_coverage='Downtown 4x4km export; urban/suburban source',horizontal_crs='EPSG:6424 native; export EPSG:32611',
            horizontal_unit='US survey foot native, meter output',vertical_datum='not_applicable_to_binary_mask',height_unit='not_a_tree_height_product',
            resolution='1m exported grid',use_conditions='County terms; source warns of artifacts and shadows and says not for authoritative measurement.',
            attribution='Los Angeles County LARIAC7',redistribution='county_terms_review_required',
            local_data_files=[file_info(canopy)],local_metadata_files=[file_info(raw/'research/canopy_layer.json'),file_info(raw/'canopy/export.json')],
            notes=['Source description equates 3.28084 meters and 10 feet; this is inconsistent. Delivered mask retained unchanged.',
                   'Class 0 not definitive absence; classified canopy does not give exact tree counts or current tree heights.'])
    treefolder=raw/'official/city_trees_downtown'
    if treefolder.exists():
        tf=root/'data/processed/stage02/trees.geojson';features=json.loads(tf.read_text())['features']
        dates=sorted({f['properties'].get('acquisition_date') for f in features if isinstance(f['properties'].get('acquisition_date'),str)})
        row('city_park_tree_inventory','LA Recreation and Parks tree inventory / Downtown envelope','City of Los Angeles Recreation and Parks',
            'https://maps.lacity.org/lahub/rest/services/Recreation_and_Parks_Department/MapServer/6',
            'https://maps.lacity.org/lahub/rest/services/Recreation_and_Parks_Department/MapServer/6/query',
            'downloaded_sample_complete_not_all_city_trees',acquisition_year=sorted({x[:4] for x in dates}),
            source_reported_gps_date_range=[dates[0],dates[-1]] if dates else None,
            spatial_coverage='queried Downtown bounding envelope, 75 returned points; parks only',horizontal_crs='EPSG:3857 service; requested EPSG:4326',
            horizontal_unit='meters service, degree exchange',height_unit='explicit ft ranges in some TREE_HEIGH values; intervals converted without midpoint',
            use_conditions='Original City GIS public service terms; inventory is archival, not current tree health/size certification.',
            attribution='City of Los Angeles Department of Recreation and Parks',redistribution='city_terms_review_required',
            local_data_files=[file_info(p) for p in sorted(treefolder.glob('page_*.json')) if not p.name.endswith('.receipt.json')],local_metadata_files=[file_info(treefolder/'layer.json'),file_info(treefolder/'completeness.json')],
            notes=['2026 third-party copy is NOT the collection date; original service and per-feature GPS_Date used.',
                   'Street trees and parks outside the query envelope not comprehensively downloaded.'])
    hfolder=raw/'landmarks/hcm'
    if hfolder.exists():
        d=by_id['city_monuments'];d.update(status='downloaded_complete_service_id_set',
            local_data_files=[file_info(p) for p in sorted(hfolder.glob('page_*.json')) if not p.name.endswith('.receipt.json')],
            local_metadata_files=d['local_metadata_files']+[file_info(hfolder/'layer.json'),file_info(hfolder/'completeness.json')],
            notes=['All 1347 returned source IDs checked. DATE_ACTIVE is designation date, not construction/acquisition date.',
                   'Official names and geometry retained, including outside-current-city references flagged for review.',
                   'No facade photos acquired or licensed; appearance study is not claimed complete.'])
    if (raw/'official/city_boundary/page_00000000.json').exists():
        row('municipal_boundary','LA City GIS published administrative boundary','City of Los Angeles',
            'https://maps.lacity.org/lahub/rest/services/Boundaries/MapServer/7',
            'https://maps.lacity.org/lahub/rest/services/Boundaries/MapServer/7/query','downloaded_verified_reference_date_unknown',
            horizontal_crs='EPSG:3857 service, requested EPSG:4326',horizontal_unit='m service / degrees exchange',
            use_conditions='City GIS public service terms; no numeric survey accuracy or effective boundary date established.',
            local_data_files=[file_info(raw/'official/city_boundary/page_00000000.json')],
            local_metadata_files=[file_info(raw/'official/city_boundary/layer.json')],
            notes=['Compared with Census 2025; large marine/coastal treatment differences are not evidence of annexation.',
                   'Census 2025 remains the explicit-date processing boundary; preserve both versions.'])
    by_id['osm'].update(status='investigated_unavailable_not_adopted',notes=[
        'Copyright page and official tile policy retrieved. No raster map tiles requested.',
        'Primary Overpass returned 503 after bounded retries; alternative hosts returned proxy 403; no OSM features falsely reported acquired.'])
    for d in rows:
        receipts=[Path(str(root/f['path'])+'.receipt.json') for f in d['local_data_files']]
        d['download_requests']=[{'receipt_file':str(p.relative_to(root)),
            'url':json.loads(p.read_text())['url'],
            'parameters':json.loads(p.read_text()).get('request_parameters',{})} for p in receipts if p.exists()]
        if d['download_date'] is None and d['local_data_files']:
            dates=[json.loads(p.read_text()).get('downloaded_at_utc') for p in receipts if p.exists()]
            d['download_date']=max((x for x in dates if x),default=None)
        if d['download_date'] is None and d['local_metadata_files']:
            d['metadata_obtained_at_utc']=datetime.datetime.fromtimestamp((root/d['local_metadata_files'][0]['path']).stat().st_mtime,datetime.timezone.utc).isoformat()
    dest=root/'data/processed/stage02';write_json(dest/'source_registry.json',{'datasets':rows})
    fields=['id','name','publisher','original_page','download_url','status','download_date','acquisition_year',
            'reference_vintage','data_content_updated_at','page_item_updated_at','spatial_coverage','horizontal_crs',
            'vertical_datum','horizontal_unit','height_unit','resolution','nominal_horizontal_accuracy_m',
            'nominal_vertical_accuracy_m','accuracy_status','use_conditions','attribution','redistribution',
            'local_data_files','local_metadata_files','download_requests','notes']
    with (dest/'source_registry.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for d in rows:w.writerow({k:json.dumps(d.get(k),ensure_ascii=False) if isinstance(d.get(k),(list,dict)) else d.get(k) for k in fields})
    docs=root/'docs/stage02';docs.mkdir(parents=True,exist_ok=True)
    lines=['# 第二阶段来源与精度登记','',
           '完整逐字段登记见 data/processed/stage02/source_registry.json / .csv。null 表示未知，不能据名称、坐标小数位或网页日期补写。','',
           '| 数据集 | 状态 | 采集/参考年代 | 条目更新 | 本地数据文件数 |','|---|---|---|---|---|']
    for d in rows:lines.append(f"| {d['name']} | {d['status']} | acquisition={d['acquisition_year']}; reference={d['reference_vintage']} | {d['page_item_updated_at']} | {len(d['local_data_files'])} |")
    lines+=['','Census 技术文档实际已读取：边界法律参考日 2025-01-01，但不是地籍法律描述；坐标精度因原始资料而异。',
            '派生产品使用 U.S. Census Bureau, 2025 TIGER/Line® Shapefiles。TIGER/Line 是 Census Bureau 注册商标，本项目不是其官方产品，也不获其背书。',
            'Census 设施/公园分类仅支持概略功能范围，不替代完整土地覆盖、当前运营交通网或法定文保名单。',
            '县建筑资料是 2020 参考版，条目 2026 更新不改变采集年份。产品指南为美国测量英尺；HEIGHT/ELEV 字段含义仍缺字典确认，候选高度单列为 inferred，已核实 height_m 保持 null。',
            'OSM 标准瓦片政策原文已读取，明确禁止批量抓取与离线预取；本工程未请求任何标准地图瓦片。']
    (docs/'sources.md').write_text('\n'.join(lines)+'\n')
    print('SOURCE_REGISTRY_WRITTEN',len(rows),flush=True)
    return rows
