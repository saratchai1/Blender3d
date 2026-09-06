from __future__ import annotations

import math
from typing import Any

import cv2
import fitz
import numpy as np

import auto_boq_v8 as v8
import pipe_reconcile_v8 as diameter


def _rotated_point(page: fitz.Page, point: tuple[float, float]) -> tuple[float, float]:
    p = fitz.Point(float(point[0]), float(point[1])) * page.rotation_matrix
    return float(p.x), float(p.y)


def _unrotated_point(page: fitz.Page, point: tuple[float, float]) -> tuple[float, float]:
    p = fitz.Point(float(point[0]), float(point[1])) * page.derotation_matrix
    return float(p.x), float(p.y)


def rotated_rect_to_unrotated_bounds(page: fitz.Page, rect: list[float]) -> list[float]:
    x0, y0, x1, y1 = map(float, rect)
    points = [
        _unrotated_point(page, (x0, y0)),
        _unrotated_point(page, (x1, y0)),
        _unrotated_point(page, (x1, y1)),
        _unrotated_point(page, (x0, y1)),
    ]
    return [
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    ]


def _render_gray(page: fitz.Page, render_scale: float) -> np.ndarray:
    pix = page.get_pixmap(
        matrix=fitz.Matrix(render_scale, render_scale),
        colorspace=fitz.csGRAY,
        alpha=False,
        annots=False,
    )
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def _crop(arr: np.ndarray, rect_pt: list[float], render_scale: float) -> np.ndarray:
    x0, y0, x1, y1 = [int(round(float(v) * render_scale)) for v in rect_pt]
    x0 = max(0, min(arr.shape[1], x0)); x1 = max(0, min(arr.shape[1], x1))
    y0 = max(0, min(arr.shape[0], y0)); y1 = max(0, min(arr.shape[0], y1))
    if x1 <= x0 or y1 <= y0:
        raise ValueError("invalid rendered crop")
    return arr[y0:y1, x0:x1]


def match_detail_view(
    detail_page: fitz.Page,
    target_page: fitz.Page,
    *,
    match_rect_rotated_pt: list[float],
    target_roi_rotated_pt: list[float],
    expected_scale_ratio: float,
    render_scale: float = 1.5,
) -> dict[str, Any]:
    """Match one enlarged detail to its primary-plan ROI using edge geometry.

    Both rectangles are expressed in the human-visible rotated page coordinate
    system. The returned affine transform is scale + translation only; Family4
    bathroom details use the same orientation as their primary-plan instances.
    """
    source = _render_gray(detail_page, render_scale)
    target = _render_gray(target_page, render_scale)
    template = _crop(source, match_rect_rotated_pt, render_scale)
    roi = _crop(target, target_roi_rotated_pt, render_scale)
    resized = cv2.resize(
        template,
        None,
        fx=float(expected_scale_ratio),
        fy=float(expected_scale_ratio),
        interpolation=cv2.INTER_AREA,
    )
    template_edge = cv2.Canny(resized, 50, 150)
    roi_edge = cv2.Canny(roi, 50, 150)
    if roi_edge.shape[0] < template_edge.shape[0] or roi_edge.shape[1] < template_edge.shape[1]:
        return {
            "status": "WITHHELD_TEMPLATE_LARGER_THAN_TARGET_ROI",
            "match_score": 0.0,
        }
    response = cv2.matchTemplate(roi_edge, template_edge, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(response)
    roi_x0, roi_y0 = map(float, target_roi_rotated_pt[:2])
    top_left = (
        roi_x0 + float(location[0]) / render_scale,
        roi_y0 + float(location[1]) / render_scale,
    )
    source_x0, source_y0 = map(float, match_rect_rotated_pt[:2])
    return {
        "status": "MATCHED",
        "match_score": round(float(score), 6),
        "render_scale": float(render_scale),
        "affine_scale": float(expected_scale_ratio),
        "source_origin_rotated_pt": [source_x0, source_y0],
        "target_origin_rotated_pt": [round(top_left[0], 4), round(top_left[1], 4)],
        "template_size_rotated_pt": [
            round(float(template.shape[1]) / render_scale, 4),
            round(float(template.shape[0]) / render_scale, 4),
        ],
    }


def _transform_unrotated_point(
    detail_page: fitz.Page,
    target_page: fitz.Page,
    point: tuple[float, float],
    match: dict[str, Any],
) -> tuple[float, float]:
    source_rot = _rotated_point(detail_page, point)
    sx, sy = map(float, match["source_origin_rotated_pt"])
    tx, ty = map(float, match["target_origin_rotated_pt"])
    scale = float(match["affine_scale"])
    target_rot = (
        tx + (source_rot[0] - sx) * scale,
        ty + (source_rot[1] - sy) * scale,
    )
    return _unrotated_point(target_page, target_rot)


def _angle_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180.0


def _angle_diff_deg(a: float, b: float) -> float:
    diff = abs(float(a) - float(b)) % 180.0
    return min(diff, 180.0 - diff)


def _associate_source_tags(
    tags: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    component_by_segment: dict[int, int],
    present_layers: set[str],
    max_distance_pt: float,
) -> None:
    for tag in tags:
        expected_layer = tag.get("expected_layer") or v8.expected_layer_for_system(tag.get("system", ""))
        if expected_layer and expected_layer in present_layers:
            indexes = [i for i, segment in enumerate(segments) if segment.get("layer") == expected_layer]
            basis = "PDF_CAD_LAYER"
        else:
            indexes = list(range(len(segments)))
            basis = "UNLAYERED_PROXIMITY_FALLBACK"
        ranked = []
        for index in indexes:
            segment = segments[index]
            dist = v8.distance_point_segment(tag["center_pt"], segment["a"], segment["b"])
            if dist <= max_distance_pt:
                ranked.append((dist, index))
        ranked.sort(key=lambda item: (item[0], item[1]))
        tag["association_basis"] = basis
        if ranked:
            dist, index = ranked[0]
            tag["nearest_segment"] = index
            tag["component_id"] = component_by_segment.get(index)
            tag["distance_pt"] = round(float(dist), 3)
            tag["associated_layer"] = segments[index].get("layer", "")
            tag["association_status"] = "ASSOCIATED_FOR_DETAIL_TRANSFER"
        else:
            tag["association_status"] = "WITHHELD_NO_DETAIL_SEGMENT_NEAR_TAG"


def _canonicalize_source_tags(tags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for tag in tags:
        try:
            normalized = diameter.normalize_diameter(f'{float(tag["diameter_in"]):g}"')
        except (KeyError, TypeError, ValueError):
            continue
        out.append({**tag, **normalized, "expected_layer": v8.expected_layer_for_system(tag.get("system", ""))})
    return out


def probe_detail_transfer(
    detail_page: fitz.Page,
    target_page: fitz.Page,
    spec: dict[str, Any],
    *,
    min_segment_pt: float,
    max_stroke_width_pt: float,
    endpoint_snap_pt: float,
    tag_snap_max_pt: float,
    render_scale: float = 1.5,
) -> dict[str, Any]:
    match = match_detail_view(
        detail_page,
        target_page,
        match_rect_rotated_pt=spec["match_rect_rotated_pt"],
        target_roi_rotated_pt=spec["target_roi_rotated_pt"],
        expected_scale_ratio=float(spec.get("expected_scale_ratio", 0.5)),
        render_scale=render_scale,
    )
    min_score = float(spec.get("min_match_score", 0.38))
    result: dict[str, Any] = {
        "id": spec.get("id"),
        "detail_page": int(spec["detail_page"]),
        "target_page": int(spec["target_page"]),
        "publication_policy": spec.get("publication_policy", "DIAGNOSTIC_TRANSFER_ONLY_NO_QUANTITY"),
        "match": match,
        "transfer_candidates": [],
    }
    if match.get("status") != "MATCHED" or float(match.get("match_score", 0.0)) < min_score:
        result["status"] = "WITHHELD_DETAIL_MATCH_LOW_SCORE"
        return result

    detail_bounds = rotated_rect_to_unrotated_bounds(detail_page, spec["detail_pipe_rect_rotated_pt"])
    detail_segments = v8.line_segments(detail_page, detail_bounds, min_segment_pt, max_stroke_width_pt)
    _, detail_component_by_segment = v8.style_components(detail_segments, endpoint_snap_pt)
    detail_tags = _canonicalize_source_tags(v8.pipe_tag_anchors(detail_page, detail_bounds))
    _associate_source_tags(
        detail_tags,
        detail_segments,
        detail_component_by_segment,
        v8.declared_layers(detail_page),
        tag_snap_max_pt,
    )

    target_segments = v8.line_segments(target_page, None, min_segment_pt, max_stroke_width_pt)
    target_components, target_component_by_segment = v8.style_components(target_segments, endpoint_snap_pt)
    del target_components
    snap = float(spec.get("transfer_snap_pt", 8.0))
    max_angle = float(spec.get("max_angle_diff_deg", 15.0))
    ambiguity_margin = float(spec.get("ambiguity_margin_pt", 1.0))
    candidates = []
    seen = set()
    for tag in detail_tags:
        source_index = tag.get("nearest_segment")
        if source_index is None:
            continue
        source_segment = detail_segments[int(source_index)]
        predicted_a = _transform_unrotated_point(detail_page, target_page, source_segment["a"], match)
        predicted_b = _transform_unrotated_point(detail_page, target_page, source_segment["b"], match)
        predicted_mid = ((predicted_a[0] + predicted_b[0]) / 2.0, (predicted_a[1] + predicted_b[1]) / 2.0)
        predicted_angle = _angle_deg(predicted_a, predicted_b)
        expected_layer = tag.get("expected_layer")
        ranked = []
        for index, target_segment in enumerate(target_segments):
            if expected_layer and target_segment.get("layer") != expected_layer:
                continue
            angle_diff = _angle_diff_deg(predicted_angle, _angle_deg(target_segment["a"], target_segment["b"]))
            if angle_diff > max_angle:
                continue
            dist = v8.distance_point_segment(predicted_mid, target_segment["a"], target_segment["b"])
            if dist <= snap:
                ranked.append((dist, angle_diff, index))
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
        key = (tag.get("system"), tag.get("diameter_key"), round(predicted_mid[0], 2), round(predicted_mid[1], 2))
        if key in seen:
            continue
        seen.add(key)
        row: dict[str, Any] = {
            "source_text": tag.get("text"),
            "system": tag.get("system"),
            "diameter_key": tag.get("diameter_key"),
            "dn": tag.get("dn"),
            "diameter_mm": tag.get("diameter_mm"),
            "diameter_in": tag.get("diameter_in"),
            "expected_layer": expected_layer,
            "source_segment_index": int(source_index),
            "predicted_target_midpoint_pt": [round(predicted_mid[0], 3), round(predicted_mid[1], 3)],
            "predicted_target_segment_pt": [
                round(predicted_a[0], 3), round(predicted_a[1], 3),
                round(predicted_b[0], 3), round(predicted_b[1], 3),
            ],
            "candidate_count": len(ranked),
        }
        if not ranked:
            row["status"] = "WITHHELD_NO_TARGET_SEGMENT_MATCH"
        else:
            best_dist, best_angle, best_index = ranked[0]
            ambiguous = len(ranked) > 1 and ranked[1][0] <= best_dist + ambiguity_margin
            row.update({
                "target_segment_index": int(best_index),
                "target_component_id": target_component_by_segment.get(best_index),
                "distance_pt": round(float(best_dist), 3),
                "angle_diff_deg": round(float(best_angle), 3),
                "target_layer": target_segments[best_index].get("layer", ""),
                "status": "WITHHELD_AMBIGUOUS_TARGET_SEGMENTS" if ambiguous else "DETAIL_TRANSFER_CANDIDATE",
            })
            if ambiguous:
                row["second_candidate_distance_pt"] = round(float(ranked[1][0]), 3)
        candidates.append(row)

    result["transfer_candidates"] = candidates
    result["status"] = "DIAGNOSTIC_TRANSFER_PROBED"
    result["source_tag_count"] = len(detail_tags)
    result["candidate_count"] = sum(1 for row in candidates if row.get("status") == "DETAIL_TRANSFER_CANDIDATE")
    result["ambiguous_count"] = sum(1 for row in candidates if row.get("status") == "WITHHELD_AMBIGUOUS_TARGET_SEGMENTS")
    result["unmatched_count"] = sum(1 for row in candidates if row.get("status") == "WITHHELD_NO_TARGET_SEGMENT_MATCH")
    return result
