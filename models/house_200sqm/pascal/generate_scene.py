from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

PASCAL_SCHEMA_REF = "pascalorg/pascal-blender@feca6f28cec9378123240115d20c6cf3971588c9"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def node(node_id: str, node_type: str, name: str, parent_id: str | None, metadata: dict | None = None, **kwargs) -> dict:
    out = {
        "object": "node",
        "id": node_id,
        "type": node_type,
        "name": name,
        "parentId": parent_id,
        "visible": True,
        "metadata": metadata or {},
    }
    out.update(kwargs)
    return out


def generate(spec: dict) -> dict:
    project = spec["project"]
    site_spec = spec["site"]
    building_spec = spec["building"]
    graph: dict[str, dict] = {}

    def add(n: dict) -> dict:
        if n["id"] in graph:
            raise ValueError(f"duplicate node id: {n['id']}")
        graph[n["id"]] = n
        return n

    level_ids = [level["id"] for level in spec["levels"]]
    add(node(
        site_spec["id"], "site", f"{project['name']} Site", None,
        {"project": project["id"], "units": "m"},
        polygon={"type": "polygon", "points": site_spec["polygon"]},
        children=[building_spec["id"]],
    ))
    add(node(
        building_spec["id"], "building", project["name"], site_spec["id"],
        {
            "gross_floor_area_sqm": project["gross_floor_area_sqm"],
            "footprint_sqm": project["footprint_sqm"],
            "style": project["style"],
            "bedrooms": project["bedrooms"],
            "bathrooms": project["bathrooms"],
        },
        children=level_ids, position=[0, 0, 0], rotation=[0, 0, 0],
    ))

    for level in spec["levels"]:
        level_node = add(node(
            level["id"], "level", level["name"], building_spec["id"],
            {"gross_area_sqm": level["gross_area_sqm"], "floor_to_floor_m": project["floor_to_floor_m"]},
            children=[], level=level["level"],
            camera={
                "position": [14, 11 + level["level"] * 3.2, 14],
                "target": [5, level["level"] * project["floor_to_floor_m"], 5],
                "mode": "perspective",
            },
        ))

        footprint = [[0, 0], [project["width_m"], 0], [project["width_m"], project["depth_m"]], [0, project["depth_m"]]]
        slab = add(node(
            level["slab_id"], "slab", f"{level['name']} Slab", level["id"],
            {"gross_area_sqm": level["gross_area_sqm"]},
            polygon=footprint, holes=level.get("holes", []), elevation=0.18,
            material={"preset": "concrete"},
        ))
        ceiling_holes = level.get("holes", []) if level["level"] == 0 else []
        ceiling = add(node(
            level["ceiling_id"], "ceiling", f"{level['name']} Ceiling", level["id"], {},
            polygon=footprint, holes=ceiling_holes, height=project["wall_height_m"],
            material={"preset": "plaster"},
        ))
        level_node["children"].extend([slab["id"], ceiling["id"]])

        for wall_spec in level["walls"]:
            wall = add(node(
                wall_spec["id"], "wall", wall_spec["name"], level["id"], {},
                children=[], thickness=project["wall_thickness_m"], height=project["wall_height_m"],
                start=wall_spec["start"], end=wall_spec["end"],
                frontSide="exterior" if wall_spec.get("exterior") else "interior",
                backSide="interior", material={"preset": "plaster"},
            ))
            level_node["children"].append(wall["id"])

        for room in level["rooms"]:
            metadata = {"area_sqm": room["area_sqm"], "room_type": room["room_type"]}
            if room.get("contains_stair"):
                metadata["contains_stair"] = True
            zone = add(node(
                room["id"], "zone", room["name"], level["id"], metadata,
                polygon=room["polygon"], color="#3b82f6",
            ))
            level_node["children"].append(zone["id"])

        for opening in level["doors"]:
            wall = graph[opening["wall"]]
            door = add(node(
                opening["id"], "door", opening["name"], wall["id"],
                {"connects": opening.get("connects", [])},
                position=[opening["x"], opening["height"] / 2.0, 0], rotation=[0, 0, 0],
                side="front", wallId=wall["id"], width=opening["width"], height=opening["height"],
                frameThickness=0.05, frameDepth=0.08, threshold=False,
                hingesSide="left", swingDirection="inward", handle=True, handleHeight=1.05,
                handleSide="right", material={"preset": "wood"},
            ))
            wall["children"].append(door["id"])

        for opening in level["windows"]:
            wall = graph[opening["wall"]]
            window = add(node(
                opening["id"], "window", opening["name"], wall["id"], {},
                position=[opening["x"], opening["y"], 0], rotation=[0, 0, 0], side="front",
                wallId=wall["id"], width=opening["width"], height=opening["height"],
                frameThickness=0.05, frameDepth=0.08, columnRatios=[1, 1], rowRatios=[1],
                columnDividerThickness=0.03, rowDividerThickness=0.03,
                sill=True, sillDepth=0.10, sillThickness=0.03, material={"preset": "glass"},
            ))
            wall["children"].append(window["id"])

    upper_level = max(spec["levels"], key=lambda item: item["level"])
    roof_spec = spec["roof"]
    roof = add(node(
        roof_spec["id"], "roof", "Main Gable Roof", upper_level["id"],
        {"style": project["style"]}, position=[5, project["wall_height_m"], 5], rotation=0,
        children=[roof_spec["segment_id"]], material={"preset": "concrete"},
    ))
    graph[upper_level["id"]]["children"].append(roof["id"])
    add(node(
        roof_spec["segment_id"], "roof-segment", "Main Gable Roof Segment", roof["id"], {},
        position=[0, 0, 0], rotation=0, roofType=roof_spec["roof_type"],
        width=roof_spec["width"], depth=roof_spec["depth"], wallHeight=roof_spec["wall_height"],
        roofHeight=roof_spec["roof_height"], wallThickness=0.1, deckThickness=0.1,
        overhang=roof_spec["overhang"], shingleThickness=0.05, material={"preset": "tile"},
    ))

    return {
        "schemaVersion": "pascal-house-poc-1",
        "nodes": graph,
        "rootNodeIds": [site_spec["id"]],
        "metadata": {
            "title": project["name"],
            "gross_floor_area_sqm": project["gross_floor_area_sqm"],
            "levels": len(spec["levels"]),
            "source": "saratchai1/Blender3d",
            "pascal_schema_reference": PASCAL_SCHEMA_REF,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate native Pascal scene JSON for the 200 sqm house POC")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scene = generate(load_json(args.spec))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scene, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(scene['nodes'])} Pascal nodes -> {args.output}")


if __name__ == "__main__":
    main()
