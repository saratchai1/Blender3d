from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import fitz

import auto_boq as base
import auto_boq_v8 as v8


POINT_TOLERANCE_PT = 1e-4
QUANTITY_TOLERANCE_M = 0.001


def _pt(value: Any) -> float:
    return round(float(value), 6)


def _assignment_class(assignment: dict[str, Any]) -> dict[str, Any] | None:
    classes = list(assignment.get("classes") or [])
    if len(classes) != 1 or str(assignment.get("status") or "").startswith("WITHHELD"):
        return None
    return classes[0]


def _raw_segment_record(
    *,
    page_no: int,
    segment_index: int,
    segment: dict[str, Any],
    source_role: str,
    publish_reason: str,
    system: str,
    diameter_key: str,
    assignment: dict[str, Any] | None = None,
    scale_ratio: int | None = None,
) -> dict[str, Any]:
    a = segment["a"]
    b = segment["b"]
    row: dict[str, Any] = {
        "page": int(page_no),
        "segment_index": int(segment_index),
        "path_index": int(segment.get("path_index", -1)),
        "x0_pt": _pt(a[0]),
        "y0_pt": _pt(a[1]),
        "x1_pt": _pt(b[0]),
        "y1_pt": _pt(b[1]),
        "length_pt": _pt(segment["length_pt"]),
        "layer": str(segment.get("layer") or ""),
        "layer_raw": str(segment.get("layer_raw") or ""),
        "system": str(system),
        "diameter_key": str(diameter_key),
        "source_role": str(source_role),
        "publish_reason": str(publish_reason),
    }
    if assignment is not None:
        row["component_id"] = int(assignment.get("component_id", -1))
        row["assignment_status"] = str(assignment.get("status") or "")
        row["assignment_classes"] = deepcopy(list(assignment.get("classes") or []))
    if scale_ratio is not None:
        ratio = int(scale_ratio)
        row["scale_ratio"] = ratio
        row["segment_length_m"] = round(float(segment["length_pt"]) / 72.0 * 0.0254 * ratio, 6)
        row["quantity_basis"] = "PRIMARY_PLAN_VECTOR_SEGMENT_AT_VALIDATED_SCALE"
    else:
        row["quantity_basis"] = "SOURCE_STROKE_ONLY_RUN_QUANTITY_IS_CALIBRATED_AT_RUN_LEVEL"
    return row


def _matching_page_spec(cfg: dict[str, Any], page_no: int) -> dict[str, Any]:
    for spec in cfg.get("page_specs") or []:
        if int(spec.get("page") or 0) == int(page_no):
            return spec
    raise ValueError(f"missing sanitary pipe page spec for p.{page_no}")


def _rehydrate_page_segments(
    guarded: base.GuardedPdf,
    cfg: dict[str, Any],
    page_no: int,
    *,
    bounds: list[float] | None,
) -> list[dict[str, Any]]:
    return v8.line_segments(
        guarded.page(int(page_no)),
        bounds,
        float(cfg.get("min_segment_pt", 3.0)),
        float(cfg.get("max_stroke_width_pt", 3.0)),
    )


def _horizontal_evidence(
    guarded: base.GuardedPdf,
    cfg: dict[str, Any],
    diag: dict[str, Any],
    release_rows: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    wanted = {(str(r.get("system") or ""), str(r.get("diameter_key") or "")) for r in release_rows}
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {key: [] for key in wanted}
    page_totals: dict[tuple[str, str], dict[int, float]] = {key: {} for key in wanted}

    for page_analysis in diag.get("pages") or []:
        if str(page_analysis.get("contribution_policy") or "") != "PRIMARY_PLAN_HORIZONTAL":
            continue
        page_no = int(page_analysis.get("page") or 0)
        spec = _matching_page_spec(cfg, page_no)
        segments = _rehydrate_page_segments(guarded, cfg, page_no, bounds=spec.get("bounds_pt"))
        scales = [int(x) for x in (page_analysis.get("effective_scale_candidates") or [])]
        if len(scales) != 1:
            errors.append({
                "kind": "HORIZONTAL_EXACT_EVIDENCE_SCALE_MISMATCH",
                "page": page_no,
                "effective_scale_candidates": scales,
            })
            continue
        scale_ratio = scales[0]
        assignments = page_analysis.get("diameter_assignments") or []
        for assignment in assignments:
            cls = _assignment_class(assignment)
            if cls is None:
                continue
            key = (str(cls.get("system") or ""), str(cls.get("diameter_key") or ""))
            if key not in wanted:
                continue
            try:
                index = int(assignment["segment_index"])
                segment = segments[index]
            except (KeyError, TypeError, ValueError, IndexError):
                errors.append({
                    "kind": "HORIZONTAL_EXACT_EVIDENCE_BAD_SEGMENT_INDEX",
                    "page": page_no,
                    "segment_index": assignment.get("segment_index"),
                    "system": key[0],
                    "diameter_key": key[1],
                })
                continue
            expected_length = float(assignment.get("length_pt") or 0.0)
            actual_length = float(segment.get("length_pt") or 0.0)
            if abs(expected_length - actual_length) > POINT_TOLERANCE_PT:
                errors.append({
                    "kind": "HORIZONTAL_EXACT_EVIDENCE_LENGTH_IDENTITY_MISMATCH",
                    "page": page_no,
                    "segment_index": index,
                    "assignment_length_pt": expected_length,
                    "rehydrated_length_pt": actual_length,
                })
                continue
            expected_layer = str(assignment.get("layer") or "")
            actual_layer = str(segment.get("layer") or "")
            if expected_layer != actual_layer:
                errors.append({
                    "kind": "HORIZONTAL_EXACT_EVIDENCE_LAYER_IDENTITY_MISMATCH",
                    "page": page_no,
                    "segment_index": index,
                    "assignment_layer": expected_layer,
                    "rehydrated_layer": actual_layer,
                })
                continue
            by_key[key].append(_raw_segment_record(
                page_no=page_no,
                segment_index=index,
                segment=segment,
                assignment=assignment,
                scale_ratio=scale_ratio,
                source_role="PRIMARY_PLAN_HORIZONTAL",
                publish_reason=str(assignment.get("status") or "ASSIGNED_PRIMARY_PLAN_SEGMENT"),
                system=key[0],
                diameter_key=key[1],
            ))
            page_totals[key][page_no] = page_totals[key].get(page_no, 0.0) + actual_length

    for release_row in release_rows:
        key = (str(release_row.get("system") or ""), str(release_row.get("diameter_key") or ""))
        expected_m = round(float(release_row.get("horizontal_length_m") or 0.0), 3)
        reconciled_pages: list[float] = []
        for page_no, total_pt in sorted(page_totals.get(key, {}).items()):
            page_analysis = next(p for p in diag.get("pages") or [] if int(p.get("page") or 0) == page_no)
            scales = [int(x) for x in (page_analysis.get("effective_scale_candidates") or [])]
            if len(scales) == 1:
                reconciled_pages.append(round(round(total_pt, 3) / 72.0 * 0.0254 * scales[0], 3))
        actual_m = round(sum(reconciled_pages), 3)
        release_row["published_segments"] = sorted(
            by_key.get(key, []),
            key=lambda x: (int(x["page"]), int(x["segment_index"])),
        )
        release_row["exact_horizontal_length_m"] = actual_m
        release_row["exact_horizontal_segment_count"] = len(release_row["published_segments"])
        if expected_m > 0.0 and not release_row["published_segments"]:
            errors.append({
                "kind": "HORIZONTAL_EXACT_EVIDENCE_MISSING",
                "system": key[0],
                "diameter_key": key[1],
                "expected_m": expected_m,
            })
        if abs(actual_m - expected_m) > QUANTITY_TOLERANCE_M:
            errors.append({
                "kind": "HORIZONTAL_EXACT_EVIDENCE_QUANTITY_MISMATCH",
                "system": key[0],
                "diameter_key": key[1],
                "expected_m": expected_m,
                "exact_reconciled_m": actual_m,
            })
    return by_key


def _vertical_source_segments(
    *,
    page_no: int,
    segments: list[dict[str, Any]],
    assignment_by_index: dict[int, dict[str, Any]],
    run: dict[str, Any],
    publish_reason: str,
    errors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    system = str(run.get("system") or "")
    diameter_key = str(run.get("diameter_key") or "")
    for raw_index in run.get("segment_indexes") or []:
        index = int(raw_index)
        if not 0 <= index < len(segments):
            errors.append({
                "kind": "VERTICAL_EXACT_EVIDENCE_BAD_SEGMENT_INDEX",
                "page": page_no,
                "segment_index": index,
                "system": system,
                "diameter_key": diameter_key,
            })
            continue
        segment = segments[index]
        assignment = assignment_by_index.get(index)
        if assignment is not None:
            expected_length = float(assignment.get("length_pt") or 0.0)
            actual_length = float(segment.get("length_pt") or 0.0)
            if abs(expected_length - actual_length) > POINT_TOLERANCE_PT:
                errors.append({
                    "kind": "VERTICAL_EXACT_EVIDENCE_LENGTH_IDENTITY_MISMATCH",
                    "page": page_no,
                    "segment_index": index,
                    "assignment_length_pt": expected_length,
                    "rehydrated_length_pt": actual_length,
                })
                continue
        out.append(_raw_segment_record(
            page_no=page_no,
            segment_index=index,
            segment=segment,
            assignment=assignment,
            source_role="SN-04_VERTICAL_SCHEMATIC_SOURCE_STROKE",
            publish_reason=publish_reason,
            system=system,
            diameter_key=diameter_key,
        ))
    return out


def _vertical_evidence(
    guarded: base.GuardedPdf,
    cfg: dict[str, Any],
    diag: dict[str, Any],
    vertical: dict[str, Any],
    release_rows: list[dict[str, Any]],
    release: dict[str, Any],
    errors: list[dict[str, Any]],
) -> None:
    page_analysis = next(
        (p for p in diag.get("pages") or [] if str(p.get("view_role") or "") == "vertical_schematic"),
        None,
    )
    if page_analysis is None:
        errors.append({"kind": "VERTICAL_EXACT_EVIDENCE_SOURCE_PAGE_MISSING"})
        return
    page_no = int(page_analysis.get("page") or 0)
    segments = _rehydrate_page_segments(guarded, cfg, page_no, bounds=None)
    assignment_by_index = {
        int(a["segment_index"]): a
        for a in page_analysis.get("diameter_assignments") or []
        if a.get("segment_index") is not None
    }

    runs_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for run in vertical.get("candidate_runs") or []:
        key = (str(run.get("system") or ""), str(run.get("diameter_key") or ""))
        record = {
            "source_page": page_no,
            "system": key[0],
            "diameter_key": key[1],
            "dn": run.get("dn"),
            "published_vertical_length_m": round(float(run.get("vertical_length_m_candidate") or 0.0), 3),
            "measured_vertical_span_m": round(float(run.get("vertical_span_m") or 0.0), 3),
            "classification_status": str(run.get("classification_status") or ""),
            "source_role": "SN-04_VALIDATED_PHYSICAL_VERTICAL",
            "publish_reason": str(run.get("classification_status") or "VALIDATED_VERTICAL_RUN"),
            "elevation_span_m": deepcopy(run.get("elevation_span_m")),
            "matched_level_interval_m": deepcopy(run.get("matched_level_interval_m")),
            "architectural_roof_elevation_m": run.get("architectural_roof_elevation_m"),
            "roof_evidence_source_page": run.get("roof_evidence_source_page"),
            "source_segments": _vertical_source_segments(
                page_no=page_no,
                segments=segments,
                assignment_by_index=assignment_by_index,
                run=run,
                publish_reason=str(run.get("classification_status") or "VALIDATED_VERTICAL_RUN"),
                errors=errors,
            ),
            "quantity_basis": "RUN_LEVEL_CALIBRATED_PHYSICAL_SPAN_NOT_SUM_OF_DRAWN_STROKES",
        }
        if record["published_vertical_length_m"] > 0.0 and not record["source_segments"]:
            errors.append({
                "kind": "VERTICAL_EXACT_EVIDENCE_MISSING_SOURCE_STROKES",
                "system": key[0],
                "diameter_key": key[1],
                "published_vertical_length_m": record["published_vertical_length_m"],
            })
        runs_by_key.setdefault(key, []).append(record)

    for release_row in release_rows:
        key = (str(release_row.get("system") or ""), str(release_row.get("diameter_key") or ""))
        records = runs_by_key.get(key, [])
        actual_m = round(sum(float(x.get("published_vertical_length_m") or 0.0) for x in records), 3)
        expected_m = round(float(release_row.get("vertical_length_m") or 0.0), 3)
        release_row["published_vertical_runs"] = records
        release_row["exact_vertical_length_m"] = actual_m
        release_row["exact_vertical_run_count"] = len(records)
        if expected_m > 0.0 and not records:
            errors.append({
                "kind": "VERTICAL_EXACT_EVIDENCE_MISSING",
                "system": key[0],
                "diameter_key": key[1],
                "expected_m": expected_m,
            })
        if abs(actual_m - expected_m) > QUANTITY_TOLERANCE_M:
            errors.append({
                "kind": "VERTICAL_EXACT_EVIDENCE_QUANTITY_MISMATCH",
                "system": key[0],
                "diameter_key": key[1],
                "expected_m": expected_m,
                "exact_reconciled_m": actual_m,
            })

    excluded_records: list[dict[str, Any]] = []
    for run in release.get("excluded_non_quantity_runs") or []:
        reason = str(run.get("release_exclusion_status") or "EXCLUDED_FROM_QUANTITY")
        excluded_records.append({
            "source_page": page_no,
            "system": str(run.get("system") or ""),
            "diameter_key": str(run.get("diameter_key") or ""),
            "quantity_added_m": 0.0,
            "source_role": "SN-04_VERTICAL_SCHEMATIC_EXCLUDED",
            "exclude_reason": reason,
            "source_segments": _vertical_source_segments(
                page_no=page_no,
                segments=segments,
                assignment_by_index=assignment_by_index,
                run=run,
                publish_reason=reason,
                errors=errors,
            ),
        })
    release["excluded_segment_evidence"] = excluded_records


def attach_exact_pipe_segment_evidence(
    pdf_path: Path,
    profile_path: Path,
    diag: dict[str, Any],
    vertical: dict[str, Any],
    release_candidate: dict[str, Any],
) -> dict[str, Any]:
    """Attach exact source-vector coordinates to a validated pipe release.

    This function never invents geometry or changes a quantity. It rehydrates the
    exact source strokes by the detector's retained segment indexes, verifies
    segment identity against the stored assignment length/layer, and fails closed
    if the rehydrated evidence cannot reconcile to the already-computed release.

    Horizontal source strokes directly carry scaled segment length. Vertical
    source strokes are visual provenance only: the published vertical quantity is
    the run-level calibrated physical span, because dashed schematic gaps and
    explicit level/roof reconciliation are not equal to raw ink-stroke length.
    """
    out = deepcopy(release_candidate)
    if out.get("status") != "PASS_VALIDATED_PIPE_RELEASE_CANDIDATE":
        return out

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    cfg = profile.get("sanitary_pipe_network") or {}
    source_page_max = int(profile["source_page_max"])
    errors: list[dict[str, Any]] = []
    doc = fitz.open(pdf_path)
    try:
        guarded = base.GuardedPdf(doc, source_page_max)
        rows = list(out.get("candidate_rows") or [])
        _horizontal_evidence(guarded, cfg, diag, rows, errors)
        _vertical_evidence(guarded, cfg, diag, vertical, rows, out, errors)
        for row in rows:
            pages = {
                int(seg["page"])
                for seg in row.get("published_segments") or []
            }
            pages.update(
                int(seg["page"])
                for run in row.get("published_vertical_runs") or []
                for seg in run.get("source_segments") or []
            )
            if any(page > source_page_max for page in pages):
                errors.append({
                    "kind": "EXACT_EVIDENCE_OUTSIDE_GENERATION_FENCE",
                    "system": row.get("system"),
                    "diameter_key": row.get("diameter_key"),
                    "pages": sorted(pages),
                    "source_page_max": source_page_max,
                })
        out["candidate_rows"] = rows
    finally:
        doc.close()

    out["exact_segment_evidence_errors"] = errors
    if errors:
        blockers = list(out.get("release_blockers") or [])
        blockers.append({
            "release_blocker_status": "WITHHELD_EXACT_PIPE_SEGMENT_EVIDENCE_INTEGRITY",
            "error_count": len(errors),
            "errors": errors,
        })
        out["release_blockers"] = blockers
        out["release_blocker_count"] = len(blockers)
        out["status"] = "WITHHELD_EXACT_PIPE_SEGMENT_EVIDENCE_INTEGRITY"
        out["publication_policy"] = "WITHHELD_NO_PIPE_PUBLICATION"
        out["exact_segment_evidence_status"] = "WITHHELD_EXACT_SOURCE_GEOMETRY_MISMATCH"
    else:
        out["exact_segment_evidence_status"] = "PASS_EXACT_SOURCE_GEOMETRY_RECONCILED"
        out["exact_segment_evidence_contract"] = (
            "Published horizontal segments are exact source PDF vectors addressed by detector segment_index. "
            "Published vertical runs expose exact source strokes, while quantity remains the validated run-level calibrated physical span. "
            "No detail/schematic/plan view length is added outside the existing non-additive release policy."
        )
    return out
