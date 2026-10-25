"""Actual stage08 GLB sample export and independent scene re-import checks.

Called by the stage08 Blender worker after reopening its saved checkpoint. Only
temporary copies are rebased; original city geometry/materials are not changed.
"""
from pathlib import Path
import hashlib
import json
import math
import struct

import bpy
import numpy as np
from mathutils import Vector


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(root, relative, value):
    path = Path(root)/relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")


def glb_document(path):
    data = Path(path).read_bytes()
    magic, version, size = struct.unpack_from("<4sII", data)
    assert magic == b"glTF" and version == 2 and size == len(data), "Invalid GLB2 header"
    cursor = 12
    document = None
    binary = b""
    while cursor < len(data):
        length, kind = struct.unpack_from("<II", data, cursor)
        cursor += 8
        payload = data[cursor:cursor+length]
        assert len(payload) == length
        cursor += length
        if kind == 0x4E4F534A:
            document = json.loads(payload.decode("utf8").rstrip("\x00 \t\r\n"))
        elif kind == 0x004E4942:
            binary = payload
    assert document is not None and cursor == len(data)
    return document, binary


def bounds(objects):
    points = [ob.matrix_world @ Vector(corner) for ob in objects for corner in ob.bound_box]
    assert points
    array = np.array(points, dtype=float)
    return array.min(axis=0), array.max(axis=0)


def _distance(ob, focus):
    p = ob.matrix_world.translation
    return (p.x-focus[0])**2+(p.y-focus[1])**2


def sample_objects(scene):
    """Choose actual source meshes, avoiding a synthetic showcase replacement."""
    meshes = [ob for ob in scene.objects if ob.type == "MESH" and len(ob.data.polygons)]
    building = [o for o in meshes if o.get("r2_building") == 1080188 and o.get("r2_lod") == "near"]
    if not building:
        building = [o for o in meshes if o.get("r2_building") == 960933 and o.get("r2_lod") == "near"]
    roads = [o for o in meshes if o.get("traffic_role") == "downtown_road"]
    assert roads, "No actual road mesh available"
    focus=json.loads(scene['stage08_camera'])['focus_xy_m']
    road = min(roads, key=lambda o: (o.location.x+500-focus[0])**2+(o.location.y+500-focus[1])**2)
    lamp = bpy.data.objects.get('S8_Export_lamp_realised')
    tree = bpy.data.objects.get("S8_Export_tree_realised")
    if tree is None:
        tree = bpy.data.objects.get("LA07_Module_tree_broadleaf")
    assert tree is not None and tree.type == "MESH", "No actual realised leaf/trunk mesh available"
    waters = [o for o in meshes if o.name.startswith("Water_") and len(o.data.polygons) >= 4]
    assert waters, "No actual source water surface available"
    water = min(waters, key=lambda o: _distance(o, (0, 1400)))
    landmark = [o for o in meshes if o.get("landmark_id") == "city_hall" and o.get("landmark_lod") == "near"]
    assert building and landmark, "Building/landmark source geometry unavailable"
    return {"building": building, "road": [road]+([lamp] if lamp else []), "vegetation": [tree], "water": [water], "landmark": landmark}


def uv_fallback(mesh):
    """Provide a documented local metre-based UV only on the export copy.

    The preferred UV comes from the saved PBR scene. This fallback is allowed for
    legacy source patches that never had UVs, and is explicitly reported.
    """
    if mesh.uv_layers:
        return False
    layer = mesh.uv_layers.new(name="Stage08_export_fallback_metres")
    coordinates = np.empty(len(mesh.vertices)*3, np.float32)
    mesh.vertices.foreach_get("co", coordinates)
    coordinates = coordinates.reshape(-1, 3)
    loops = np.empty(len(mesh.loops), np.int32)
    mesh.loops.foreach_get("vertex_index", loops)
    uv = np.empty((len(mesh.loops), 2), np.float32)
    for p in mesh.polygons:
        # Dominant plane per face; UV units remain source local metres. Exact
        # material-specific texel density is the saved scene's responsibility.
        axes = [a for a in range(3) if a != int(np.argmax(np.abs(p.normal)))]
        ids = np.arange(p.loop_start, p.loop_start+p.loop_total)
        uv[ids] = coordinates[loops[ids]][:, axes]
    layer.data.foreach_set("uv", uv.ravel())
    mesh.update()
    return True


def material_inventory(objects):
    # Stage08 deliberately overrides materials per object so linked unchanged
    # meshes can retain their original source slots. Inspect effective slots.
    materials = {slot.material.as_pointer(): slot.material for o in objects
                 for slot in o.material_slots if slot.material}
    records = []
    for mat in materials.values():
        textures = []
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    im = node.image
                    textures.append({"image": im.name, "colorspace": im.colorspace_settings.name,
                                     "packed": bool(im.packed_file or im.packed_files),
                                     "size": list(im.size), "filepath": im.filepath,
                                     "extension": node.extension, "interpolation": node.interpolation})
        records.append({"name": mat.name, "textures": textures,
                        "surface_render_method": getattr(mat, "surface_render_method", "unknown"),
                        "backface_culling": bool(mat.use_backface_culling)})
    return records


def inspect_document(document, binary):
    """Inspect actual exported material graph and embedded image payloads."""
    images = []
    for index, image in enumerate(document.get("images", [])):
        assert "bufferView" in image and not image.get("uri"), "GLB sample must embed every image"
        view = document["bufferViews"][image["bufferView"]]
        assert view.get("buffer", 0) == 0
        offset, length = view.get("byteOffset", 0), view["byteLength"]
        payload = binary[offset:offset+length]
        assert len(payload) == length and payload
        mime = image.get("mimeType")
        if mime == "image/png":
            assert payload[:8] == b"\x89PNG\r\n\x1a\n"
            width, height = struct.unpack_from(">II", payload, 16)
        elif mime == "image/jpeg":
            assert payload[:2] == b"\xff\xd8"
            width = height = None
        else:
            raise AssertionError("Unexpected embedded texture format: "+str(mime))
        images.append({"index": index, "name": image.get("name"), "mimeType": mime,
                       "bytes": length, "width": width, "height": height,
                       "sha256": hashlib.sha256(payload).hexdigest()})
    materials = []
    used_images = set()
    for index, material in enumerate(document.get("materials", [])):
        pbr = material.get("pbrMetallicRoughness", {})
        slots = {}
        for slot, value in (("baseColor", pbr.get("baseColorTexture")),
                            ("metallicRoughness", pbr.get("metallicRoughnessTexture")),
                            ("normal", material.get("normalTexture")),
                            ("occlusion", material.get("occlusionTexture")),
                            ("emissive", material.get("emissiveTexture"))):
            if value is None:
                continue
            texture = document["textures"][value["index"]]
            image_index = texture["source"]
            assert 0 <= image_index < len(images)
            used_images.add(image_index)
            slots[slot] = {"texture_index": value["index"], "image_index": image_index,
                           "uv_set": value.get("texCoord", 0),
                           "colorspace_by_glTF_semantics": "sRGB" if slot in ("baseColor", "emissive") else "linear data"}
            if slot == "normal":
                slots[slot]["scale"] = value.get("scale", 1.0)
                slots[slot]["direction"] = "tangent-space +Y (OpenGL / glTF2 convention)"
        materials.append({"index": index, "name": material.get("name"), "texture_slots": slots,
                          "metallic_factor": pbr.get("metallicFactor", 1.0),
                          "roughness_factor": pbr.get("roughnessFactor", 1.0),
                          "base_color_factor": pbr.get("baseColorFactor", [1, 1, 1, 1]),
                          "alpha_mode": material.get("alphaMode", "OPAQUE"),
                          "alpha_cutoff": material.get("alphaCutoff", 0.5),
                          "double_sided": material.get("doubleSided", False),
                          "emissive_factor": material.get("emissiveFactor", [0, 0, 0]),
                          "extensions": material.get("extensions", {})})
    primitives = [p for mesh in document.get("meshes", []) for p in mesh.get("primitives", [])]
    assert primitives and materials and images, "Textured PBR sample is incomplete"
    assert all("POSITION" in p["attributes"] and "NORMAL" in p["attributes"] for p in primitives)
    textured = []
    for p in primitives:
        mi = p.get("material")
        if mi is not None and materials[mi]["texture_slots"]:
            for slot in materials[mi]["texture_slots"].values():
                assert "TEXCOORD_"+str(slot["uv_set"]) in p["attributes"], "Texture has no exported UV set"
            textured.append(p)
    assert textured, "No actual textured primitive exported"
    def accessor(index):
        a=document['accessors'][index];view=document['bufferViews'][a['bufferView']];width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']];dtype=np.dtype({5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}[a['componentType']]);return np.ndarray((a['count'],width),dtype=dtype,buffer=binary,offset=view.get('byteOffset',0)+a.get('byteOffset',0),strides=(view.get('byteStride',dtype.itemsize*width),dtype.itemsize))
    normal_count=normal_bad=0
    for primitive in primitives:
        xyz=accessor(primitive['attributes']['POSITION']);normal=accessor(primitive['attributes']['NORMAL']);assert np.isfinite(xyz).all() and np.isfinite(normal).all();normal_count+=len(normal);normal_bad+=int((abs(np.linalg.norm(normal.astype(float),axis=1)-1)>.002).sum())
    assert normal_bad==0,'Actual exported NORMAL accessor is not unit length'
    return {"material_count": len(materials), "materials": materials,
            "embedded_image_count": len(images), "embedded_images": images,
            "used_embedded_images": len(used_images), "primitive_count": len(primitives),
            "textured_primitive_count": len(textured),
            "extensions_used": document.get("extensionsUsed", []),
            "samplers": document.get("samplers", []),
            "normal_map_convention": "glTF2 tangent-space +Y; no green-channel flip",
            "uv_and_vertex_normal_attributes_present": True,
            "actual_normal_accessor_vectors":normal_count,"actual_nonunit_normal_accessor_vectors":normal_bad,
            "missing_external_image_uris": 0}


def inspect_reimport(objects):
    meshes = [o for o in objects if o.type == "MESH"]
    assert meshes
    nonfinite = normal_nonfinite = bad_normals = averaged_bad = missing = vertex_count = triangles = 0
    for ob in meshes:
        data = ob.data
        xyz = np.empty(len(data.vertices)*3, np.float32)
        data.vertices.foreach_get("co", xyz)
        nonfinite += int((~np.isfinite(xyz)).sum())
        vertex_count += len(data.vertices)
        data.calc_loop_triangles()
        triangles += len(data.loop_triangles)
        averaged = np.empty(len(data.vertices)*3,np.float32);data.vertices.foreach_get('normal',averaged);averaged_bad+=int((abs(np.linalg.norm(averaged.reshape(-1,3),axis=1)-1)>.01).sum())
        # glTF imports custom split normals. Opposing roof/cornice faces may
        # cancel the derived averaged vertex normal, which is not the normal
        # used for rendering. Validate actual rendered corner normals instead.
        normals = np.empty(len(data.corner_normals)*3, np.float32)
        data.corner_normals.foreach_get("vector", normals)
        normal_nonfinite += int((~np.isfinite(normals)).sum())
        magnitude = np.linalg.norm(normals.reshape(-1, 3), axis=1)
        bad_normals += int(((magnitude < .99) | (magnitude > 1.01)).sum())
    inventory = material_inventory(meshes)
    all_images = {}
    for ob in meshes:
        for slot in ob.material_slots:
            mat = slot.material
            if mat and mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if node.type == "TEX_IMAGE" and node.image:
                        im = node.image
                        all_images[im.as_pointer()] = im
    for image in all_images.values():
        exists = bool(image.packed_file or image.packed_files)
        if not exists and image.filepath:
            exists = Path(bpy.path.abspath(image.filepath)).is_file()
        missing += int(not exists or image.size[0] <= 0 or image.size[1] <= 0)
    assert nonfinite == normal_nonfinite == bad_normals == missing == 0, (nonfinite, normal_nonfinite, bad_normals, missing)
    return {"actual_reimport": True, "mesh_objects": len(meshes), "vertices": vertex_count,
            "triangles": triangles, "nonfinite_vertices": nonfinite,
            "nonfinite_rendered_corner_normals": normal_nonfinite, "nonunit_rendered_corner_normals": bad_normals,
            "nonunit_averaged_vertex_normals_informational":averaged_bad,
            "normal_validation_basis":"Actual glTF NORMAL accessor and imported rendered split corner normals; derived averaged normals may cancel at opposing surfaces",
            "missing_textures": missing, "reimport_image_count": len(all_images),
            "reimport_material_count": len(inventory), "reimport_materials": inventory}


def export_samples(root, scene, cfg):
    root = Path(root)
    saved = Path(bpy.data.filepath)
    assert saved.is_file(), "Save/reopen the stage08 checkpoint before export QA"
    checkpoint_sha = sha(saved)
    assert bpy.context.window.scene == scene
    scene.view_layers[0].update()
    chosen = sample_objects(scene)
    results = {}
    original_scene = bpy.context.window.scene
    original_images = {im.as_pointer() for im in bpy.data.images}
    for category, sources in chosen.items():
        source_bounds = bounds(sources)
        origin = (source_bounds[0]+source_bounds[1])/2
        origin[2] = source_bounds[0][2]
        sample_scene = bpy.data.scenes.new("Stage08_export_QA_"+category)
        sample_scene.unit_settings.system = "METRIC"
        sample_scene.unit_settings.scale_length = 1.0
        copies = []
        reimport_scene = None
        try:
            bpy.context.window.scene = sample_scene
            fallback = []
            for source in sources:
                duplicate = source.copy()
                duplicate.data = source.data.copy()
                duplicate.parent = None
                duplicate.matrix_world = source.matrix_world.copy()
                duplicate.matrix_world.translation -= Vector(origin)
                duplicate.animation_data_clear()
                duplicate.name = "S8_"+category+"_"+source.name
                sample_scene.collection.objects.link(duplicate)
                duplicate.hide_render = False
                duplicate.hide_viewport = False
                duplicate.hide_select = False
                duplicate.hide_set(False)
                if uv_fallback(duplicate.data):
                    fallback.append(source.name)
                copies.append(duplicate)
            sample_scene.view_layers[0].update()
            for ob in sample_scene.objects:
                ob.select_set(False)
            for ob in copies:
                ob.select_set(True)
            bpy.context.view_layer.objects.active = copies[0]
            path = root/"outputs/stage08/glb"/(category+".glb")
            path.parent.mkdir(parents=True, exist_ok=True)
            kwargs = {"filepath": str(path), "export_format": "GLB", "use_selection": True,
                      "export_apply": True, "export_extras": True, "export_cameras": False,
                      "export_lights": False, "export_yup": True, "export_materials": "EXPORT",
                      "export_texcoords": True, "export_normals": True, "export_tangents": True,
                      "export_image_format": "AUTO"}
            result = bpy.ops.export_scene.gltf(**kwargs)
            assert result == {"FINISHED"} and path.is_file()
            from stage08_atlas import patch_glb_sampler
            patch_glb_sampler(path)
            document, binary = glb_document(path)
            graph = inspect_document(document, binary)
            assert any({"baseColor", "normal", "metallicRoughness"}.issubset(m["texture_slots"])
                       for m in graph["materials"]), "No complete texture-backed metallic-roughness material exported"
            if category == 'water':
                assert any('water' in str(m['name']).lower() and abs(m['extensions'].get('KHR_materials_ior',{}).get('ior',1.5)-1.333)<.0001 for m in graph['materials']),'Water sample must preserve the actual water shader and IOR1.333'
                graph['actual_water_material_semantics_verified']=True
            if category == "vegetation":
                leaves = [m for m in graph["materials"] if "leaf" in str(m["name"]).lower()]
                assert leaves and all(m["alpha_mode"] == "MASK" and m["double_sided"] for m in leaves), \
                    "Leaf transparency must export as double-sided MASK, not an opaque rectangle"
                graph["actual_leaf_mask_and_double_sided_verified"] = True
            reimport_scene = bpy.data.scenes.new("Stage08_reimport_QA_"+category)
            reimport_scene.unit_settings.system = "METRIC"
            reimport_scene.unit_settings.scale_length = 1.0
            bpy.context.window.scene = reimport_scene
            status = bpy.ops.import_scene.gltf(filepath=str(path))
            assert status == {"FINISHED"}
            reimport_scene.view_layers[0].update()
            imported = list(reimport_scene.objects)
            check = inspect_reimport(imported)
            imported_bounds = bounds([o for o in imported if o.type == "MESH"])
            expected = np.array(source_bounds)-origin
            observed = np.array(imported_bounds)
            bbox_error = float(np.max(np.abs(expected-observed)))
            assert bbox_error <= .02, (category, bbox_error)
            record = {
                "path": str(path.relative_to(root)), "sha256": sha(path), "bytes": path.stat().st_size,
                "actual_export": True, "source_objects": [o.name for o in sources],
                "source_stable_ids": sorted({str(o.get("stable_id", o.get("source_uid", o.get("landmark_id", "")))) for o in sources}),
                "temporary_rebase_city_origin_m": origin.tolist(),
                "source_bounds_city_m": np.array(source_bounds).tolist(),
                "reimport_bounds_local_m": observed.tolist(),
                "maximum_bbox_roundtrip_error_m": bbox_error,
                "bbox_error_meaning": "computation/export roundtrip only; not geographic source accuracy",
                "uv_fallback_source_objects": fallback,
                "saved_material_inventory": material_inventory(sources),
                "glb_document_check": graph,
                "glb_axes": "Y-up glTF metres; Blender importer restores Z-up",
                **check,
            }
            results[category] = record
            print("STAGE08_ACTUAL_GLB_EXPORT_REIMPORT", category, graph["material_count"], graph["embedded_image_count"], flush=True)
        finally:
            bpy.context.window.scene = original_scene
            for temporary in (reimport_scene, sample_scene):
                if temporary is not None and temporary.name in bpy.data.scenes:
                    for ob in list(temporary.objects):
                        data = ob.data if ob.type == "MESH" else None
                        bpy.data.objects.remove(ob, do_unlink=True)
                        if data is not None and data.users == 0:
                            bpy.data.meshes.remove(data)
                    bpy.data.scenes.remove(temporary)
            # Import may unpack embedded data to temporary images. Remove only
            # new unused images, never the original scene's PBR image datablocks.
            for image in list(bpy.data.images):
                if image.as_pointer() not in original_images and image.users == 0:
                    bpy.data.images.remove(image)
    assert set(results) == {"building", "road", "vegetation", "water", "landmark"}
    assert sha(saved) == checkpoint_sha, "Export QA must not rewrite the checkpoint"
    report = {"status": "passed", "saved_model_sha256": checkpoint_sha,
              "saved_model": str(saved.relative_to(root)), "samples": results,
              "actual_export_and_reimport_categories": 5,
              "original_city_geometry_or_saved_file_modified": False,
              "limitations": [
                  "glTF material graph and Blender re-import are checked here; browser screenshots are a separate actual check",
                  "Rasterization, transparency sorting, transmission, tone mapping, environment lighting and shadows differ across engines",
                  "glTF2 baseColor/emissive textures are sRGB, metallic-roughness/normal/AO are linear data by specification",
                  "Emission strength/transmission extensions require runtime support; unsupported viewers may ignore them",
                  "These five samples test material compatibility, not whole-city GLB streaming or runtime LOD",
                  "Source geometry remains approximate where inherited; export numerical agreement is not survey accuracy",
              ]}
    write(root, "work/reports/stage08/export_check.json", report)
    return report
