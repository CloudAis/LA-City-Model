// Remove only exact zero-area indexed triangles. Keep all nonzero geometry and
// untouched attribute buffers byte-for-byte; replace hardlinks atomically.
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';
import {MeshoptEncoder,MeshoptDecoder} from '../viewer/node_modules/meshoptimizer/index.js';
await Promise.all([MeshoptEncoder.ready,MeshoptDecoder.ready]);
const root=path.resolve(import.meta.dirname,'..'),base=path.join(root,'outputs/LA_Delivery/tiles'),manifest=JSON.parse(fs.readFileSync(path.join(base,'manifest.json'))),audit=JSON.parse(fs.readFileSync(path.join(root,'work/reports/stage10/runtime_geometry_before.json'))),repairs=[];
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex'),align=n=>(n+3)&~3;
for(const item of audit.issues){
 if(item.nan||item.invalid||item.mixedIds)throw Error('Non-degenerate issue requires separate repair '+item.id);
 const resource=manifest.resources.find(r=>r.id===item.id&&r.lod===item.lod),filename=path.join(base,resource.url),raw=fs.readFileSync(filename);if(hash(raw)!==item.source_sha256)throw Error('Changed repair source');
 const n=raw.readUInt32LE(12),doc=JSON.parse(raw.subarray(20,20+n)),bin=raw.subarray(28+n),changed=new Map(),remove=[];
 for(const issue of item.primitives){
  const mesh=doc.meshes[issue.node_mesh],p=mesh.primitives[issue.primitive_index];let a,v,before;
  if(p.indices!==undefined){a=doc.accessors[p.indices];v=doc.bufferViews[a.bufferView];const e=v.extensions.EXT_meshopt_compression;
   if(a.componentType!==5125||(a.byteOffset||0)!==0)throw Error('Unsupported repair index layout');
   const decoded=new Uint8Array(v.byteLength);MeshoptDecoder.decodeGltfBuffer(decoded,e.count,e.byteStride,bin.subarray(e.byteOffset,e.byteOffset+e.byteLength),e.mode,e.filter||'NONE');before=Buffer.from(decoded);
  }else{const count=doc.accessors[p.attributes.POSITION].count;before=Buffer.alloc(count*4);for(let i=0;i<count;i++)before.writeUInt32LE(i,i*4);}
  const skip=new Set(issue.degenerate_triangle_indices),parts=[];
  for(let i=0;i<before.length/12;i++)if(!skip.has(i))parts.push(before.subarray(i*12,i*12+12));
  if(!parts.length){remove.push([issue.node_mesh,issue.primitive_index]);continue;}
  const after=Buffer.concat(parts),encoded=MeshoptEncoder.encodeGltfBuffer(after,after.length/4,4,'INDICES'),test=new Uint8Array(after.length);MeshoptDecoder.decodeGltfBuffer(test,after.length/4,4,encoded,'INDICES','NONE');if(!Buffer.from(test).equals(after))throw Error('Actual index decode mismatch');
  if(!a){v={buffer:1,byteLength:after.length,target:34963,extensions:{EXT_meshopt_compression:{mode:'INDICES',filter:'NONE'}}};doc.bufferViews.push(v);a={bufferView:doc.bufferViews.length-1,componentType:5125,type:'SCALAR',count:after.length/4};doc.accessors.push(a);p.indices=doc.accessors.length-1;}
  a.count=after.length/4;delete a.min;delete a.max;v.byteLength=after.length;changed.set(a.bufferView,{encoded:Buffer.from(encoded),count:a.count,stride:4});
 }
 for(const [mesh,primitive] of remove.sort((a,b)=>b[1]-a[1]))doc.meshes[mesh].primitives.splice(primitive,1);
 const map=new Map(),meshes=[];doc.meshes.forEach((m,i)=>{if(m.primitives.length){map.set(i,meshes.length);meshes.push(m);}});doc.meshes=meshes;
 for(const node of doc.nodes)if(node.mesh!==undefined){if(map.has(node.mesh))node.mesh=map.get(node.mesh);else delete node.mesh;}
 let offset=0,fallback=0;const chunks=[];
 doc.bufferViews.forEach((view,i)=>{const e=view.extensions.EXT_meshopt_compression,change=changed.get(i),encoded=change?.encoded||bin.subarray(e.byteOffset,e.byteOffset+e.byteLength);view.buffer=1;view.byteOffset=fallback;fallback+=view.byteLength;view.extensions.EXT_meshopt_compression={...e,buffer:0,byteOffset:offset,byteLength:encoded.length,count:change?.count||e.count,byteStride:change?.stride||e.byteStride};chunks.push(encoded,Buffer.alloc(align(encoded.length)-encoded.length));offset+=align(encoded.length);});
 doc.buffers=[{byteLength:offset},{byteLength:fallback,extensions:{EXT_meshopt_compression:{fallback:true}}}];
 const json=Buffer.from(JSON.stringify(doc)),padded=Buffer.concat([json,Buffer.alloc(align(json.length)-json.length,32)]),header=Buffer.alloc(20),tail=Buffer.alloc(8);header.write('glTF');header.writeUInt32LE(2,4);header.writeUInt32LE(28+padded.length+offset,8);header.writeUInt32LE(padded.length,12);header.write('JSON',16);tail.writeUInt32LE(offset);tail.write('BIN\0',4);const output=Buffer.concat([header,padded,tail,...chunks]);
 fs.writeFileSync(filename+'.stage10.tmp',output);fs.renameSync(filename+'.stage10.tmp',filename);resource.sha256=hash(output);resource.bytes=output.length;resource.triangles-=item.degenerate;resource.build_version='stage10-v1-zero-area-only';resource.stage10_removed_zero_area_triangles=item.degenerate;
 repairs.push({id:resource.id,lod:resource.lod,removed_exact_zero_area_triangles:item.degenerate,source_sha256:item.source_sha256,final_sha256:resource.sha256,non_index_attribute_buffers_unchanged:true,actual_reencoded_indices_byte_verified:true});
}
manifest.stage=10;manifest.source_stage9_catalog_sha256=hash(fs.readFileSync(path.join(root,'outputs/stage09/resources/manifest.json')));manifest.final_audit='stage10';fs.writeFileSync(path.join(base,'manifest.json'),JSON.stringify(manifest)+'\n');
fs.writeFileSync(path.join(root,'work/reports/stage10/runtime_repairs.json'),JSON.stringify({status:'actual_zero_area_only_repairs_applied',resources:repairs.length,triangles_removed:repairs.reduce((s,r)=>s+r.removed_exact_zero_area_triangles,0),repairs,source_stage09_files_unchanged:true},null,2)+'\n');console.log('EXACT_ZERO_AREA_FACES_REMOVED',repairs.length);
