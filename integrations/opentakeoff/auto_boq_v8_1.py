#!/usr/bin/env python3
"""v8.1 pipe diagnostics: diameter normalization + non-additive view reconciliation.

This remains diagnostic-only for pipe BOQ publication. It extends v8 without
changing the released v7 quantity rows. Enlarged-detail matches may seed diameter
classes onto the corresponding primary-plan segment, but detail lengths are never
added to primary quantities and ambiguous/conflicting transfers are withheld.
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
import detail_view_transfer_v8 as detail_transfer
import fixture_schedule_v8 as fixture_schedule
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
            [i for i, segment in enumerate(segments) if segment["layer"] == expected_layer]
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
                "layer": segments[index]["layer"],
            }
            for distance, index in ranked[:5]
        ]
        if ranked:
            distance, index = ranked[0]
            tag["nearest_segment"] = index
            tag["component_id"] = component_by_segment.get(index)
            tag["distance_pt"] = round(distance, 2)
            tag["associated_layer"] = segments[index]["layer"]
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


def _merge_detail_transfer_tags(
    direct_tags: list[dict[str, Any]],
    extra_tags: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    component_by_segment: dict[int, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Add only unambiguous detail-derived size seeds; direct drawing tags win."""
    merged = list(direct_tags)
    events: list[dict[str, Any]] = []
    direct_by_segment_system: dict[tuple[int, str], set[str]] = defaultdict(set)
    for tag in direct_tags:
        index = tag.get("nearest_segment")
        if index is not None and tag.get("system") and tag.get("diameter_key"):
            direct_by_segment_system[(int(index), str(tag["system"]))].add(str(tag["diameter_key"]))

    grouped_extra: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for tag in extra_tags:
        try:
            index = int(tag["nearest_segment"])
        except (KeyError, TypeError, ValueError):
            events.append({**tag, "merge_status": "WITHHELD_DETAIL_SEED_NO_TARGET_SEGMENT"})
            continue
        grouped_extra[(index, str(tag.get("system") or ""))].append(tag)

    for (index, system), group in sorted(grouped_extra.items()):
        if not (0 <= index < len(segments)):
            for tag in group:
                events.append({**tag, "merge_status": "WITHHELD_DETAIL_SEED_BAD_TARGET_INDEX"})
            continue
        classes = {str(tag.get("diameter_key")) for tag in group if tag.get("diameter_key")}
        if len(classes) != 1:
            for tag in group:
                events.append({**tag, "merge_status": "WITHHELD_CONFLICTING_DETAIL_SEEDS_ON_SEGMENT"})
            continue
        detail_class = next(iter(classes))
        direct_classes = direct_by_segment_system.get((index, system), set())
        if direct_classes:
            status = "REDUNDANT_DIRECT_TAG_CONFIRMS_DETAIL" if direct_classes == {detail_class} else "WITHHELD_DETAIL_CONFLICTS_WITH_DIRECT_TAG"
            for tag in group:
                events.append({**tag, "merge_status": status, "direct_classes": sorted(direct_classes)})
            continue
        segment_layer = str(segments[index].get("layer") or "")
        expected_layer = str(group[0].get("expected_layer") or "")
        if expected_layer and segment_layer != expected_layer:
            for tag in group:
                events.append({**tag, "merge_status": "WITHHELD_DETAIL_LAYER_MISMATCH", "actual_layer": segment_layer})
            continue

        representative = dict(group[0])
        representative.update({
            "center_pt": tuple(map(float, representative.get("center_pt") or (0.0, 0.0))),
            "nearest_segment": index,
            "component_id": component_by_segment.get(index),
            "distance_pt": float(representative.get("distance_pt", 0.0)),
            "associated_layer": segment_layer,
            "semantic_layer_present": bool(expected_layer),
            "association_basis": "DETAIL_VIEW_AFFINE_TRANSFER",
            "association_status": "ASSOCIATED_BY_DETAIL_VIEW_TRANSFER",
        })
        merged.append(representative)
        events.append({**representative, "merge_status": "ACCEPTED_DETAIL_DIAMETER_SEED"})
    return merged, events


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
    extra_tags: list[dict[str, Any]] | None = None,
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
    direct_tags = pipe_tag_anchors(page, bounds)
    _associate_tags(direct_tags, segments, component_by_segment, present_layers, tag_snap_max_pt)

    semantic_present = set(baseline.get("semantic_layers_present") or [])
    if semantic_present:
        pipe_components = [component for component in components if component.get("layer") in semantic_present]
    else:
        tagged_component_ids = {int(tag["component_id"]) for tag in direct_tags if tag.get("component_id") is not None}
        pipe_components = [component for component in components if int(component["id"]) in tagged_component_ids]

    direct_assignments = reconcile.assign_segment_diameters(
        segments,
        pipe_components,
        direct_tags,
        endpoint_snap_pt=endpoint_snap_pt,
    )
    scales = baseline.get("effective_scale_candidates") or []
    scale_ratio = int(scales[0]) if len(scales) == 1 else None
    direct_rows, direct_coverage = reconcile.aggregate_diameter_rows(direct_assignments, scale_ratio)

    tags, transfer_events = _merge_detail_transfer_tags(
        direct_tags,
        extra_tags or [],
        segments,
        component_by_segment,
    )
    assignments = reconcile.assign_segment_diameters(
        segments,
        pipe_components,
        tags,
        endpoint_snap_pt=endpoint_snap_pt,
    )
    diameter_rows, diameter_coverage = reconcile.aggregate_diameter_rows(assignments, scale_ratio)

    baseline["tag_parser_version"] = "v8.1-normalized-diameter+detail-transfer"
    baseline["tags_v8_legacy"] = baseline.get("tags", [])
    baseline["tags_direct"] = direct_tags
    baseline["tag_count_direct"] = len(direct_tags)
    baseline["tags"] = tags
    baseline["tag_count"] = len(tags)
    baseline["detail_transfer_seed_events"] = transfer_events
    baseline["accepted_detail_seed_count"] = sum(1 for event in transfer_events if event.get("merge_status") == "ACCEPTED_DETAIL_DIAMETER_SEED")
    baseline["diameter_assignments_direct"] = direct_assignments
    baseline["diameter_rows_direct"] = direct_rows
    baseline["diameter_coverage_direct"] = direct_coverage
    baseline["diameter_assignments"] = assignments
    baseline["diameter_rows"] = diameter_rows
    baseline["diameter_coverage"] = diameter_coverage
    baseline["diameter_publication_status"] = (
        "PRIMARY_DIAMETER_GATE_CANDIDATE"
        if diameter_coverage.get("assigned_fraction", 0.0) >= 0.95 and scale_ratio
        else "WITHHELD_DIAMETER_COVERAGE_OR_SCALE"
    )
    return baseline


def _extra_tags_by_target_page(detail_probes: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for probe in detail_probes:
        if probe.get("status") != "DIAGNOSTIC_TRANSFER_PROBED":
            continue
        match_score = float((probe.get("match") or {}).get("match_score", 0.0))
        for candidate in probe.get("transfer_candidates", []):
            if candidate.get("status") != "DETAIL_TRANSFER_CANDIDATE":
                continue
            by_page[int(probe["target_page"])].append({
                "text": candidate.get("source_text"),
                "system": candidate.get("system"),
                "diameter_key": candidate.get("diameter_key"),
                "dn": candidate.get("dn"),
                "diameter_mm": candidate.get("diameter_mm"),
                "diameter_in": candidate.get("diameter_in"),
                "expected_layer": candidate.get("expected_layer"),
                "center_pt": tuple(map(float, candidate["predicted_target_midpoint_pt"])),
                "nearest_segment": int(candidate["target_segment_index"]),
                "distance_pt": float(candidate.get("distance_pt", 0.0)),
                "detail_id": probe.get("id"),
                "detail_page": int(probe["detail_page"]),
                "detail_match_score": match_score,
                "detail_transfer_angle_diff_deg": candidate.get("angle_diff_deg"),
                "evidence_role": "DETAIL_VIEW_DIAMETER_SEED_ONLY",
            })
    return by_page


def extract(pdf_path: Path, profile_path: Path) -> dict[str, Any]:
    result = v8.extract(pdf_path, profile_path)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    cfg = profile.get("sanitary_pipe_network", {})
    page_specs = cfg.get("page_specs", [])
    if not page_specs:
        return result

    doc = fitz.open(pdf_path)
    guarded = base.GuardedPdf(doc, int(profile["source_page_max"]))

    schedule_diag: dict[str, Any] | None = None
    schedule_cfg = cfg.get("fixture_branch_schedule")
    if schedule_cfg:
        schedule_page = int(schedule_cfg["page"])
        schedule_diag = fixture_schedule.parse_fixture_schedule_page(
            guarded.page(schedule_page),
            list(map(float, schedule_cfg["bounds_pt"])),
        )
        schedule_diag.update({
            "page": schedule_page,
            "sheet": schedule_cfg.get("sheet"),
            "evidence_role": schedule_cfg.get("evidence_role"),
            "coordinate_basis": schedule_cfg.get("coordinate_basis"),
            "publication_policy": schedule_cfg.get("publication_policy", "EVIDENCE_ONLY_NO_PIPE_LENGTH_ADDITION"),
        })

    detail_probes: list[dict[str, Any]] = []
    for link in cfg.get("detail_view_links", []):
        detail_probes.append(detail_transfer.probe_detail_transfer(
            guarded.page(int(link["detail_page"])),
            guarded.page(int(link["target_page"])),
            link,
            min_segment_pt=float(cfg.get("min_segment_pt", 3.0)),
            max_stroke_width_pt=float(cfg.get("max_stroke_width_pt", 3.0)),
            endpoint_snap_pt=float(cfg.get("endpoint_snap_pt", 1.5)),
            tag_snap_max_pt=float(cfg.get("tag_snap_max_pt", 30.0)),
            render_scale=float(cfg.get("detail_match_render_scale", 1.5)),
        ))
    extra_by_page = _extra_tags_by_target_page(detail_probes)

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
            extra_tags=extra_by_page.get(page_no, []),
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
        "fixture_branch_schedule": schedule_diag,
        "detail_view_reconciliation": detail_probes,
        "reconciliation": reconciliation,
        "systems": list(v8.PIPE_SYSTEMS),
        "system_layer_map": v8.SYSTEM_LAYER,
        "non_additive_rule": cfg.get("non_additive_rule"),
        "note": "v8.1 normalizes inch/mm/DN evidence, parses the SN-07 fixture branch-size grid, and geometrically matches enlarged bathrooms back to SN-05/SN-06. Only unambiguous detail matches may seed a diameter onto the corresponding primary-plan segment; direct primary tags always win and detail lengths are never added. Equal-distance or conflicting mappings remain withheld.",
    })
    for item in result["coverage"].get("withheld_detectors", []):
        if item.get("name") == "sanitary piping":
            item["reason"] = "v8.1 can use accepted enlarged-detail matches as primary-plan diameter seeds without adding detail length, but full pipe publication remains withheld until diameter coverage and vertical-riser reconciliation pass release gates"
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
    schedule = (diag or {}).get("fixture_branch_schedule") or {}
    detail_probes = (diag or {}).get("detail_view_reconciliation") or []
    pages = (diag or {}).get("pages") or []
    print("AUTO_BOQ_V8_1_OK", json.dumps({
        "rows": len(result["rows"]),
        "pipe_pages": len(pages),
        "fixture_schedule_connections": schedule.get("connection_count", 0),
        "detail_matches": {probe.get("id"): (probe.get("match") or {}).get("match_score") for probe in detail_probes},
        "accepted_detail_seeds": {page.get("sheet", page.get("page")): page.get("accepted_detail_seed_count", 0) for page in pages},
        "primary_coverage_direct": {page.get("sheet"): (page.get("diameter_coverage_direct") or {}).get("assigned_fraction") for page in pages if page.get("contribution_policy") == "PRIMARY_PLAN_HORIZONTAL"},
        "primary_coverage_reconciled": {page.get("sheet"): (page.get("diameter_coverage") or {}).get("assigned_fraction") for page in pages if page.get("contribution_policy") == "PRIMARY_PLAN_HORIZONTAL"},
        "horizontal_candidates": len(reconciliation.get("horizontal_primary_rows", [])),
        "horizontal_diameter_gate": reconciliation.get("horizontal_diameter_gate"),
        "published_pipe_rows": 0,
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
