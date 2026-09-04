from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

PREFIX = {
    "site": "site_",
    "building": "building_",
    "level": "level_",
    "wall": "wall_",
    "zone": "zone_",
    "slab": "slab_",
    "ceiling": "ceiling_",
    "roof": "roof_",
    "roof-segment": "rseg_",
    "window": "window_",
    "door": "door_",
}


def polygon_area(points: list[list[float]]) -> float:
    return abs(sum(x1 * z2 - x2 * z1 for (x1, z1), (x2, z2) in zip(points, points[1:] + points[:1]))) / 2.0


def validate(scene: dict) -> list[str]:
    errors: list[str] = []
    nodes: dict[str, dict] = scene.get("nodes", {})

    if not nodes:
        return ["scene has no nodes"]

    for root_id in scene.get("rootNodeIds", []):
        if root_id not in nodes:
            errors.append(f"missing root node: {root_id}")

    for node_id, n in nodes.items():
        if n.get("id") != node_id:
            errors.append(f"map key/id mismatch: {node_id}")
        expected = PREFIX.get(n.get("type"))
        if expected and not node_id.startswith(expected):
            errors.append(f"wrong Pascal id prefix for {node_id}: expected {expected}")
        parent = n.get("parentId")
        if parent is not None and parent not in nodes:
            errors.append(f"missing parent {parent} for {node_id}")
        for child in n.get("children", []):
            if child not in nodes:
                errors.append(f"missing child {child} referenced by {node_id}")

    levels = sorted((n for n in nodes.values() if n.get("type") == "level"), key=lambda n: n.get("level", 0))
    if len(levels) != 2:
        errors.append(f"expected 2 levels, got {len(levels)}")

    gross = sum(float(n.get("metadata", {}).get("gross_area_sqm", 0)) for n in levels)
    if not math.isclose(gross, 200.0, abs_tol=1e-6):
        errors.append(f"gross floor area must be 200 sqm, got {gross}")

    for level in levels:
        zones = [nodes[c] for c in level.get("children", []) if c in nodes and nodes[c].get("type") == "zone"]
        zone_area = sum(float(z.get("metadata", {}).get("area_sqm", polygon_area(z["polygon"]))) for z in zones)
        if not math.isclose(zone_area, 100.0, abs_tol=1e-6):
            errors.append(f"{level['id']} zone area must total 100 sqm, got {zone_area}")

    for wall in (n for n in nodes.values() if n.get("type") == "wall"):
        sx, sz = wall["start"]
        ex, ez = wall["end"]
        length = math.hypot(ex - sx, ez - sz)
        height = float(wall.get("height", 2.5))
        for child_id in wall.get("children", []):
            child = nodes.get(child_id)
            if not child or child.get("type") not in {"door", "window"}:
                continue
            if child.get("parentId") != wall["id"] or child.get("wallId") != wall["id"]:
                errors.append(f"opening {child_id} wall relationship is inconsistent")
            x, y, _ = child.get("position", [0, 0, 0])
            width = float(child.get("width", 0.9))
            opening_height = float(child.get("height", 1.5))
            if x - width / 2 < -1e-6 or x + width / 2 > length + 1e-6:
                errors.append(f"opening {child_id} falls outside wall length")
            if y - opening_height / 2 < -1e-6 or y + opening_height / 2 > height + 1e-6:
                errors.append(f"opening {child_id} falls outside wall height")
            for endpoint in child.get("metadata", {}).get("connects", []):
                if endpoint != "outside" and endpoint not in nodes:
                    errors.append(f"door {child_id} connects to missing node {endpoint}")

    project_gross = float(scene.get("metadata", {}).get("gross_floor_area_sqm", 0))
    if not math.isclose(project_gross, 200.0, abs_tol=1e-6):
        errors.append(f"scene metadata gross floor area must be 200 sqm, got {project_gross}")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the generated Pascal house scene")
    parser.add_argument("scene", type=Path)
    args = parser.parse_args()
    scene = json.loads(args.scene.read_text(encoding="utf-8"))
    errors = validate(scene)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    counts: dict[str, int] = {}
    for n in scene["nodes"].values():
        counts[n["type"]] = counts.get(n["type"], 0) + 1
    print("Pascal scene: OK")
    print("Gross floor area: 200.0 sqm")
    print("Nodes:", json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
