"""Stage 01: documented working extents only; no city-feature acquisition."""
import hashlib
import json
import datetime
import shutil
from pathlib import Path

from pyproj import Geod, Transformer
from shapely import make_valid
from shapely.geometry import Point, box, mapping, shape
from shapely.ops import transform, unary_union
from shapely.validation import explain_validity


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def prepare(root, cfg):
    raw = root / 'data/raw'
    for receipt in raw.glob('*.receipt.json'):
        r = json.loads(receipt.read_text())
        p = raw / receipt.name.removesuffix('.receipt.json')
        if hashlib.sha256(p.read_bytes()).hexdigest() != r['sha256']:
            raise ValueError(f'Raw source checksum mismatch: {p}')
    scope_hash=hashlib.sha256()
    scope_hash.update(json.dumps({'geography':cfg['geography'],'coordinates':cfg['coordinates']},sort_keys=True).encode())
    scope_hash.update(Path(__file__).read_bytes())
    for p in sorted(p for p in raw.glob('*') if p.is_file()):
        scope_hash.update(p.name.encode());scope_hash.update(p.read_bytes())
    scope_fp=scope_hash.hexdigest()
    manifest_path=root/'data/processed/scopes.manifest.json'
    targets=[root/'data/processed/scopes.geojson',root/'data/processed/scopes.local-meters.json',root/'data/processed/origin.json',root/'work/reports/scopes.json',root/'work/previews/scopes.svg']
    if manifest_path.exists():
        old=json.loads(manifest_path.read_text())
        for item in old['artifacts']:
            p=root/item['path']
            if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:
                raise ValueError('Scope output changed; preserve user edits: '+str(p))
        if old['fingerprint']==scope_fp:
            print('SCOPES_CACHE_VERIFIED')
            return json.loads((root/'work/reports/scopes.json').read_text())
        archive=root/'work/history'/('scopes_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        for p in [*targets,manifest_path]:
            dest=archive/p.relative_to(root);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    elif any(p.exists() for p in targets):
        raise ValueError('Existing scope outputs lack manifest; preserve them explicitly before rebuilding')
    source = json.loads((raw / cfg['geography']['city']['source']).read_text())
    fwd = Transformer.from_crs(4326, 32611, always_xy=True)
    rev = Transformer.from_crs(32611, 4326, always_xy=True)
    geod = Geod(ellps='WGS84')
    checks = []
    def check(name, ok, details):
        checks.append({'name': name, 'passed': bool(ok), 'details': details})
        if not ok:
            raise ValueError(f'{name}: {details}')
    def city(geoid):
        matches = [f for f in source['features'] if f['properties']['GEOID'] == geoid]
        check('unique_geoid_' + geoid, len(matches) == 1, len(matches))
        return matches[0]
    la = city(cfg['geography']['city']['geoid'])
    la_geo = shape(la['geometry'])
    la_metric = transform(fwd.transform, la_geo)
    check('city_geometry_valid', la_geo.is_valid and not la_geo.is_empty, la_geo.geom_type)
    nbs = json.loads((raw / cfg['geography']['downtown']['source']).read_text())
    downtown = next(f for f in nbs['features'] if f['properties']['name'] == 'Downtown')
    dt_raw = transform(fwd.transform, shape(downtown['geometry']))
    repair = {'needed': not dt_raw.is_valid, 'original_validity': explain_validity(dt_raw), 'method': None}
    dt = dt_raw
    if not dt_raw.is_valid:
        fixed = make_valid(dt_raw)
        def polygons(geom):
            if geom.geom_type == 'Polygon': return [geom]
            return [p for part in getattr(geom, 'geoms', []) for p in polygons(part)]
        dt = unary_union(polygons(fixed))
        repair.update({'method':'GEOS make_valid; retain polygonal parts only; raw unmodified',
                       'original_area_m2':dt_raw.area,'processed_area_m2':dt.area,
                       'area_change_m2':dt.area-dt_raw.area})
        check('downtown_repair_area_change_under_one_m2',abs(dt.area-dt_raw.area)<1,repair)
    check('downtown_geometry_valid', dt.is_valid, dt.area)
    center = dt.centroid
    lon, lat = rev.transform(center.x, center.y)
    check('downtown_center_inside_city_and_neighborhood', la_metric.contains(center) and dt.contains(center), [lon, lat])
    fw, fh = cfg['geography']['focus']['width_m'], cfg['geography']['focus']['height_m']
    focus = box(center.x-fw/2, center.y-fh/2, center.x+fw/2, center.y+fh/2)
    check('focus_inside_city', la_metric.covers(focus), focus.difference(la_metric).area)
    check('focus_exact_16_square_km', abs(focus.area - 16000000) < .01, focus.area)
    features = []
    local_features = []
    def add(key, label, metric_geom, properties):
        props = {'id': key, 'label': label, **properties,
                 'projected_area_m2': metric_geom.area}
        features.append({'type': 'Feature', 'properties': props,
                         'geometry': mapping(transform(rev.transform, metric_geom))})
        local_features.append({'type': 'Feature', 'properties': props, 'geometry': mapping(
            transform(lambda x, y, z=None: (x-center.x, y-center.y), metric_geom))})
    add('city', 'Los Angeles city', la_metric, {
        'data_class': 'processed_observed', 'source': cfg['geography']['city']['source'],
        'geoid': '0644000', 'vintage': 2020, 'scale_denominator': 500000,
        'status': 'verified_official_2020_generalized_not_current_legal_boundary',
        'land_area_source_m2': la['properties']['ALAND'],
        'water_area_source_m2': la['properties']['AWATER']})
    add('downtown_reference', 'Downtown / LA Times neighborhood', dt, {
        'source': cfg['geography']['downtown']['source'], 'data_class': 'processed_observed',
        'status': 'editorial_neighborhood_not_administrative'})
    add('downtown', 'Downtown 4 km x 4 km work extent', focus, {
        'data_class': 'inferred', 'derivation': 'project_defined_UTM_aligned_work_window',
        'width_m': fw, 'height_m': fh, 'center_lon': lon, 'center_lat': lat})
    closeups = []
    for c in cfg['geography']['closeups']:
        x, y = fwd.transform(c['center_lon'], c['center_lat'])
        g = box(x-c['width_m']/2, y-c['height_m']/2, x+c['width_m']/2, y+c['height_m']/2)
        check(c['id'] + '_inside_focus_and_city', focus.covers(g) and la_metric.covers(g), g.bounds)
        closeups.append(g)
        add(c['id'], c['label'], g, {
            'data_class': 'inferred', 'width_m': c['width_m'], 'height_m': c['height_m'],
            'status': 'project_selected_multi_block_window_street_edges_not_yet_surveyed'})
    union = unary_union(closeups)
    check('at_least_two_closeups', len(closeups) >= 2, len(closeups))
    check('closeup_union_at_least_250000_m2', union.area >= 250000, union.area)
    bg = []
    for b in cfg['geography']['backgrounds']:
        f = city(b['geoid'])
        check(b['name'] + '_independent_city', f['properties']['LSAD'] == '25' and f['properties']['GEOID'] != '0644000', f['properties'])
        g = transform(fwd.transform, shape(f['geometry']))
        add('background_' + b['geoid'], b['name'], g, {
            'geoid': b['geoid'], 'enabled': b['enabled'], 'role': 'separate_background_not_city_scope',
            'data_class': 'processed_observed', 'source': cfg['geography']['city']['source']})
        bg.append({'name': b['name'], 'geoid': b['geoid'], 'enabled': b['enabled'],
                   'outside_la_centroid': not la_metric.contains(g.centroid),
                   'shared_generalization_sliver_m2': la_metric.intersection(g).area})
    check('roundtrip_under_1mm', abs(fwd.transform(lon, lat)[0]-center.x) < .001 and abs(fwd.transform(lon, lat)[1]-center.y) < .001, [center.x, center.y])
    out = root / 'data/processed'
    save_json(out / 'scopes.geojson', {'type': 'FeatureCollection', 'features': features})
    save_json(out / 'scopes.local-meters.json', {
        'type': 'FeatureCollection', 'coordinate_system': 'local UTM-offset meters, NOT RFC7946 GeoJSON',
        'origin_utm_m': [center.x, center.y], 'epsg': 32611, 'features': local_features})
    origin = {'horizontal_epsg': 32611, 'exchange_epsg': 4326,
              'origin_lon_lat': [lon, lat], 'origin_utm_m': [center.x, center.y],
              'origin_height_m': 0, 'height_status': 'synthetic_not_surveyed',
              'center_method': 'UTM polygon centroid of LA Times Downtown neighborhood'}
    save_json(out / 'origin.json', origin)
    report = {'status': 'passed', 'checks': checks, 'origin': origin, 'downtown_topology_repair': repair,
              'focus_area_m2': focus.area, 'closeup_union_m2': union.area,
              'city_geodesic_polygon_area_m2': abs(geod.geometry_area_perimeter(la_geo)[0]),
              'backgrounds': bg,
              'limitations': ['2020 generalized administrative boundary, current legal precision unverified',
                              'neighborhood reference is editorial', 'closeup edges are work windows, not surveyed street edges']}
    save_json(root / 'work/reports/scopes.json', report)
    # Lightweight real-coordinate overview: same projection for all geometry, no cartographic repositioning.
    def panel(bounds, ids, px, py, width, height):
        xmin, ymin, xmax, ymax = bounds
        scale = min(width/(xmax-xmin), height/(ymax-ymin)) * .91
        cx, cy = (xmin+xmax)/2, (ymin+ymax)/2
        def points(poly):
            rings = [poly.exterior, *poly.interiors]
            return ' '.join('M ' + ' L '.join(f'{px+width/2+(x-cx)*scale:.2f},{py+height/2-(y-cy)*scale:.2f}' for x,y in ring.coords) + ' Z' for ring in rings)
        paths = []
        colors = {'city':'#24475a','downtown_reference':'#487f8a','downtown':'#f6be60','historic_core':'#f47c67','civic_center':'#99dfb5'}
        for f in local_features:
            key = f['properties']['id']
            if key not in ids: continue
            geom = shape(f['geometry'])
            polys = list(geom.geoms) if geom.geom_type == 'MultiPolygon' else [geom]
            color = colors.get(key, '#637286')
            paths += [f'<path d="{points(p)}" fill="{color}" fill-opacity="0.35" stroke="{color}" stroke-width="1.5" fill-rule="evenodd"/>' for p in polys]
        bar = 10000 if width/scale > 20000 else 1000
        paths.append(f'<path d="M {px+25},{py+height-25} h {bar*scale}" stroke="white" stroke-width="3"/><text x="{px+25}" y="{py+height-35}" fill="white">{bar/1000:g} km / grid north ↑</text>')
        return ''.join(paths)
    la_local = shape(local_features[0]['geometry'])
    b = la_local.bounds
    f_bounds = (-2200, -2200, 2200, 2200)
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="700" viewBox="0 0 1200 700"><rect width="1200" height="700" fill="#101d2b"/><g font-family="sans-serif" font-size="16"><text x="30" y="35" fill="white">LA / administrative scope (2020 generalized)</text><text x="625" y="35" fill="white">Downtown / 4 km work extent + closeup windows</text>'
    svg += panel(b, {'city','downtown','background_0670000','background_0606308'}, 0,45,600,600)
    svg += panel(f_bounds, {'downtown_reference','downtown','historic_core','civic_center'},600,45,600,600)
    svg += '<text x="30" y="680" fill="#9eb4c4">Blue: LA | Grey: independent cities, disabled | Gold: focus | Coral: Historic Core | Green: Civic Center</text></g></svg>'
    (root / 'work/previews/scopes.svg').write_text(svg)
    save_json(manifest_path,{'fingerprint':scope_fp,'artifacts':[
        {'path':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in targets]})
    print(f'SCOPES_OK: focus={focus.area:.0f} m2; closeups={union.area:.0f} m2; origin={lon:.8f},{lat:.8f}')
    return report
