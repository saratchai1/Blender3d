#!/usr/bin/env python3
"""v8 extension: source-page-only sanitary pipe-network diagnostics.

This stage deliberately does NOT publish pipe-length BOQ rows. It reads vector
linework and nearby diameter/system tags from drawing pages only, groups open CAD
segments by stroke style and real endpoint/T-junction connectivity, and reports
candidate network lengths only when a single sheet scale is stated. The official
BOQ reference remains scorer-only and is never imported here.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import fitz

import auto_boq as base
from auto_boq_v7 import extract as extract_v7

SCHEMA = base.SCHEMA
PIPE_SYSTEMS = ("CW", "W", "SW", "V", "RL")
TAG_RX = re.compile(
    r'(?:Ø|DIA\.?\s*)?(?P<dia>\d+(?:-\d+/\d+|/\d+|\.\d+)?)\s*["”″]?\s*'
    r'(?P<system>CW|SW|RL|W|V)(?![A-Z])',
    re.IGNORECASE,
)
SCALE_RX = re.compile(r"(?i)SCALE[^\n\r]{0,40}?1\s*[:/]\s*(\d{1,4})")


def _point(value: Any) -> tuple[float, float]:
    if hasattr(value, "x"):
        return float(value.x), float(value.y)
    return float(value[0]), float(value[1])


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _midpoint(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2


def _inside(point: tuple[float, float], bounds: list[float] | None) -> bool:
    if not bounds:
        return True
    x0, y0, x1, y1 = map(float, bounds)
    return x0 <= point[0] <= x1 and y0 <= point[1] <= y1


def _color(value: Any) -> tuple[float, float, float] | None:
    if not value:
        return None
    return tuple(round(float(x), 3) for x in value[:3])


def _segment_key(
    a: tuple[float, float],
    b: tuple[float, float],
    width: float,
    color: tuple[float, float, float] | None,
) -> tuple[Any, ...]:
    aa = (round(a[0], 2), round(a[1], 2))
    bb = (round(b[0], 2), round(b[1], 2))
    lo, hi = sorted((aa, bb))
    return lo, hi, round(width, 2), color


def line_segments(
    page: fitz.Page,
    bounds: list[float] | None = None,
    min_len_pt: float = 3.0,
    max_width_pt: float = 3.0,
) -> list[dict[str, Any]]:
    """Return unique OPEN straight vector segments only.

    Closed paths are intentionally excluded because on sanitary sheets they are
    usually symbols, fixtures, bubbles, or frames rather than pipe centre-lines.
    Curves are withheld in v8 instead of flattening them into invented pipe runs.
    """
    out: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for path_index, drawing in enumerate(page.get_drawings() or []):
        if drawing.get("closePath"):
            continue
        width = float(drawing.get("width") or 0.0)
        if width > max_width_pt:
            continue
        color = _color(drawing.get("color"))
        for item in drawing.get("items") or []:
            if not item or item[0] != "l":
                continue
            a, b = _point(item[1]), _point(item[2])
            length = _distance(a, b)
            if length < min_len_pt or not _inside(_midpoint(a, b), bounds):
                continue
            key = _segment_key(a, b, width, color)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "a": a,
                "b": b,
                "length_pt": length,
                "width_pt": width,
                "color": color,
                "path_index": path_index,
            })
    return out


def _style(segment: dict[str, Any]) -> tuple[Any, ...]:
    return round(float(segment["width_pt"]), 2), segment["color"]


def distance_point_segment(
    point: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    wx, wy = point[0] - a[0], point[1] - a[1]
    denom = vx * vx + vy * vy
    if denom <= 1e-12:
        return _distance(point, a)
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
    projection = a[0] + t * vx, a[1] + t * vy
    return _distance(point, projection)


def style_components(
    segments: list[dict[str, Any]],
    snap_pt: float = 1.5,
) -> tuple[list[dict[str, Any]], dict[int, int]]:
    """Group same-style runs through shared endpoints and real T junctions.

    An interior/interior X crossing is NOT connected. This avoids silently
    joining two systems merely because their lines cross on a plan.
    """
    by_style: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    for index, segment in enumerate(segments):
        by_style[_style(segment)].append(index)

    components: list[dict[str, Any]] = []
    component_by_segment: dict[int, int] = {}
    for style, ids in by_style.items():
        parent = {i: i for i in ids}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        cell = max(12.0, snap_pt * 6.0)
        segment_grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        for i in ids:
            segment = segments[i]
            x0 = min(segment["a"][0], segment["b"][0]) - snap_pt
            y0 = min(segment["a"][1], segment["b"][1]) - snap_pt
            x1 = max(segment["a"][0], segment["b"][0]) + snap_pt
            y1 = max(segment["a"][1], segment["b"][1]) + snap_pt
            for gx in range(math.floor(x0 / cell), math.floor(x1 / cell) + 1):
                for gy in range(math.floor(y0 / cell), math.floor(y1 / cell) + 1):
                    segment_grid[(gx, gy)].append(i)

        for i in ids:
            for endpoint in (segments[i]["a"], segments[i]["b"]):
                key = math.floor(endpoint[0] / cell), math.floor(endpoint[1] / cell)
                for gx in range(key[0] - 1, key[0] + 2):
                    for gy in range(key[1] - 1, key[1] + 2):
                        for j in segment_grid.get((gx, gy), []):
                            if j == i:
                                continue
                            if distance_point_segment(endpoint, segments[j]["a"], segments[j]["b"]) <= snap_pt:
                                union(i, j)

        groups: dict[int, list[int]] = defaultdict(list)
        for i in ids:
            groups[find(i)].append(i)
        for members in groups.values():
            component_id = len(components)
            for i in members:
                component_by_segment[i] = component_id
            xs: list[float] = []
            ys: list[float] = []
            for i in members:
                for point in (segments[i]["a"], segments[i]["b"]):
                    xs.append(point[0])
                    ys.append(point[1])
            components.append({
                "id": component_id,
                "style": {"width_pt": style[0], "color": style[1]},
                "segment_indexes": members,
                "segment_count": len(members),
                "length_pt": sum(float(segments[i]["length_pt"]) for i in members),
                "bbox_pt": [min(xs), min(ys), max(xs), max(ys)],
            })
    return components, component_by_segment


def parse_inches(token: str) -> float:
    value = token.strip().replace(" ", "")
    if "-" in value:
        whole, fraction = value.split("-", 1)
        return float(whole) + parse_inches(fraction)
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        return float(numerator) / float(denominator)
    return float(value)


def pipe_tag_anchors(
    page: fitz.Page,
    bounds: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Read pipe size/system tags, including tags split across adjacent PDF words."""
    words = page.get_text("words") or []
    lines: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for word in words:
        block = int(word[5]) if len(word) > 5 else 0
        line = int(word[6]) if len(word) > 6 else 0
        lines[(block, line)].append(word)

    hits: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for line_words in lines.values():
        line_words.sort(key=lambda w: (float(w[0]), float(w[1])))
        for start in range(len(line_words)):
            for size in (1, 2, 3):
                chunk = line_words[start:start + size]
                if len(chunk) != size:
                    continue
                if any(float(chunk[i + 1][0]) - float(chunk[i][2]) > 10.0 for i in range(len(chunk) - 1)):
                    break
                x0 = min(float(w[0]) for w in chunk)
                y0 = min(float(w[1]) for w in chunk)
                x1 = max(float(w[2]) for w in chunk)
                y1 = max(float(w[3]) for w in chunk)
                center = (x0 + x1) / 2, (y0 + y1) / 2
                if not _inside(center, bounds):
                    continue
                raw = "".join(str(w[4]) for w in chunk).upper().replace(" ", "")
                for match in TAG_RX.finditer(raw):
                    try:
                        diameter = parse_inches(match.group("dia"))
                    except (TypeError, ValueError, ZeroDivisionError):
                        continue
                    system = match.group("system").upper()
                    key = (system, round(diameter, 4), round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
                    if key in seen:
                        continue
                    seen.add(key)
                    hits.append({
                        "text": " ".join(str(w[4]) for w in chunk),
                        "system": system,
                        "diameter_in": diameter,
                        "center_pt": center,
                        "bbox_pt": [x0, y0, x1, y1],
                    })
    return hits


def scale_candidates(page: fitz.Page) -> list[int]:
    text = page.get_text("text") or ""
    out: list[int] = []
    for match in SCALE_RX.finditer(text):
        ratio = int(match.group(1))
        if 1 <= ratio <= 2000 and ratio not in out:
            out.append(ratio)
    return out


def analyze_pipe_page(
    page: fitz.Page,
    page_no: int,
    *,
    bounds: list[float] | None = None,
    min_len_pt: float = 3.0,
    max_width_pt: float = 3.0,
    endpoint_snap_pt: float = 1.5,
    tag_snap_max_pt: float = 30.0,
    explicit_scale_ratio: int | None = None,
) -> dict[str, Any]:
    segments = line_segments(page, bounds, min_len_pt, max_width_pt)
    components, component_by_segment = style_components(segments, endpoint_snap_pt)
    tags = pipe_tag_anchors(page, bounds)

    for tag in tags:
        ranked: list[tuple[float, int]] = []
        for index, segment in enumerate(segments):
            distance = distance_point_segment(tag["center_pt"], segment["a"], segment["b"])
            if distance <= tag_snap_max_pt:
                ranked.append((distance, index))
        ranked.sort(key=lambda item: item[0])
        tag["segment_candidates"] = [
            {
                "segment_index": index,
                "component_id": component_by_segment.get(index),
                "distance_pt": round(distance, 2),
            }
            for distance, index in ranked[:5]
        ]
        if ranked:
            tag["nearest_segment"] = ranked[0][1]
            tag["distance_pt"] = round(ranked[0][0], 2)
            tag["component_id"] = component_by_segment.get(ranked[0][1])

    inferred_scales = scale_candidates(page)
    scales = [int(explicit_scale_ratio)] if explicit_scale_ratio else inferred_scales
    tags_by_component: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for tag in tags:
        component_id = tag.get("component_id")
        if component_id is not None and float(tag.get("distance_pt", 1e9)) <= tag_snap_max_pt:
            tags_by_component[int(component_id)].append(tag)

    candidate_components: list[dict[str, Any]] = []
    for component_id, component_tags in tags_by_component.items():
        component = components[component_id]
        classes = sorted({(tag["system"], float(tag["diameter_in"])) for tag in component_tags})
        row: dict[str, Any] = {
            "component_id": component_id,
            "classes": [{"system": system, "diameter_in": diameter} for system, diameter in classes],
            "segment_count": component["segment_count"],
            "length_pt": round(float(component["length_pt"]), 2),
            "bbox_pt": [round(float(value), 2) for value in component["bbox_pt"]],
            "style": component["style"],
            "tag_count": len(component_tags),
            "status": "UNAMBIGUOUS_TAG_CLASS" if len(classes) == 1 else "WITHHELD_CONFLICTING_TAGS",
        }
        if len(scales) == 1:
            ratio = scales[0]
            row["scale_ratio"] = ratio
            row["length_m"] = round(float(component["length_pt"]) / 72.0 * 0.0254 * ratio, 3)
        else:
            row["length_status"] = "WITHHELD_SCALE_AMBIGUOUS" if len(scales) > 1 else "WITHHELD_SCALE_NOT_FOUND"
        candidate_components.append(row)

    style_summary: dict[str, dict[str, Any]] = {}
    for component in components:
        style = component["style"]
        key = f"w={style['width_pt']}|c={style['color']}"
        entry = style_summary.setdefault(key, {"components": 0, "segments": 0, "length_pt": 0.0})
        entry["components"] += 1
        entry["segments"] += int(component["segment_count"])
        entry["length_pt"] += float(component["length_pt"])
    for entry in style_summary.values():
        entry["length_pt"] = round(entry["length_pt"], 2)

    return {
        "page": int(page_no),
        "bounds_pt": bounds,
        "scale_candidates": inferred_scales,
        "effective_scale_candidates": scales,
        "segment_count": len(segments),
        "component_count": len(components),
        "tag_count": len(tags),
        "tags": tags,
        "candidate_components": candidate_components,
        "style_summary": style_summary,
    }


def extract(pdf_path: Path, profile_path: Path) -> dict[str, Any]:
    result = extract_v7(pdf_path, profile_path)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    cfg = profile.get("sanitary_pipe_network", {})
    if not cfg:
        drawing_cfg = profile.get("drawing_tag_counts", {})
        pages = [int(p) for p in drawing_cfg.get("pipe_tag_inventory_pages", [])]
        cfg = {"page_specs": [{"page": page} for page in pages]}
    page_specs = cfg.get("page_specs", [])
    if not page_specs:
        return result

    max_page = int(profile["source_page_max"])
    doc = fitz.open(pdf_path)
    guarded = base.GuardedPdf(doc, max_page)
    analyses: list[dict[str, Any]] = []
    for spec in page_specs:
        page_no = int(spec["page"])
        analyses.append(analyze_pipe_page(
            guarded.page(page_no),
            page_no,
            bounds=spec.get("bounds_pt"),
            min_len_pt=float(cfg.get("min_segment_pt", 3.0)),
            max_width_pt=float(cfg.get("max_stroke_width_pt", 3.0)),
            endpoint_snap_pt=float(cfg.get("endpoint_snap_pt", 1.5)),
            tag_snap_max_pt=float(cfg.get("tag_snap_max_pt", 30.0)),
            explicit_scale_ratio=int(spec["scale_ratio"]) if spec.get("scale_ratio") else None,
        ))
    result["diagnostics"].append({
        "detector": "sanitary_pipe_network_v8",
        "status": "DIAGNOSTIC_ONLY_NO_QUANTITY",
        "pages": analyses,
        "systems": list(PIPE_SYSTEMS),
        "note": "v8 groups source-page vector pipe candidates by stroke style and real endpoint/T-junction connectivity. No pipe BOQ length is published until components, scale, and diameter/system attribution are validated against drawing evidence.",
    })
    for item in result["coverage"].get("withheld_detectors", []):
        if item.get("name") == "sanitary piping":
            item["reason"] = "v8 now inventories vector network components and tag-linked candidate lengths, but publication remains withheld until sheet-scale and system/diameter attribution are validated"
    doc.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = extract(args.pdf, args.profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    diag = next((d for d in result.get("diagnostics", []) if d.get("detector") == "sanitary_pipe_network_v8"), None)
    print("AUTO_BOQ_V8_OK", json.dumps({
        "rows": len(result["rows"]),
        "pipe_pages": len(diag.get("pages", [])) if diag else 0,
        "pipe_tags": sum(int(p.get("tag_count", 0)) for p in diag.get("pages", [])) if diag else 0,
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
