"""Replay pinned public-source GETs and verify bytes; never silently adopt changed data."""
import json
import shutil
import zipfile
from pathlib import Path
import yaml
from stage02_io import Client,digest,write_json


def acquire(root):
    cfg=yaml.safe_load((root/'config/stage02.yaml').read_text())
    requests=json.loads((root/'config/stage02_requests.lock.json').read_text())['requests']
    missing=sum(r['bytes'] for r in requests if not (root/r['path']).exists())
    if missing>cfg['request']['max_total_download_gib']*1024**3:
        raise ValueError('Pinned missing downloads exceed total budget')
    if shutil.disk_usage(root).free<missing+cfg['request']['disk_headroom_gib']*1024**3:
        raise ValueError('Insufficient disk budget before acquisition')
    client=Client(root,cfg)
    for r in requests:
        # URL includes the recorded query, so do not append the parameters twice.
        p=client.get(r['url'],r['path'],limit=min(cfg['request']['max_download_mib']*1024**2,max(r['bytes']*2,1024**2)))
        if digest(p)!=r['sha256']:raise ValueError('Upstream content changed; retain as a NEW version after review: '+r['path'])
    # These are derived proofs, not modified server responses.
    for folder in (root/'data/raw/stage02').rglob('*'):
        if not folder.is_dir() or not (folder/'ids.json').exists() or not (folder/'count.json').exists():continue
        # Metadata-only investigations (e.g. the map-only bridge service) are not adopted inputs.
        if not list(folder.glob('page_*.json')):continue
        layer=json.loads((folder/'layer.json').read_text());oid=layer.get('objectIdField') or next(f['name'] for f in layer['fields'] if f['type']=='esriFieldTypeOID')
        wanted=set(json.loads((folder/'ids.json').read_text()).get('objectIds') or [])
        count=json.loads((folder/'count.json').read_text())['count'];got=[]
        for page in folder.glob('page_*.json'):
            response=json.loads(page.read_text())
            if not response.get('exceededTransferLimit'):got += [f['attributes'][oid] for f in response.get('features',[])]
        if len(got)!=len(set(got)) or set(got)!=wanted or len(wanted)!=count:raise ValueError('Pinned ArcGIS exact ID mismatch: '+str(folder))
        write_json(folder/'completeness.json',{'server_count':count,'downloaded_count':len(got),'id_set_equal':True,'object_id_field':oid})
    cache=root/'work/cache/lariac6';gdb=cache/'LARIAC6_Buildings_2020.gdb'
    if not gdb.exists():
        archive=root/'data/raw/stage02/buildings/LARIAC6_Buildings_2020.gdb.zip'
        with zipfile.ZipFile(archive) as z:
            if any(not (cache/n).resolve().is_relative_to(cache.resolve()) for n in z.namelist()):raise ValueError('Unsafe archive member')
            if shutil.disk_usage(root).free<sum(n.file_size for n in z.infolist())+cfg['request']['disk_headroom_gib']*1024**3:raise ValueError('Insufficient extraction headroom')
            z.extractall(cache)
    print('PINNED_RAW_REQUESTS_VERIFIED',len(requests),'missing-byte budget',missing,flush=True)


if __name__=='__main__':acquire(Path(__file__).resolve().parents[1])
