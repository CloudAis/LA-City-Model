"""Revision2 coordinator: actual model checks, actual images and an explicit visual gate.

The preserved technical checkpoint is a required linked mesh library.  Registering
this revision never rewrites the old stage07 manifest or fabricates a visual pass.
"""
from pathlib import Path
import argparse
import ast
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPORTS = "work/reports/stage07_final"
MANIFEST = "outputs/stage07_final.manifest.json"
ACCEPTANCE = "outputs/stage07_final_acceptance.json"
PROFILES = ("alexandria", "arcade", "times", "records", "theatre")
VISUAL_ACCEPTED = "accepted_with_documented_approximations"


class ReviewPending(RuntimeError):
    """Incomplete evidence is a pending gate (exit4), never a successful check."""


def read(root, relative):
    return json.loads((Path(root)/relative).read_text())


def write(root, relative, value):
    path = Path(root)/relative
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix+".tmp")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")
    pending.replace(path)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def context(root):
    # Every entry starts from the current project contract and progress record.
    for name in ("PROJECT_SPEC.md", "STATUS.md"):
        require(bool((Path(root)/name).read_text().strip()), "Empty project contract: "+name)


def supported(region, quality):
    if (region, quality) != ("city", "medium"):
        print("未实现 / NOT IMPLEMENTED: stage07 revision2 supports city/medium; both near regions are retained.", flush=True)
        return False
    return True


def fp(items):
    return hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()


def inputs(root=ROOT):
    """Hash the consumed checkpoint, source records, configuration and geometry.

    The final NPZ geometry is deliberately an input as well as a deliverable:
    changing a local editable generated mesh invalidates the accepted revision.
    Volatile progress logs and mutable STATUS.md are not build inputs.
    """
    root = Path(root)
    cfg = read(root, "config/stage07_final.json")
    required = [cfg["source_scene"], "requirements.lock",
        "config/stage03.yaml", "config/stage06.json", "config/stage07.json", "config/stage07_views.json",
        "config/stage07_final.json", "config/stage07_final_views.json",
        "data/processed/origin.json", "data/processed/scopes.geojson",
        "data/processed/stage02/city_boundary_2025.geojson",
        "data/processed/stage03/medium/tile_index.json",
        "data/processed/stage03/medium/water_index.json",
        "data/processed/stage04/mesh_index.json",
        "data/processed/stage04/road_floor_index.json",
        "data/processed/stage04/downtown_surface_masks.geojson",
        "data/processed/stage05/buildings.sqlite",
        "data/processed/stage05/mesh_index.json",
        "data/processed/stage06/ground_index.json",
        "data/processed/stage06/landmark_index.json",
        "data/processed/stage02/city_10m_dem_navd88_m.tif",
        "data/processed/stage02/downtown_1m_dem_navd88_m.tif",
        "data/processed/stage02/landcover_nlcd2021_30m.tif",
        "data/processed/stage02/facility_area.geojson",
        "docs/stage07_revision_research.md"]
    paths = {root/p for p in required}
    for folder in ("data/raw/stage07", "data/raw/stage07_revision",
                   "data/processed/stage07", "data/processed/stage07_final"):
        paths.update(p for p in (root/folder).rglob("*") if p.is_file())

    # Discover the local Python dependency closure without importing bpy.
    # Unified entry routing and project-stage bookkeeping may advance later;
    # they do not alter this frozen worker's actual geometry inputs.
    scripts = set((root/"scripts").glob("stage07*.py"))
    pending = list(scripts)
    while pending:
        source = pending.pop()
        for node in ast.walk(ast.parse(source.read_text(), filename=str(source))):
            modules = [node.module] if isinstance(node, ast.ImportFrom) else (
                [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
            for module in modules:
                candidate = root/"scripts"/((module or "").split(".")[0]+".py")
                if candidate.is_file() and candidate not in scripts:
                    scripts.add(candidate)
                    pending.append(candidate)
    paths.update(scripts)

    # The old checkpoint contains the full city. Only the source mesh tiles read
    # by this local revision need separate raw-array hashes.
    ix = read(root, "data/processed/stage07_final/index.json")
    public = read(root, "data/processed/stage07_final/public_surface.json")
    tiles = {tuple(t["ij"]) for t in ix["ground"]}
    for t in ix["ground"]:
        paths.add(root/t["source_file"])
    for t in read(root, "data/processed/stage06/ground_index.json")["tiles"]:
        if tuple(t["ij"]) in tiles:
            paths.add(root/t["file"])
    for record in read(root, "data/processed/stage03/medium/tile_index.json")["tiles"]:
        if tuple(record["ij"]) in tiles:
            paths.add(root/record["file"])
            variant = root/"data/processed/stage04/ground"/(record["id"]+".npz")
            if variant.exists():
                paths.add(variant)
    for record in public["road_updates"]:
        paths.add(root/record["source_file"])
    for record in read(root, "data/processed/stage04/mesh_index.json")["meshes"]:
        origin = record.get("origin_m", [])
        if len(origin) >= 2 and (round(origin[0]/1000), round(origin[1]/1000)) in tiles:
            if record["role"] in ("downtown_road", "profiled_priority_road", "downtown_sidewalk", "curb_ramp"):
                paths.add(root/record["file"])
    for record in read(root, "data/processed/stage04/road_floor_index.json")["meshes"]:
        if record["tile_id"] in {t["id"] for t in ix["ground"]}:
            paths.add(root/record["file"])
    for p in paths:
        require(p.is_file(), "Missing reproducible input: "+str(p.relative_to(root)))
    return [{"path":str(p.relative_to(root)), "sha256":digest(p)} for p in sorted(paths)]


def command(root, args, label):
    path = Path(root)/"work/logs/stage07_final"/label
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as log:
        log.write("\n"+json.dumps(list(map(str, args)))+"\n")
        log.flush()
        result = subprocess.run(list(map(str, args)), cwd=root, stdout=log, stderr=subprocess.STDOUT)
        log.write("\nEXIT_CODE="+str(result.returncode)+"\n")
    require(result.returncode == 0, "Actual command failed; inspect "+str(path))
    print(label+"_OK", flush=True)


def libraries(root=ROOT):
    """Append the five object libraries in an independent Blender process."""
    root = Path(root)
    paths = ["assets/buildings/stage07_final/"+p+".blend" for p in PROFILES]
    for path in paths:
        require((root/path).is_file(), "Missing appendable object library: "+path)
    hashes = {p:digest(root/p) for p in paths}
    report_path = root/REPORTS/"library_check.json"
    if report_path.exists():
        old = json.loads(report_path.read_text())
        if (old.get("status") == "passed" and old.get("library_sha256") == hashes
                and len(old.get("libraries", [])) == len(PROFILES)
                and all(item.get("actual_independent_append") is True for item in old["libraries"])):
            return old
    # An object library is loaded with bpy.data.libraries.load, not mistaken for
    # a complete scene with a camera and lights. The saved city is never changed.
    expression = "\n".join([
        "import bpy,json,math",
        "from pathlib import Path",
        "root=Path("+repr(str(root))+")",
        "paths="+repr(paths),
        "records=[]",
        "for relative in paths:",
        " for ob in list(bpy.data.objects): bpy.data.objects.remove(ob,do_unlink=True)",
        " with bpy.data.libraries.load(str(root/relative),link=False) as (src,dst): dst.objects=list(src.objects)",
        " objects=[ob for ob in dst.objects if ob is not None]",
        " meshes=[ob for ob in objects if ob.type=='MESH']",
        " assert objects and meshes, relative",
        " for ob in objects:",
        "  if ob.name not in bpy.context.scene.objects: bpy.context.scene.collection.objects.link(ob)",
        " nonfinite=sum(not math.isfinite(c) for ob in meshes for v in ob.data.vertices for c in v.co)",
        " polygons=sum(len(ob.data.polygons) for ob in meshes)",
        " assert nonfinite==0 and polygons>0,relative",
        " records.append({'path':relative,'appended_objects':len(objects),'mesh_objects':len(meshes),'polygons':polygons,'nonfinite_vertices':nonfinite,'actual_independent_append':True})",
        "report={'status':'passed','object_libraries_not_full_scenes':True,'saved_final_scene_unchanged':True,'libraries':records,'library_sha256':"+repr(hashes)+"}",
        "(root/"+repr(REPORTS+"/library_check.json")+").write_text(json.dumps(report,indent=2)+'\\n')",
        "print('STAGE07_FINAL_FIVE_OBJECT_LIBRARIES_APPENDED',flush=True)",
    ])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    command(root, [shutil.which("blender") or "blender", "--background", "--threads", "4",
                   "--factory-startup", "--python-exit-code", "1", "--python-expr", expression],
            "library_append_check.log")
    result = json.loads(report_path.read_text())
    require(result["status"] == "passed" and result["library_sha256"] == hashes, "Object library append check failed")
    return result


def evidence(root=ROOT):
    root = Path(root)
    cfg = read(root, "config/stage07_final.json")
    required = [cfg["output_scene"], "data/processed/stage07_final/index.json",
        "data/processed/stage07_final/public_surface.json", REPORTS+"/build.json",
        REPORTS+"/blender_check.json", REPORTS+"/ground_generation_check.json",
        REPORTS+"/geometry_audit.json", REPORTS+"/renders_all.json", REPORTS+"/visual_inspection.json"]
    missing = [p for p in required if not (root/p).is_file()]
    if missing:
        raise ReviewPending("Missing actual final evidence: "+", ".join(missing))
    ix = read(root, "data/processed/stage07_final/index.json")
    build = read(root, REPORTS+"/build.json")
    check_report = read(root, REPORTS+"/blender_check.json")
    ground = read(root, REPORTS+"/ground_generation_check.json")
    geometry = read(root, REPORTS+"/geometry_audit.json")
    renders = read(root, REPORTS+"/renders_all.json")
    visual = read(root, REPORTS+"/visual_inspection.json")
    views = read(root, "config/stage07_final_views.json")
    if visual.get("status") != VISUAL_ACCEPTED or visual.get("stage_gate_passed") is not True:
        raise ReviewPending("Actual final image inspection has not explicitly accepted the documented approximations")
    require(len(views) == 10 and visual.get("actual_images_viewed") == len(views), "Ten actual final views must be inspected")
    model_sha256 = digest(root/cfg["output_scene"])
    require(visual.get("final_saved_model_sha256") == model_sha256, "Visual review refers to a different saved model")
    require(build["source_scene"] == cfg["source_scene"] and build["output_scene"] == cfg["output_scene"], "Build checkpoint paths differ from configuration")
    require(build.get("local_editable_refinements") is True and build.get("source_library_must_accompany_final_file") is True, "Linked editable-city delivery contract missing")
    require(check_report["status"] == "passed" and check_report.get("saved_checkpoint_reopened_independently") is True, "Independent reopened Blender check has not passed")
    require(check_report.get("saved_model_sha256") == model_sha256, "Independent reopen check refers to a different saved model")
    for name in ("nonfinite_vertices", "degenerate_triangles", "invalid_material_indices", "old_selected_body_faces", "old_selected_attached_points"):
        require(check_report[name] == 0, "Blender geometry check failed: "+name)
    require(check_report["units_metres_per_blender_unit"] == 1 and check_report["refined_buildings_checked"] == 100, "Metre scale or building count differs")
    require(check_report["source06_landmarks_retained"] == 10, "Ten stage06 landmarks were not retained")
    require(check_report["default_visible_triangles"] <= cfg["max_visible_triangles"], "Default saved-view triangle budget exceeded")
    require(all(item["exists"] and Path(item["path"]).is_file() for item in check_report["libraries"]), "Linked baseline is unavailable")
    require(any(Path(item["path"]).resolve() == (root/cfg["source_scene"]).resolve() for item in check_report["libraries"]), "Final checkpoint does not use its declared preserved source library")
    require(ground["status"] == "passed_geometry_generation_checks", "Actual public-surface generation checks did not pass")
    require(ground["old_sidewalk_retained_inside_replacement_scope_m2"] < .02, "Old and new sidewalks overlap")
    require(ground.get("new_paving_excludes_ramps") and ground.get("curb_omits_ramp_openings"), "Source ramp openings were not preserved")
    require(ground["unrestored_bridge_sidewalk_m2"] < .05 and ground["raw_and_previous_stages_modified"] is False, "Skybridge ground restoration or source preservation check failed")
    require({r["region"] for r in ground["regions"]} == set(cfg["regions"]), "Ground checks do not cover both work windows")
    for path, expected in ground["source_mesh_hashes_after_read"].items():
        require(digest(root/path) == expected, "Original ground/road mesh changed after generation: "+path)
    for region in ground["regions"]:
        require(region["paving_downward_or_vertical_faces"] == 0 and region["curb_normals_pointing_into_pavement"] == 0, "Public-surface winding check failed")
        require(region["new_paving_ramp_overlap_m2"] < .02, "New pavement covers a source ramp opening")
    require(ix["actual_buildings"] == 100 and len(ix["buildings"]) == 100 and ix["original_county_features"] == 103, "Expected 100 buildings replacing 103 source records")
    require(len({b["i"] for b in ix["buildings"]}) == 100 and len(set(ix["replaced_source_indices"])) == 103, "Duplicate building replacement ID")
    require(ix["skybridge"]["no_ground_door_required"] is True and ix["skybridge"]["old85m_tower_interpretation_rejected"] is True, "Rejected 85m skybridge interpretation reappeared")
    require(set(ix["skybridge"]["replaces"]) == set(cfg["skybridge"]["replaces"]), "Skybridge mapping differs from source correction")
    require({b["profile"] for b in ix["buildings"] if b["reference_guided"]} == set(PROFILES), "Five researched profiles not all present")
    require(geometry.get("status") == "passed" and geometry.get("passed") is True and not geometry.get("failures"), "Actual source/geometry audit has not passed")
    require(geometry.get("index_sha256") == digest(root/"data/processed/stage07_final/index.json"), "Geometry audit refers to a stale generated index")
    geometry_hashes = {str(p.relative_to(root)):digest(p) for p in sorted((root/"data/processed/stage07_final").rglob("*.npz"))}
    require(geometry.get("geometry_sha256") == geometry_hashes, "Audited generated mesh files are missing, stale or changed")
    require({b["i"] for b in geometry.get("buildings", [])} == {b["i"] for b in ix["buildings"]}, "Actual geometry audit does not cover all100 source buildings")
    require(renders["status"] == "actual_render_completed" and set(renders["images"]) == set(views), "Final ten-camera render set is incomplete")
    require(Path(renders["saved_scene"]).resolve() == (root/cfg["output_scene"]).resolve(), "Rendered scene is not the saved final checkpoint")
    require(renders.get("saved_scene_sha256") == model_sha256, "Final render evidence refers to a different saved model")
    inspected = {v["path"]:v for v in visual["images"]}
    require(len(inspected) == len(views), "Actual inspection image set contains duplicates or omissions")
    image_checks = {}
    from PIL import Image, ImageStat
    for name, result in renders["images"].items():
        for field in ("position_m", "target_m", "focus_xy_m", "radius_m", "detail_radius_m", "lens_mm", "ortho_scale_m", "target_uid"):
            require(result.get(field) == views[name].get(field), "Stale rendered camera field: "+name+"/"+field)
        require(result.get("actual_cpu_cycles") is True, "Actual Cycles render evidence absent: "+name)
        path = result["output"]
        require(path == "work/previews/stage07_final/"+name+".png", "Draft or unexpected image substituted for final: "+name)
        require(path in inspected and inspected[path].get("actual_view_image_inspection") is True, "Image not actually inspected: "+name)
        require(digest(root/path) == inspected[path]["sha256"], "Image changed after actual inspection: "+name)
        with Image.open(root/path) as image:
            require(image.format == "PNG" and image.size == (cfg["render"]["width"], cfg["render"]["height"]), "Final PNG size/format mismatch: "+name)
            deviation = ImageStat.Stat(image.convert("RGB")).stddev
            require(max(deviation) > 5, "Final render is nearly blank: "+name)
        image_checks[name] = {"path":path, "sha256":inspected[path]["sha256"], "dimensions_px":[cfg["render"]["width"],cfg["render"]["height"]], "rgb_stddev":deviation, "visible_triangles":result["actual_triangles_including_shared_instances"]}
    require(set(inspected) == {r["output"] for r in renders["images"].values()}, "Inspection and render image sets differ")
    # A report older than the saved model cannot certify that model. Hashes in
    # the manual report bind the current scene and the current final images.
    for report in ("blender_check.json", "renders_all.json"):
        require((root/REPORTS/report).stat().st_mtime >= (root/cfg["output_scene"]).stat().st_mtime, "Saved checkpoint newer than actual check: "+report)
    return cfg, ix, build, check_report, ground, visual, image_checks


def register(root=ROOT):
    root = Path(root)
    context(root)
    if (root/MANIFEST).exists():
        verify(root)
        print("STAGE07_FINAL_ACCEPTED_CACHE_VERIFIED; preserved previous stage07 manifests unchanged", flush=True)
        return 0
    cfg, ix, build, check_report, ground, visual, images = evidence(root)
    previous_manifest = root/"outputs/stage07_city_medium.manifest.json"
    require(previous_manifest.is_file(), "Preserved technical checkpoint manifest is required")
    previous_sha256 = digest(previous_manifest)
    previous = json.loads(previous_manifest.read_text())
    preserved_source = next((a for a in previous["artifacts"] if a["path"] == cfg["source_scene"]), None)
    require(preserved_source is not None and digest(root/cfg["source_scene"]) == preserved_source["sha256"], "Preserved technical checkpoint changed from its original registered artifact")
    library_report = libraries(root)
    limits = [
        "No façade is certified as fully measured. Five buildings are reference-guided approximations; other ordinary buildings retain explicit neutral inferred detail.",
        "LARIAC6 roofline/heights, OSM snapshots and historical architectural references have different dates; this is not a single-date surveyed city.",
        "Street grade, entry geometry, sidewalk widths, ordinary windows, roof plant and generic tree species remain labelled visual inferences; no engineering or accessibility certification.",
        "The final .blend requires the unchanged scenes/stage07_city_medium.blend linked mesh library. Local revision geometry is editable; linked unchanged meshes are edited in the source file or made local.",
        "The five profile .blend assets are appendable object libraries, not complete standalone camera/light scenes.",
        "LOD choices are static authoring/render selections; interactive distance switching, streaming, viewer and stage08–10 are not implemented.",
        *ground.get("limitations", []), *visual.get("limits", [])]
    missing_entries = [b["uid"] for b in ix["buildings"] if not b["doors"]]
    if missing_entries:
        limits.append("Source-grounded buildings without a modeled entrance: "+", ".join(missing_entries))
    now = datetime.datetime.now(ZoneInfo("Asia/Singapore"))
    acceptance = {"stage":7, "revision":cfg["revision"], "status":VISUAL_ACCEPTED,
        "stage_gate_passed":True, "region":"city", "quality":"medium",
        "model":cfg["output_scene"], "required_linked_library":cfg["source_scene"],
        "linked_library_sha256":digest(root/cfg["source_scene"]),
        "preserved_technical_checkpoint_manifest":"outputs/stage07_city_medium.manifest.json",
        "regions":cfg["regions"], "work_window_area_m2":280000,
        "source_records_replaced":103, "ordinary_buildings":100, "mapped_skybridges":1,
        "rejected_skybridge_sliver_indices":ix["skybridge"]["replaces"],
        "stage06_landmarks_retained":check_report["source06_landmarks_retained"],
        "reference_guided_approximate_profiles":list(PROFILES),
        "fully_measured_facades":0, "window_openings":sum(b["windows"] for b in ix["buildings"]),
        "entry_records":sum(len(b["doors"]) for b in ix["buildings"]),
        "buildings_without_modeled_entry":missing_entries,
        "local_refinement_triangles":sum(sum(p["triangles"] for p in b["near"]) for b in ix["buildings"]),
        "default_visible_triangles":check_report["default_visible_triangles"],
        "actual_final_render_count":len(images), "image_checks":images,
        "saved_and_independently_reopened":True, "actual_five_library_append_check":library_report["status"],
        "visual_review_report":REPORTS+"/visual_inspection.json",
        "ground_check_report":REPORTS+"/ground_generation_check.json",
        "source_geometry_audit":REPORTS+"/geometry_audit.json",
        "final_model_sha256":visual["final_saved_model_sha256"],
        "runtime_switching_streaming_viewer":False,
        "created_at":now.isoformat(), "display_timezone":"Asia/Singapore", "limits":list(dict.fromkeys(limits))}
    # Validate and hash every other artifact before publishing an accepted
    # record. An incomplete input tree must never leave a false accepted file.
    require(not (root/ACCEPTANCE).exists(), "Unregistered acceptance file already exists; preserve it before publishing a replacement")
    artifacts = {root/cfg["output_scene"], root/cfg["source_scene"],
        root/"config/stage07_final.json", root/"config/stage07_final_views.json",
        root/"docs/stage07_final.md", root/"docs/stage07_revision_research.md"}
    artifacts.update(root/v["path"] for v in images.values())
    for folder in ("assets/buildings/stage07_final", "data/processed/stage07_final"):
        artifacts.update(p for p in (root/folder).rglob("*") if p.is_file())
    for name in ("build.json", "blender_check.json", "ground_generation_check.json", "geometry_audit.json", "renders_all.json", "visual_inspection.json", "library_check.json"):
        artifacts.add(root/REPORTS/name)
    for path in artifacts:
        require(path.is_file(), "Missing delivery artifact: "+str(path.relative_to(root)))
    ii = inputs(root)
    aa = [{"path":str(p.relative_to(root)), "bytes":p.stat().st_size, "sha256":digest(p)} for p in sorted(artifacts)]
    require(digest(previous_manifest) == previous_sha256, "Previous manifest changed during final registration")
    manifest = {"stage":7, "revision":cfg["revision"], "status":VISUAL_ACCEPTED,
        "stage_gate_passed":True, "fingerprint":fp(ii), "inputs":ii, "artifacts":aa,
        "accepted_from_actual_model_and_image_review":True, "created_at":now.isoformat(),
        "required_linked_library":cfg["source_scene"], "previous_manifest_modified":False,
        "preserved_previous_manifest_sha256":previous_sha256}
    write(root, ACCEPTANCE, acceptance)
    acceptance_hash = digest(root/ACCEPTANCE)
    aa.append({"path":ACCEPTANCE, "bytes":(root/ACCEPTANCE).stat().st_size, "sha256":acceptance_hash})
    aa.sort(key=lambda item:item["path"])
    try:
        write(root, MANIFEST, manifest)
    except OSError:
        if (root/ACCEPTANCE).is_file() and digest(root/ACCEPTANCE) == acceptance_hash:
            (root/ACCEPTANCE).unlink()
        raise
    print("STAGE07_FINAL_ACCEPTED_WITH_DOCUMENTED_APPROXIMATIONS",len(aa),"ARTIFACTS; later stages use independent acceptance gates", flush=True)
    return 0


def verify(root=ROOT):
    root = Path(root)
    manifest = read(root, MANIFEST)
    require(manifest.get("stage_gate_passed") is True and manifest.get("status") == VISUAL_ACCEPTED, "Manifest does not contain an actual accepted stage07 revision")
    for item in manifest["artifacts"]:
        path = root/item["path"]
        require(path.is_file() and digest(path) == item["sha256"], "Artifact missing or changed; preserve edits before rebuilding: "+item["path"])
    require(manifest["fingerprint"] == fp(inputs(root)), "Stage07 final inputs changed; preserve the accepted checkpoint before an incremental rebuild")
    return manifest


def check(root, region, quality):
    if not supported(region, quality):
        return 3
    context(root)
    if not (Path(root)/MANIFEST).exists():
        print("STAGE07_FINAL_REVIEW_PENDING: no registered accepted revision; actual reopened/render/visual evidence required. exit4", flush=True)
        return 4
    verify(root)
    print("STAGE07_FINAL_ACCEPTED_WITH_DOCUMENTED_APPROXIMATIONS: 100 buildings+1 mapped skybridge,10 retained landmarks,10 inspected final views; cached artifact/input hashes verified.", flush=True)
    return 0


def execute(root, region, quality):
    if not supported(region, quality):
        return 3
    root = Path(root)
    context(root)
    if (root/MANIFEST).exists():
        return check(root, region, quality)
    cfg = read(root, "config/stage07_final.json")
    if (root/cfg["output_scene"]).exists():
        try:
            return register(root)
        except ReviewPending as error:
            print("STAGE07_FINAL_REVIEW_PENDING:",error,"Existing final scene preserved; exit4", flush=True)
            return 4
    require((root/cfg["source_scene"]).is_file(), "Preserved technical checkpoint required; no automatic replacement by synthetic data")
    python = root/".venv/bin/python"
    require(python.is_file(), "Use the locked project .venv")
    index = root/"data/processed/stage07_final/index.json"
    if index.exists():
        # Existing unregistered geometry can be reviewed and built, but is not
        # silently regenerated over possible edits.
        for relative in ("data/processed/stage07_final/public_surface.json", "data/processed/stage07_final/street_positions.json", "data/processed/stage07_final/leaf_asset.json", "config/stage07_final_views.json", REPORTS+"/ground_generation_check.json"):
            require((root/relative).is_file(), "Partial editable data cache preserved; explicitly complete the missing worker output: "+relative)
        print("STAGE07_FINAL_EXISTING_LOCAL_GEOMETRY_PRESERVED_FOR_BUILD", flush=True)
    else:
        for worker in ("stage07_final_data.py", "stage07_final_enrich.py", "stage07_final_ground.py", "stage07_final_prepare_views.py"):
            command(root, [python, root/"scripts"/worker], worker+".log")
    audit_worker = root/"scripts/stage07_final_audit.py"
    require(audit_worker.is_file(), "Actual source/geometry audit worker has not been implemented")
    command(root, [python, audit_worker], "geometry_audit.log")
    worker = root/"scripts/stage07_final_blender.py"
    common = [shutil.which("blender") or "blender", "--background", "--threads", str(cfg["render"]["threads"]), "--python-exit-code", "1"]
    # The builder first saves its main file to a temporary owned path before
    # linking from this preserved source. Direct self-library linking crashes
    # Blender; appending the enormous source scene is prohibitively slow.
    command(root, common+[root/cfg["source_scene"], "--python", worker, "--", "--mode", "build-final"], "blender_build.log")
    command(root, common+[root/cfg["output_scene"], "--python", worker, "--", "--mode", "check-render-final"], "blender_reopen_and_render.log")
    libraries(root)
    print("STAGE07_FINAL_ACTUAL_VISUAL_REVIEW_PENDING: inspect the10 final PNGs and record the current scene/image hashes; no automatic visual success. exit4", flush=True)
    return 4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("execute", "check", "register", "libraries"), nargs="?", default="check")
    parser.add_argument("--region", default="city")
    parser.add_argument("--quality", default="medium")
    args = parser.parse_args()
    try:
        if not supported(args.region, args.quality):
            return 3
        if args.action == "libraries":
            context(ROOT)
            libraries(ROOT)
            return 0
        if args.action == "register":
            return register(ROOT)
        return globals()[args.action](ROOT, args.region, args.quality)
    except ReviewPending as error:
        print("STAGE07_FINAL_REVIEW_PENDING:",error,"exit4", file=sys.stderr)
        return 4
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print("STAGE07_FINAL_FAILED:",error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
