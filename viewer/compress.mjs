// Persistent local GLB compression worker. Every encoded buffer is decoded and
// byte-compared before the original temporary file can be removed.
import fs from 'node:fs';
import readline from 'node:readline';
import { MeshoptEncoder, MeshoptDecoder } from 'meshoptimizer';
await Promise.all([MeshoptEncoder.ready,MeshoptDecoder.ready]);
const align=n=>(n+3)&~3;
for await(const line of readline.createInterface({input:process.stdin,crlfDelay:Infinity})){
 try{
  const request=JSON.parse(line),raw=fs.readFileSync(request.input);
  const jsonSize=raw.readUInt32LE(12),doc=JSON.parse(raw.subarray(20,20+jsonSize).toString());
  const bin=raw.subarray(28+jsonSize);let offset=0,fallback=0;const chunks=[];
  for(const view of doc.bufferViews){
   const stride=view.byteStride||4,count=view.byteLength/stride;
   if(!Number.isInteger(count))throw new Error('Non-integral meshopt buffer stride');
   const source=bin.subarray(view.byteOffset||0,(view.byteOffset||0)+view.byteLength);
   const mode=view.target===34963?'INDICES':'ATTRIBUTES';
   const encoded=MeshoptEncoder.encodeGltfBuffer(source,count,stride,mode);
   const decoded=new Uint8Array(view.byteLength);
   MeshoptDecoder.decodeGltfBuffer(decoded,count,stride,encoded,mode,'NONE');
   if(!Buffer.from(decoded).equals(source))throw new Error('Meshopt byte round-trip mismatch');
   view.buffer=1;view.byteOffset=fallback;fallback+=view.byteLength;
   view.extensions={EXT_meshopt_compression:{buffer:0,byteOffset:offset,byteLength:encoded.length,byteStride:stride,count,mode,filter:'NONE'}};
   chunks.push(Buffer.from(encoded),Buffer.alloc(align(encoded.length)-encoded.length));offset+=align(encoded.length);
  }
  doc.buffers=[{byteLength:offset},{byteLength:fallback,extensions:{EXT_meshopt_compression:{fallback:true}}}];
  doc.extensionsUsed=[...new Set([...(doc.extensionsUsed||[]),'EXT_meshopt_compression'])];
  doc.extensionsRequired=[...new Set([...(doc.extensionsRequired||[]),'EXT_meshopt_compression'])];
  const json=Buffer.from(JSON.stringify(doc)),padded=Buffer.concat([json,Buffer.alloc(align(json.length)-json.length,32)]);
  const header=Buffer.alloc(20);header.write('glTF');header.writeUInt32LE(2,4);header.writeUInt32LE(28+padded.length+offset,8);header.writeUInt32LE(padded.length,12);header.write('JSON',16);
  const binHeader=Buffer.alloc(8);binHeader.writeUInt32LE(offset);binHeader.write('BIN\0',4);
  const output=Buffer.concat([header,padded,binHeader,...chunks]);fs.writeFileSync(request.output,output);
  console.log(JSON.stringify({status:'passed',raw_bytes:raw.length,compressed_bytes:output.length,buffers_verified:doc.bufferViews.length,actual_lossless_decode_byte_comparison:true}));
 }catch(error){console.log(JSON.stringify({status:'failed',error:String(error.stack||error)}));}
}
