#!/usr/bin/env python3
"""v8.1 pipe diagnostics: diameter normalization + non-additive view reconciliation.

This remains diagnostic-only for pipe BOQ publication. It extends v8 without
changing the released v7 quantity rows. The purpose is to close two known v8
gaps safely: diameter splitting on connected CAD networks and deterministic
exclusion of overlapping schematic/detail views from additive horizontal totals.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import fitz

import auto_boq as base
import auto_boq_v8 as v8
import pipe_reconcile_v8 as reconcile

SCHEMA = base.SCHEMA


def _inside(point: tuple[float, float], bounds: list[float] | None) -> bool:
    if not bounds:
        return True
    x0, y0, x1, y1 = map(float, bounds)
    return x0 <= point[0] <= x1 and y0 <= point[1] <= y1


def _box_area(box: list[float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def pipe_tag_anchors(page: fitz.Page, bounds: list[float] | None = None) -> list[dict[str, Any]]:
    """Read diameter/system tags in either order and normalize to canonical DN keys."""
    words = page.get_text("words") or []
    lines: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for word in words:
        block = int(word[5]) if len(word) > 5 else 0
        line = int(word[6]) if len(word) > 6 else 0
        lines[(block, line)].append(word)

    raw_hits: list[dict[str, Any]] = []
    for line_words in lines.values():
        line_words.sort(key=lambda w: (float(w[0]), float(w[1])))
        for start in range(len(line_words)):
            for size in (1, 2, 3, 4):
                chunk = line_words[start:start + size]
                if len(chunk) != size:
                    continue
                if any(float(chunk[i + 1][0]) - float(chunk[i][2]) > 14.0 for i in range(len(chunk) - 1)):
                    break
                x0 = min(float(w[0]) for w in chunk)
                y0 = min(float(w[1]) for w in chunk)
                x1 = max(float(w[2]) for w in chunk)
                y1 = max(float(w[3]) for w in chunk)
                center = ((x0 + x1) / 2, (y0 + y1) / 2)
                if not _inside(center, bounds):
                    continue
                text = " ".join(str(w[4]) for w in chunk)
                for parsed in reconcile.extract_pipe_tag_classes(text):
                    raw_hits.append({
                        "text": text,
                        **parsed,
                        "expected_layer": v8.expected_layer_for_system(parsed["system"]),
                        "center_pt": center,
                        "bbox_pt": [x0, y0, x1, y1],
                    })

    hits: list[dict[str, Any]] = []
    for candidate in sorted(raw_hits, key=lambda h: (_box_area(h["bbox_pt"]), h["bbox_pt"][1], h["bbox_pt"][0])):
        duplicate = False
        for kept in hits:
            if kept["system"] != candidate["system"] or kept["diameter_key"] != candidate["diameter_key"]:
                continue
            dx = float(kept["center_pt"][0]) - float(candidate["center_pt"][0])
            dy = float(kept["center_pt"][1]) - float(candidate["center_pt"][1])
            if (dx * dx + dy * dy) ** 0.5 <= 8.0:
                duplicate = True
                break
        if not duplicate:
            hits.append(candidate)
    hits.sort(key=lambda h: (h["bbox_pt"][1], h["bbox_pt"][0], h["system"], h["diameter_key"]))
    return hits


def _associate_tags(
    tags: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    component_by_segment: dict[int, int],
    present_layers: set[str],
    max_distance_pt: float,
) -> None:
    for tag in tags:
        expected_layer = tag.get("expected_layer")
        semantic_layer_present = bool(expected_layer and expected_layer in present_layers)
        indexes = (
            [i for i, segment in enumerate(segments) if segment.get("layer") == expected_layer]
            if semantic_layer_present
            else list(range(len(segments)))
        )
        ranked: list[tuple[float, int]] = []
        for index in indexes:
            segment = segments[index]
            distance = v8.distance_point_segment(tag["center_pt"], segment["a"], segment["b"])
            if distance <= max_distance_pt:
                ranked.append((distance, index))
        ranked.sort(key=lambda item: (item[0], item[1]))
        tag["semantic_layer_present"] = semantic_layer_present
        tag["association_basis"] = "PDF_CAD_LAYER" if semantic_layer_present else "UNLAYERED_PROXIMITY_FALLBACK"
        tag["segment_candidates"] = [
            {
                "segment_index": index,
                "component_id": component_by_segment.get(index),
                "distance_pt": round(distance, 2),
                "layer": segments[index].get("layer", ""),
            }
            for distance, index in ranked[:5]
        ]
        if ranked:
            distance, index = ranked[0]
            tag["nearest_segment"] = index
            tag["component_id"] = component_by_segment.get(index)
            tag["distance_pt"] = round(distance, 2)
            tag["associated_layer"] = segments[index].get("layer", "")
            tag["association_status"] = (
                "ASSOCIATED_BY_PDF_CAD_LAYER"
                if semantic_layer_present
                else "UNLAYERED_FALLBACK_CANDIDATE"
            )
        else:
            tag["association_status"] = (
                "WITHHELD_NO_SEMANTIC_LAYER_SEGMENT_NEAR_TAG"
                if semantic_layer_present
                else "WITHHELD_NO_VECTOR_SEGMENT_NEAR_TAG"
            )


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
    baseline = v8.analyze_pipe_page(
        page,
        page_no,
        bounds=bounds,
        min_len_pt=min_len_pt,
        max_width_pt=max_width_pt,
        endpoint_snap_pt=endpoint_snap_pt,
        tag_snap_max_pt=tag_snap_max_pt,
        explicit_scale_ratio=explicit_scale_ratio,
    )
    segments = v8.line_segments(page, bounds, min_len_pt, max_width_pt)
    components, component_by_segment = v8.style_components(segments, endpoint_snap_pt)
    present_layers = v8.declared_layers(page)
    tags = pipe_tag_anchors(page, bounds)
    _associate_tags(tags, segments, component_by_segment, present_layers, tag_snap_max_pt)

    semantic_present = set(baseline.get("semantic_layers_present") or [])
    if semantic_present:
        pipe_components = [component for component in components if component.get("layer") in semantic_present]
    else:
        tagged_component_ids = {int(tag["component_id"]) for tag in tags if tag.get("component_id") is not None}
        pipe_components = [component for component in components if int(component["id"]) in tagged_component_ids]

    assignments = reconcile.assign_segment_diameters(
        segments,
        pipe_components,
        tags,
        endpoint_snap_pt=endpoint_snap_pt,
    )
    scales = baseline.get("effective_scale_candidates") or []
    scale_ratio = int(scales[0]) if len(scales) == 1 else None
    diameter_rows, diameter_coverage = reconcile.aggregate_diameter_rows(assignments, scale_ratio)

    baseline["tag_parser_version"] = "v8.1-normalized-diameter"
    baseline["tags_v8_legacy"] = baseline.get("tags", [])
    baseline["tags"] = tags
    baseline["tag_count"] = len(tags)
    baseline["diameter_assignments"] = assignments
    baseline["diameter_rows"] = diameter_rows
    baseline["diameter_coverage"] = diameter_coverage
    baseline["diameter_publication_status"] = (
        "PRIMARY_DIAMETER_GATE_CANDIDATE"
        if diameter_coverage.get("assigned_fraction", 0.0) >= 0.95 and scale_ratio
        else "WITHHELD_DIAMETER_COVERAGE_OR_SCALE"
    )
    return baseline


def extract(pdf_path: Path, profile_path: Path) -> dict[str, Any]:
    result = v8.extract(pdf_path, profile_path)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    cfg = profile.get("sanitary_pipe_network", {})
    page_specs = cfg.get("page_specs", [])
    if not page_specs:
        return result

    doc = fitz.open(pdf_path)
    guarded = base.GuardedPdf(doc, int(profile["source_page_max"]))
    analyses: list[dict[str, Any]] = []
    for spec in page_specs:
        page_no = int(spec["page"])
        analysis = analyze_pipe_page(
            guarded.page(page_no),
            page_no,
            bounds=spec.get("bounds_pt"),
            min_len_pt=float(cfg.get("min_segment_pt", 3.0)),
            max_width_pt=float(cfg.get("max_stroke_width_pt", 3.0)),
            endpoint_snap_pt=float(cfg.get("endpoint_snap_pt", 1.5)),
            tag_snap_max_pt=float(cfg.get("tag_snap_max_pt", 30.0)),
            explicit_scale_ratio=int(spec["scale_ratio"]) if spec.get("scale_ratio") else None,
        )
        for key in ("sheet", "view_role", "scale_evidence", "contribution_policy"):
            if spec.get(key) is not None:
                analysis[key] = spec[key]
        analyses.append(analysis)
    doc.close()

    reconciliation = reconcile.reconcile_pages(
        analyses,
        min_primary_diameter_coverage=float(cfg.get("min_primary_diameter_coverage", 0.95)),
    )
    result["diagnostics"].append({
        "detector": "sanitary_pipe_network_v8_1",
        "status": "DIAGNOSTIC_HORIZONTAL_CANDIDATES_NO_PUBLISHED_PIPE_ROWS",
        "pages": analyses,
        "reconciliation": reconciliation,
        "systems": list(v8.PIPE_SYSTEMS),
        "system_layer_map": v8.SYSTEM_LAYER,
        "non_additive_rule": cfg.get("non_additive_rule"),
        "note": "v8.1 normalizes inch/mm/DN diameter evidence and splits connected CAD networks by nearest network tag. Equal-distance multi-size segments are withheld rather than guessed. Only PRIMARY_PLAN_HORIZONTAL views can contribute horizontal candidates; vertical schematic and enlarged details remain evidence-only.",
    })
    for item in result["coverage"].get("withheld_detectors", []):
        if item.get("name") == "sanitary piping":
            item["reason"] = "v8.1 has deterministic horizontal non-additive reconciliation and normalized diameter splitting, but full pipe publication remains withheld until vertical risers and detail-to-primary overrides are explicitly reconciled"
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
    diag = next((d for d in result.get("diagnostics", []) if d.get("detector") == "sanitary_pipe_network_v8_1"), None)
    reconciliation = (diag or {}).get("reconciliation", {})
    print("AUTO_BOQ_V8_1_OK", json.dumps({
        "rows": len(result["rows"]),
        "pipe_pages": len((diag or {}).get("pages", [])),
        "horizontal_candidates": len(reconciliation.get("horizontal_primary_rows", [])),
        "horizontal_diameter_gate": reconciliation.get("horizontal_diameter_gate"),
        "published_pipe_rows": 0,
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
