import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';
import {MeshoptDecoder} from '../viewer/node_modules/meshoptimizer/index.js';
await MeshoptDecoder.ready;
const root=path.resolve(import.meta.dirname,'..'),base=path.join(root,'outputs/LA_Delivery/tiles'),catalog=JSON.parse(fs.readFileSync(path.join(base,'manifest.json'))),reports=[],ordinary=new Set();
const drawable=new Set(),tag=process.argv[2]||'before';let totalTriangles=0,totalVertices=0,zero=0,missing=0,nonfinite=0,badIndices=0,mixed=0;
const started=performance.now();
for(const resource of catalog.resources){
 const filename=path.join(base,resource.url),raw=fs.readFileSync(filename),hash=crypto.createHash('sha256').update(raw).digest('hex');if(hash!==resource.sha256)throw Error('Changed source asset '+resource.url);
 const length=raw.readUInt32LE(12),doc=JSON.parse(raw.subarray(20,20+length)),bin=raw.subarray(28+length),decoded=new Map();let degenerate=0,triangles=0,vertices=0,nan=0,invalid=0,mixedIds=0;const primitiveProblems=[];
 function attr(id){
  const a=doc.accessors[id],v=doc.bufferViews[a.bufferView],components={SCALAR:1,VEC2:2,VEC3:3,VEC4:4}[a.type],bytes={5120:1,5121:1,5123:2,5125:4,5126:4}[a.componentType];
  if(!decoded.has(a.bufferView)){let b;const e=v.extensions?.EXT_meshopt_compression;if(e){b=new Uint8Array(v.byteLength);MeshoptDecoder.decodeGltfBuffer(b,e.count,e.byteStride,bin.subarray(e.byteOffset,e.byteOffset+e.byteLength),e.mode,e.filter||'NONE');}else b=bin.subarray(v.byteOffset,v.byteOffset+v.byteLength);decoded.set(a.bufferView,new DataView(b.buffer,b.byteOffset,b.byteLength));}
  const data=decoded.get(a.bufferView),stride=v.byteStride||components*bytes,offset=a.byteOffset||0;
  function get(i,c=0){const p=offset+i*stride+c*bytes;return a.componentType===5123?data.getUint16(p,true):a.componentType===5125?data.getUint32(p,true):a.componentType===5126?data.getFloat32(p,true):a.componentType===5120?data.getInt8(p):data.getUint8(p);}
  return {a,get,components};
 }
 for(const image of doc.images||[])if(image.uri&&!fs.existsSync(path.resolve(path.dirname(filename),image.uri)))missing++;
 for(const node of doc.nodes){if(node.mesh===undefined)continue;for(const [primitiveIndex,p] of doc.meshes[node.mesh].primitives.entries()){
  const q=attr(p.attributes.POSITION),indices=p.indices!==undefined?attr(p.indices):null,ids=attr(p.attributes._FEATURE_ID_0);vertices+=q.a.count;let removed=[];
  for(const aId of Object.values(p.attributes)){const attribute=attr(aId);if(attribute.a.componentType===5126)for(let i=0;i<attribute.a.count;i++)for(let c=0;c<attribute.components;c++)if(!Number.isFinite(attribute.get(i,c)))nan++;}
  if(resource.layer==='buildings'&&resource.id.startsWith('buildings-')&&resource.lod===1)for(let i=0;i<ids.a.count;i++)ordinary.add(Math.round(ids.get(i)));
  if(p.mode!==undefined&&p.mode!==4)continue;
  const count=indices?indices.a.count:q.a.count;triangles+=count/3;
  for(let k=0;k<count;k+=3){const a=indices?indices.get(k):k,b=indices?indices.get(k+1):k+1,c=indices?indices.get(k+2):k+2;
   if(a>=q.a.count||b>=q.a.count||c>=q.a.count){invalid++;continue;}
   const ux=q.get(b,0)-q.get(a,0),uy=q.get(b,1)-q.get(a,1),uz=q.get(b,2)-q.get(a,2),vx=q.get(c,0)-q.get(a,0),vy=q.get(c,1)-q.get(a,1),vz=q.get(c,2)-q.get(a,2);
   if(uy*vz-uz*vy===0&&uz*vx-ux*vz===0&&ux*vy-uy*vx===0){degenerate++;removed.push(k/3);}
   else if(resource.layer==='buildings'&&resource.id.startsWith('buildings-')&&resource.lod===1)drawable.add(Math.round(ids.get(a)));
   if(ids.get(a)!==ids.get(b)||ids.get(a)!==ids.get(c))mixedIds++;
  }
  if(removed.length)primitiveProblems.push({node_mesh:node.mesh,primitive_index:primitiveIndex,degenerate_triangle_indices:removed});
 }}
 totalTriangles+=triangles;totalVertices+=vertices;zero+=degenerate;nonfinite+=nan;badIndices+=invalid;mixed+=mixedIds;
 if(degenerate||nan||invalid||mixedIds)reports.push({id:resource.id,lod:resource.lod,url:resource.url,source_sha256:hash,triangles,degenerate,nan,invalid,mixedIds,primitives:primitiveProblems});
 if(reports.length%50===0&&degenerate)console.log('GLB_GEOMETRY_WARNING',resource.id,degenerate);
}
const report={status:missing||nonfinite||badIndices||mixed?'failed':zero?'numeric_passed_zero_area_repair_required':'passed',actual_all_catalog_glbs_decoded:true,resources:catalog.resources.length,triangles_including_exclusive_lods:totalTriangles,vertices_including_exclusive_lods:totalVertices,zero_area_triangles:zero,missing_texture_references:missing,nonfinite_attributes:nonfinite,invalid_indices:badIndices,mixed_feature_triangles:mixed,ordinary_lod1_unique_building_ids:ordinary.size,elapsed_seconds:(performance.now()-started)/1000,issues:reports,interpretation:'All resource buffers decoded; zero area is tested in exact quantized integer coordinates. Open sheets are permitted. This does not certify global watertightness, all pairwise intersections or source surveying accuracy.'};
report.drawable_ordinary_lod1_unique_ids=drawable.size;
fs.writeFileSync(path.join(root,'work/reports/stage10/runtime_geometry_'+tag+'.json'),JSON.stringify(report,null,2)+'\n');fs.writeFileSync(path.join(root,'work/reports/stage10/runtime_building_ids.json'),JSON.stringify([...drawable].sort((a,b)=>a-b))+'\n');console.log('ALL_GLB_AUDITED',report.status,catalog.resources.length,'triangles',totalTriangles,'zero',zero,'buildings',ordinary.size,'drawable',drawable.size);
