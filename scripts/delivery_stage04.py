"""Package existing, verified Stage04 evidence without rebuilding or changing raw data."""
from pathlib import Path
import hashlib
import json
import datetime
from stage02_io import digest, write_json
from stage04 import verify, inputs, fingerprint

ROOT = Path(__file__).resolve().parents[1]


def package(root=ROOT):
    for name in ['PROJECT_SPEC.md', 'STATUS.md']:
        assert (root/name).read_text().strip(), name
    data = verify(root, root/'outputs/stage04_data_medium.manifest.json')
    scene = verify(root, root/'outputs/stage04_city_medium.manifest.json')
    assert data['fingerprint'] == scene['fingerprint'] == fingerprint(inputs(root))
    check = json.loads((root/'work/reports/stage04/blender_check.json').read_text())
    assert check['status'] == 'passed' and len(check['renders']) == 4
    visual = json.loads((root/'work/reports/stage04/visual_inspection.json').read_text())
    assert visual['images_actually_viewed']
    paths = {a['path'] for a in data['inputs'] + data['artifacts'] + scene['artifacts']}
    for directory in ['config', 'docs', 'scripts', 'work/logs/stage04', 'work/reports/stage04', 'work/previews/stage04']:
        paths.update(str(p.relative_to(root)) for p in (root/directory).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts)
    paths.update(['PROJECT_SPEC.md','STATUS.md','README.md','AGENTS.md','.gitignore','project','requirements.lock','work/reports/environment.json',
                  'assets/street_furniture/README_stage04.md','outputs/stage04_data_medium.manifest.json',
                  'outputs/stage04_city_medium.manifest.json'])
    # This script's stdout may be redirected here; do not checksum an active output file.
    paths.discard('work/logs/stage04/delivery_validation.log')
    entries = [{'path':p,'bytes':(root/p).stat().st_size,'sha256':digest(root/p)} for p in sorted(paths)]
    delivery = {'stage':4,'status':'complete_with_documented_gaps',
                'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'project_root':str(root),'model':'scenes/stage04_city_medium.blend',
                'artifact_count':len(entries),'total_bytes':sum(x['bytes'] for x in entries),
                'artifacts':entries,'acceptance':'outputs/stage04_city_medium_acceptance.json',
                'limitations':'STATUS.md and docs/stage04_validation.md',
                'excluded':'venv, cache, historical archives, this delivery index, checksum itself and active validation log'}
    out = root/'outputs/stage04_delivery.json'
    write_json(out,delivery)
    entries.append({'path':str(out.relative_to(root)),'sha256':digest(out)})
    listing = root/'outputs/stage04_files.sha256'
    listing.write_text(''.join(f"{e['sha256']}  {e['path']}\n" for e in entries))
    for e in entries:
        assert digest(root/e['path']) == e['sha256'], e['path']
    write_json(root/'outputs/stage04_integrity.json',
               {'status':'passed','files_verified':len(entries),'checksum_file_sha256':digest(listing),
                'original_manifest_integrity_verified':True,'raw_data_modified':False})
    print('STAGE04_DELIVERY_INTEGRITY_PASSED',len(entries),'files',delivery['total_bytes'],'bytes',flush=True)


if __name__ == '__main__':
    package()
