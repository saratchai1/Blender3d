#!/usr/bin/env python3
"""Diagnostic-only probes for fragmented v8 Family4 pipe components.

No BOQ quantity changes here. Two conservative evidence-transfer ideas are
measured against the real drawings before either can enter production logic:
1. same-page/same-layer small geometry gaps around fittings or style breaks;
2. exact preserved CAD layer+stroke-style matches across sheets.

Schematic/detail lengths remain non-additive. Cross-sheet style matching can only
suggest a diameter class for a primary-plan component; it never contributes the
source view's length.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import fitz

import auto_boq as base
import auto_boq_v8 as v8
import auto_boq_v8_1 as v81


def component_gap_pt(a: dict[str, Any], b: dict[str, Any], segments: list[dict[str, Any]]) -> float:
    best = math.inf
    for i in a["segment_indexes"]:
        si = segments[i]
        for j in b["segment_indexes"]:
            sj = segments[j]
            for endpoint in (si["a"], si["b"]):
                best = min(best, v8.distance_point_segment(endpoint, sj["a"], sj["b"]))
            for endpoint in (sj["a"], sj["b"]):
                best = min(best, v8.distance_point_segment(endpoint, si["a"], si["b"]))
            if best <= 1e-9:
                return 0.0
    return best


def _tag_classes(tags: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    by_component: dict[int, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    for tag in tags:
        cid = tag.get("component_id")
        if cid is None or not tag.get("diameter_key"):
            continue
        key = (str(tag["system"]), str(tag["diameter_key"]))
        by_component[int(cid)][key] = {
            "system": tag["system"],
            "diameter_key": tag["diameter_key"],
            "dn": tag.get("dn"),
            "diameter_mm": tag.get("diameter_mm"),
            "diameter_in": tag.get("diameter_in"),
        }
    return {cid: [classes[k] for k in sorted(classes)] for cid, classes in by_component.items()}


def _style_key(component: dict[str, Any]) -> str:
    style = component["style"]
    return json.dumps({
        "layer": str(style.get("layer") or ""),
        "width_pt": round(float(style.get("width_pt") or 0.0), 3),
        "color": style.get("color"),
        "dash": str(style.get("dash") or "solid"),
    }, sort_keys=True, separators=(",", ":"))


def analyze_page(page: fitz.Page, spec: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    bounds = spec.get("bounds_pt")
    min_len = float(cfg.get("min_segment_pt", 3.0))
    max_width = float(cfg.get("max_stroke_width_pt", 3.0))
    snap = float(cfg.get("endpoint_snap_pt", 1.5))
    tag_snap = float(cfg.get("tag_snap_max_pt", 30.0))
    scale = int(spec["scale_ratio"]) if spec.get("scale_ratio") else None

    segments = v8.line_segments(page, bounds, min_len, max_width)
    components, component_by_segment = v8.style_components(segments, snap)
    tags = v81.pipe_tag_anchors(page, bounds)
    v81._associate_tags(tags, segments, component_by_segment, v8.declared_layers(page), tag_snap)
    classes_by_component = _tag_classes(tags)
    semantic = [c for c in components if c.get("layer") in v8.SEMANTIC_PIPE_LAYERS]
    seeded = [c for c in semantic if int(c["id"]) in classes_by_component]
    unseeded = [c for c in semantic if int(c["id"]) not in classes_by_component]

    candidates: list[dict[str, Any]] = []
    for component in unseeded:
        same_layer = [s for s in seeded if s.get("layer") == component.get("layer")]
        ranked: list[tuple[float, dict[str, Any]]] = []
        for seed in same_layer:
            ranked.append((component_gap_pt(component, seed, segments), seed))
        ranked.sort(key=lambda item: (item[0], int(item[1]["id"])))
        if not ranked:
            continue
        best_gap, best_seed = ranked[0]
        best_classes = classes_by_component[int(best_seed["id"])]
        second_gap = ranked[1][0] if len(ranked) > 1 else None
        competing_classes = []
        if len(ranked) > 1 and second_gap is not None and abs(second_gap - best_gap) <= 1.5:
            competing_classes = classes_by_component[int(ranked[1][1]["id"])]
        row = {
            "component_id": int(component["id"]),
            "layer": component.get("layer"),
            "style_key": _style_key(component),
            "segment_count": int(component["segment_count"]),
            "length_pt": round(float(component["length_pt"]), 3),
            "bbox_pt": [round(float(v), 2) for v in component["bbox_pt"]],
            "nearest_seed_component_id": int(best_seed["id"]),
            "nearest_seed_classes": best_classes,
            "gap_pt": round(float(best_gap), 3),
            "second_seed_gap_pt": round(float(second_gap), 3) if second_gap is not None else None,
            "competing_classes_within_1_5pt": competing_classes,
        }
        if scale:
            row["gap_m_real"] = round(float(best_gap) / 72.0 * 0.0254 * scale, 4)
            row["length_m_candidate"] = round(float(component["length_pt"]) / 72.0 * 0.0254 * scale, 3)
        candidates.append(row)

    candidates.sort(key=lambda row: (row["gap_pt"], -row["length_pt"], row["component_id"]))
    thresholds = [0.25, 0.5, 1.0, 1.5, 3.0, 6.0, 10.0, 15.0, 30.0]
    total_semantic_pt = sum(float(c["length_pt"]) for c in semantic)
    seeded_pt = sum(float(c["length_pt"]) for c in seeded)
    threshold_summary = []
    for threshold in thresholds:
        eligible = [
            row for row in candidates
            if float(row["gap_pt"]) <= threshold
            and len(row["nearest_seed_classes"]) == 1
            and not row["competing_classes_within_1_5pt"]
        ]
        bridge_pt = sum(float(row["length_pt"]) for row in eligible)
        threshold_summary.append({
            "gap_threshold_pt": threshold,
            "eligible_components": len(eligible),
            "eligible_length_pt": round(bridge_pt, 3),
            "potential_coverage_fraction": round((seeded_pt + bridge_pt) / total_semantic_pt, 4) if total_semantic_pt else 0.0,
        })

    style_seed_evidence = [{
        "component_id": int(component["id"]),
        "layer": component.get("layer"),
        "style_key": _style_key(component),
        "classes": classes_by_component[int(component["id"])],
        "length_pt": round(float(component["length_pt"]), 3),
    } for component in seeded]
    unseeded_style_components = [{
        "component_id": int(component["id"]),
        "layer": component.get("layer"),
        "style_key": _style_key(component),
        "segment_count": int(component["segment_count"]),
        "length_pt": round(float(component["length_pt"]), 3),
        "bbox_pt": [round(float(v), 2) for v in component["bbox_pt"]],
    } for component in unseeded]

    return {
        "page": int(spec["page"]),
        "sheet": spec.get("sheet"),
        "view_role": spec.get("view_role"),
        "contribution_policy": spec.get("contribution_policy"),
        "scale_ratio": scale,
        "semantic_component_count": len(semantic),
        "seeded_component_count": len(seeded),
        "unseeded_component_count": len(unseeded),
        "semantic_length_pt": round(total_semantic_pt, 3),
        "seeded_component_length_pt": round(seeded_pt, 3),
        "seeded_component_fraction": round(seeded_pt / total_semantic_pt, 4) if total_semantic_pt else 0.0,
        "threshold_summary": threshold_summary,
        "nearest_seed_candidates": candidates,
        "style_seed_evidence": style_seed_evidence,
        "unseeded_style_components": unseeded_style_components,
    }


def apply_global_style_probe(pages: list[dict[str, Any]]) -> dict[str, Any]:
    observed: dict[str, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    sheets_by_style: dict[str, set[str]] = defaultdict(set)
    for page in pages:
        for seed in page["style_seed_evidence"]:
            style_key = seed["style_key"]
            sheets_by_style[style_key].add(str(page.get("sheet") or page["page"]))
            for cls in seed["classes"]:
                key = (str(cls["system"]), str(cls["diameter_key"]))
                observed[style_key][key] = cls

    style_catalog = []
    for style_key, classes in observed.items():
        style_catalog.append({
            "style_key": style_key,
            "classes": [classes[k] for k in sorted(classes)],
            "source_sheets": sorted(sheets_by_style[style_key]),
            "status": "UNIQUE_CLASS" if len(classes) == 1 else "CONFLICTING_CLASSES",
        })
    style_catalog.sort(key=lambda row: row["style_key"])

    unique_map = {
        style_key: next(iter(classes.values()))
        for style_key, classes in observed.items()
        if len(classes) == 1
    }
    class_count_map = {style_key: len(classes) for style_key, classes in observed.items()}
    for page in pages:
        eligible = []
        conflicts = []
        for component in page["unseeded_style_components"]:
            style_key = component["style_key"]
            if style_key in unique_map:
                eligible.append({**component, "transferred_class": unique_map[style_key], "source_sheets": sorted(sheets_by_style[style_key])})
            elif class_count_map.get(style_key, 0) > 1:
                conflicts.append({**component, "candidate_class_count": class_count_map[style_key], "source_sheets": sorted(sheets_by_style[style_key])})
        eligible_pt = sum(float(row["length_pt"]) for row in eligible)
        total_pt = float(page["semantic_length_pt"])
        seeded_pt = float(page["seeded_component_length_pt"])
        page["exact_global_style_transfer"] = {
            "eligible_component_count": len(eligible),
            "eligible_length_pt": round(eligible_pt, 3),
            "potential_coverage_fraction": round((seeded_pt + eligible_pt) / total_pt, 4) if total_pt else 0.0,
            "conflicting_style_component_count": len(conflicts),
            "eligible_components": eligible,
            "conflicting_style_components": conflicts,
            "publication_status": "DIAGNOSTIC_ONLY_NO_ASSIGNMENT",
        }
    return {
        "style_catalog": style_catalog,
        "unique_style_count": sum(1 for row in style_catalog if row["status"] == "UNIQUE_CLASS"),
        "conflicting_style_count": sum(1 for row in style_catalog if row["status"] == "CONFLICTING_CLASSES"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--profile", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    cfg = profile.get("sanitary_pipe_network", {})
    doc = fitz.open(args.pdf)
    guarded = base.GuardedPdf(doc, int(profile["source_page_max"]))
    pages = [analyze_page(guarded.page(int(spec["page"])), spec, cfg) for spec in cfg.get("page_specs", [])]
    doc.close()
    style_probe = apply_global_style_probe(pages)
    result = {
        "status": "DIAGNOSTIC_ONLY_NO_QUANTITY_CHANGE",
        "purpose": "measure same-layer gaps and exact global CAD-style diameter transfer before enabling either bridge",
        "global_style_probe": style_probe,
        "pages": pages,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("AUTO_BOQ_V8_GAP_PROBE_OK", json.dumps({
        p["sheet"]: {
            "seeded_fraction": p["seeded_component_fraction"],
            "gap_6pt": next(x["potential_coverage_fraction"] for x in p["threshold_summary"] if x["gap_threshold_pt"] == 6.0),
            "gap_10pt": next(x["potential_coverage_fraction"] for x in p["threshold_summary"] if x["gap_threshold_pt"] == 10.0),
            "exact_global_style": p["exact_global_style_transfer"]["potential_coverage_fraction"],
        }
        for p in pages
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
