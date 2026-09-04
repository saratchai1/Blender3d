from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


MATERIALS = {
    "wall": (0.88, 0.86, 0.80, 1.0),
    "concrete": (0.48, 0.50, 0.52, 1.0),
    "wood": (0.28, 0.12, 0.05, 1.0),
    "glass": (0.20, 0.55, 0.75, 0.28),
    "roof": (0.22, 0.24, 0.20, 1.0),
    "zone": (0.20, 0.45, 0.85, 0.12),
    "site": (0.22, 0.38, 0.18, 1.0),
    "stair": (0.52, 0.40, 0.27, 1.0),
}


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Build a Blender model from a Pascal scene graph")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--export-glb", type=Path)
    parser.add_argument("--preview", type=Path)
    return parser.parse_args(argv)


def clean_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def material(name: str, rgba: tuple[float, float, float, float]):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = rgba
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.55
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = rgba[3]
        if name == "MAT_Glass":
            if "Roughness" in bsdf.inputs:
                bsdf.inputs["Roughness"].default_value = 0.12
            if "Transmission Weight" in bsdf.inputs:
                bsdf.inputs["Transmission Weight"].default_value = 0.72
    return mat


def collection(name: str):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def move_to_collection(obj, col) -> None:
    for existing in list(obj.users_collection):
        existing.objects.unlink(obj)
    col.objects.link(obj)


def tag(obj, node: dict | None = None, *, derived_from: str | None = None) -> None:
    if node:
        obj["pascal_id"] = node["id"]
        obj["pascal_type"] = node["type"]
        obj["pascal_name"] = node.get("name", node["id"])
        obj["pascal_metadata"] = json.dumps(node.get("metadata", {}), separators=(",", ":"))
    if derived_from:
        obj["derived_from_pascal_id"] = derived_from


def empty_for(node: dict, col):
    obj = bpy.data.objects.new(node["id"], None)
    col.objects.link(obj)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.25
    tag(obj, node)
    return obj


def cube(name: str, location, dimensions, mat=None, rotation_z=0.0, parent=None, col=None, node=None, derived_from=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=(0, 0, rotation_z))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        obj.data.materials.append(mat)
    if parent:
        obj.parent = parent
    if col:
        move_to_collection(obj, col)
    tag(obj, node, derived_from=derived_from)
    return obj


def level_z(level_node: dict) -> float:
    return float(level_node.get("level", 0)) * float(level_node.get("metadata", {}).get("floor_to_floor_m", 3.2))


def wall_basis(wall: dict):
    sx, sy = wall["start"]
    ex, ey = wall["end"]
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy)
    return sx, sy, dx / length, dy / length, length, math.atan2(dy, dx)


def local_on_wall(wall: dict, x: float, z: float, base_z: float):
    sx, sy, ux, uy, _, angle = wall_basis(wall)
    return (sx + ux * x, sy + uy * x, base_z + z), angle


def merged_intervals(intervals, lo: float, hi: float):
    cleaned = sorted((max(lo, a), min(hi, b)) for a, b in intervals if b > lo and a < hi)
    out = []
    for a, b in cleaned:
        if b <= a:
            continue
        if out and a <= out[-1][1] + 1e-8:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def free_intervals(blocked, lo: float, hi: float):
    merged = merged_intervals(blocked, lo, hi)
    cursor = lo
    out = []
    for a, b in merged:
        if a > cursor:
            out.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < hi:
        out.append((cursor, hi))
    return out


def wall_openings(wall: dict, nodes: dict):
    openings = []
    for child_id in wall.get("children", []):
        child = nodes.get(child_id)
        if not child or child.get("type") not in {"door", "window"}:
            continue
        x, y, _ = child.get("position", [0, 0, 0])
        width = float(child.get("width", 0.9))
        height = float(child.get("height", 1.5))
        openings.append((x - width / 2, x + width / 2, y - height / 2, y + height / 2, child))
    return openings


def build_wall(wall: dict, nodes: dict, base_z: float, col, mats: dict):
    parent = empty_for(wall, col)
    _, _, _, _, length, angle = wall_basis(wall)
    height = float(wall.get("height", 3.0))
    thickness = float(wall.get("thickness", 0.15))
    openings = wall_openings(wall, nodes)
    cuts = sorted({0.0, length, *[max(0.0, min(length, x)) for o in openings for x in o[:2]]})
    segment_index = 0
    for xa, xb in zip(cuts, cuts[1:]):
        if xb - xa < 1e-6:
            continue
        mid = (xa + xb) / 2
        blocked = [(yb, yt) for xl, xr, yb, yt, _ in openings if xl < mid < xr]
        for yb, yt in free_intervals(blocked, 0.0, height):
            if yt - yb < 1e-6:
                continue
            loc, _ = local_on_wall(wall, mid, (yb + yt) / 2, base_z)
            cube(
                f"{wall['id']}_seg_{segment_index:02d}", loc,
                (xb - xa, thickness, yt - yb), mats["wall"], angle, parent, col,
                derived_from=wall["id"],
            )
            segment_index += 1
    return parent


def build_door(door: dict, wall: dict, base_z: float, col, mats: dict, wall_parent):
    parent = empty_for(door, col)
    parent.parent = wall_parent
    x, y, _ = door["position"]
    width, height = float(door.get("width", 0.9)), float(door.get("height", 2.1))
    loc, angle = local_on_wall(wall, x, height / 2, base_z)
    cube(f"{door['id']}_leaf", loc, (width - 0.06, 0.045, height - 0.05), mats["wood"], angle, parent, col, derived_from=door["id"])
    frame = 0.055
    for suffix, lx, lz, dx, dz in [
        ("L", x - width / 2, height / 2, frame, height),
        ("R", x + width / 2, height / 2, frame, height),
        ("T", x, height, width + frame, frame),
    ]:
        floc, _ = local_on_wall(wall, lx, lz, base_z)
        cube(f"{door['id']}_frame_{suffix}", floc, (dx, 0.10, dz), mats["wood"], angle, parent, col, derived_from=door["id"])
    return parent


def build_window(window: dict, wall: dict, base_z: float, col, mats: dict, wall_parent):
    parent = empty_for(window, col)
    parent.parent = wall_parent
    x, y, _ = window["position"]
    width, height = float(window.get("width", 1.5)), float(window.get("height", 1.5))
    angle = wall_basis(wall)[-1]
    frame = 0.055
    for suffix, lx, lz, dx, dz in [
        ("L", x - width / 2, y, frame, height),
        ("R", x + width / 2, y, frame, height),
        ("B", x, y - height / 2, width, frame),
        ("T", x, y + height / 2, width, frame),
        ("M", x, y, frame, height - 2 * frame),
    ]:
        floc, _ = local_on_wall(wall, lx, lz, base_z)
        cube(f"{window['id']}_frame_{suffix}", floc, (dx, 0.09, dz), mats["concrete"], angle, parent, col, derived_from=window["id"])
    gloc, _ = local_on_wall(wall, x, y, base_z)
    cube(f"{window['id']}_glass", gloc, (width - 2 * frame, 0.025, height - 2 * frame), mats["glass"], angle, parent, col, derived_from=window["id"])
    return parent


def rect_bounds(polygon):
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return min(xs), max(xs), min(ys), max(ys)


def point_in_rect(x, y, rect):
    xmin, xmax, ymin, ymax = rect
    return xmin < x < xmax and ymin < y < ymax


def build_rect_with_holes(node: dict, base_z: float, thickness: float, mat, col, z_offset=0.0):
    outer = rect_bounds(node["polygon"])
    holes = [rect_bounds(h) for h in node.get("holes", [])]
    xs = sorted({outer[0], outer[1], *[v for h in holes for v in h[:2]]})
    ys = sorted({outer[2], outer[3], *[v for h in holes for v in h[2:]]})
    parent = empty_for(node, col)
    idx = 0
    for xa, xb in zip(xs, xs[1:]):
        for ya, yb in zip(ys, ys[1:]):
            cx, cy = (xa + xb) / 2, (ya + yb) / 2
            if any(point_in_rect(cx, cy, hole) for hole in holes):
                continue
            cube(
                f"{node['id']}_part_{idx:02d}", (cx, cy, base_z + z_offset + thickness / 2),
                (xb - xa, yb - ya, thickness), mat, 0, parent, col, derived_from=node["id"],
            )
            idx += 1
    return parent


def build_zone(zone: dict, base_z: float, col, mats: dict):
    xmin, xmax, ymin, ymax = rect_bounds(zone["polygon"])
    parent = empty_for(zone, col)
    floor = cube(
        f"{zone['id']}_zone", ((xmin + xmax) / 2, (ymin + ymax) / 2, base_z + 0.205),
        (xmax - xmin, ymax - ymin, 0.012), mats["zone"], 0, parent, col, derived_from=zone["id"],
    )
    bpy.ops.object.text_add(location=((xmin + xmax) / 2, (ymin + ymax) / 2, base_z + 0.23))
    text = bpy.context.object
    text.name = f"{zone['id']}_label"
    text.data.body = f"{zone.get('name', zone['id'])}\n{zone.get('metadata', {}).get('area_sqm', '?')} m2"
    text.data.align_x = "CENTER"
    text.data.size = 0.30
    text.rotation_euler = (0, 0, 0)
    text.parent = parent
    move_to_collection(text, col)
    tag(text, derived_from=zone["id"])
    return parent


def build_stair(zone: dict, base_z: float, floor_to_floor: float, col, mats: dict):
    parent = bpy.data.objects.new("stair_ground_to_upper", None)
    col.objects.link(parent)
    tag(parent, derived_from=zone["id"])
    steps = 16
    rise = floor_to_floor / steps
    tread = 0.255
    width = 1.25
    x_center = 8.10
    y_start = 0.30
    for i in range(steps):
        h = rise * (i + 1)
        cube(
            f"stair_step_{i+1:02d}", (x_center, y_start + tread * i, base_z + h / 2),
            (width, tread, h), mats["stair"], 0, parent, col, derived_from=zone["id"],
        )
    return parent


def build_roof(segment: dict, upper_level_z: float, wall_height: float, col, mats: dict):
    parent = empty_for(segment, col)
    width = float(segment.get("width", 10.0))
    depth = float(segment.get("depth", 10.0))
    rise = float(segment.get("roofHeight", 2.0))
    overhang = float(segment.get("overhang", 0.8))
    half_span = width / 2 + overhang
    slope = math.hypot(half_span, rise)
    pitch = math.atan2(rise, half_span)
    roof_base = upper_level_z + wall_height + float(segment.get("wallHeight", 0.2))
    center_y = depth / 2
    for side, sign in (("left", -1), ("right", 1)):
        x = width / 2 + sign * half_span / 2
        z = roof_base + rise / 2
        obj = cube(
            f"{segment['id']}_{side}", (x, center_y, z),
            (slope, depth + 2 * overhang, 0.11), mats["roof"], 0, parent, col,
            derived_from=segment["id"],
        )
        obj.rotation_euler[1] = -sign * pitch
    return parent


def setup_camera_and_lighting(mats: dict):
    scene = bpy.context.scene
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        pass
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.color = (0.055, 0.07, 0.09)

    bpy.ops.object.light_add(type="SUN", location=(5, 5, 12))
    sun = bpy.context.object
    sun.name = "Sun"
    sun.data.energy = 2.2
    sun.rotation_euler = (math.radians(28), math.radians(-18), math.radians(32))

    bpy.ops.object.light_add(type="AREA", location=(5, -4, 10))
    area = bpy.context.object
    area.name = "Fill_Area"
    area.data.energy = 1300
    area.data.shape = "DISK"
    area.data.size = 8

    bpy.ops.object.camera_add(location=(16.5, -17.5, 12.5))
    camera = bpy.context.object
    camera.name = "House_Camera"
    target = Vector((5, 5, 3.2))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 48
    scene.camera = camera


def build(scene_data: dict):
    nodes = scene_data["nodes"]
    clean_scene()
    mats = {
        key: material(f"MAT_{key.title()}", rgba)
        for key, rgba in MATERIALS.items()
    }
    site_col = collection("00_Site")
    ground_col = collection("10_Ground")
    upper_col = collection("20_Upper")
    roof_col = collection("30_Roof")

    site = next(n for n in nodes.values() if n.get("type") == "site")
    sx0, sx1, sy0, sy1 = rect_bounds(site["polygon"]["points"])
    cube("Site_Ground", ((sx0 + sx1) / 2, (sy0 + sy1) / 2, -0.055), (sx1 - sx0, sy1 - sy0, 0.10), mats["site"], col=site_col, node=site)

    levels = sorted((n for n in nodes.values() if n.get("type") == "level"), key=lambda n: n.get("level", 0))
    wall_parents = {}
    for level in levels:
        base_z = level_z(level)
        col = ground_col if level.get("level", 0) == 0 else upper_col
        for child_id in level.get("children", []):
            n = nodes.get(child_id)
            if not n:
                continue
            if n["type"] == "slab":
                build_rect_with_holes(n, base_z, float(n.get("elevation", 0.18)), mats["concrete"], col)
            elif n["type"] == "ceiling":
                build_rect_with_holes(n, base_z, 0.05, mats["wall"], col, z_offset=float(n.get("height", 3.0)) - 0.05)
            elif n["type"] == "zone":
                build_zone(n, base_z, col, mats)
                if n.get("metadata", {}).get("contains_stair"):
                    build_stair(n, base_z + 0.18, float(level.get("metadata", {}).get("floor_to_floor_m", 3.2)), col, mats)
            elif n["type"] == "wall":
                wall_parents[n["id"]] = build_wall(n, nodes, base_z + 0.18, col, mats)

        for child_id in level.get("children", []):
            wall = nodes.get(child_id)
            if not wall or wall.get("type") != "wall":
                continue
            for opening_id in wall.get("children", []):
                opening = nodes[opening_id]
                if opening["type"] == "door":
                    build_door(opening, wall, base_z + 0.18, col, mats, wall_parents[wall["id"]])
                elif opening["type"] == "window":
                    build_window(opening, wall, base_z + 0.18, col, mats, wall_parents[wall["id"]])

    roof_segment = next((n for n in nodes.values() if n.get("type") == "roof-segment"), None)
    if roof_segment:
        build_roof(roof_segment, level_z(levels[-1]), 3.0, roof_col, mats)

    snapshot = bpy.data.texts.get("PASCAL_SCENE_JSON") or bpy.data.texts.new("PASCAL_SCENE_JSON")
    snapshot.clear()
    snapshot.write(json.dumps(scene_data, indent=2))
    setup_camera_and_lighting(mats)
    bpy.context.scene["pascal_scene_title"] = scene_data.get("metadata", {}).get("title", "")
    bpy.context.scene["gross_floor_area_sqm"] = scene_data.get("metadata", {}).get("gross_floor_area_sqm", 0)


def main() -> None:
    args = parse_args()
    scene_data = json.loads(args.input.read_text(encoding="utf-8"))
    build(scene_data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    if args.export_glb:
        args.export_glb.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.gltf(filepath=str(args.export_glb.resolve()), export_format="GLB")
    if args.preview:
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        bpy.context.scene.render.filepath = str(args.preview.resolve())
        bpy.ops.render.render(write_still=True)
    print(f"HOUSE_BUILD_OK:{args.output}")


if __name__ == "__main__":
    main()
