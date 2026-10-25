import fs from 'node:fs';
import path from 'node:path';
import {MeshoptDecoder} from '../viewer/node_modules/meshoptimizer/index.js';
import validator from '../viewer/node_modules/gltf-validator/index.js';
await MeshoptDecoder.ready;
const root=path.resolve(import.meta.dirname,'..'),base=path.join(root,'outputs/LA_Delivery/tiles');
const manifest=JSON.parse(fs.readFileSync(path.join(base,'manifest.json'),'utf8'));
const records=[];const chosen=[];
const find=(id,lod)=>manifest.resources.find(r=>r.id===id&&r.lod===lod);
chosen.push(find('landmark-city_hall',1),find('landmark-griffith_observatory',1),find('roads-la_t_x-001_y+000',1),find('terrain-la_t_x-001_y+000',1));
const nearby=manifest.resources.filter(r=>r.id.startsWith('detail-')&&r.lod===1).sort((a,b)=>Math.hypot(a.origin_city_m[0]+400,a.origin_city_m[1]-950)-Math.hypot(b.origin_city_m[0]+400,b.origin_city_m[1]-950));chosen.push(...nearby.slice(0,2));
for(const name of ['default','modified']){const meta=JSON.parse(fs.readFileSync(path.join(base,'rebuild',name+'.json')));chosen.push({id:'rebuild-'+name,lod:0,url:'rebuild/'+name+'.glb',sha256:meta.sha256,origin_city_m:meta.origin_city_m});}
const cache=path.join(root,'work/cache/stage10/glb_samples');fs.mkdirSync(cache,{recursive:true});
for(const resource of chosen){
 if(!resource)throw new Error('Required representative source resource missing');
 const raw=fs.readFileSync(path.join(base,resource.url)),len=raw.readUInt32LE(12),doc=JSON.parse(raw.subarray(20,20+len).toString()),bin=raw.subarray(28+len);let offset=0;const parts=[];
 for(const view of doc.bufferViews){const ext=view.extensions?.EXT_meshopt_compression;let data;
  if(ext){data=new Uint8Array(view.byteLength);MeshoptDecoder.decodeGltfBuffer(data,ext.count,ext.byteStride,bin.subarray(ext.byteOffset,ext.byteOffset+ext.byteLength),ext.mode,ext.filter||'NONE');}
  else data=bin.subarray(view.byteOffset,view.byteOffset+view.byteLength);
  view.buffer=0;view.byteOffset=offset;delete view.extensions;parts.push(Buffer.from(data),Buffer.alloc((-data.length)&3));offset+=data.length+((-data.length)&3);
 }
 doc.buffers=[{byteLength:offset}];doc.extensionsRequired=doc.extensionsRequired.filter(x=>x!=='EXT_meshopt_compression');doc.extensionsUsed=doc.extensionsUsed.filter(x=>x!=='EXT_meshopt_compression');
 for(const image of doc.images||[]){const original=path.resolve(base,'tiles',image.uri);image.uri=path.relative(cache,original).split(path.sep).join('/');}
 const json=Buffer.from(JSON.stringify(doc)),padded=Buffer.concat([json,Buffer.alloc((-json.length)&3,32)]),header=Buffer.alloc(20),binHeader=Buffer.alloc(8);header.write('glTF');header.writeUInt32LE(2,4);header.writeUInt32LE(28+padded.length+offset,8);header.writeUInt32LE(padded.length,12);header.write('JSON',16);binHeader.writeUInt32LE(offset);binHeader.write('BIN\0',4);
 const output=Buffer.concat([header,padded,binHeader,...parts]);const filename=path.join(cache,resource.id+'-l'+resource.lod+'.glb');fs.writeFileSync(filename,output);
 const validation=await validator.validateBytes(new Uint8Array(output),{externalResourceFunction:async uri=>new Uint8Array(fs.readFileSync(path.resolve(cache,decodeURIComponent(uri))))});
 records.push({resource:resource.id,lod:resource.lod,origin_city_m:resource.origin_city_m,source_sha256:resource.sha256,decompressed_file:path.relative(root,filename),actual_meshopt_decode:true,validator_errors:validation.issues.numErrors,validator_warnings:validation.issues.numWarnings,issues:[...validation.issues.messages.filter(m=>m.severity===0),...validation.issues.messages.filter(m=>m.severity===1)].slice(0,14)});
}
const result={status:records.every(r=>r.validator_errors===0)?'passed':'failed',actual_independent_decode_and_gltf_validator:true,samples:records};
fs.writeFileSync(path.join(root,'work/reports/stage10/gltf_validation.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
process.exitCode=result.status==='passed'?0:1;
