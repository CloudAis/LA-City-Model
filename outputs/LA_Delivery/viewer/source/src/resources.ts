import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {MeshoptDecoder} from 'meshoptimizer';
import type {Manifest,Resource,Quality,V3} from './types';

type Entry={resource:Resource;group:THREE.Group;lastUsed:number;memoryBytes:number};
type Pending={controller:AbortController;wanted:number;resource:Resource};
const asWorld=(p:V3)=>new THREE.Vector3(p[0],p[2],-p[1]);
export class Resources {
 readonly cache=new Map<string,Entry>();readonly pending=new Map<string,Pending>();readonly groups=new Map<string,Resource[]>();
 readonly layers=new Set(['terrain','roads','buildings','landmarks','vegetation','furniture','water']);
 readonly texturePool=new Map<string,{texture:THREE.Texture;references:number}>();
 readonly decodedMaterials=new Set<THREE.Material>();readonly decodedGeometries=new Set<THREE.BufferGeometry>();
 readonly errors=new Map<string,string>();readonly metadata=new Map<string,Record<string,unknown>>();
 readonly stats={loaded:0,bytesReceived:0,cacheHits:0,cancelled:0,retries:0,released:0,failed:0,geometriesDisposed:0,materialsDisposed:0,texturesDisposed:0,loads:[] as {url:string;ms:number;bytes:number}[]};
 origin=new THREE.Vector3();quality:Quality;qualityName='medium';wanted=new Set<string>();focus=new THREE.Vector3();
 private localGroundRects:THREE.Vector4[]=[];
 private groundClips=new Map<THREE.Material,{count:{value:number},rects:{value:THREE.Vector4[]}}>();
 private generation=0;private frozen=false;private desired:Resource[]=[];private failures=new Map<string,{attempts:number,next:number}>();
 private instanceGroup:THREE.Group|null=null;private instancePromise:Promise<void>|null=null;private instanceAbort:AbortController|null=null;private instanceExpiry=0;private currentNight=false;
 constructor(readonly manifest:Manifest,readonly scene:THREE.Scene,readonly changed:()=>void){
  this.quality=manifest.config.qualities.medium;
  const prototypeUrls=new Set(Object.values(manifest.instances.prototypes).map(r=>r.url));
  for(const resource of manifest.resources){if(prototypeUrls.has(resource.url))continue;const key=resource.id;const rows=this.groups.get(key)||[];rows.push(resource);this.groups.set(key,rows);}
 }
 private makeLoader(){const manager=new THREE.LoadingManager();manager.setURLModifier(url=>this.quality.texture_px<=256?url.replace('/textures/','/textures-low/'):url);const loader=new GLTFLoader(manager);loader.setMeshoptDecoder(MeshoptDecoder);return loader;}
 private async acquire(resource:Resource,signal:AbortSignal):Promise<THREE.Group>{
  const start=performance.now();const response=await fetch('/resources/'+resource.url,{signal,cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}: ${resource.url}`);
  const buffer=await response.arrayBuffer();signal.throwIfAborted();this.stats.bytesReceived+=buffer.byteLength;
  const gltf=await this.makeLoader().parseAsync(buffer,new URL('/resources/tiles/',location.href).href);
  if(signal.aborted){this.disposeGroup(gltf.scene);signal.throwIfAborted();}
  gltf.scene.userData.resource=resource;
  gltf.scene.traverse(object=>{if(!(object instanceof THREE.Mesh)&&!(object instanceof THREE.LineSegments))return;object.castShadow=resource.layer!=='terrain'&&resource.layer!=='water';object.receiveShadow=resource.layer!=='water';object.userData.resource=resource;
   this.decodedGeometries.add(object.geometry);
   const effective=(Array.isArray(object.material)?object.material:[object.material]).map(original=>{
    if(original instanceof THREE.MeshPhysicalMaterial&&this.manifest.config.software_glass_compatibility){original.transmission=0;original.userData.runtimeCompatibility='software opaque dielectric reflection; original transmission retained in GLB and Blender';}
    if(this.qualityName==='high'||!(original instanceof THREE.MeshStandardMaterial))return original;
    const compatible=new THREE.MeshLambertMaterial({name:original.name+'_runtime_diffuse',color:original.color,map:original.map,vertexColors:original.vertexColors,side:original.side,alphaTest:original.alphaTest,transparent:false,opacity:1,emissive:original.emissive,emissiveIntensity:original.emissiveIntensity});
    compatible.userData={...original.userData,runtimeCompatibility:'base-color diffuse lighting; high preserves full source PBR/normal/ORM/transmission'};
    const unused=new Set([original.normalMap,original.roughnessMap,original.metalnessMap,original.aoMap,original.emissiveMap].filter(t=>t&&t!==original.map));
    for(const texture of unused){texture!.dispose();(texture!.source.data as {close?:()=>void})?.close?.();}
    original.dispose();return compatible;
   });
   object.material=Array.isArray(object.material)?effective:effective[0];
   if(resource.id==='overview-terrain'&&object instanceof THREE.Mesh){const original=object.raycast.bind(object);object.raycast=(raycaster,hits)=>{const picked:THREE.Intersection[]=[];original(raycaster,picked);for(const hit of picked)if(!this.localGroundRects.some(r=>hit.point.x>=r.x&&hit.point.x<=r.z&&hit.point.z>=r.y&&hit.point.z<=r.w))hits.push(hit);};}
   for(const material of effective){
    if(resource.id==='overview-terrain'){object.castShadow=false;object.receiveShadow=false;this.installGroundClip(material);}
    // The city overview road lines are a cartographic overlay. Their true
    // source elevations can fall below the simplified terrain between samples.
    // Preserve coordinates and show the map line without a depth competition.
    if(resource.overview&&object instanceof THREE.LineSegments){material.depthTest=false;material.depthWrite=false;object.renderOrder=2;}
    if(this.decodedMaterials.has(material))continue;
    this.decodedMaterials.add(material);const m=material as THREE.MeshStandardMaterial;
    if(this.qualityName!=='high'&&'transmission' in m){(m as THREE.MeshPhysicalMaterial).transmission=0;m.needsUpdate=true;m.userData.runtimeCompatibility='opaque dielectric tint; physical transmission reserved for high quality';}
    for(const key of ['map','normalMap','roughnessMap','metalnessMap','aoMap','emissiveMap'] as const){const texture=m[key];if(!texture)continue;
     const image=texture.source.data as {src?:string;width?:number;height?:number};const uri=image?.src||texture.name||texture.uuid;
     // ImageBitmap has no URL. Loader texture names identify the local map;
     // include color-space/sampler state to avoid aliasing data and color maps.
     const poolKey=[texture.name,uri.startsWith('http')?uri:'',texture.colorSpace,texture.wrapS,texture.wrapT,texture.minFilter].join('|');
     if(!texture.name&&!image?.src)continue;
     const pooled=this.texturePool.get(poolKey);
     if(pooled){m[key]=pooled.texture;pooled.references++;if(texture!==pooled.texture){texture.dispose();if(!texture.userData.bitmapClosed&&texture.source!==pooled.texture.source){(texture.source.data as {close?:()=>void})?.close?.();texture.userData.bitmapClosed=true;}}}
     else{texture.userData.poolKey=poolKey;this.texturePool.set(poolKey,{texture,references:1});}
    }
    this.applyNightMaterial(m);
   }
  });
  this.stats.loads.push({url:resource.url,ms:performance.now()-start,bytes:buffer.byteLength});if(this.stats.loads.length>200)this.stats.loads.shift();
  return gltf.scene;
 }
 private installGroundClip(material:THREE.Material){
  if(this.groundClips.has(material))return;
  const state={count:{value:0},rects:{value:Array.from({length:64},()=>new THREE.Vector4())}};this.groundClips.set(material,state);
  material.onBeforeCompile=shader=>{shader.uniforms.localGroundCount=state.count;shader.uniforms.localGroundRects=state.rects;
   shader.vertexShader='varying vec3 fallbackGroundWorld;\n'+shader.vertexShader;shader.vertexShader=shader.vertexShader.replace('#include <project_vertex>','#include <project_vertex>\nfallbackGroundWorld=(modelMatrix*vec4(transformed,1.0)).xyz;');
   shader.fragmentShader='varying vec3 fallbackGroundWorld;\nuniform int localGroundCount;\nuniform vec4 localGroundRects[64];\n'+shader.fragmentShader;
   shader.fragmentShader=shader.fragmentShader.replace('#include <clipping_planes_fragment>','#include <clipping_planes_fragment>\nfor(int gi=0;gi<64;gi++){if(gi>=localGroundCount)break;vec4 r=localGroundRects[gi];if(fallbackGroundWorld.x>=r.x&&fallbackGroundWorld.x<=r.z&&fallbackGroundWorld.z>=r.y&&fallbackGroundWorld.z<=r.w)discard;}');};
  material.customProgramCacheKey=()=> 'phase10-fallback-ground-mask-v1';material.needsUpdate=true;
 }
 private updateGroundClips(){
  const rows=new Map<string,[number,number][]>();
  for(const entry of this.cache.values()){const r=entry.resource;if(!entry.group.visible||r.layer!=='terrain'||r.overview)continue;const [a,b]=r.bounds_city_m;const y0=-b[1]-this.origin.z,y1=-a[1]-this.origin.z,key=y0+','+y1;const xs=rows.get(key)||[];xs.push([a[0]-this.origin.x,b[0]-this.origin.x]);rows.set(key,xs);}
  const rectangles:THREE.Vector4[]=[];for(const [key,parts] of rows){const [y0,y1]=key.split(',').map(Number);parts.sort((a,b)=>a[0]-b[0]);let merged=parts[0];for(const next of parts.slice(1)){if(next[0]<=merged[1]+.04)merged=[merged[0],Math.max(merged[1],next[1])];else{rectangles.push(new THREE.Vector4(merged[0],y0,merged[1],y1));merged=next;}}rectangles.push(new THREE.Vector4(merged[0],y0,merged[1],y1));}
  this.localGroundRects=rectangles.slice(0,64);
  for(const state of this.groundClips.values()){state.count.value=Math.min(rectangles.length,64);rectangles.slice(0,64).forEach((r,i)=>state.rects.value[i].copy(r));}
 }
 private applyNightMaterial(m:THREE.MeshStandardMaterial){if(!m.emissive)return;const base=m.userData.nightEmissionStrength as number|undefined;if(base!==undefined)m.emissiveIntensity=this.currentNight?base:0;}
 setNight(night:boolean){this.currentNight=night;for(const m of this.decodedMaterials)this.applyNightMaterial(m as THREE.MeshStandardMaterial);}
 setOrigin(origin:THREE.Vector3){this.origin.copy(origin);for(const entry of this.cache.values())this.position(entry);if(this.instanceGroup)this.instanceGroup.position.copy(origin).multiplyScalar(-1);}
 private position(entry:Entry){entry.group.position.copy(asWorld(entry.resource.origin_city_m)).sub(this.origin);}
 setQuality(name:string){this.qualityName=name;this.quality=this.manifest.config.qualities[name];this.generation++;this.disposeAll();this.changed();}
 setLayer(layer:string,on:boolean){if(on)this.layers.add(layer);else this.layers.delete(layer);for(const entry of this.cache.values())if(entry.resource.layer===layer)entry.group.visible=on&&this.wanted.has(entry.resource.url);if(this.instanceGroup)this.instanceGroup.traverse(o=>{if(o.userData.layer)o.visible=this.layers.has(o.userData.layer);});}
 private distance(resource:Resource,camera:THREE.Vector3){const [lo,hi]=resource.bounds_city_m;const box=new THREE.Box3(asWorld([lo[0],hi[1],lo[2]]),asWorld([hi[0],lo[1],hi[2]]));return box.distanceToPoint(camera);}
 update(camera:THREE.PerspectiveCamera,focus:THREE.Vector3,now=performance.now()){
  if(this.frozen)return;this.focus.copy(focus);const q=this.quality,globalCamera=camera.position.clone().add(this.origin);
  const overview=globalCamera.y>5500;const frustum=new THREE.Frustum().setFromProjectionMatrix(new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse));
  const candidates:{r:Resource;distance:number;priority:number}[]=[];
  for(const rows of this.groups.values()){
   const first=rows[0];if(!this.layers.has(first.layer))continue;
   if(first.overview){if(overview||first.layer==='terrain')candidates.push({r:first,distance:0,priority:-200});continue;}
   if(overview&&first.layer!=='landmarks')continue;
   const d=this.distance(first,globalCamera);if(!overview&&d>q.load_radius_m&&first.layer!=='landmarks')continue;
   const [a,b]=first.bounds_city_m;const center=asWorld([(a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2]).sub(this.origin);
   const radius=Math.max(1,new THREE.Vector3(b[0]-a[0],b[2]-a[2],b[1]-a[1]).length()/2);
   const visible=frustum.intersectsSphere(new THREE.Sphere(center,radius));
   // One neighbor ring outside the view is allowed within10% of the budget.
   if(!visible&&d>q.near_m*2)continue;
   const lod=overview?2:d<q.near_m?0:d<q.mid_m?1:2;
   let r=rows.reduce((best,v)=>Math.abs(v.lod-lod)<Math.abs(best.lod-lod)?v:best,first);
   const current=[...this.cache.values()].find(e=>e.resource.id===first.id&&e.group.visible);
   if(current&&Math.abs(current.resource.lod-r.lod)===1){const boundary=r.lod===0||current.resource.lod===0?q.near_m:q.mid_m;if(Math.abs(d-boundary)<boundary*.15)r=current.resource;}
   const focusedLandmark=first.layer==='landmarks'&&this.distance(first,focus)<50;
   const focusOnTile=focus.x>=a[0]&&focus.x<=b[0]&&-focus.z>=a[1]&&-focus.z<=b[1]&&this.distance(first,focus)<200;
   const cameraOnTile=globalCamera.x>=a[0]&&globalCamera.x<=b[0]&&-globalCamera.z>=a[1]&&-globalCamera.z<=b[1]&&d<150;
   // A cut terrain tile needs its matching pavement before façade detail.
   // Far roads omit minor streets and cannot fill a close-up street opening.
   if((cameraOnTile||focusOnTile)&&(first.layer==='roads'||first.layer==='terrain')&&r.lod>1)r=rows.find(v=>v.lod===1)||r;
   const essential=(cameraOnTile||focusOnTile)&&(first.layer==='roads'||first.layer==='terrain');
   if(first.layer==='roads'&&!essential)r=rows.find(v=>v.lod===2)||r;
   candidates.push({r,distance:d,priority:(essential&&first.layer==='terrain'?-170:essential&&first.layer==='roads'?-160:focusedLandmark?-150:first.layer==='landmarks'?-140:first.layer==='terrain'?-130:first.id.startsWith('detail-')&&d<q.near_m?-120:first.layer==='roads'?-110:first.id.startsWith('detail-')?-90:-100)+d/1000+(visible?0:20)});
  }
  candidates.sort((a,b)=>a.priority-b.priority);let tris=0,count=0,detailTris=0,terrainTris=0,roadTris=0;const desired:Resource[]=[];
  for(const item of candidates){let r=item.r;if(count>=q.tile_cap)break;
   if(r.id==='overview-terrain'){desired.push(r);continue;}
   const layerUsed=r.layer==='terrain'?terrainTris:r.layer==='roads'?roadTris:0;
   if((r.layer==='terrain'||r.layer==='roads')&&layerUsed+r.triangles>q.triangles*.25){const rows=this.groups.get(r.id)||[];r=r.layer==='roads'&&item.priority< -150?(rows.find(v=>v.lod===1)||r):(rows.filter(v=>v.lod>=r.lod).sort((a,b)=>a.triangles-b.triangles)[0]||r);}
   if(r.id.startsWith('detail-')&&detailTris+r.triangles>q.triangles*.55){const rows=this.groups.get(r.id)||[];const simpler=rows.filter(v=>v.lod>r.lod).sort((a,b)=>a.lod-b.lod).find(v=>detailTris+v.triangles<=q.triangles*.55);if(simpler)r=simpler;else continue;}
   if(tris+r.triangles>q.triangles){const rows=this.groups.get(r.id)||[];const alternatives=rows.filter(v=>v.lod>r.lod).sort((a,b)=>a.lod-b.lod);const fallback=alternatives.find(v=>tris+v.triangles<=q.triangles)||alternatives.at(-1);if(fallback)r=fallback;}
   if(tris+r.triangles>q.triangles&&r.layer!=='terrain')continue;
   if(tris+r.triangles>q.triangles*1.2)continue;
   desired.push(r);tris+=r.triangles;if(r.id.startsWith('detail-'))detailTris+=r.triangles;if(r.layer==='terrain')terrainTris+=r.triangles;if(r.layer==='roads')roadTris+=r.triangles;count++;
  }
  this.desired=desired;this.wanted=new Set(desired.map(r=>r.url));
  for(const [url,pending] of this.pending)if(!this.wanted.has(url)){pending.controller.abort();this.stats.cancelled++;this.pending.delete(url);}
  for(const [url,entry] of this.cache){entry.group.visible=this.wanted.has(url)&&this.layers.has(entry.resource.layer);if(entry.group.visible)entry.lastUsed=now;}
  // Avoid a visible hole while its requested replacement LOD is in flight.
  for(const r of desired){if(this.cache.has(r.url))continue;const old=[...this.cache.values()].find(e=>e.resource.id===r.id);if(old&&this.layers.has(r.layer)){old.group.visible=true;old.lastUsed=now;}}
  this.updateGroundClips();this.pump();this.evict(now);
  const nearInstances=!overview&&globalCamera.distanceTo(asWorld([0,1400,100]))<2000;
  if(nearInstances){this.instanceExpiry=now+this.manifest.config.loading.unload_after_s*1000;this.ensureInstances();if(this.instanceGroup)this.instanceGroup.visible=true;}
  else if(this.instanceGroup){this.instanceGroup.visible=false;if(now>this.instanceExpiry)this.disposeInstances();}
  this.changed();
 }
 private pump(){
  if(this.frozen)return;
  for(const r of this.desired){
   if(this.pending.size>=this.manifest.config.loading.concurrency)break;
   if(this.cache.has(r.url)){this.stats.cacheHits++;continue;}if(this.pending.has(r.url))continue;
   const f=this.failures.get(r.url);if(f&&(f.attempts>this.manifest.config.loading.max_retries||performance.now()<f.next))continue;
   const controller=new AbortController(),generation=this.generation;this.pending.set(r.url,{controller,wanted:generation,resource:r});
   this.acquire(r,controller.signal).then(group=>{
    if(controller.signal.aborted||generation!==this.generation||!this.wanted.has(r.url)){this.disposeGroup(group);return;}
    const memoryBytes=this.memory(group);const entry={resource:r,group,lastUsed:performance.now(),memoryBytes};this.position(entry);this.scene.add(group);this.cache.set(r.url,entry);this.stats.loaded++;this.errors.delete(r.url);
    for(const old of this.cache.values())if(old!==entry&&old.resource.id===r.id)old.group.visible=false;
   }).catch(error=>{
    if(controller.signal.aborted)return;const previous=this.failures.get(r.url)?.attempts||0;this.failures.set(r.url,{attempts:previous+1,next:performance.now()+this.manifest.config.loading.retry_delay_ms*2**previous});
    if(previous<this.manifest.config.loading.max_retries)this.stats.retries++;else this.stats.failed++;this.errors.set(r.url,String(error));
   }).finally(()=>{if(this.pending.get(r.url)?.controller===controller)this.pending.delete(r.url);this.changed();this.pump();});
  }
 }
 retryErrors(){this.failures.clear();this.errors.clear();this.pump();}
 private memory(group:THREE.Object3D){let bytes=0;const geometry=new Set<THREE.BufferGeometry>();group.traverse(o=>{if((o instanceof THREE.Mesh||o instanceof THREE.LineSegments)&&!geometry.has(o.geometry)){geometry.add(o.geometry);for(const a of Object.values(o.geometry.attributes) as THREE.BufferAttribute[])bytes+=a.array.byteLength;if(o.geometry.index)bytes+=o.geometry.index.array.byteLength;}});return bytes;}
 private evict(now:number){
  const cap=this.quality.cache_mib*1024**2,expired=this.manifest.config.loading.unload_after_s*1000;
  let bytes=[...this.cache.values()].reduce((s,e)=>s+e.memoryBytes,0);
  for(const [url,entry] of [...this.cache].sort((a,b)=>a[1].lastUsed-b[1].lastUsed)){
   if(entry.group.visible)continue;if(now-entry.lastUsed<expired&&bytes<=cap)continue;
   this.scene.remove(entry.group);this.disposeGroup(entry.group);this.cache.delete(url);bytes-=entry.memoryBytes;this.stats.released++;
  }
 }
 private disposeGroup(group:THREE.Object3D){
  const geometries=new Set<THREE.BufferGeometry>(),materials=new Set<THREE.Material>();group.traverse(o=>{if(!(o instanceof THREE.Mesh)&&!(o instanceof THREE.LineSegments))return;geometries.add(o.geometry);for(const m of Array.isArray(o.material)?o.material:[o.material])materials.add(m);});
  for(const geometry of geometries){geometry.dispose();this.decodedGeometries.delete(geometry);this.stats.geometriesDisposed++;}
  for(const material of materials){const m=material as THREE.MeshStandardMaterial;
   for(const key of ['map','normalMap','roughnessMap','metalnessMap','aoMap','emissiveMap'] as const){const t=m[key];if(!t)continue;const pooled=this.texturePool.get(t.userData.poolKey as string);
    if(pooled){if(--pooled.references<=0){pooled.texture.dispose();const image=pooled.texture.source.data as {close?:()=>void};image?.close?.();this.texturePool.delete(t.userData.poolKey as string);this.stats.texturesDisposed++;}}
    else{t.dispose();this.stats.texturesDisposed++;}
   }
   material.dispose();this.groundClips.delete(material);this.decodedMaterials.delete(material);this.stats.materialsDisposed++;
  }
 }
 private async ensureInstances(){
  if(this.instanceGroup||this.instancePromise)return;const generation=this.generation,controller=new AbortController();this.instanceAbort=controller;
  this.instancePromise=(async()=>{
   const group=new THREE.Group();group.name='Mapped shared instances';
   try{
    for(const [kind,r] of Object.entries(this.manifest.instances.prototypes)){
     if(controller.signal.aborted)break;const prototype=await this.acquire(r,controller.signal);prototype.updateMatrixWorld(true);
     const fields=this.manifest.instances.fields.filter(f=>f.kind===kind);const points=fields.flatMap(f=>f.points_city_m.map((p,i)=>({p,rotation:(f.attributes.module_rotation as number[][])?.[i]||[0,0,0],scale:(f.attributes.module_scale as number[][])?.[i]||[1,1,1],sourceId:(f.attributes.building_index as number[])?.[i]})));
     prototype.traverse(object=>{if(!(object instanceof THREE.Mesh))return;
      const mesh=new THREE.InstancedMesh(object.geometry,object.material,points.length);mesh.userData.layer=r.layer;mesh.userData.instances=points;mesh.userData.resource=r;mesh.visible=this.layers.has(r.layer);
      const local=object.matrixWorld.clone(),transform=new THREE.Matrix4(),rotation=new THREE.Quaternion();
      points.forEach((p,i)=>{rotation.setFromAxisAngle(new THREE.Vector3(0,1,0),p.rotation[2]);transform.compose(asWorld(p.p),rotation,new THREE.Vector3(p.scale[0],p.scale[2],p.scale[1]));mesh.setMatrixAt(i,transform.clone().multiply(local));});mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingSphere();group.add(mesh);
     });
    }
    if(controller.signal.aborted||generation!==this.generation){this.disposeGroup(group);return;}
    this.instanceGroup=group;group.position.copy(this.origin).multiplyScalar(-1);this.scene.add(group);
   }catch(error){this.disposeGroup(group);if(!controller.signal.aborted)this.errors.set('instances',String(error));}
  })().finally(()=>{this.instancePromise=null;if(this.instanceAbort===controller)this.instanceAbort=null;});
 }
 private disposeInstances(){this.instanceAbort?.abort();if(!this.instanceGroup)return;this.scene.remove(this.instanceGroup);this.disposeGroup(this.instanceGroup);this.instanceGroup=null;}
 async feature(resource:Resource,id:number){
  const url=id>=3000000&&id<4000000?'metadata/roads-'+Math.floor((id-3000000)/1000)+'.json.gz':resource.metadata_url;
  let data=this.metadata.get(url);
  if(!data){const response=await fetch('/resources/'+url);if(!response.ok)throw new Error('属性读取失败');data=await response.json() as Record<string,unknown>;this.metadata.set(url,data);while(this.metadata.size>8)this.metadata.delete(this.metadata.keys().next().value!);}
  return data[String(id)]||{id,name:resource.id,source:resource.source_summary||'本项目实际模型',note:'合并面或远景概览；完整属性见邻近要素'};
 }
 disposeAll(){this.generation++;for(const p of this.pending.values())p.controller.abort();this.pending.clear();for(const entry of this.cache.values()){this.scene.remove(entry.group);this.disposeGroup(entry.group);}this.cache.clear();this.disposeInstances();this.metadata.clear();this.failures.clear();this.desired=[];this.wanted.clear();}
 pauseLoading(paused:boolean){this.frozen=paused;if(paused)for(const p of this.pending.values())p.controller.abort();}
 async settle(timeout=15000){const start=performance.now();while((this.pending.size||this.instancePromise||this.desired.some(r=>!this.cache.has(r.url)&&!this.failures.has(r.url)))&&performance.now()-start<timeout)await new Promise(r=>setTimeout(r,100));}
 snapshot(){const textures=[...this.texturePool.values()].map(({texture})=>{const image=texture.source.data as {width?:number;height?:number};return {name:texture.name,width:image?.width||0,height:image?.height||0,mipmapped:texture.minFilter!==THREE.NearestFilter&&texture.minFilter!==THREE.LinearFilter};});return {cache_entries:this.cache.size,pending:this.pending.size,wanted:this.wanted.size,geometry_bytes:[...this.cache.values()].reduce((s,e)=>s+e.memoryBytes,0),texture_pool_entries:this.texturePool.size,texture_dimensions:textures,decoded_texture_estimated_rgba_mip_bytes:textures.reduce((s,t)=>s+t.width*t.height*4*(t.mipmapped?4/3:1),0),texture_memory_is_estimated:true,texture_slot_references:[...this.texturePool.values()].reduce((s,e)=>s+e.references,0),tracked_geometries:this.decodedGeometries.size,tracked_materials:this.decodedMaterials.size,metadata_cache_entries:this.metadata.size,errors:[...this.errors.values()],...this.stats};}
}
