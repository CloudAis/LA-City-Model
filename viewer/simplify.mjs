// Actual mesh simplification for distant overview only; local authoring meshes
// remain untouched. Output is a temporary indexed binary for the Python writer.
import fs from 'node:fs';
import {MeshoptDecoder,MeshoptSimplifier} from 'meshoptimizer';
await Promise.all([MeshoptDecoder.ready,MeshoptSimplifier.ready]);
const [input,output,targetText,errorText]=process.argv.slice(2),raw=fs.readFileSync(input),jsonLength=raw.readUInt32LE(12);
const doc=JSON.parse(raw.subarray(20,20+jsonLength).toString()),binary=raw.subarray(28+jsonLength),decoded=new Map();
function view(index){if(decoded.has(index))return decoded.get(index);const v=doc.bufferViews[index],ext=v.extensions?.EXT_meshopt_compression;let data;if(ext){data=new Uint8Array(v.byteLength);MeshoptDecoder.decodeGltfBuffer(data,ext.count,ext.byteStride,binary.subarray(ext.byteOffset,ext.byteOffset+ext.byteLength),ext.mode,ext.filter||'NONE');}else data=binary.subarray(v.byteOffset,v.byteOffset+v.byteLength);decoded.set(index,data);return data;}
function attribute(index){const a=doc.accessors[index],v=doc.bufferViews[a.bufferView],data=view(a.bufferView),dv=new DataView(data.buffer,data.byteOffset,data.byteLength),size={SCALAR:1,VEC2:2,VEC3:3,VEC4:4}[a.type],component={5120:1,5121:1,5123:2,5125:4,5126:4}[a.componentType],stride=v.byteStride||size*component;
const result=[];for(let i=0;i<a.count;i++){const values=[];for(let j=0;j<size;j++){const p=(a.byteOffset||0)+i*stride+j*component;values.push(a.componentType===5125?dv.getUint32(p,true):a.componentType===5123?dv.getUint16(p,true):a.componentType===5126?dv.getFloat32(p,true):a.componentType===5120?dv.getInt8(p):dv.getUint8(p));}result.push(values);}return result;}
const node=doc.nodes.find(n=>n.mesh!==undefined),primitive=doc.meshes[node.mesh].primitives[0],q=attribute(primitive.attributes.POSITION),c=attribute(primitive.attributes.COLOR_0);
const unique=new Map(),positions=[],colorSums=[],counts=[],remap=new Uint32Array(q.length);
for(let i=0;i<q.length;i++){
 const key=q[i].join(',');let index=unique.get(key);if(index===undefined){index=positions.length/3;unique.set(key,index);for(let a=0;a<3;a++)positions.push(q[i][a]/65535*node.scale[a]+node.translation[a]);colorSums.push([0,0,0]);counts.push(0);}
 remap[i]=index;counts[index]++;for(let a=0;a<3;a++)colorSums[index][a]+=c[i][a]/255;
}
const originalIndices=primitive.indices!==undefined?attribute(primitive.indices).map(v=>v[0]):Array.from({length:q.length},(_,i)=>i);const indices=Uint32Array.from(originalIndices,i=>remap[i]);
const attributes=new Float32Array(positions.length);for(let i=0;i<counts.length;i++)for(let a=0;a<3;a++)attributes[i*3+a]=colorSums[i][a]/counts[i];
const p=new Float32Array(positions),flags=['ErrorAbsolute'];let locks=null;let retainedBorder=[];let working=indices;
if(input.includes('overview-terrain'))flags.push('LockBorder');
else if(input.includes('terrain-')){
 locks=new Uint8Array(counts.length);const strip=new Uint8Array(counts.length);for(let i=0;i<counts.length;i++)if(Math.min(Math.abs(p[i*3]),Math.abs(p[i*3]-1000),Math.abs(p[i*3+2]),Math.abs(p[i*3+2]+1000))<2)strip[i]=1;
 const interior=[];for(let i=0;i<indices.length;i+=3){const tri=[indices[i],indices[i+1],indices[i+2]];if(tri.some(v=>strip[v])){retainedBorder.push(...tri);tri.forEach(v=>locks[v]=1);}else interior.push(...tri);}working=Uint32Array.from(interior);
}
const target=Math.min(working.length,Math.max(0,Number(targetText)*3-retainedBorder.length));
const [reduced,error]=working.length?MeshoptSimplifier.simplifyWithAttributes(working,p,3,attributes,3,[10,10,10],locks,target,Number(errorText),flags):[new Uint32Array(),0];
const simplified=new Uint32Array(retainedBorder.length+reduced.length);simplified.set(retainedBorder);simplified.set(reduced,retainedBorder.length);
const colors=new Uint8Array(counts.length*4);for(let i=0;i<counts.length;i++){for(let a=0;a<3;a++)colors[i*4+a]=Math.round(attributes[i*3+a]*255);colors[i*4+3]=255;}
const header=Buffer.from(JSON.stringify({vertices:counts.length,indices:simplified.length,input_triangles:indices.length/3,output_triangles:simplified.length/3,reported_quadric_error_m:error,locked_boundary:flags.includes('LockBorder'),locked_tile_outer_vertices:locks?locks.reduce((a,b)=>a+b,0):0,original_outer_border_triangles_retained:retainedBorder.length/3}));
const prefix=Buffer.alloc(4);prefix.writeUInt32LE(header.length);fs.writeFileSync(output,Buffer.concat([prefix,header,Buffer.from(p.buffer),Buffer.from(colors.buffer),Buffer.from(simplified.buffer,simplified.byteOffset,simplified.byteLength)]));console.log(header.toString());
