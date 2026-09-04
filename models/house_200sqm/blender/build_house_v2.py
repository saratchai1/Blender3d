from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

BASE_PATH = Path(__file__).with_name("build_house_from_pascal.py")
_spec = importlib.util.spec_from_file_location("house_base", BASE_PATH)
base = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(base)


def args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description="Build the visual v2 Blender house from Pascal semantics")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--export-glb", type=Path)
    p.add_argument("--preview", type=Path)
    return p.parse_args(argv)


def mat(name: str, rgba, *, roughness: float = 0.55, metallic: float = 0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = rgba
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF") if m.node_tree else None
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = rgba[3]
    return m


def ensure_details_collection():
    return base.collection("40_Architectural_Details")


def cube(name, loc, dims, material, *, rz=0.0, col=None, derived=None):
    return base.cube(name, loc, dims, material, rz, None, col, None, derived)


def remove_visual_zone_overlays(nodes: dict) -> None:
    zone_ids = {n["id"] for n in nodes.values() if n.get("type") == "zone"}
    for obj in list(bpy.data.objects):
        d = obj.get("derived_from_pascal_id")
        if d in zone_ids and (obj.name.endswith("_zone") or obj.name.endswith("_label")):
            bpy.data.objects.remove(obj, do_unlink=True)


def remove_base_roof() -> None:
    col = bpy.data.collections.get("30_Roof")
    if not col:
        return
    for obj in list(col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def mesh_obj(name: str, verts, faces, material, col, derived: str | None = None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    obj.data.materials.append(material)
    base.tag(obj, derived_from=derived)
    return obj


def build_hip_roof(nodes: dict, materials: dict) -> None:
    seg = next(n for n in nodes.values() if n.get("type") == "roof-segment")
    col = base.collection("30_Roof")
    over = 0.90
    z0 = 6.62
    zr = 8.10
    x0, x1, y0, y1 = -over, 10 + over, -over, 10 + over
    ridge_s, ridge_n = 2.2, 7.8
    verts = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (5.0, ridge_s, zr), (5.0, ridge_n, zr),
    ]
    faces = [
        (0, 1, 4),
        (1, 2, 5, 4),
        (2, 3, 5),
        (3, 0, 4, 5),
    ]
    roof = mesh_obj("roof_visual_hip", verts, faces, materials["roof"], col, seg["id"])
    solid = roof.modifiers.new("Roof thickness", "SOLIDIFY")
    solid.thickness = 0.10
    solid.offset = -0.5
    bevel = roof.modifiers.new("Roof edge softening", "BEVEL")
    bevel.width = 0.035
    bevel.segments = 2

    fascia_h = 0.18
    cube("fascia_front", (5, y0, z0 - 0.02), (x1 - x0, 0.10, fascia_h), materials["charcoal"], col=col, derived=seg["id"])
    cube("fascia_rear", (5, y1, z0 - 0.02), (x1 - x0, 0.10, fascia_h), materials["charcoal"], col=col, derived=seg["id"])
    cube("fascia_west", (x0, 5, z0 - 0.02), (0.10, y1 - y0, fascia_h), materials["charcoal"], col=col, derived=seg["id"])
    cube("fascia_east", (x1, 5, z0 - 0.02), (0.10, y1 - y0, fascia_h), materials["charcoal"], col=col, derived=seg["id"])


def outside_normal(wall_id: str):
    if wall_id.endswith("south"):
        return (0.0, -1.0)
    if wall_id.endswith("north"):
        return (0.0, 1.0)
    if wall_id.endswith("west"):
        return (-1.0, 0.0)
    if wall_id.endswith("east"):
        return (1.0, 0.0)
    return None


def opening_world(wall: dict, opening: dict, base_z: float):
    sx, sy, ux, uy, _, angle = base.wall_basis(wall)
    x, y, _ = opening.get("position", [0, 0, 0])
    return (sx + ux * x, sy + uy * x, base_z + y), angle


def add_window_shades(nodes: dict, materials: dict, col) -> None:
    for n in nodes.values():
        if n.get("type") != "window":
            continue
        wall = nodes.get(n.get("parentId"))
        if not wall:
            continue
        normal = outside_normal(wall["id"])
        if not normal:
            continue
        level = 0 if wall["id"].startswith("wall_g_") else 1
        base_z = 0.18 + 3.2 * level
        (x, y, zc), angle = opening_world(wall, n, base_z)
        width = float(n.get("width", 1.5))
        height = float(n.get("height", 1.5))
        nx, ny = normal

        awn_depth = 0.62 if level == 1 else 0.46
        cx = x + nx * (awn_depth / 2 + 0.08)
        cy = y + ny * (awn_depth / 2 + 0.08)
        cube(
            f"{n['id']}_sunshade", (cx, cy, zc + height / 2 + 0.16),
            (width + 0.34, awn_depth, 0.09), materials["charcoal"], rz=angle,
            col=col, derived=n["id"],
        )
        sill_d = 0.20
        sx = x + nx * (sill_d / 2 + 0.08)
        sy = y + ny * (sill_d / 2 + 0.08)
        cube(
            f"{n['id']}_sill", (sx, sy, zc - height / 2 - 0.05),
            (width + 0.18, sill_d, 0.08), materials["light_concrete"], rz=angle,
            col=col, derived=n["id"],
        )


def add_front_entry(materials: dict, col) -> None:
    cube("front_entry_deck", (7.70, -0.78, 0.12), (3.35, 1.55, 0.22), materials["paving"], col=col, derived="door_g_main")
    cube("front_entry_canopy", (7.70, -0.92, 2.78), (3.55, 1.85, 0.16), materials["light_concrete"], col=col, derived="door_g_main")
    for x in (6.08, 9.32):
        cube(f"front_column_{x:.2f}", (x, -1.58, 1.40), (0.18, 0.18, 2.60), materials["charcoal"], col=col, derived="door_g_main")

    for i in range(7):
        x = 9.38 + i * 0.095
        cube(f"front_teak_fin_{i:02d}", (x, -0.13, 1.65), (0.055, 0.16, 3.05), materials["teak"], col=col, derived="door_g_main")

    cube("upper_front_frame_top", (7.55, -0.24, 6.17), (4.25, 0.22, 0.18), materials["charcoal"], col=col, derived="level_upper_200sqm")
    cube("upper_front_frame_left", (5.48, -0.24, 4.78), (0.18, 0.22, 2.95), materials["charcoal"], col=col, derived="level_upper_200sqm")
    cube("upper_front_frame_right", (9.62, -0.24, 4.78), (0.18, 0.22, 2.95), materials["charcoal"], col=col, derived="level_upper_200sqm")


def add_horizontal_bands(materials: dict, col) -> None:
    for z in (3.30, 6.40):
        cube(f"band_s_{z}", (5, -0.105, z), (10.25, 0.08, 0.12), materials["charcoal"], col=col)
        cube(f"band_n_{z}", (5, 10.105, z), (10.25, 0.08, 0.12), materials["charcoal"], col=col)
        cube(f"band_w_{z}", (-0.105, 5, z), (0.08, 10.25, 0.12), materials["charcoal"], col=col)
        cube(f"band_e_{z}", (10.105, 5, z), (0.08, 10.25, 0.12), materials["charcoal"], col=col)


def add_site_hardscape(materials: dict, col) -> None:
    cube("front_walk", (7.70, -3.15, 0.04), (1.55, 3.15, 0.08), materials["paving"], col=col)
    cube("front_drive", (2.40, -2.55, 0.035), (4.70, 4.85, 0.07), materials["driveway"], col=col)
    cube("garden_bed_left", (5.15, -2.50, 0.055), (0.85, 4.70, 0.11), materials["soil"], col=col)


def refine_existing_materials() -> None:
    replacements = {
        "MAT_Wall": ((0.93, 0.91, 0.86, 1.0), 0.72),
        "MAT_Concrete": ((0.57, 0.59, 0.60, 1.0), 0.70),
        "MAT_Wood": ((0.30, 0.13, 0.055, 1.0), 0.43),
        "MAT_Roof": ((0.11, 0.13, 0.14, 1.0), 0.48),
        "MAT_Stair": ((0.47, 0.34, 0.20, 1.0), 0.55),
    }
    for name, (rgba, rough) in replacements.items():
        m = bpy.data.materials.get(name)
        if not m:
            continue
        m.diffuse_color = rgba
        bsdf = m.node_tree.nodes.get("Principled BSDF") if m.use_nodes and m.node_tree else None
        if bsdf:
            bsdf.inputs["Base Color"].default_value = rgba
            bsdf.inputs["Roughness"].default_value = rough


def setup_visual_camera() -> None:
    scene = bpy.context.scene
    world = scene.world
    if world:
        world.color = (0.055, 0.075, 0.085)
    cam = scene.camera
    if cam:
        cam.location = (16.8, -18.8, 11.2)
        target = Vector((5.0, 4.3, 3.25))
        cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = 52
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass


def enhance(scene_data: dict) -> None:
    nodes = scene_data["nodes"]
    refine_existing_materials()
    remove_visual_zone_overlays(nodes)
    remove_base_roof()
    col = ensure_details_collection()
    materials = {
        "roof": mat("MAT_V2_Roof", (0.10, 0.12, 0.13, 1.0), roughness=0.48),
        "charcoal": mat("MAT_V2_Charcoal", (0.12, 0.15, 0.16, 1.0), roughness=0.52),
        "light_concrete": mat("MAT_V2_LightConcrete", (0.78, 0.78, 0.75, 1.0), roughness=0.72),
        "teak": mat("MAT_V2_Teak", (0.43, 0.20, 0.075, 1.0), roughness=0.46),
        "paving": mat("MAT_V2_Paving", (0.42, 0.43, 0.42, 1.0), roughness=0.82),
        "driveway": mat("MAT_V2_Driveway", (0.31, 0.33, 0.34, 1.0), roughness=0.88),
        "soil": mat("MAT_V2_Soil", (0.16, 0.105, 0.06, 1.0), roughness=0.95),
    }
    build_hip_roof(nodes, materials)
    add_window_shades(nodes, materials, col)
    add_front_entry(materials, col)
    add_horizontal_bands(materials, col)
    add_site_hardscape(materials, col)
    setup_visual_camera()
    bpy.context.scene["visual_revision"] = "v2-modern-tropical"


def main() -> None:
    a = args()
    scene_data = json.loads(a.input.read_text(encoding="utf-8"))
    base.build(scene_data)
    enhance(scene_data)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(a.output.resolve()))
    if a.export_glb:
        a.export_glb.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.gltf(
            filepath=str(a.export_glb.resolve()),
            export_format="GLB",
            export_extras=True,
        )
    if a.preview:
        a.preview.parent.mkdir(parents=True, exist_ok=True)
        bpy.context.scene.render.filepath = str(a.preview.resolve())
        bpy.ops.render.render(write_still=True)
    print(f"HOUSE_V2_BUILD_OK:{a.output}")


if __name__ == "__main__":
    main()
