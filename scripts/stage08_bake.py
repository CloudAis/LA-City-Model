"""Actually bake one preserved procedural source material into glTF-ready maps.

Run in Blender, after the accepted stage07 checkpoint exists. This is an honest
single-material reference patch; it does not relabel original sampled textures
as Blender bakes and does not alter the preserved stage07 shader.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time

import bpy
import numpy as np


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2)+"\n")
    temporary.replace(path)


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def _png_check(image, path, kind):
    image.reload()
    image.colorspace_settings.name = "sRGB" if kind == "base_color" else "Non-Color"
    values = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(values)
    channels = len(values)//(image.size[0]*image.size[1])
    pixels = values.reshape(image.size[1], image.size[0], channels)[:, :, :3]
    require(tuple(image.size) == (1024, 1024), "Actual baked PNG dimensions differ")
    require(bool(np.isfinite(pixels).all()), "Nonfinite actual baked PNG pixels")
    require(float(pixels.max()) > .05, "Actual baked PNG is black")
    entry = {"path": str(path), "sha256": digest(path), "dimensions_px": list(image.size),
        "bytes": path.stat().st_size, "actual_reloaded_png": True,
        "colorspace": image.colorspace_settings.name, "finite": True,
        "pixel_min": float(pixels.min()), "pixel_max": float(pixels.max()),
        "rgb_channel_stddev": pixels.std(axis=(0, 1)).tolist()}
    if kind == "base_color":
        require(float(pixels.std()) > .002, "Baked brick base color lacks nonblank variation")
    elif kind == "normal":
        normals = pixels*2-1
        entry["tangent_normal_space"] = "OpenGL +Y; Blender bake normal_r=POS_X, normal_g=POS_Y, normal_b=POS_Z"
        entry["normal_z_min"] = float(normals[:, :, 2].min())
        entry["normal_xy_stddev"] = normals[:, :, :2].std(axis=(0, 1)).tolist()
        require(entry["normal_z_min"] > 0, "Baked tangent normal points below the patch")
        require(float(normals[:, :, :2].std()) > .0001, "Baked procedural bump unexpectedly flat")
    return entry


def bake_reference(root, source_scene="scenes/stage07_final.blend"):
    """Bake source brick on a standalone UV patch and restore caller scene.

    This function may be imported by a factory-startup worker. It requires the
    real phase07 acceptance and exact source-model SHA before any bake occurs.
    """
    root = Path(root).resolve()
    source_path = root/source_scene
    acceptance_path = root/"outputs/stage07_final_acceptance.json"
    require(acceptance_path.is_file(), "Stage07 must be accepted before stage08 bake")
    acceptance = json.loads(acceptance_path.read_text())
    require(acceptance.get("stage_gate_passed") is True, "Stage07 gate has not passed")
    require(source_path.is_file(), "Accepted source scene does not exist")
    source_sha = digest(source_path)
    require(source_sha == acceptance.get("final_model_sha256"), "Source scene changed after stage07 acceptance")

    source_name = "LA07R2_brick"
    target_folder = root/"assets/textures/stage08/bakes"
    report_path = root/"work/reports/stage08/bake_check.json"
    target_folder.mkdir(parents=True, exist_ok=True)
    consumed = {"source_scene": source_scene, "source_scene_sha256": source_sha,
        "source_material": source_name, "script_sha256": digest(__file__)}
    # Do not overwrite an editable bake or previously registered texture.
    if report_path.exists():
        previous = json.loads(report_path.read_text())
        same = previous.get("inputs") == consumed and previous.get("status") == "passed"
        require(same, "Existing bake input version differs; preserve it before rebuilding")
        for item in previous["outputs"].values():
            require((root/item["path"]).is_file() and digest(root/item["path"]) == item["sha256"], "Existing bake changed: "+item["path"])
        library = root/previous["compatible_library"]["path"]
        require(library.is_file() and digest(library) == previous["compatible_library"]["sha256"], "Existing baked material library changed")
        print("STAGE08_ACTUAL_BAKE_CACHE_VERIFIED", flush=True)
        return previous

    # Append only the material and its dependencies, not the multi-GB city.
    with bpy.data.libraries.load(str(source_path), link=False) as (src, dst):
        require(source_name in src.materials, "Preserved procedural material is unavailable")
        dst.materials = [source_name]
    source_material = dst.materials[0]
    require(source_material is not None and source_material.use_nodes, "Source material lacks editable nodes")
    require(any(node.bl_idname == "ShaderNodeTexBrick" for node in source_material.node_tree.nodes), "Expected actual procedural brick node missing")
    source_material.use_fake_user = True
    source_material["stage08_source_role"] = "Preserved editable procedural shader, appended without editing source file"
    procedural = source_material.copy()
    procedural.name = "LA08_Bake_Working_Copy_Original_Procedural_Brick"

    previous_scene = bpy.context.window.scene
    work_scene = bpy.data.scenes.new("LA08_Actual_Bake_Calibration_Temporary")
    bpy.context.window.scene = work_scene
    try:
        work_scene.render.engine = "CYCLES"
        work_scene.cycles.device = "CPU"
        work_scene.cycles.samples = 1
        work_scene.render.threads_mode = "FIXED"
        work_scene.render.threads = 4
        work_scene.unit_settings.system = "METRIC"
        work_scene.unit_settings.scale_length = 1
        work_scene.render.bake.margin = 4
        work_scene.render.bake.use_selected_to_active = False
        work_scene.render.bake.use_clear = True
        work_scene.render.bake.normal_space = "TANGENT"
        work_scene.render.bake.normal_r = "POS_X"
        work_scene.render.bake.normal_g = "POS_Y"
        work_scene.render.bake.normal_b = "POS_Z"

        # Source node uses Object.X+Object.Y for brick U and Object.Z for V.
        # This XZ patch reproduces that actual source projection at meter scale.
        data = bpy.data.meshes.new("LA08_Bake_Patch_3_84m_by_1_20m")
        data.from_pydata([(0, 0, 0), (3.84, 0, 0), (3.84, 0, 1.2), (0, 0, 1.2)], [], [(0, 1, 2, 3)])
        data.materials.append(procedural)
        uv = data.uv_layers.new(name="BakedPatchUV")
        for loop, point in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            loop.uv = point
        obj = bpy.data.objects.new("LA08_Baked_Brick_Reference_Patch", data)
        work_scene.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        outputs = {}
        baked_images = {}
        stages = []
        for kind, bake_type in [("base_color", "DIFFUSE"), ("normal", "NORMAL"), ("roughness", "EMIT")]:
            material = procedural
            if kind == "roughness":
                material = procedural.copy()
                material.name = "LA08_Temporary_Roughness_Emission_Clone"
                tree = material.node_tree
                bsdf = next(node for node in tree.nodes if node.bl_idname == "ShaderNodeBsdfPrincipled")
                output = next(node for node in tree.nodes if node.bl_idname == "ShaderNodeOutputMaterial" and node.is_active_output)
                emission = tree.nodes.new("ShaderNodeEmission")
                emission.inputs["Strength"].default_value = 1
                if bsdf.inputs["Roughness"].is_linked:
                    tree.links.new(bsdf.inputs["Roughness"].links[0].from_socket, emission.inputs["Color"])
                else:
                    roughness = float(bsdf.inputs["Roughness"].default_value)
                    emission.inputs["Color"].default_value = (roughness, roughness, roughness, 1)
                tree.links.new(emission.outputs[0], output.inputs["Surface"])
            obj.data.materials[0] = material
            image = bpy.data.images.new("LA08_Actual_Baked_Brick_"+kind, width=1024, height=1024, alpha=False, float_buffer=False)
            image.colorspace_settings.name = "sRGB" if kind == "base_color" else "Non-Color"
            tree = material.node_tree
            for node in tree.nodes:
                node.select = False
            target = tree.nodes.new("ShaderNodeTexImage")
            target.name = "Actual Bake Target "+kind
            target.image = image
            target.select = True
            tree.nodes.active = target
            work_scene.render.bake.use_pass_direct = False
            work_scene.render.bake.use_pass_indirect = False
            work_scene.render.bake.use_pass_color = True
            start = time.monotonic()
            result = bpy.ops.object.bake(type=bake_type)
            require("FINISHED" in result, "Actual bpy bake did not finish: "+kind)
            elapsed = time.monotonic()-start
            path = target_folder/("brick_reference_"+kind+".png")
            require(not path.exists(), "Unregistered existing bake would be overwritten: "+str(path))
            image.filepath_raw = str(path)
            image.file_format = "PNG"
            image.save()
            info = _png_check(image, path, kind)
            info["path"] = str(path.relative_to(root))
            info.update(actual_bpy_object_bake=True, bake_type=bake_type, actual_duration_seconds=elapsed)
            outputs[kind] = info
            stages.append({"kind": kind, "type": bake_type, "result": list(result), "seconds": elapsed})
            baked_images[kind] = image
            print("ACTUAL_STAGE08_BAKE", kind, bake_type, "FINISHED", elapsed, flush=True)
            obj.data.materials[0] = procedural
            tree.nodes.remove(target)
            if material != procedural:
                bpy.data.materials.remove(material)

        compatible = bpy.data.materials.new("LA08_Actual_Baked_Procedural_Brick_Compatible")
        compatible.use_nodes = True
        compatible["source_material"] = source_name
        compatible["source_blend"] = source_scene
        compatible["texture_scope"] = "Single original procedural shader patch, not a seamless survey texture"
        tree = compatible.node_tree
        bsdf = tree.nodes.get("Principled BSDF")
        bsdf.inputs["Metallic"].default_value = 0
        texcoord = tree.nodes.new("ShaderNodeTexCoord")
        for kind, image in baked_images.items():
            tex = tree.nodes.new("ShaderNodeTexImage")
            tex.name = "Baked "+kind
            tex.image = image
            tex.extension = "EXTEND"
            tex.interpolation = "Linear"
            tree.links.new(texcoord.outputs["UV"], tex.inputs["Vector"])
            if kind == "normal":
                normal = tree.nodes.new("ShaderNodeNormalMap")
                normal.space = "TANGENT"
                normal.inputs["Strength"].default_value = 1
                tree.links.new(tex.outputs["Color"], normal.inputs["Color"])
                tree.links.new(normal.outputs["Normal"], bsdf.inputs["Normal"])
            else:
                tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color" if kind == "base_color" else "Roughness"])
        obj.data.materials[0] = compatible
        obj["actual_bake_scope"] = "3.84m x1.20m vertical source-projection calibration patch"
        library = root/"assets/materials/stage08/baked_brick.blend"
        library.parent.mkdir(parents=True, exist_ok=True)
        require(not library.exists(), "Unregistered baked library already exists")
        # Keep absolute source image paths while writing. Blender remaps them
        # relative to the output library, not the caller's current main file.
        bpy.data.libraries.write(str(library), {obj, compatible, source_material}, fake_user=True, compress=True, path_remap="RELATIVE")
        report = {"status": "passed", "stage": 8, "actual_bake": True,
            "inputs": consumed, "source_material": source_name, "source_blend_sha256": source_sha,
            "source_scene_sha256": source_sha,
            "source_shader_preserved_editable": True, "source_file_modified": False,
            "actual_cycles_cpu": True, "samples": 1, "resolution_px": [1024, 1024],
            "bake_patch_dimensions_m": [3.84, 1.2], "bake_patch_plane": "XZ, normal -Y, U +X, V +Z",
            "uv": "0..1 physical patch; source Object X+Y/Z projection sampled without changing source node graph",
            "diffuse_pass": "COLOR only; direct/indirect lighting disabled",
            "normal_convention": "Tangent OpenGL +Y, XYZ positive bake swizzles",
            "roughness_method": "Actual EMIT bake from clone of original Roughness socket; no color transform on output PNG",
            "operations": stages, "outputs": outputs, "files": list(outputs.values()),
            "compatible_library": {"path": str(library.relative_to(root)), "sha256": digest(library)},
            "limits": ["Only this preserved brick material was actually Blender-baked; the main14-material library remains independently original generated PBR maps.",
                       "Source procedural noise is not periodic. This standalone calibration patch uses EXTEND addressing and is not asserted to be seamless when repeated.",
                       "No lighting or geometry AO is baked; no architectural dimensions are inferred from this patch.",
                       "Saved compatible object-library append and GLB round-trip remain separate checks."]}
        require(digest(source_path) == source_sha, "Preserved source changed unexpectedly")
        write(report_path, report)
        print("STAGE08_ACTUAL_PROCEDURAL_BAKE_PASSED", flush=True)
        return report
    finally:
        bpy.context.window.scene = previous_scene
        bpy.data.scenes.remove(work_scene)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/workspace/Base")
    parser.add_argument("--source-scene", default="scenes/stage07_final.blend")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    bake_reference(args.root, args.source_scene)
