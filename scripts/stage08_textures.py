"""Original deterministic periodic PBR maps; no downloaded/photo texture inputs.

Maps are sampled from scalar height/color fields, not purported city measurements.
They are immediately compatible with glTF metallic-roughness via packed ORM.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CONFIG = "config/stage08_materials.json"
REGISTRY = "assets/materials/stage08/registry.json"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")
    temporary.replace(path)


def periodic_noise(rng, n, cutoff, anisotropy=1.0):
    white = rng.standard_normal((n, n))
    spectrum = np.fft.rfft2(white)
    kx = np.fft.rfftfreq(n)*n
    ky = np.fft.fftfreq(n)*n
    kernel = np.exp(-((kx[None, :]/cutoff)**2+(ky[:, None]/(cutoff*anisotropy))**2))
    field = np.fft.irfft2(spectrum*kernel, s=(n, n))
    field -= field.mean()
    return np.clip(field/max(field.std()*2.8, 1e-12), -1.0, 1.0)


def shared_edges(array):
    # Include one duplicate edge texel. Repeat filtering sees equal edge colors;
    # the physical tile size refers to the complete normalized UV interval.
    array[-1, ...] = array[0, ...]
    array[:, -1, ...] = array[:, 0, ...]
    return array


def fields(material_id, spec, rng, n):
    y, x = np.mgrid[0:n, 0:n].astype(float)/n
    broad = periodic_noise(rng, n, 4)
    medium = periodic_noise(rng, n, 28)
    fine = periodic_noise(rng, n, 160, .08 if material_id == "metal" else 1)
    modulation = .55*broad+.3*medium+.15*fine
    base = np.array(spec["base_color_srgb"])[None, None, :]*(1+spec["variation"]*modulation[:, :, None])
    rough = spec["roughness"]+.045*modulation
    height = spec["height_amplitude_m"]*(.14*medium+.86*fine)
    alpha = np.ones((n, n))

    if material_id == "asphalt":
        # Broad mottling is color-only; aggregate relief has millimetre scale.
        aggregate = np.maximum(fine-.25, 0)
        base += aggregate[:, :, None]*.035
        height += spec["height_amplitude_m"]*aggregate
    elif material_id == "paving_stone":
        pitch_x = spec["slab_size_m"][0]/spec["tile_size_m"][0]
        pitch_y = spec["slab_size_m"][1]/spec["tile_size_m"][1]
        fx, fy = (x/pitch_x)%1, (y/pitch_y)%1
        edge_distance = np.minimum(np.minimum(fx, 1-fx)*spec["slab_size_m"][0], np.minimum(fy, 1-fy)*spec["slab_size_m"][1])
        raised = np.clip((edge_distance-spec["joint_width_m"]/2)/.006, 0, 1)
        base *= (.72+.28*raised[:, :, None])
        height += spec["height_amplitude_m"]*raised
    elif material_id == "brick":
        columns = spec["tile_size_m"][0]/spec["brick_pitch_m"][0]
        rows = spec["tile_size_m"][1]/spec["brick_pitch_m"][1]
        row = np.floor(y*rows).astype(int)
        fx, fy = (x*columns+.5*(row%2))%1, (y*rows)%1
        dx = np.minimum(fx, 1-fx)*spec["brick_pitch_m"][0]
        dy = np.minimum(fy, 1-fy)*spec["brick_pitch_m"][1]
        raised = np.clip((np.minimum(dx, dy)-spec["mortar_width_m"]/2)/.002, 0, 1)
        mortar = np.array([.51, .48, .41])
        base = base*raised[:, :, None]+mortar[None, None, :]*(1-raised[:, :, None])
        height += spec["height_amplitude_m"]*raised
        rough += (1-raised)*.05
    elif material_id == "leaf":
        xx, yy = (x-.5)*2, (y-.5)*2
        ellipse = xx**2+(yy/.95)**2
        alpha = np.clip((1-ellipse)*48, 0, 1)
        centre_vein = np.exp(-(xx/.018)**2)
        side_veins = np.maximum(0, np.cos(2*np.pi*(yy*7+abs(xx)*4)))**18
        side_veins *= np.exp(-abs(xx)*1.6)
        veins = np.maximum(centre_vein, side_veins*.55)
        base *= (.88+.22*veins[:, :, None]+.1*np.clip(xx, 0, 1)[:, :, None])
        height += spec["height_amplitude_m"]*veins
    elif material_id == "water":
        height = spec["height_amplitude_m"]*(.55*np.sin(2*np.pi*(7*x+3*y))+.25*np.sin(2*np.pi*(13*x-9*y))+.2*medium)
        rough = spec["roughness"]+.015*medium
    elif material_id == "glass":
        # Architectural glass has no fabricated bump, dust cloud or metalness.
        height[:] = 0
        rough = spec["roughness"]+.008*broad

    dx = (np.roll(height, -1, axis=1)-np.roll(height, 1, axis=1))/(2*spec["tile_size_m"][0]/n)
    dy = (np.roll(height, -1, axis=0)-np.roll(height, 1, axis=0))/(2*spec["tile_size_m"][1]/n)
    # PNG row index grows downward; positive UV V grows upward. Therefore
    # dH/dV=-dH/drow and the OpenGL tangent normal's green component is +dy.
    normal = np.stack([-dx, dy, np.ones_like(height)], axis=-1)
    normal /= np.linalg.norm(normal, axis=-1)[:, :, None]
    rgba = np.dstack([np.clip(base, 0, 1), alpha])
    orm = np.dstack([np.ones((n, n)), np.clip(rough, .04, 1), np.full((n, n), spec["metallic"])])
    return {"base_color": shared_edges(np.rint(rgba*255).astype(np.uint8)),
            "normal": shared_edges(np.rint((normal*.5+.5)*255).astype(np.uint8)),
            "orm": shared_edges(np.rint(orm*255).astype(np.uint8))}


def resize_map(array, size, normal=False):
    im = Image.fromarray(array)
    if im.width != size:
        im = im.resize((size, size), Image.Resampling.LANCZOS)
    result = np.array(im)
    if normal:
        vec = result.astype(float)/255*2-1
        vec /= np.maximum(np.linalg.norm(vec, axis=-1)[:, :, None], 1e-12)
        result = np.rint((vec*.5+.5)*255).astype(np.uint8)
    return shared_edges(result)


def check_file(path, kind, size):
    with Image.open(path) as image:
        image.load()
        ar = np.array(image)
        assert image.size == (size, size)
    horizontal = int(abs(ar[0].astype(int)-ar[-1].astype(int)).max())
    vertical = int(abs(ar[:, 0].astype(int)-ar[:, -1].astype(int)).max())
    assert horizontal == vertical == 0
    row = {"path": str(path.relative_to(ROOT)), "sha256": sha(path), "bytes": path.stat().st_size,
           "dimensions_px": [size, size], "horizontal_edge_max_byte_difference": horizontal,
           "vertical_edge_max_byte_difference": vertical, "pixel_min": int(ar.min()), "pixel_max": int(ar.max()),
           "color_space": "sRGB" if kind == "base_color" else "Non-Color"}
    if kind == "normal":
        vec = ar.astype(float)/255*2-1
        length = np.linalg.norm(vec, axis=-1)
        row["normal_unit_length_max_error_after_8bit_encoding"] = float(abs(length-1).max())
        row["normal_positive_z"] = bool((vec[:, :, 2] > 0).all())
        assert row["normal_positive_z"] and row["normal_unit_length_max_error_after_8bit_encoding"] < .012
    return row


def verify(registry):
    for item in registry["files"]:
        path = ROOT/item["path"]
        assert path.is_file() and sha(path) == item["sha256"], "Changed texture: "+str(path)
    return registry


def run():
    config = json.loads((ROOT/CONFIG).read_text())
    inputs = {CONFIG: sha(ROOT/CONFIG), "scripts/stage08_textures.py": sha(__file__)}
    fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    registry_path = ROOT/REGISTRY
    if registry_path.exists():
        previous = verify(json.loads(registry_path.read_text()))
        if previous["input_fingerprint"] == fingerprint:
            print("STAGE08_TEXTURE_CACHE_VERIFIED", len(previous["files"]), flush=True)
            return previous
        # Distinct content-addressed directories retain all previous map assets.
        write(registry_path.parent/"history"/(previous["input_fingerprint"]+".json"), previous)
    folder = ROOT/"assets/textures/stage08"/fingerprint[:12]
    folder.mkdir(parents=True, exist_ok=True)
    registry = {"status": "passed_generated_texture_checks", "stage": 8,
                "source_class": "artistic_synthetic_original", "external_texture_inputs": [],
                "license": "Original project-generated procedural textures; no third-party texture restrictions. Copyright/licensing decisions remain with the project owner; no unauthorized CC0 grant is asserted.",
                "input_fingerprint": fingerprint, "inputs": inputs,
                "seed": config["seed"], "normal_convention": config["normal_convention"],
                "orm_channels": config["orm_channels"], "sampler": config["sampler"],
                "materials": {}, "files": []}
    for material_id, spec in config["materials"].items():
        material_seed = int.from_bytes(hashlib.sha256((str(config["seed"])+material_id).encode()).digest()[:8], "little")
        rng = np.random.default_rng(material_seed)
        maps = fields(material_id, spec, rng, config["dimensions_px"]["near"])
        entry = dict(spec, seed=material_seed, maps={}, texel_density_px_per_m={})
        for lod, size in config["dimensions_px"].items():
            entry["maps"][lod] = {}
            entry["texel_density_px_per_m"][lod] = [size/m for m in spec["tile_size_m"]]
            for kind, source in maps.items():
                data = resize_map(source, size, kind == "normal")
                # Non-leaf colors have no unnecessary alpha/transparent sorting.
                if kind == "base_color" and material_id != "leaf":
                    data = data[:, :, :3]
                path = folder/(material_id+"_"+lod+"_"+kind+".png")
                temp = path.with_suffix(".tmp.png")
                Image.fromarray(data).save(temp, optimize=True)
                temp.replace(path)
                info = check_file(path, kind, size)
                registry["files"].append(info)
                entry["maps"][lod][kind] = info["path"]
        registry["materials"][material_id] = entry
        print("PBR_TEXTURES_GENERATED", material_id, flush=True)
    total = sum(f["bytes"] for f in registry["files"])
    assert total <= config["texture_budget_mib"]*1024**2, total
    registry["total_texture_bytes"] = total
    # Independent tangent cross-product check on a known sloping height plane.
    yy, xx = np.mgrid[0:5, 0:5]/4
    hh = .1*xx+.2*(1-yy)
    ddrow, ddx = np.gradient(hh, .25, .25)
    encoded_direction = np.stack([-ddx, ddrow, np.ones_like(hh)], axis=-1)
    encoded_direction /= np.linalg.norm(encoded_direction, axis=-1)[:, :, None]
    geometric = np.cross([1, 0, .1], [0, 1, .2])
    geometric /= np.linalg.norm(geometric)
    orientation_error = float(abs(encoded_direction-geometric).max())
    assert orientation_error < 1e-12
    registry["checks"] = {"file_count": len(registry["files"]), "all_images_reopened": True,
        "all_edges_byte_identical": True, "normal_maps_finite_positive_z": True,
        "normal_png_row_down_uv_v_up_geometric_direction_max_error": orientation_error,
        "actual_total_mib": total/1024**2, "configured_budget_mib": config["texture_budget_mib"],
        "no_displacement_of_city_geometry": True,
        "blender_and_glb_visual_verification": "pending separate actual scene/export checks"}
    write(registry_path, registry)
    print("STAGE08_PBR_TEXTURES_PASSED", len(registry["materials"]), len(registry["files"]), round(total/1024**2, 2), "MiB", flush=True)
    return registry


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", nargs="?", choices=["generate", "check"], default="generate")
    args = parser.parse_args()
    if args.action == "check":
        registry = verify(json.loads((ROOT/REGISTRY).read_text()))
        print("STAGE08_TEXTURE_FILES_SHA_VERIFIED", len(registry["files"]))
    else:
        run()
