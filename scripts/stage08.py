"""Stage08 PBR/lighting coordinator, gated on actually accepted stage07 geometry."""
from pathlib import Path
import argparse
import ast
import datetime
import hashlib
import io
import json
import shutil
import struct
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPORTS = "work/reports/stage08"
MANIFEST = "outputs/stage08_city_medium.manifest.json"
ACCEPTANCE = "outputs/stage08_city_medium_acceptance.json"
REGISTRY = "assets/materials/stage08/registry.json"
LIBRARY = "assets/materials/stage08/material_library.blend"
CATEGORIES = ("building", "road", "vegetation", "water", "landmark")
ACCEPTED = "accepted_with_documented_approximations"


class ReviewPending(RuntimeError):
    pass


def read(root, path):
    return json.loads((Path(root)/path).read_text())


def write(root, path, value):
    path = Path(root)/path
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix+".tmp")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")
    pending.replace(path)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def context(root):
    for path in ("PROJECT_SPEC.md", "STATUS.md"):
        require(bool((Path(root)/path).read_text().strip()), "Missing project contract: "+path)


def supported(region, quality):
    if (region, quality) != ("city", "medium"):
        print("未实现 / NOT IMPLEMENTED: stage08 supports city/medium only", flush=True)
        return False
    return True


def source_gate(root):
    from stage07_final import check
    if check(Path(root), "city", "medium") != 0:
        print("STAGE08_REVIEW_PENDING: Stage07 actual visual acceptance is required before any stage08 scene build; exit4",flush=True)
        return False
    return True


def fp(items):
    return hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()


def inputs(root=ROOT):
    root = Path(root)
    cfg = read(root, "config/stage08.json")
    paths = {root/p for p in (cfg["source_scene"], "scenes/stage07_city_medium.blend",
        "outputs/stage07_final.manifest.json", "outputs/stage07_final_acceptance.json",
        "config/stage08.json", "config/stage08_materials.json", "config/stage08_lighting.json", "config/stage08_atlas.json",
        "config/stage06.json", "config/stage07_final.json", "config/stage07_final_views.json",
        "data/processed/origin.json", "requirements.lock", REGISTRY)}
    paths.update(root/item["path"] for item in read(root,REGISTRY)["files"])
    atlas=read(root,"assets/materials/stage08/atlas_registry.json")
    paths.add(root/"assets/materials/stage08/atlas_registry.json")
    paths.update(root/item["path"] for item in atlas["files"])
    # Later routing/status updates do not change this stage's frozen inputs.
    scripts = set((root/"scripts").glob("stage08*.py"))
    pending = list(scripts)
    while pending:
        path = pending.pop()
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            modules = [node.module] if isinstance(node, ast.ImportFrom) else (
                [a.name for a in node.names] if isinstance(node, ast.Import) else [])
            for module in modules:
                candidate = root/"scripts"/((module or "").split(".")[0]+".py")
                if candidate.is_file() and candidate not in scripts:
                    scripts.add(candidate)
                    pending.append(candidate)
    paths.update(scripts)
    for path in paths:
        require(path.is_file(), "Missing reproducible stage08 input: "+str(path.relative_to(root)))
    return [{"path":str(p.relative_to(root)), "sha256":digest(p)} for p in sorted(paths)]


def command(root, args, label):
    path = Path(root)/"work/logs/stage08"/label
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as log:
        log.write("\n"+json.dumps(list(map(str,args)))+"\n")
        log.flush()
        result = subprocess.run(list(map(str,args)), cwd=root, stdout=log, stderr=subprocess.STDOUT)
        log.write("\nEXIT_CODE="+str(result.returncode)+"\n")
    require(result.returncode == 0, "Actual stage08 command failed: "+str(path))
    print(label+"_OK", flush=True)


def textures(root=ROOT):
    """Check actual pixels and registered hashes; source images are original art."""
    root = Path(root)
    registry = read(root, REGISTRY)
    cfg = read(root, "config/stage08_materials.json")
    require(registry["status"] == "passed_generated_texture_checks", "Texture generation checks have not passed")
    for path, expected in registry["inputs"].items():
        require(digest(root/path) == expected, "Texture source/config changed: "+path)
    require(set(registry["materials"]) == set(cfg["materials"]), "PBR material registry is incomplete")
    files = {item["path"]:item for item in registry["files"]}
    expected = set()
    from PIL import Image
    for material, record in registry["materials"].items():
        for level, size in cfg["dimensions_px"].items():
            for role in ("base_color", "normal", "orm"):
                path = record["maps"][level][role]
                expected.add(path)
                require(path in files, "Unregistered material image: "+path)
                item = files[path]
                require(digest(root/path) == item["sha256"], "Material image changed: "+path)
                require(item["color_space"] == ("sRGB" if role == "base_color" else "Non-Color"), "Incorrect material color-space contract: "+path)
                with Image.open(root/path) as image:
                    require(image.size == (size,size) and image.format == "PNG", "PBR texture dimensions/format mismatch: "+path)
                    image.verify()
    require(set(files) == expected and len(files) == len(cfg["materials"])*len(cfg["dimensions_px"])*3, "Texture registry has duplicate or missing map files")
    total = sum((root/p).stat().st_size for p in expected)
    require(total <= cfg["texture_budget_mib"]*1024**2, "Compressed texture-file budget exceeded")
    return {"status":"passed", "materials":len(cfg["materials"]), "images":len(expected), "compressed_texture_bytes":total,
            "budget_meaning":"file/cache bytes; not measured GPU texture memory", "registry_sha256":digest(root/REGISTRY)}


def bake_check(root=ROOT):
    root=Path(root)
    report=read(root,REPORTS+"/bake_check.json")
    cfg=read(root,"config/stage08.json")
    require(report.get("status")=="passed" and report.get("actual_bake") is True and report.get("actual_cycles_cpu") is True,"Actual procedural-source Blender bake has not passed")
    require(report.get("source_file_modified") is False,"Reference bake altered the preserved source")
    require(report.get("source_scene_sha256")==digest(root/cfg["source_scene"]),"Reference bake uses a different accepted source scene")
    require(report["inputs"]["script_sha256"]==digest(root/"scripts/stage08_bake.py"),"Reference bake helper changed after actual execution")
    require(set(report["outputs"])=={"base_color","normal","roughness"},"Actual reference bake map set incomplete")
    from PIL import Image
    require(len(report["files"])==3,"Expected three actual reference bake maps")
    require({item["path"] for item in report["files"]}=={item["path"] for item in report["outputs"].values()},"Actual bake artifact/output lists differ")
    for role,item in report["outputs"].items():
        require(item.get("actual_reloaded_png") is True and item.get("actual_bpy_object_bake") is True,"PNG is not an actual Blender bake: "+role)
        require(item["colorspace"]==("sRGB" if role=="base_color" else "Non-Color"),"Baked map color-space mismatch")
        require(digest(root/item["path"])==item["sha256"],"Actual baked map changed: "+role)
        with Image.open(root/item["path"]) as actual:
            require(list(actual.size)==item["dimensions_px"] and actual.format=="PNG","Baked map dimensions/format mismatch")
            actual.verify()
    lib=report["compatible_library"]
    require((root/lib["path"]).is_file() and digest(root/lib["path"])==lib["sha256"],"Actual baked compatible library missing/stale")
    return report


def library(root=ROOT):
    """Actually append the material library in a fresh Blender process."""
    root = Path(root)
    require((root/LIBRARY).is_file(), "Missing editable material library")
    expected = digest(root/LIBRARY)
    specs=[(LIBRARY,14)]
    if (root/REPORTS/"bake_check.json").exists():
        baked=bake_check(root)
        specs.append((baked["compatible_library"]["path"],1))
    library_hashes={path:digest(root/path) for path,_ in specs}
    report = root/REPORTS/"library_check.json"
    if report.exists():
        old = json.loads(report.read_text())
        if old.get("status") == "passed" and old.get("library_sha256") == expected and old.get("library_sha256_by_path")==library_hashes and old.get("actual_independent_material_append") is True:
            return old
    code = "\n".join([
        "import bpy,json,os",
        "from pathlib import Path",
        "root=Path("+repr(str(root))+")",
        "records=[]",
        "for relative,minimum in "+repr(specs)+":",
        " with bpy.data.libraries.load(str(root/relative),link=False) as (src,dst): dst.materials=list(src.materials)",
        " materials=[m for m in dst.materials if m is not None]",
        " assert len(materials)>=minimum and all(m.use_nodes for m in materials)",
        " missing=[];images=set()",
        " for m in materials:",
        "  for node in m.node_tree.nodes:",
        "   if node.type=='TEX_IMAGE' and node.image:",
        "    image=node.image;images.add(image.name)",
        "    if not image.packed_file and not os.path.isfile(bpy.path.abspath(image.filepath,library=image.library)): missing.append(image.filepath)",
        " assert images and not missing, missing",
        " records.append({'path':relative,'materials':len(materials),'images':len(images),'missing_images':missing,'actual_independent_material_append':True})",
        "report={'status':'passed','actual_independent_material_append':True,'library_sha256':"+repr(expected)+",'library_sha256_by_path':"+repr(library_hashes)+",'libraries':records,'saved_city_unchanged':True}",
        "(root/"+repr(REPORTS+"/library_check.json")+").write_text(json.dumps(report,indent=2)+'\\n')",
        "print('STAGE08_MATERIAL_LIBRARY_APPENDED',len(materials),flush=True)",
    ])
    report.parent.mkdir(parents=True, exist_ok=True)
    command(root, [shutil.which("blender") or "blender", "--background", "--threads", "4", "--factory-startup", "--python-exit-code", "1", "--python-expr", code], "material_library_append.log")
    return json.loads(report.read_text())


def glb_check(path, category):
    """Inspect the exported binary itself; actual reimport/browser remain separate."""
    data = Path(path).read_bytes()
    require(len(data) >= 20, "Truncated GLB: "+str(path))
    magic, version, length = struct.unpack_from("<4sII", data)
    require(magic == b"glTF" and version == 2 and length == len(data), "Invalid GLB container: "+str(path))
    offset = 12
    document = None
    binary = b""
    while offset < len(data):
        require(offset+8 <= len(data), "Truncated GLB chunk")
        length, kind = struct.unpack_from("<I4s", data, offset)
        offset += 8
        require(offset+length <= len(data), "GLB chunk outside file")
        chunk = data[offset:offset+length]
        if kind == b"JSON":
            document = json.loads(chunk.rstrip(b" \t\r\n\x00"))
        elif kind == b"BIN\x00":
            binary = chunk
        offset += length
    require(document is not None and document.get("meshes"), "GLB contains no actual mesh")
    require(all(not buffer.get("uri") for buffer in document.get("buffers", [])), "GLB depends on external buffer")
    from PIL import Image
    blue_maxima = {}
    for image_index, image in enumerate(document.get("images", [])):
        require("bufferView" in image and not image.get("uri"), "GLB texture is not embedded")
        view = document["bufferViews"][image["bufferView"]]
        start = view.get("byteOffset",0)
        payload = binary[start:start+view["byteLength"]]
        require(len(payload) == view["byteLength"], "Embedded texture outside binary chunk")
        with Image.open(io.BytesIO(payload)) as actual:
            actual.load()
            blue_maxima[image_index] = actual.convert("RGB").getextrema()[2][1]/255
    materials = document.get("materials", [])
    mapped = [m for m in materials if "baseColorTexture" in m.get("pbrMetallicRoughness",{})
              and "metallicRoughnessTexture" in m.get("pbrMetallicRoughness",{}) and "normalTexture" in m]
    require(mapped and document.get("images"), "Actual exported sample lacks complete image-backed base/normal/ORM PBR: "+category)
    if category == "vegetation":
        require(any(m.get("alphaMode") == "MASK" and m.get("doubleSided") is True for m in materials), "Vegetation GLB lacks alpha-tested double-sided foliage")
    if category == 'water':
        require(any('water' in m.get('name','').lower() and abs(m.get('extensions',{}).get('KHR_materials_ior',{}).get('ior',1.5)-1.333)<.0001 for m in materials),'Water sample lost its water material or IOR1.333')
    for m in materials:
        if category == "water" or any(token in m.get("name", "").lower() for token in ("glass", "water")):
            pbr = m.get("pbrMetallicRoughness",{})
            maximum_metallic = pbr.get("metallicFactor",1)
            if "metallicRoughnessTexture" in pbr:
                texture = document["textures"][pbr["metallicRoughnessTexture"]["index"]]
                maximum_metallic *= blue_maxima[texture["source"]]
            require(maximum_metallic <= 1e-6, "Glass/water exported as metallic surface")
    return {"status":"passed", "meshes":len(document["meshes"]), "materials":len(materials), "embedded_images":len(document.get("images",[])),
            "mapped_pbr_materials":len(mapped), "extensions_used":document.get("extensionsUsed",[]), "bytes":len(data)}


def evidence(root=ROOT):
    root = Path(root)
    cfg = read(root, "config/stage08.json")
    needed = [cfg["output_scene"], LIBRARY, REGISTRY, REPORTS+"/scene_check.json", REPORTS+"/renders.json",REPORTS+"/bake_check.json",
              REPORTS+"/export_check.json", REPORTS+"/browser_check.json", REPORTS+"/visual_inspection.json"]
    missing = [p for p in needed if not (root/p).is_file()]
    if missing:
        raise ReviewPending("Missing actual stage08 evidence: "+", ".join(missing))
    scene = read(root, REPORTS+"/scene_check.json")
    renders = read(root, REPORTS+"/renders.json")
    exported = read(root, REPORTS+"/export_check.json")
    browser = read(root, REPORTS+"/browser_check.json")
    visual = read(root, REPORTS+"/visual_inspection.json")
    lighting = read(root, "config/stage08_lighting.json")
    model_hash = digest(root/cfg["output_scene"])
    require(scene["status"] == "passed" and scene.get("saved_checkpoint_reopened_independently") is True, "Stage08 independent reopen has not passed")
    require(scene.get("saved_model_sha256") == model_hash and scene["units_metres_per_blender_unit"] == 1, "Stage08 scene check stale or not metre scale")
    require(scene["nonfinite_vertices"] == 0 and not scene["missing_images"] and scene["source_geometry_unchanged"] is True, "Stage08 geometry/image preservation check failed")
    for field in ("pbr_material_checks_passed", "uv_checks_passed", "color_space_checks_passed"):
        require(scene.get(field) is True, "Actual Blender PBR check missing: "+field)
    atlas_check=read(root,REPORTS+"/atlas_check.json")
    require(scene.get("atlas_checks_passed") is True and atlas_check.get("status")=="passed" and atlas_check.get("saved_model_sha256")==model_hash,"Actual furniture atlas check missing/stale")
    semantics=read(root,REPORTS+'/material_semantics.json')
    require(semantics.get('status')=='passed' and semantics.get('independent_saved_model_check') is True and semantics.get('saved_model_sha256')==model_hash and semantics.get('original_seat_palette_retained') is True,'Actual water/seat material semantics have not passed')
    require(all(item["exists"] and Path(item["path"]).is_file() for item in scene["libraries"]), "Required linked geometry source unavailable")
    expected_libraries = {(root/cfg["source_scene"]).resolve(), (root/"scenes/stage07_city_medium.blend").resolve()}
    require(expected_libraries <= {Path(item["path"]).resolve() for item in scene["libraries"]}, "Stage08 saved scene omits its two required geometry libraries")
    if visual.get("status") != ACCEPTED or visual.get("stage_gate_passed") is not True:
        raise ReviewPending("Stage08 actual final images have not been explicitly accepted")
    require(visual.get("final_saved_model_sha256") == model_hash, "Stage08 visual review refers to a different model")
    names = set(lighting["presets"])
    require(len(names) == 4 and renders["status"] == "actual_render_completed" and set(renders["images"]) == names, "Four actual lighting renders are required")
    require(renders.get("saved_scene_sha256") == model_hash and Path(renders["saved_scene"]).resolve() == (root/cfg["output_scene"]).resolve(), "Lighting render evidence refers to a different saved model")
    require(renders.get("lighting_config_sha256")==digest(root/"config/stage08_lighting.json"),"Actual lighting render configuration changed")
    require(renders.get("build_config_sha256")==digest(root/"config/stage08.json"),"Actual render build/quality configuration changed")
    view = cfg["camera"]
    if "stage07_view" in view:
        view = read(root, "config/stage07_final_views.json")[view["stage07_view"]]
    inspected = {item["path"]:item for item in visual["images"]}
    require(visual.get("actual_images_viewed") == 4 and len(inspected) == 4, "Four final lighting PNGs must actually be inspected")
    from PIL import Image, ImageStat
    image_checks = {}
    for name, row in renders["images"].items():
        require(row.get("actual_cpu_cycles") is True and row.get("lighting_preset") == name, "Missing actual lighting render: "+name)
        preset=lighting["presets"][name]
        require(row.get("local_datetime")==preset["solar"]["local_datetime"],"Rendered lighting datetime changed: "+name)
        require(row.get("sun_altitude_deg")==preset["solar"]["altitude_geometric_deg"] and row.get("sun_grid_azimuth_deg")==preset["azimuth_grid_north_clockwise_deg"],"Rendered solar position changed: "+name)
        require(abs(row.get("exposure",float("inf"))-preset["exposure_stops"])<1e-6,"Rendered exposure changed: "+name)
        for field in ("position_m", "target_m", "lens_mm", "ortho_scale_m"):
            require(row.get(field) == view.get(field), "Lighting comparisons must use their fixed configured camera: "+field)
        path = row["output"]
        require(path == "work/previews/stage08/"+name+".png", "Draft substituted for final lighting render")
        require(path in inspected and inspected[path].get("actual_view_image_inspection") is True, "Lighting image not actually opened: "+path)
        require(digest(root/path) == inspected[path]["sha256"], "Lighting image changed after inspection")
        with Image.open(root/path) as actual:
            require(actual.format == "PNG" and actual.size == (cfg["render"]["width"],cfg["render"]["height"]), "Lighting PNG format/size mismatch")
            deviation = ImageStat.Stat(actual.convert("RGB")).stddev
            require(max(deviation) > 5, "Lighting render nearly blank: "+name)
        image_checks[name] = {"path":path, "sha256":inspected[path]["sha256"], "rgb_stddev":deviation}
    require(set(inspected) == {r["output"] for r in renders["images"].values()}, "Inspection/render image sets differ")
    require(exported["status"] == "passed" and exported.get("saved_model_sha256") == model_hash and set(exported["samples"]) == set(CATEGORIES), "Actual export/reimport sample set is incomplete or stale")
    sample_hashes = {}
    glb_checks = {}
    for category in CATEGORIES:
        row = exported["samples"][category]
        path = "outputs/stage08/glb/"+category+".glb"
        require(row["path"] == path and row.get("actual_export") is True and row.get("actual_reimport") is True, "Sample not actually exported/reimported: "+category)
        require(row["missing_textures"] == 0 and row["nonfinite_vertices"] == 0 and digest(root/path) == row["sha256"], "Exported sample invalid/stale: "+category)
        sample_hashes[category] = row["sha256"]
        glb_checks[category] = glb_check(root/path, category)
    require(browser["status"] == "passed" and browser.get("actual_browser_executed") is True and browser.get("actual_webgl_render") is True, "Actual WebGL/browser compatibility has not passed")
    require(browser.get("sample_sha256") == sample_hashes and not browser.get("console_errors") and not browser.get("page_errors"), "Browser check refers to different samples or contains errors")
    screenshot = browser["screenshot"]
    require((root/screenshot["path"]).is_file() and digest(root/screenshot["path"]) == screenshot["sha256"], "Actual browser screenshot missing/stale")
    with Image.open(root/screenshot["path"]) as actual:
        require(max(ImageStat.Stat(actual.convert("RGB")).stddev) > 5, "Actual browser screenshot nearly blank")
    require(lighting["validation"]["status"] == "passed" and lighting["validation"]["actual_execution"] is True, "Actual solar/time/projection checks missing")
    texture_checks = textures(root)
    bake_check(root)
    return cfg, scene, visual, image_checks, glb_checks, screenshot, texture_checks


def register(root=ROOT):
    root = Path(root)
    context(root)
    if not source_gate(root):
        return 4
    if (root/MANIFEST).exists():
        verify(root)
        return 0
    cfg, scene, visual, images, glbs, screenshot, texture_checks = evidence(root)
    baked=bake_check(root)
    library_check = library(root)
    require(not (root/ACCEPTANCE).exists(), "Unregistered stage08 acceptance exists; preserve it before replacement")
    now = datetime.datetime.now(ZoneInfo("Asia/Singapore")).isoformat()
    limits = ["Original synthetic PBR textures approximate surface appearance; they are not photographed or measured materials for every real building.",
        "Inherited stage07 heights, mixed source dates, unmeasured façades and inferred site interfaces remain; material/light validation does not certify architectural survey accuracy.",
        "Solar direction uses an analytical date/time/location model; sky, weather, surface response and artificial light intensities are authored, not calibrated measurements.",
        "AO in ORM red is1 and is not baked geometric occlusion. Height detail is normal mapping, not changed city/terrain geometry.",
        "Transmission and foliage alpha depend on renderer support; five actual sample exports and this browser test are demonstrated, not all-device or whole-city certification.",
        "CPU rendering and browser/software-WebGL do not establish hardware GPU availability, VRAM or real-time frame-rate capacity.",
        "Both scenes/stage07_final.blend and scenes/stage07_city_medium.blend must accompany the stage08 scene. Linked original geometry is edited in its source or made local.",
        "Stage08 exports are five material compatibility samples. Whole-city tiled GLB streaming and interactive LOD remain separate later work.",
        *visual.get("limits", []),*baked.get("limits", [])]
    accepted = {"stage":8, "status":ACCEPTED, "stage_gate_passed":True, "region":"city", "quality":"medium",
        "model":cfg["output_scene"], "source_stage07_manifest":"outputs/stage07_final.manifest.json",
        "model_sha256":visual["final_saved_model_sha256"], "required_libraries":[cfg["source_scene"],"scenes/stage07_city_medium.blend"],
        "material_library":LIBRARY, "material_registry":REGISTRY, "texture_checks":texture_checks,
        "actual_reference_blender_bake":REPORTS+"/bake_check.json", "baked_compatible_library":baked["compatible_library"],
        "saved_and_independently_reopened":True, "actual_material_library_append":library_check["status"],
        "actual_lighting_render_count":4, "images":images, "actual_export_and_reimport_categories":list(CATEGORIES),
        "glb_container_checks":glbs, "actual_browser_check":REPORTS+"/browser_check.json", "browser_screenshot":screenshot,
        "runtime_streaming_viewer_implemented":False, "limits":list(dict.fromkeys(limits)),
        "created_at":now, "display_timezone":"Asia/Singapore"}
    artifacts = {root/cfg["output_scene"], root/cfg["source_scene"],root/"scenes/stage07_city_medium.blend",root/LIBRARY,
        root/"docs/stage08.md", root/screenshot["path"]}
    artifacts.update((root/"docs").glob("stage08*.md"))
    artifacts.add(root/"work/previews/stage08/lighting_review.html")
    artifacts.add(root/"work/logs/stage08/final_checked_four_renders.log")
    artifacts.update(root/row["path"] for row in images.values())
    artifacts.update(root/"outputs/stage08/glb"/(name+".glb") for name in CATEGORIES)
    artifacts.add(root/REGISTRY)
    artifacts.update(root/item["path"] for item in read(root,REGISTRY)["files"])
    artifacts.add(root/"assets/materials/stage08/atlas_registry.json")
    artifacts.update(root/item["path"] for item in read(root,"assets/materials/stage08/atlas_registry.json")["files"])
    artifacts.update(root/item["path"] for item in baked["files"])
    artifacts.add(root/baked["compatible_library"]["path"])
    if (root/"docs/stage08_bake.md").is_file():
        artifacts.add(root/"docs/stage08_bake.md")
    for name in ("scene_check.json", "renders.json", "export_check.json", "browser_check.json", "visual_inspection.json", "library_check.json","bake_check.json","atlas_check.json","material_semantics.json"):
        artifacts.add(root/REPORTS/name)
    for name in ("stage08.json", "stage08_materials.json", "stage08_lighting.json", "stage08_atlas.json"):
        artifacts.add(root/"config"/name)
    for path in artifacts:
        require(path.is_file(), "Missing stage08 deliverable: "+str(path.relative_to(root)))
    ii = inputs(root)
    aa = [{"path":str(p.relative_to(root)), "bytes":p.stat().st_size, "sha256":digest(p)} for p in sorted(artifacts)]
    manifest = {"stage":8, "status":ACCEPTED, "stage_gate_passed":True, "fingerprint":fp(ii), "inputs":ii,"artifacts":aa,
        "accepted_from_actual_scene_render_export_browser_review":True, "created_at":now}
    write(root, ACCEPTANCE, accepted)
    acceptance_hash = digest(root/ACCEPTANCE)
    aa.append({"path":ACCEPTANCE, "bytes":(root/ACCEPTANCE).stat().st_size,"sha256":acceptance_hash})
    aa.sort(key=lambda item:item["path"])
    try:
        write(root, MANIFEST, manifest)
    except OSError:
        if (root/ACCEPTANCE).is_file() and digest(root/ACCEPTANCE) == acceptance_hash:
            (root/ACCEPTANCE).unlink()
        raise
    print("STAGE08_ACCEPTED_WITH_DOCUMENTED_APPROXIMATIONS",len(aa),"ARTIFACTS",flush=True)
    return 0


def verify(root=ROOT):
    root = Path(root)
    manifest = read(root, MANIFEST)
    require(manifest.get("status") == ACCEPTED and manifest.get("stage_gate_passed") is True, "Stage08 manifest does not record actual acceptance")
    for row in manifest["artifacts"]:
        require((root/row["path"]).is_file() and digest(root/row["path"]) == row["sha256"], "Stage08 artifact missing/changed; preserve edits: "+row["path"])
    require(manifest["fingerprint"] == fp(inputs(root)), "Stage08 input changed; preserve accepted checkpoint before incremental rebuild")
    return manifest


def check(root, region, quality):
    if not supported(region, quality):
        return 3
    context(root)
    if not source_gate(root):
        return 4
    if not (Path(root)/MANIFEST).exists():
        print("STAGE08_REVIEW_PENDING: actual saved-model/render/export/browser/manual evidence is not registered; exit4",flush=True)
        return 4
    verify(root)
    print("STAGE08_ACCEPTED_CACHE_VERIFIED: image-backed PBR,4 actual lighting renders,5 actual GLB compatibility samples; no real-time performance claim",flush=True)
    return 0


def execute(root, region, quality):
    if not supported(region, quality):
        return 3
    root = Path(root)
    context(root)
    if not source_gate(root):
        return 4
    if (root/MANIFEST).exists():
        return check(root, region, quality)
    cfg = read(root,"config/stage08.json")
    if (root/cfg["output_scene"]).exists():
        try:
            return register(root)
        except ReviewPending as error:
            print("STAGE08_REVIEW_PENDING:",error,"Saved scene preserved; exit4",flush=True)
            return 4
    python = root/".venv/bin/python"
    require(python.is_file(), "Use the locked project .venv")
    worker = root/"scripts/stage08_textures.py"
    require(worker.is_file(), "Texture worker is not implemented")
    command(root,[python,worker,"check" if (root/REGISTRY).exists() else "generate"],"texture_checks.log")
    textures(root)
    command(root,[python,root/"scripts/stage08_solar.py","--check"],"solar_check.log")
    worker = root/"scripts/stage08_blender.py"
    require(worker.is_file(), "Blender stage08 worker is not implemented")
    common=[shutil.which("blender") or "blender","--background","--threads",str(cfg["render"]["threads"]),"--python-exit-code","1"]
    bake_worker=root/"scripts/stage08_bake.py"
    require(bake_worker.is_file(),"Actual procedural-source bake worker not implemented")
    command(root,common+["--factory-startup","--python",bake_worker,"--","--root",root],"actual_reference_bake.log")
    bake_check(root)
    # The worker saves to an owned temporary main path before linking source
    # mesh data; this avoids Blender's same-file library crash and slow scene append.
    command(root,common+[root/cfg["source_scene"],"--python",worker,"--","--mode","build-eight"],"blender_build.log")
    for mode in ("check-eight","check-semantics-eight","render-eight","export-eight"):
        command(root,common+[root/cfg["output_scene"],"--python",worker,"--","--mode",mode],mode+".log")
    library(root)
    print("STAGE08_ACTUAL_BROWSER_AND_VISUAL_REVIEW_PENDING: four final images and five actual GLB/browser samples require inspection; no automatic visual success. exit4",flush=True)
    return 4


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("execute","check","register","textures","library"),nargs="?",default="check")
    parser.add_argument("--region",default="city")
    parser.add_argument("--quality",default="medium")
    args=parser.parse_args()
    try:
        if not supported(args.region,args.quality):
            return 3
        if args.action in ("textures","library"):
            context(ROOT)
            result=globals()[args.action](ROOT)
            print(json.dumps(result,ensure_ascii=False),flush=True)
            return 0
        if args.action=="register":
            return register(ROOT)
        return globals()[args.action](ROOT,args.region,args.quality)
    except ReviewPending as error:
        print("STAGE08_REVIEW_PENDING:",error,"exit4",file=sys.stderr)
        return 4
    except (OSError,ValueError,KeyError,RuntimeError) as error:
        print("STAGE08_FAILED:",error,file=sys.stderr)
        return 1


if __name__=="__main__":
    sys.exit(main())
