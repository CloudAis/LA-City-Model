"""Independent source-plan, saved-array, entry and actual terrain-seam audit.

This checks numerical consistency of generated arrays, not architectural survey
accuracy. It never edits source records or repairs a failed geometry silently.
"""
from pathlib import Path
import datetime
import hashlib
import json
import math
import sys
from zoneinfo import ZoneInfo

import numpy as np
import shapely
from shapely.geometry import shape

from stage07_final_data import Grade
from stage03_common import polygon_parts
from stage05_geometry import partitioned_bands

ROOT = Path(__file__).resolve().parents[1]
OUT = 'data/processed/stage07_final'
REPORT = 'work/reports/stage07_final/geometry_audit.json'
FRAGMENTS = {967433, 968803, 1042507}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads((ROOT/path).read_text())


def holes(g):
    return sum(len(p.interiors) for p in polygon_parts(g))


def load_npz(relative):
    with np.load(ROOT/relative) as arrays:
        return {k: arrays[k].copy() for k in arrays.files}


def boundary_segments(v, f, axis, coordinate):
    """Real triangle edges on a tile boundary; do not span road-cut holes."""
    edges = np.concatenate((f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]))
    vv = v[edges]
    selected = np.all(np.abs(vv[:, :, axis]-coordinate) < 1e-5, axis=1)
    vv = vv[selected]
    along = 1-axis
    vv = vv[np.abs(vv[:, 1, along]-vv[:, 0, along]) > 1e-7]
    if not len(vv):
        return np.empty((0, 4))
    reverse = vv[:, 0, along] > vv[:, 1, along]
    vv[reverse] = vv[reverse, ::-1]
    segments = np.column_stack((vv[:, 0, along], vv[:, 1, along], vv[:, 0, 2], vv[:, 1, 2]))
    return np.unique(np.round(segments, 7), axis=0)


def heights_at(segments, t):
    selected = (segments[:, 0]-1e-6 <= t) & (segments[:, 1]+1e-6 >= t)
    s = segments[selected]
    if not len(s):
        return None
    z = s[:, 2] + (t-s[:, 0])/(s[:, 1]-s[:, 0])*(s[:, 3]-s[:, 2])
    return float(np.median(z)), float(np.ptp(z))


def seam(a, b, axis, boundary):
    sa = boundary_segments(*a, axis, boundary)
    sb = boundary_segments(*b, axis, boundary)
    endpoints = np.unique(np.concatenate((sa[:, :2].ravel(), sb[:, :2].ravel())))
    samples = sorted(set(endpoints.tolist()+((endpoints[:-1]+endpoints[1:])/2).tolist()))
    errors, spreads = [], []
    for t in samples:
        za, zb = heights_at(sa, t), heights_at(sb, t)
        if za is not None and zb is not None:
            errors.append(abs(za[0]-zb[0]))
            spreads.extend((za[1], zb[1]))
    return {
        'actual_boundary_edges_a': len(sa), 'actual_boundary_edges_b': len(sb),
        'shared_supported_samples': len(errors),
        'max_computational_z_difference_m': max(errors, default=None),
        'max_same_side_multivalued_z_m': max(spreads, default=None),
        'road_cut_gaps_not_interpolated': True,
    }


def run():
    for path in ('PROJECT_SPEC.md', 'STATUS.md'):
        assert (ROOT/path).read_text().strip()
    index = read(OUT+'/index.json')
    source = {b['i']: b for b in read('data/processed/stage07/buildings.json')}
    grade = Grade()
    failures, buildings, mesh_checks, entrances, part_checks = [], [], [], [], []

    def require(ok, message):
        if not ok:
            failures.append(message)

    wanted = set(source)-set(index['skybridge']['replaces'])
    require(len(wanted) == 100 and {b['i'] for b in index['buildings']} == wanted,
            'Source replacement building IDs do not match the 100 non-skybridge records')
    for b in index['buildings']:
        original = source[b['i']]
        g, retained, wall = shape(original['geometry']), shape(b['source_geometry']), shape(b['wall_plan'])
        distance = float(g.hausdorff_distance(wall))
        row = {'i': b['i'], 'uid': b['uid'], 'name': b['name'], 'region': b['region'],
               'source_plan_valid': bool(g.is_valid), 'wall_plan_valid': bool(wall.is_valid),
               'original_geometry_retained_exactly': bool(g.equals_exact(retained, 0)),
               'source_to_wall_hausdorff_m': distance,
               'source_parts': len(polygon_parts(g)), 'wall_parts': len(polygon_parts(wall)),
               'source_courtyard_holes': holes(g), 'wall_courtyard_holes': holes(wall),
               'source_height_input_m': original['height_m'], 'generated_height_input_m': b['height_input_m'],
               'height_evidence': b['height_source'], 'doors': len(b['doors'])}
        buildings.append(row)
        require(row['original_geometry_retained_exactly'], f"{b['i']}: original source geometry changed")
        require(wall.is_valid and distance <= .10001, f"{b['i']}: wall plan exceeds documented 0.10m simplification")
        require(row['source_parts'] == row['wall_parts'] and holes(g) == holes(wall), f"{b['i']}: multipart/courtyard count changed")
        require(b['uid'] == original['uid'] and abs(b['height_input_m']-original['height_m']) < 1e-9,
                f"{b['i']}: stable ID or source height altered")
        if not b['doors']:
            require(b['i'] in FRAGMENTS and g.area <= 10,
                    f"{b['i']}: non-exempt missing door")
            row['entry_exemption'] = 'Tiny source roofline fragment; independent ground building not established; source height remains unverified'
            row['source_plan_area_m2'] = float(g.area)
        for d in b['doors']:
            xy, outward = np.asarray(d['xy_city_m']), np.asarray(d['outward_xy'])
            signed = b['floor_navd88_m']-(grade.local_height(xy+outward*1.5)+.15)
            stored = d['rise_m']
            entry = {'i': b['i'], 'name': b['name'], 'xy_city_m': xy.tolist(),
                     'signed_threshold_minus_sidewalk_at_1_5m_m': signed,
                     'signed_threshold_minus_sidewalk_at_0_6m_m': b['floor_navd88_m']-(grade.local_height(xy+outward*.6)+.15),
                     'signed_threshold_minus_sidewalk_at_door_m': b['floor_navd88_m']-(grade.local_height(xy)+.15),
                     'stored_step_rise_m': stored, 'steps': d['steps'],
                     'step_rise_m': d['step_rise_m'],
                     'signed_to_stored_difference_m': signed-stored,
                     'near_grade_visual_tolerance_m': .10}
            entrances.append(entry)
            require(abs(signed-stored) <= .10, f"{b['i']}: entrance signed grade differs from stored rise by >0.10m: {signed-stored:.6f}m")
            require(d['steps'] <= 24 and d['step_rise_m'] <= .170001,
                    f"{b['i']}: generated step rise/count exceeds configured bounds")

        if original['attrs'].get('parts'):
            roof_record = next((r for r in b['near'] if r['name'] == 'roof'), None)
            require(roof_record is not None, f"{b['i']}: source-part roofs missing")
            if roof_record:
                arrays = load_npz(roof_record['file'])
                triangles = arrays['v'][arrays['f']].astype(float)
                flat = np.ptp(triangles[:, :, 2], axis=1) < 1e-5
                observed = np.unique(np.round(triangles[flat, 0, 2], 4)).tolist()
                expected_heights = sorted({min(b['height_input_m'], p['height_m']) for p in original['attrs']['parts']})
                actual_support = []
                for z in expected_heights:
                    matched = flat & (np.abs(triangles[:, 0, 2]-z) < 1e-4)
                    xy = triangles[matched, :, :2]
                    area = float(shapely.area(shapely.polygons(xy)).sum()) if len(xy) else 0.
                    actual_support.append({'source_part_top_m': z, 'actual_roof_triangles_at_top': int(matched.sum()), 'actual_horizontal_area_m2': area})
                part_checks.append({'i': b['i'], 'source_part_count': len(original['attrs']['parts']),
                                    'source_podium_height_m': original['attrs'].get('podium_height_m'),
                                    'source_part_heights_m': expected_heights, 'observed_flat_roof_levels_m': observed,
                                    'actual_roof_support': actual_support,
                                    'source_parts_not_interpreted_as_random_heights': True})
                # Covered lower parts can have no exposed roof; at least two
                # source-height levels must survive to reject a full-height prism.
                require(sum(x['actual_horizontal_area_m2'] > .1 for x in actual_support) >= 2,
                        f"{b['i']}: source-part tiered roofs not demonstrated")

    npz_paths = sorted((ROOT/OUT).rglob('*.npz'))
    hashes = {}
    for path in npz_paths:
        relative = str(path.relative_to(ROOT))
        hashes[relative] = digest(path)
        arrays = load_npz(relative)
        if not {'v', 'f', 'm'} <= set(arrays):
            require(False, relative+': missing v/f/m arrays')
            continue
        v, f, m = arrays['v'], arrays['f'], arrays['m']
        finite = int((~np.isfinite(v)).sum())
        invalid_indices = int(((f < 0) | (f >= len(v))).sum())
        bad_material = int(((m < 0) | (m >= len(index['materials']))).sum())
        # Transportation meshes use their source transport palette, also <=17.
        degen = 0
        if not invalid_indices and len(f):
            xyz = v[f].astype(float)
            degen = int((np.linalg.norm(np.cross(xyz[:, 1]-xyz[:, 0], xyz[:, 2]-xyz[:, 0]), axis=1) <= 1e-8).sum())
        require(finite == invalid_indices == bad_material == degen == 0,
                relative+f': invalid geometry finite={finite},index={invalid_indices},material={bad_material},degenerate={degen}')
        mesh_checks.append({'path': relative, 'vertices': len(v), 'triangles': len(f),
                            'nonfinite_coordinates': finite, 'invalid_indices': invalid_indices,
                            'invalid_material_indices': bad_material, 'degenerate_triangles': degen})

    final_tiles = {tuple(t['ij']): t for t in index['ground']}
    terrain_arrays, terrain_sources = {}, {}

    def terrain(ij):
        if ij in terrain_arrays:
            return terrain_arrays[ij]
        if ij in final_tiles:
            relative = final_tiles[ij]['file']
            a = load_npz(relative)
            v, f = a['v'].astype(float), a['f']
        elif ij in grade.ground.overrides:
            relative = grade.ground.overrides[ij]['file']
            a = load_npz(relative)
            v, f = a['v'].astype(float), a['f']
        else:
            record = grade.ground.base.tiles.get(ij)
            if record is None:
                return None
            candidate = ROOT/'data/processed/stage04/ground'/(record['id']+'.npz')
            relative = str(candidate.relative_to(ROOT)) if candidate.exists() else record['file']
            lod = grade.ground.base.active[record['id']]
            a = load_npz(relative)
            v, f = a['v'+str(lod)].astype(float), a['f'+str(lod)]
        v[:, :2] += np.asarray(ij)*1000
        terrain_arrays[ij] = v, f
        terrain_sources[relative] = digest(ROOT/relative)
        return v, f

    seams, pairs = [], set()
    for ij in final_tiles:
        for axis in (0, 1):
            for sign in (-1, 1):
                neighbor = list(ij)
                neighbor[axis] += sign
                neighbor = tuple(neighbor)
                pair = tuple(sorted((ij, neighbor)))
                if pair in pairs:
                    continue
                pairs.add(pair)
                a, b = terrain(ij), terrain(neighbor)
                if b is None:
                    continue
                boundary = (ij[axis]+(1 if sign > 0 else 0))*1000
                row = seam(a, b, axis, boundary)
                row.update(tile_a=list(ij), tile_b=list(neighbor), axis='X' if axis == 0 else 'Y',
                           boundary_city_m=boundary, computational_tolerance_m=.001)
                seams.append(row)
                if row['shared_supported_samples']:
                    require(row['max_computational_z_difference_m'] <= .001,
                            f'{pair}: terrain shared edge differs by {row["max_computational_z_difference_m"]:.6f}m')
                    require(row['max_same_side_multivalued_z_m'] <= .001,
                            f'{pair}: terrain edge contains contradictory same-side heights')
                else:
                    row['status'] = 'no_shared_mesh_support; not tested across excluded road/water gaps'

    require(any(s['shared_supported_samples'] for s in seams), 'No actual common terrain boundary samples were tested')
    report = {
        'status': 'passed' if not failures else 'failed', 'passed': not failures,
        'created_at': datetime.datetime.now(ZoneInfo('Asia/Singapore')).isoformat(),
        'failures': failures, 'index_sha256': digest(ROOT/OUT/'index.json'),
        'geometry_sha256': hashes, 'buildings': buildings, 'meshes': mesh_checks,
        'source_part_roof_checks': part_checks, 'entrances': entrances,
        'terrain_seams': seams, 'terrain_source_sha256': terrain_sources,
        'summary': {
            'buildings': len(buildings), 'doors': len(entrances),
            'tiny_source_fragment_entry_exemptions': sorted(FRAGMENTS),
            'mesh_files': len(mesh_checks), 'triangles': sum(m['triangles'] for m in mesh_checks),
            'max_source_to_wall_hausdorff_m': max(b['source_to_wall_hausdorff_m'] for b in buildings),
            'min_signed_threshold_minus_sidewalk_m': min(d['signed_threshold_minus_sidewalk_at_1_5m_m'] for d in entrances),
            'max_signed_threshold_minus_sidewalk_m': max(d['signed_threshold_minus_sidewalk_at_1_5m_m'] for d in entrances),
            'max_signed_to_stored_rise_difference_m': max(abs(d['signed_to_stored_difference_m']) for d in entrances),
            'actual_terrain_seam_pairs': len(seams),
            'terrain_shared_samples': sum(s['shared_supported_samples'] for s in seams),
            'max_terrain_computational_z_difference_m': max((s['max_computational_z_difference_m'] or 0) for s in seams),
        },
        'limits': [
            'Computation consistency is not original survey accuracy. Source roofline horizontal accuracy and county imported height accuracy are not independently established.',
            'Street grade is an explicitly inferred visual edit anchored to previous road geometry, not a new measured DTM or engineering profile.',
            'Signed door values preserve small below-sidewalk thresholds rather than clamping them. 0.10m is a disclosed near-grade visual tolerance, not accessibility compliance.',
            'Three tiny roofline fragments retain unverified source geometry/heights; independent ground-level building identity and entrances are not established.',
            'Array checks require separate saved Blender reopen and actual image inspection before stage acceptance.',
        ],
    }
    destination = ROOT/REPORT
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print('STAGE07_FINAL_GEOMETRY_AUDIT', report['status'], json.dumps(report['summary']), flush=True)
    for item in failures:
        print('FAILED:', item, flush=True)
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(run())
