"""Recorded HTTP, bounded downloads and ArcGIS object-id pagination. Never disable TLS."""
import datetime
import hashlib
import json
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


class Client:
    def __init__(self, root, cfg):
        self.root=Path(root);self.cfg=cfg['request'];self.log=self.root/'work/logs/stage02/requests.jsonl'
        self.log.parent.mkdir(parents=True,exist_ok=True)
    def record(self, entry):
        with self.log.open('a') as f:f.write(json.dumps({'at':now(),**entry},ensure_ascii=False)+'\n')
    def get(self, url, relative, params=None, limit=None, method='GET'):
        if params:url += ('&' if '?' in url else '?')+urllib.parse.urlencode(params)
        path=self.root/relative;receipt=Path(str(path)+'.receipt.json')
        if path.exists():
            if not receipt.exists():raise ValueError('Unregistered existing raw file: '+str(path))
            meta=json.loads(receipt.read_text())
            if meta['sha256']!=digest(path):raise ValueError('Raw checksum mismatch: '+str(path))
            if meta['url']!=url:raise ValueError('Cache request mismatch: '+str(path))
            self.record({'event':'cache_verified','url':url,'file':relative});return path
        path.parent.mkdir(parents=True,exist_ok=True)
        bound=limit or self.cfg['max_json_mib']*1024**2
        part=Path(str(path)+'.part');part_meta=Path(str(part)+'.json')
        for attempt in range(self.cfg['retries']):
            headers={'User-Agent':'Los-Angeles-Geographic-Project/Stage02'}
            offset=part.stat().st_size if part.exists() else 0
            validator=None
            if offset and part_meta.exists():
                cached=json.loads(part_meta.read_text())
                if cached.get('url')!=url:raise ValueError('Partial download belongs to another request')
                validator=cached.get('validator')
                if validator:headers.update({'Range':f'bytes={offset}-','If-Range':validator})
                else:offset=0
            try:
                req=urllib.request.Request(url,headers=headers,method=method)
                with urllib.request.urlopen(req,timeout=self.cfg['timeout_seconds']) as response:
                    status=response.status
                    resumed=status==206 and offset>0
                    if status==206 and not response.headers.get('Content-Range','').startswith('bytes '+str(offset)+'-'):
                        raise ValueError('Unexpected Content-Range')
                    if not resumed:offset=0
                    length=response.headers.get('Content-Length')
                    expected=int(length)+offset if length else None
                    if expected and expected>bound:raise ValueError('Response exceeds configured size budget')
                    if shutil.disk_usage(self.root).free < (expected or bound)+self.cfg['disk_headroom_gib']*1024**3:
                        raise ValueError('Insufficient disk headroom')
                    write_json(part_meta,{'url':url,'validator':response.headers.get('ETag') or response.headers.get('Last-Modified')})
                    mode='ab' if resumed else 'wb'
                    with part.open(mode) as out:
                        while chunk:=response.read(1024*1024):
                            offset+=len(chunk)
                            if offset>bound:raise ValueError('Streaming response exceeds configured budget')
                            out.write(chunk)
                    if expected and offset!=expected:raise OSError('Truncated response')
                    metadata={'url':url,'method':method,'request_parameters':params or {},'downloaded_at_utc':now(),
                              'http_status':status,'http_last_modified':response.headers.get('Last-Modified'),
                              'etag':response.headers.get('ETag'),'content_type':response.headers.get('Content-Type'),
                              'bytes':part.stat().st_size,'sha256':digest(part),'resumed':resumed}
                part.replace(path);write_json(receipt,metadata);part_meta.unlink(missing_ok=True)
                self.record({'event':'downloaded','file':relative,**metadata});return path
            except urllib.error.HTTPError as e:
                self.record({'event':'http_error','url':url,'status':e.code,'attempt':attempt+1})
                if e.code not in self.cfg['retry_statuses'] or attempt==self.cfg['retries']-1:raise
                retry=e.headers.get('Retry-After','');time.sleep(min(float(retry) if retry.isdigit() else 2**attempt,10))
            except (OSError,urllib.error.URLError) as e:
                self.record({'event':'transport_error','url':url,'error':str(e),'attempt':attempt+1})
                # Proxy policy denial must be resolved through configuration, never retried unchanged.
                if '403' in str(e) or 'Operation not permitted' in str(e) or attempt==self.cfg['retries']-1:raise
                time.sleep(2**attempt)
        raise RuntimeError('Unreachable retry state')
    def json(self,url,relative,params=None):
        path=self.get(url,relative,params)
        value=json.loads(path.read_text())
        if isinstance(value,dict) and value.get('error'):raise ValueError('Service error: '+str(value['error']))
        return value


def arcgis_fetch(client, layer, target, query=None, page_size=500):
    """IDs + server count + exact ID-set equality prevents silent transfer-limit loss."""
    target=Path(target);query={'where':'1=1',**(query or {})}
    meta=client.json(layer,str(target/'layer.json'),{'f':'json'})
    oid=meta.get('objectIdField') or next(f['name'] for f in meta['fields'] if f['type']=='esriFieldTypeOID')
    count=client.json(layer+'/query',str(target/'count.json'),{**query,'f':'json','returnCountOnly':'true'})['count']
    listed=client.json(layer+'/query',str(target/'ids.json'),{**query,'f':'json','returnIdsOnly':'true'})
    ids=sorted(set(listed.get('objectIds') or []))
    if len(ids)!=count:raise ValueError('Server count and ID list disagree; split spatial query')
    limit=min(page_size,meta.get('maxRecordCount',page_size))
    features=[]
    def page(batch, name):
        response=client.json(layer+'/query',str(target/(name+'.json')),{'f':'json','objectIds':','.join(map(str,batch)),
            'outFields':'*','returnGeometry':'true','outSR':4326})
        if response.get('exceededTransferLimit'):
            if len(batch)==1:raise ValueError('Single feature exceeds service transfer limit')
            mid=len(batch)//2;return page(batch[:mid],name+'a')+page(batch[mid:],name+'b')
        values=response.get('features',[])
        if {f['attributes'][oid] for f in values}!=set(batch):raise ValueError('Page ID set mismatch')
        return values
    for offset in range(0,len(ids),limit):features+=page(ids[offset:offset+limit],f'page_{offset:08d}')
    got=[f['attributes'][oid] for f in features]
    if len(got)!=len(set(got)) or set(got)!=set(ids):raise ValueError('Missing or duplicate objects after paging')
    evidence={'server_count':count,'downloaded_count':len(got),'id_set_equal':True,'object_id_field':oid}
    write_json(client.root/target/'completeness.json',evidence)
    return meta,features,evidence
