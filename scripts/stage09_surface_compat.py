"""Incremental equivalent of exporter's two-sided thin transport materials.

Only GLB JSON changes. The exact original JSON chunks are archived so each
previous file can be reconstructed from the unchanged BIN chunk without a
second full copy. Source authoring and vertex/index buffers remain unchanged.
"""
from pathlib import Path
import base64,gzip,hashlib,json,struct
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 base=ROOT/'outputs/stage09/resources';p=base/'manifest.json';manifest=json.loads(p.read_text());changes=[]
 for r in manifest['resources']:
  if r['layer']!='roads':continue
  target=base/r['url'];blob=target.read_bytes();assert sha(blob)==r['sha256']
  length,kind=struct.unpack_from('<II',blob,12);assert kind==0x4e4f534a
  original=blob[20:20+length];doc=json.loads(original)
  if all(m.get('doubleSided',False) for m in doc['materials']):continue
  for m in doc['materials']:m['doubleSided']=True
  replacement=json.dumps(doc,separators=(',',':')).encode();replacement+=b' '*((-len(replacement))%4)
  tail=blob[20+length:];updated=struct.pack('<III',0x46546c67,2,20+len(replacement)+len(tail))+struct.pack('<II',len(replacement),kind)+replacement+tail
  old_sha=r['sha256'];target.write_bytes(updated);r['sha256']=sha(updated);r['bytes']=len(updated)
  changes.append({'url':r['url'],'old_sha256':old_sha,'new_sha256':r['sha256'],'original_json_base64':base64.b64encode(original).decode(),'unchanged_binary_chunks_sha256':sha(tail)})
 if changes:
  archive=ROOT/'work/history/stage09_transport_original_headers.json.gz'
  assert not archive.exists(),'Preserve earlier header archive before a new repair'
  with gzip.open(archive,'wt') as stream:json.dump(changes,stream,separators=(',',':'))
  p.write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+'\n')
 report={'status':'actual_glb_material_compatibility_fixed','changed_resources':len(changes),'original_header_archive':'work/history/stage09_transport_original_headers.json.gz','vertex_index_and_meshopt_bytes_unchanged':True,'source_authoring_unchanged':True,'reason':'Preserve Blender two-sided thin transport surfaces, including source downward-wound road polygons.'}
 (ROOT/'work/reports/stage09/surface_compatibility.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
