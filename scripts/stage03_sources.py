"""Reproducible official planning inputs; original responses and ID evidence retained."""
import json
import yaml
from stage02_io import Client,arcgis_fetch,digest,write_json


def acquire(root):
    c=Client(root,yaml.safe_load((root/'config/stage02.yaml').read_text()));c.log=root/'work/logs/stage03/requests.jsonl';c.log.parent.mkdir(parents=True,exist_ok=True)
    for url,folder,query in [
        ('https://maps.lacity.org/lahub/rest/services/City_Planning_Department/MapServer/7','landuse_selected',
         "UPPER(GPLU_Legend) LIKE '%INDUSTR%' OR UPPER(GPLU_Legend) LIKE '%PORT%' OR UPPER(GPLU_Legend) LIKE '%AIRPORT%'"),
        ('https://services5.arcgis.com/7nsPwEMP38bSkCjy/arcgis/rest/services/Community_Plan_Areas/FeatureServer/0','port_plan_verified',"UPPER(NAME_ALF) LIKE '%PORT%'")]:
        arcgis_fetch(c,url,'data/raw/stage03/'+folder,{'where':query},page_size=100)
    receipts=[]
    for p in sorted((root/'data/raw/stage03').rglob('*.receipt.json')):
        r=json.loads(p.read_text());file=root/str(p.relative_to(root)).removesuffix('.receipt.json')
        if digest(file)!=r['sha256']:raise ValueError('Raw stage03 research checksum mismatch: '+str(file))
        receipts.append({'path':str(file.relative_to(root)),**r})
    write_json(root/'data/processed/stage03/source_requests.json',receipts)


if __name__=='__main__':
    from pathlib import Path
    acquire(Path(__file__).resolve().parents[1])
