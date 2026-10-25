"""Small glTF2 writer: quantized, flat normals, per-face stable feature IDs.

Blender Z-up is converted once to glTF Y-up: (east, up, -north).
Every tile stays local; its city origin belongs to the external manifest.
"""
from pathlib import Path
import hashlib,json,struct
import numpy as np

def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def linear_rgba(color):
    return np.clip(np.array(color[:3])*255,0,255).astype(np.uint8)

class GLB:
    def __init__(self,name):
        self.doc={'asset':{'version':'2.0','generator':'LA stage09 repeatable runtime exporter'},'scene':0,'scenes':[{'nodes':[]}],
                  'nodes':[],'meshes':[],'materials':[],'accessors':[],'bufferViews':[],'buffers':[],
                  'extensionsUsed':['KHR_mesh_quantization'],'extensionsRequired':['KHR_mesh_quantization']}
        self.parts=[];self.offset=0;self.name=name;self.triangles=0;self.feature_ids=set();self.quantization_error_m=0;self.array_by_view={};self.vertices_before_indexing=0;self.indexed_vertices=0
        self.mats={};self.images={};self.textures={};self.lines=0
    def accessor(self,array,component,kind,normalized=False,stride=None,bounds=False):
        array=np.ascontiguousarray(array);blob=array.tobytes();stride=stride or array.dtype.itemsize*(array.shape[1] if array.ndim>1 else 1)
        view={'buffer':0,'byteOffset':self.offset,'byteLength':len(blob),'byteStride':stride,'target':34962}
        self.doc['bufferViews'].append(view);self.parts.append(blob);pad=(-len(blob))%4;self.parts.append(bytes(pad));self.offset+=len(blob)+pad
        self.array_by_view[len(self.doc['bufferViews'])-1]=array
        record={'bufferView':len(self.doc['bufferViews'])-1,'componentType':component,'count':len(array),'type':kind}
        if normalized:record['normalized']=True
        if bounds:
            record['min']=array.min(axis=0).tolist();record['max']=array.max(axis=0).tolist()
        self.doc['accessors'].append(record);return len(self.doc['accessors'])-1
    def index_attributes(self,attrs):
        arrays=[self.array_by_view[self.doc['accessors'][index]['bufferView']] for index in attrs.values()]
        n=len(arrays[0]);self.vertices_before_indexing+=n
        rows=np.concatenate([a.view(np.uint8).reshape(n,-1) for a in arrays],axis=1)
        keys=np.ascontiguousarray(rows).view(np.dtype('V'+str(rows.shape[1]))).reshape(-1)
        _,first,inverse=np.unique(keys,return_index=True,return_inverse=True)
        # Keep first-use spatial order. Lexicographic byte sorting substantially
        # worsens delta/index compression despite using fewer vertices.
        order=np.argsort(first,kind='stable');remap=np.empty(len(order),np.int64);remap[order]=np.arange(len(order));first=first[order];inverse=remap[inverse]
        if len(first)>=n*.99:self.indexed_vertices+=n;return None
        for index in attrs.values():
            accessor=self.doc['accessors'][index];view=accessor['bufferView'];original=self.array_by_view[view];compact=original[first]
            assert np.array_equal(np.ascontiguousarray(compact[inverse]).view(np.uint8),np.ascontiguousarray(original).view(np.uint8)),'Indexed attribute round-trip changed geometry or metadata'
            self.array_by_view[view]=compact;accessor['count']=len(first)
        self.indexed_vertices+=len(first)
        index=self.accessor(inverse.astype('<u4'),5125,'SCALAR',bounds=False)
        view=self.doc['bufferViews'][self.doc['accessors'][index]['bufferView']];view['target']=34963;view.pop('byteStride',None)
        return index
    def material(self,spec):
        key=json.dumps(spec,sort_keys=True)
        if key in self.mats:return self.mats[key]
        mat={'name':spec.get('name','runtime_shared'),'pbrMetallicRoughness':{
            'baseColorFactor':spec.get('base_color',[1,1,1,1]),'metallicFactor':spec.get('metallic',0),'roughnessFactor':spec.get('roughness',.85)},
             'doubleSided':spec.get('double_sided',False),'extras':{'family':spec.get('family',''),'night':spec.get('night',False)}}
        for role,uri in spec.get('maps',{}).items():
            if uri not in self.images:
                self.doc.setdefault('images',[]).append({'uri':uri});self.images[uri]=len(self.doc['images'])-1
            if uri not in self.textures:
                self.doc.setdefault('samplers',[{'magFilter':9729,'minFilter':9987,'wrapS':10497,'wrapT':10497}])
                sampler=0
                if 'atlas' in spec.get('name','').lower():
                    if len(self.doc['samplers'])==1:self.doc['samplers'].append({'magFilter':9729,'minFilter':9729,'wrapS':33071,'wrapT':33071})
                    sampler=1
                self.doc.setdefault('textures',[]).append({'source':self.images[uri],'sampler':sampler});self.textures[uri]=len(self.doc['textures'])-1
            info={'index':self.textures[uri]}
            if role=='base_color':mat['pbrMetallicRoughness']['baseColorTexture']=info
            elif role=='normal':mat['normalTexture']=info
            elif role=='orm':mat['pbrMetallicRoughness']['metallicRoughnessTexture']=info
        if spec.get('family')=='leaf':mat.update(alphaMode='MASK',alphaCutoff=.45,doubleSided=True)
        if spec.get('transmission',0):
            mat['extensions']={'KHR_materials_transmission':{'transmissionFactor':spec['transmission']},'KHR_materials_ior':{'ior':spec.get('ior',1.5)}}
            self.doc['extensionsUsed']+=['KHR_materials_transmission','KHR_materials_ior']
        strength=spec.get('emission_strength',0)
        if strength:
            color=spec.get('emission',[1,.7,.4])[:3];mat['emissiveFactor']=[min(1,c) for c in color]
            mat.setdefault('extensions',{})['KHR_materials_emissive_strength']={'emissiveStrength':strength};self.doc['extensionsUsed'].append('KHR_materials_emissive_strength')
            mat['extras']['nightEmissionStrength']=strength
        self.doc['materials'].append(mat);index=len(self.doc['materials'])-1;self.mats[key]=index;return index
    def add(self,positions,faces,face_ids,material,colors=None,uv=None,name=None):
        if not len(faces):return
        p=np.asarray(positions,np.float64)[faces]
        cross=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);length=np.linalg.norm(cross,axis=1)
        keep=np.isfinite(p).all(axis=(1,2))&(length>1e-9)
        if not keep.all():
            p=p[keep];cross=cross[keep];length=length[keep];face_ids=np.asarray(face_ids)[keep]
            if colors is not None:colors=np.asarray(colors)[keep]
            if uv is not None:uv=np.asarray(uv)[keep]
        if not len(p):return
        normal=cross/length[:,None];p=p[:,:,[0,2,1]];p[:,:,2]*=-1;normal=normal[:,[0,2,1]];normal[:,2]*=-1
        flat=p.reshape(-1,3);lo=flat.min(axis=0);span=np.maximum(flat.max(axis=0)-lo,1e-5)
        quant=np.rint((flat-lo)/span*65535).astype('<u2')
        # ushort VEC3 needs an8-byte aligned stride for meshopt; the fourth lane
        # is padding, not a fourth position component.
        q=np.zeros((len(flat),4),'<u2');q[:,:3]=quant
        # The position dequantization is nonuniform node scale. Pre-transform
        # normals so its inverse-transpose recovers the source face direction.
        local_normal=normal*span;local_normal/=np.linalg.norm(local_normal,axis=1)[:,None]
        normals=np.zeros((len(flat),4),np.int8);normals[:,:3]=np.rint(np.repeat(local_normal,3,axis=0)*127).astype(np.int8)
        ids=np.repeat(np.asarray(face_ids,np.float32),3)
        attrs={'POSITION':self.accessor(q,5123,'VEC3',True,8,True),
               'NORMAL':self.accessor(normals,5120,'VEC3',True,4),
               '_FEATURE_ID_0':self.accessor(ids,5126,'SCALAR')}
        # POSITION min/max must describe only actual VEC3 lanes.
        self.doc['accessors'][attrs['POSITION']]['min']=quant.min(axis=0).tolist();self.doc['accessors'][attrs['POSITION']]['max']=quant.max(axis=0).tolist()
        if colors is not None:
            cc=np.zeros((len(flat),4),np.uint8);cc[:,:3]=np.repeat(np.asarray(colors,np.uint8)[:,:3],3,axis=0);cc[:,3]=255
            attrs['COLOR_0']=self.accessor(cc,5121,'VEC4',True,4)
        if uv is not None:attrs['TEXCOORD_0']=self.accessor(np.asarray(uv,dtype='<f4').reshape(-1,2),5126,'VEC2')
        if uv is not None and material.get('maps',{}).get('normal'):
            tex=np.asarray(uv,np.float64);du=tex[:,1]-tex[:,0];dv=tex[:,2]-tex[:,0];edge1=p[:,1]-p[:,0];edge2=p[:,2]-p[:,0]
            determinant=du[:,0]*dv[:,1]-du[:,1]*dv[:,0];safe=np.where(abs(determinant)>1e-14,determinant,1)
            tangent=(edge1*dv[:,1,None]-edge2*du[:,1,None])/safe[:,None]
            tangent-=normal*np.sum(tangent*normal,axis=1)[:,None];size=np.linalg.norm(tangent,axis=1)
            bad=size<1e-12
            if bad.any():
                axis=np.eye(3)[np.argmin(abs(normal[bad]),axis=1)];tangent[bad]=np.cross(axis,normal[bad]);size[bad]=np.linalg.norm(tangent[bad],axis=1)
            tangent/=size[:,None]
            bitangent=(edge2*du[:,0,None]-edge1*dv[:,0,None])/safe[:,None]
            handed=np.where(np.sum(np.cross(normal,tangent)*bitangent,axis=1)<0,-1,1)
            local_tangent=tangent/span;local_tangent/=np.linalg.norm(local_tangent,axis=1)[:,None]
            tangent4=np.empty((len(p),4),np.int8);tangent4[:,:3]=np.rint(local_tangent*127).astype(np.int8);tangent4[:,3]=handed*127
            attrs['TANGENT']=self.accessor(np.repeat(tangent4,3,axis=0),5120,'VEC4',True,4)
        primitive={'attributes':attrs,'material':self.material(material),'mode':4}
        index=self.index_attributes(attrs)
        if index is not None:primitive['indices']=index
        self.doc['meshes'].append({'name':name or self.name,'primitives':[primitive]})
        node={'name':name or self.name,'mesh':len(self.doc['meshes'])-1,'translation':lo.tolist(),'scale':span.tolist()}
        self.doc['nodes'].append(node);self.doc['scenes'][0]['nodes'].append(len(self.doc['nodes'])-1)
        self.triangles+=len(p);self.feature_ids.update(map(int,np.unique(face_ids)))
        self.quantization_error_m=max(self.quantization_error_m,float(np.linalg.norm(span/65535/2)))
    def add_lines(self,segments,ids):
        p=np.asarray(segments,np.float64).reshape(-1,3)[:,[0,2,1]];p[:,2]*=-1
        lo=p.min(axis=0);span=np.maximum(p.max(axis=0)-lo,1e-5);q=np.zeros((len(p),4),'<u2');q[:,:3]=np.rint((p-lo)/span*65535).astype('<u2')
        a=self.accessor(q,5123,'VEC3',True,8,True);self.doc['accessors'][a]['min']=q[:,:3].min(axis=0).tolist();self.doc['accessors'][a]['max']=q[:,:3].max(axis=0).tolist()
        attrs={'POSITION':a,'_FEATURE_ID_0':self.accessor(np.repeat(np.asarray(ids,np.float32),2),5126,'SCALAR')}
        primitive={'attributes':attrs,'material':self.material({'name':'overview_transport_lines','base_color':[.10,.16,.19,1],'roughness':1}),'mode':1}
        index=self.index_attributes(attrs)
        if index is not None:primitive['indices']=index
        self.doc['meshes'].append({'name':self.name,'primitives':[primitive]})
        self.doc['nodes'].append({'mesh':len(self.doc['meshes'])-1,'translation':lo.tolist(),'scale':span.tolist()});self.doc['scenes'][0]['nodes'].append(len(self.doc['nodes'])-1)
        self.lines+=len(p)//2;self.quantization_error_m=float(np.linalg.norm(span/65535/2))
    def save(self,path):
        parts=[];offset=0
        for index,view in enumerate(self.doc['bufferViews']):
            payload=np.ascontiguousarray(self.array_by_view[index]).tobytes();view['byteOffset']=offset;view['byteLength']=len(payload);parts.extend([payload,bytes((-len(payload))%4)]);offset+=len(payload)+((-len(payload))%4)
        self.doc['buffers']=[{'byteLength':offset}]
        self.doc['extensionsUsed']=sorted(set(self.doc['extensionsUsed']))
        data=json.dumps(self.doc,separators=(',',':')).encode();data+=b' '*((-len(data))%4);binary=b''.join(parts)
        header=struct.pack('<4sII',b'glTF',2,28+len(data)+len(binary))
        Path(path).write_bytes(header+struct.pack('<I4s',len(data),b'JSON')+data+struct.pack('<I4s',len(binary),b'BIN\0')+binary)
