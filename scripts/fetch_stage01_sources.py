"""Optional reproducible restore of stage-01 reference data; never alter raw inputs."""
import datetime
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

root=Path(__file__).resolve().parents[1]
for name in ['PROJECT_SPEC.md','STATUS.md']:(root/name).read_text()
lock=json.loads((root/'config/sources.lock.json').read_text())
for entry in lock['sources']:
    path=root/'data/raw'/entry['filename']
    if path.exists():
        body=path.read_bytes()
    else:
        with urllib.request.urlopen(entry['url'],timeout=60) as response:body=response.read()
    if hashlib.sha256(body).hexdigest()!=entry['sha256'] or len(body)!=entry['bytes']:
        raise RuntimeError('Source checksum/size mismatch: '+entry['filename'])
    if not path.exists():
        path.write_bytes(body)
        receipt={**entry,'immutable_url':entry['url'],
                 'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        path.with_name(path.name+'.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('SOURCE_VERIFIED',entry['filename'])
