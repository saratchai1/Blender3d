#!/usr/bin/env python3
"""Fail-closed generic vector-PDF sanitary takeoff inference.

This module is deliberately narrower than the validated Family4 profile engine.
It publishes only when a previously unseen PDF contains one unambiguous sanitary
PLAN page with:
- preserved semantic CAD pipe layers (CW / WASTE / SOIL / V / RL),
- an explicit sheet scale (e.g. SCALE 1:100),
- explicit pipe system + diameter tags (e.g. DN20 CW, Ø3/4\" CW), and
- enough tag-to-network evidence to classify at least 95% of semantic pipe
  linework by length.

It never reads BOQ/reference quantities. Pages that look like BOQ/reference
sheets are excluded from generation. Multiple primary plan pages, ambiguous
scales, missing semantic layers, or unresolved diameter coverage all fail closed.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import fitz

import auto_boq_v8 as v8
import pipe_reconcile_v8 as reconcile
import strict_pipe_tags_v8 as strict_tags

SCHEMA = "blender3d.auto_boq.runtime.v1"
SEMANTIC_LAYERS = set(v8.SEMANTIC_PIPE_LAYERS)
REFERENCE_RX = re.compile(
    r"\b(?:BILL\s+OF\s+QUANTIT(?:Y|IES)|BOQ|ESTIMATE|COST\s+ESTIMATE|PRICED\s+BOQ)\b",
    re.IGNORECASE,
)
PLAN_RX = re.compile(r"\bPLAN\b", re.IGNORECASE)
SCHEMATIC_RX = re.compile(r"\b(?:SCHEMATIC|RISER|DIAGRAM)\b", re.IGNORECASE)
DETAIL_RX = re.compile(r"\b(?:DETAIL|ENLARGED)\b", re.IGNORECASE)
SANITARY_RX = re.compile(r"\b(?:SANITARY|PLUMBING|WATER\s+SUPPLY|DRAINAGE)\b", re.IGNORECASE)
SCALE_RX = re.compile(r"\bSCALE\b[^\n\r]{0,48}?1\s*[:/]\s*(\d{1,4})", re.IGNORECASE)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _page_scale_candidates(text: str) -> list[int]:
    out: list[int] = []
    for match in SCALE_RX.finditer(text or ""):
        value = int(match.group(1))
        if 1 <= value <= 2000 and value not in out:
            out.append(value)
    return out


def _page_role(text: str, semantic_layers: set[str]) -> str:
    if REFERENCE_RX.search(text or ""):
        return "reference_excluded"
    if SCHEMATIC_RX.search(text or ""):
        return "vertical_schematic_non_additive"
    if DETAIL_RX.search(text or ""):
        return "detail_non_additive"
    if PLAN_RX.search(text or "") and (SANITARY_RX.search(text or "") or semantic_layers):
        return "primary_sanitary_plan"
    if semantic_layers:
        return "unclassified_semantic_pipe_page"
    return "other"


def _joined_word_chunks(page: fitz.Page) -> list[dict[str, Any]]:
    words = page.get_text("words") or []
    by_line: dict[tuple[int, int], list[Any]] = {}
    for word in words:
        key = (int(word[5]) if len(word) > 5 else 0, int(word[6]) if len(word) > 6 else 0)
        by_line.setdefault(key, []).append(word)
    chunks: list[dict[str, Any]] = []
    for line_words in by_line.values():
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
                chunks.append({
                    "text": " ".join(str(w[4]) for w in chunk),
                    "center_pt": ((x0 + x1) / 2.0, (y0 + y1) / 2.0),
                    "bbox_pt": [x0, y0, x1, y1],
                    "token_count": size,
                })
    chunks.sort(key=lambda c: (c["token_count"], c["bbox_pt"][1], c["bbox_pt"][0]))
    return chunks


def _generic_tag_anchors(
    page: fitz.Page,
    segments: list[dict[str, Any]],
    components: list[dict[str, Any]],
    component_by_segment: dict[int, int],
    *,
    max_distance_pt: float = 30.0,
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int, int]] = set()
    for chunk in _joined_word_chunks(page):
        classes = strict_tags.extract_pipe_tag_classes(chunk["text"])
        if not classes:
            continue
        for cls in classes:
            system = str(cls["system"]).upper()
            expected_layer = v8.expected_layer_for_system(system)
            if not expected_layer:
                continue
            indexes = [i for i, segment in enumerate(segments) if segment.get("layer") == expected_layer]
            if not indexes:
                continue
            ranked = []
            for index in indexes:
                segment = segments[index]
                distance = v8.distance_point_segment(chunk["center_pt"], segment["a"], segment["b"])
                if distance <= max_distance_pt:
                    ranked.append((distance, index))
            if not ranked:
                continue
            ranked.sort(key=lambda item: (item[0], item[1]))
            distance, index = ranked[0]
            key = (
                system,
                str(cls["diameter_key"]),
                int(round(float(chunk["center_pt"][0]) / 4.0)),
                int(round(float(chunk["center_pt"][1]) / 4.0)),
            )
            if key in seen:
                continue
            seen.add(key)
            hits.append({
                **cls,
                "text": chunk["text"],
                "center_pt": chunk["center_pt"],
                "bbox_pt": chunk["bbox_pt"],
                "expected_layer": expected_layer,
                "associated_layer": expected_layer,
                "association_basis": "PDF_CAD_LAYER_PLUS_EXPLICIT_TAG",
                "association_status": "ASSOCIATED_BY_GENERIC_INFERENCE",
                "nearest_segment": index,
                "component_id": component_by_segment.get(index),
                "distance_pt": round(float(distance), 3),
            })
    hits.sort(key=lambda hit: (hit["bbox_pt"][1], hit["bbox_pt"][0], hit["system"], hit["diameter_key"]))
    return hits


def _analyze_primary_page(page: fitz.Page, page_no: int, scale_ratio: int) -> dict[str, Any]:
    all_segments = v8.line_segments(page, min_len_pt=3.0, max_width_pt=3.0)
    segments = [segment for segment in all_segments if str(segment.get("layer") or "").upper() in SEMANTIC_LAYERS]
    components, component_by_segment = v8.style_components(segments, snap_pt=1.5)
    tags = _generic_tag_anchors(page, segments, components, component_by_segment)
    assignments = reconcile.assign_segment_diameters(
        segments,
        components,
        tags,
        endpoint_snap_pt=1.5,
        tie_tolerance_pt=0.5,
    )
    rows, coverage = reconcile.aggregate_diameter_rows(assignments, scale_ratio)
    return {
        "page": page_no,
        "scale_ratio": scale_ratio,
        "semantic_layers": sorted({str(s.get("layer") or "") for s in segments}),
        "segment_count": len(segments),
        "component_count": len(components),
        "tag_count": len(tags),
        "tags": tags,
        "assignments": assignments,
        "candidate_rows": rows,
        "coverage": coverage,
    }


def infer_generic_pdf(path: Path) -> dict[str, Any]:
    path = path.resolve()
    digest = _sha256(path)
    doc = fitz.open(path)
    try:
        page_catalog: list[dict[str, Any]] = []
        primary_pages: list[dict[str, Any]] = []
        excluded_reference_pages: list[int] = []
        for index in range(len(doc)):
            page_no = index + 1
            page = doc[index]
            text = page.get_text("text") or ""
            layers = {
                str(drawing.get("layer") or "").strip().upper()
                for drawing in (page.get_drawings() or [])
                if str(drawing.get("layer") or "").strip().upper() in SEMANTIC_LAYERS
            }
            role = _page_role(text, layers)
            scales = _page_scale_candidates(text)
            entry = {
                "page": page_no,
                "role": role,
                "semantic_layers": sorted(layers),
                "scale_candidates": scales,
                "text_signal": "sanitary" if SANITARY_RX.search(text) else None,
            }
            page_catalog.append(entry)
            if role == "reference_excluded":
                excluded_reference_pages.append(page_no)
            elif role == "primary_sanitary_plan":
                primary_pages.append(entry)

        blockers: list[str] = []
        if len(primary_pages) != 1:
            blockers.append(f"expected exactly one unambiguous primary sanitary plan page, found {len(primary_pages)}")
        analysis: dict[str, Any] | None = None
        if len(primary_pages) == 1:
            primary = primary_pages[0]
            if len(primary["scale_candidates"]) != 1:
                blockers.append(
                    f"primary page {primary['page']} requires exactly one explicit SCALE 1:N value; found {primary['scale_candidates']}"
                )
            if not primary["semantic_layers"]:
                blockers.append(f"primary page {primary['page']} has no preserved semantic CAD pipe layers")
            if not blockers:
                analysis = _analyze_primary_page(
                    doc[int(primary["page"]) - 1],
                    int(primary["page"]),
                    int(primary["scale_candidates"][0]),
                )
                coverage = float(analysis["coverage"].get("assigned_fraction") or 0.0)
                if analysis["tag_count"] <= 0:
                    blockers.append("no explicit pipe system + diameter tag could be associated to a semantic CAD layer")
                if analysis["segment_count"] <= 0:
                    blockers.append("no semantic pipe linework found on the primary plan")
                if coverage < 0.95:
                    blockers.append(f"diameter-classified semantic pipe coverage {coverage:.3f} is below 0.95 release threshold")
                if not analysis["candidate_rows"]:
                    blockers.append("no pipe quantity row survived generic inference")

        source_policy = {
            "reference_used_for_generation": False,
            "reference_page_detection": "TEXT_ROLE_EXCLUSION_ONLY_NO_REFERENCE_QUANTITY_PARSE",
            "excluded_reference_pages": excluded_reference_pages,
            "generic_profile_inference": True,
            "multi_primary_plan_policy": "WITHHOLD_UNTIL_CROSS_VIEW_REVISION_RECONCILIATION",
        }

        if blockers or analysis is None:
            return {
                "schema": SCHEMA,
                "runtime_status": "WITHHELD_GENERIC_INFERENCE",
                "engine": "generic-vector-sanitary-v0",
                "profile": "inferred-not-published",
                "document": {
                    "name": path.name,
                    "sha256": digest,
                    "bytes": path.stat().st_size,
                    "pages": len(doc),
                },
                "rows": [],
                "coverage": {"withheld_detectors": [
                    {"name": "GENERIC-SANITARY-PIPE", "reason": reason} for reason in blockers
                ]},
                "source_policy": source_policy,
                "diagnostics": [{
                    "detector": "generic_profile_inference_v0",
                    "status": "WITHHELD_FAIL_CLOSED",
                    "page_catalog": page_catalog,
                    "primary_analysis": analysis,
                    "blockers": blockers,
                }],
            }

        rows: list[dict[str, Any]] = []
        source_page = int(analysis["page"])
        for item in analysis["candidate_rows"]:
            system = str(item["system"])
            diameter_key = str(item["diameter_key"])
            quantity = float(item.get("length_m_candidate") or 0.0)
            if quantity <= 0:
                continue
            rows.append({
                "id": f"GEN-SAN-PIPE-{system}-{diameter_key}",
                "description": f"{system} {diameter_key} sanitary pipe",
                "category": "Sanitary",
                "quantity": round(quantity, 3),
                "unit": "m",
                "confidence": 0.92,
                "source_pages": [source_page],
                "method": "generic:PDF CAD layer + explicit SCALE + explicit diameter/system tag + vector topology",
                "evidence": {
                    "release_gate_status": "PASS_GENERIC_VECTOR_PIPE_V0",
                    "scale_ratio": int(analysis["scale_ratio"]),
                    "semantic_layers": analysis["semantic_layers"],
                    "assigned_fraction": analysis["coverage"].get("assigned_fraction"),
                    "segment_count": int(item.get("segment_count") or 0),
                    "reference_used_for_generation": False,
                },
            })

        if not rows:
            return {
                "schema": SCHEMA,
                "runtime_status": "WITHHELD_GENERIC_INFERENCE",
                "engine": "generic-vector-sanitary-v0",
                "profile": "inferred-not-published",
                "document": {"name": path.name, "sha256": digest, "bytes": path.stat().st_size, "pages": len(doc)},
                "rows": [],
                "coverage": {"withheld_detectors": [{"name": "GENERIC-SANITARY-PIPE", "reason": "candidate rows converted to zero publishable quantities"}]},
                "source_policy": source_policy,
                "diagnostics": [{"detector": "generic_profile_inference_v0", "status": "WITHHELD_ZERO_ROWS", "page_catalog": page_catalog, "primary_analysis": analysis}],
            }

        return {
            "schema": SCHEMA,
            "runtime_status": "PUBLISHED_GENERIC_INFERRED_BOQ",
            "engine": "generic-vector-sanitary-v0",
            "profile": "generic-inferred-vector-sanitary-v0",
            "runtime_profile": "generic-inferred-vector-sanitary-v0",
            "document": {
                "name": path.name,
                "sha256": digest,
                "bytes": path.stat().st_size,
                "pages": len(doc),
            },
            "rows": rows,
            "coverage": {
                "generic_scope": "SANITARY_PIPE_LENGTH_ONLY",
                "assigned_fraction": analysis["coverage"].get("assigned_fraction"),
                "withheld_detectors": [
                    {"name": "GENERIC-FULL-BOQ", "reason": "generic v0 publishes only sanitary pipe length; architectural, structural, electrical and non-pipe items remain withheld until separate generic detectors are validated"}
                ],
            },
            "source_policy": source_policy,
            "diagnostics": [{
                "detector": "generic_profile_inference_v0",
                "status": "PUBLISHED_SINGLE_PRIMARY_VECTOR_SANITARY_PLAN",
                "page_catalog": page_catalog,
                "primary_analysis": analysis,
                "blockers": [],
            }],
        }
    finally:
        doc.close()


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = infer_generic_pdf(args.pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("AUTO_BOQ_GENERIC_INFERENCE", json.dumps({
        "runtime_status": result.get("runtime_status"),
        "rows": len(result.get("rows", [])),
        "profile": result.get("runtime_profile") or result.get("profile"),
        "reference_used_for_generation": result.get("source_policy", {}).get("reference_used_for_generation"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
