from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any

import fitz

import auto_boq_v8 as v8

ELEVATION_RX = re.compile(r'^[+]?-?\d+(?:\.\d+)$')


def _rotated_point(page: fitz.Page, point: tuple[float, float]) -> tuple[float, float]:
    p = fitz.Point(float(point[0]), float(point[1])) * page.rotation_matrix
    return float(p.x), float(p.y)


def extract_elevation_markers(page: fitz.Page) -> list[dict[str, Any]]:
    by_value: dict[float, list[tuple[float, float, str]]] = defaultdict(list)
    for word in page.get_text('words') or []:
        text = str(word[4]).strip()
        if not ELEVATION_RX.match(text):
            continue
        if not (text.startswith('+') or text.startswith('-')):
            continue
        try:
            value = float(text)
        except ValueError:
            continue
        if not (-10.0 <= value <= 30.0):
            continue
        center = ((float(word[0]) + float(word[2])) / 2.0, (float(word[1]) + float(word[3])) / 2.0)
        xr, yr = _rotated_point(page, center)
        by_value[round(value, 4)].append((xr, yr, text))

    markers = []
    for value, hits in sorted(by_value.items()):
        # A level value may be repeated in a note; use the leftmost hit because the
        # Family4 schematic level callouts sit on the left margin of the diagram.
        hit = sorted(hits, key=lambda h: (h[0], h[1]))[0]
        markers.append({
            'elevation_m': float(value),
            'x_rotated_pt': round(float(hit[0]), 3),
            'y_rotated_pt': round(float(hit[1]), 3),
            'text': hit[2],
            'duplicate_count': len(hits),
        })
    return markers


def fit_elevation_axis(markers: list[dict[str, Any]]) -> dict[str, Any]:
    if len(markers) < 3:
        return {'status': 'WITHHELD_INSUFFICIENT_LEVEL_MARKERS', 'marker_count': len(markers)}
    xs = [float(m['y_rotated_pt']) for m in markers]
    ys = [float(m['elevation_m']) for m in markers]
    xbar = sum(xs) / len(xs); ybar = sum(ys) / len(ys)
    denom = sum((x - xbar) ** 2 for x in xs)
    if denom <= 1e-9:
        return {'status': 'WITHHELD_DEGENERATE_LEVEL_AXIS', 'marker_count': len(markers)}
    slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / denom
    intercept = ybar - slope * xbar
    predicted = [slope * x + intercept for x in xs]
    ss_res = sum((y - p) ** 2 for y, p in zip(ys, predicted))
    ss_tot = sum((y - ybar) ** 2 for y in ys)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 1.0
    max_residual = max(abs(y - p) for y, p in zip(ys, predicted))
    status = (
        'CALIBRATED_FROM_EXPLICIT_LEVEL_MARKERS'
        if slope < 0.0 and r2 >= 0.98 and max_residual <= 0.20
        else 'WITHHELD_LEVEL_AXIS_FIT_QUALITY'
    )
    return {
        'status': status,
        'marker_count': len(markers),
        'slope_m_per_rotated_pt': slope,
        'intercept_m': intercept,
        'r2': round(r2, 6),
        'max_residual_m': round(max_residual, 4),
        'markers': markers,
    }


def elevation_at(axis: dict[str, Any], y_rotated_pt: float) -> float:
    return float(axis['slope_m_per_rotated_pt']) * float(y_rotated_pt) + float(axis['intercept_m'])


def reconstruct_vertical_runs(
    page: fitz.Page,
    page_analysis: dict[str, Any],
    *,
    min_segment_pt: float,
    max_stroke_width_pt: float,
    axis: dict[str, Any],
    column_snap_pt: float = 2.0,
    max_dash_gap_pt: float = 25.0,
    max_vertical_dx_ratio: float = 0.12,
) -> list[dict[str, Any]]:
    if axis.get('status') != 'CALIBRATED_FROM_EXPLICIT_LEVEL_MARKERS':
        return []
    segments = v8.line_segments(page, None, min_segment_pt, max_stroke_width_pt)
    assignments = {
        int(r['segment_index']): r
        for r in page_analysis.get('diameter_assignments') or []
    }
    items: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        assignment = assignments.get(index)
        if not assignment or assignment.get('status', '').startswith('WITHHELD'):
            continue
        classes = assignment.get('classes') or []
        if len(classes) != 1:
            continue
        a = _rotated_point(page, tuple(segment['a']))
        b = _rotated_point(page, tuple(segment['b']))
        dx = abs(b[0] - a[0]); dy = abs(b[1] - a[1])
        if dy < float(min_segment_pt):
            continue
        if dx > max(1.0, max_vertical_dx_ratio * dy):
            continue
        cls = classes[0]
        items.append({
            'segment_index': index,
            'x': (a[0] + b[0]) / 2.0,
            'y0': min(a[1], b[1]),
            'y1': max(a[1], b[1]),
            'system': str(cls['system']),
            'diameter_key': str(cls['diameter_key']),
            'dn': cls.get('dn'),
            'layer': str(segment.get('layer') or ''),
        })

    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    # Stable incremental x clustering inside each class.
    class_items: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        class_items[(item['system'], item['diameter_key'])].append(item)
    for cls, rows in class_items.items():
        centers: list[float] = []
        for row in sorted(rows, key=lambda r: r['x']):
            best = None
            for cid, center in enumerate(centers):
                if abs(row['x'] - center) <= column_snap_pt:
                    best = cid; break
            if best is None:
                best = len(centers); centers.append(row['x'])
            else:
                group_rows = grouped[(cls[0], cls[1], best)]
                centers[best] = (centers[best] * len(group_rows) + row['x']) / (len(group_rows) + 1)
            grouped[(cls[0], cls[1], best)].append(row)

    runs: list[dict[str, Any]] = []
    for (system, diameter_key, column_id), rows in grouped.items():
        rows = sorted(rows, key=lambda r: (r['y0'], r['y1']))
        current: list[dict[str, Any]] = []
        current_y1 = None
        for row in rows:
            if current and current_y1 is not None and row['y0'] - current_y1 > max_dash_gap_pt:
                runs.append(_finalize_run(current, axis, system, diameter_key, column_id))
                current = []
            current.append(row)
            current_y1 = max(float(row['y1']), float(current_y1) if current_y1 is not None else float(row['y1']))
        if current:
            runs.append(_finalize_run(current, axis, system, diameter_key, column_id))
    runs.sort(key=lambda r: (-r['vertical_span_m'], r['system'], r['x_rotated_pt']))
    return runs


def _finalize_run(
    rows: list[dict[str, Any]],
    axis: dict[str, Any],
    system: str,
    diameter_key: str,
    column_id: int,
) -> dict[str, Any]:
    y0 = min(float(r['y0']) for r in rows); y1 = max(float(r['y1']) for r in rows)
    e0 = elevation_at(axis, y0); e1 = elevation_at(axis, y1)
    return {
        'system': system,
        'diameter_key': diameter_key,
        'dn': rows[0].get('dn'),
        'layer': rows[0].get('layer'),
        'column_id': int(column_id),
        'x_rotated_pt': round(sum(float(r['x']) for r in rows) / len(rows), 3),
        'y_span_rotated_pt': [round(y0, 3), round(y1, 3)],
        'elevation_span_m': [round(e0, 3), round(e1, 3)],
        'vertical_span_m': round(abs(e1 - e0), 3),
        'segment_count': len(rows),
        'segment_indexes': sorted(int(r['segment_index']) for r in rows),
    }


def probe_vertical_schematic(
    page: fitz.Page,
    page_analysis: dict[str, Any],
    *,
    min_segment_pt: float,
    max_stroke_width_pt: float,
) -> dict[str, Any]:
    markers = extract_elevation_markers(page)
    axis = fit_elevation_axis(markers)
    runs = reconstruct_vertical_runs(
        page,
        page_analysis,
        min_segment_pt=min_segment_pt,
        max_stroke_width_pt=max_stroke_width_pt,
        axis=axis,
    )
    major = [r for r in runs if float(r['vertical_span_m']) >= 2.0]
    return {
        'status': 'DIAGNOSTIC_VERTICAL_RECONSTRUCTION_ONLY',
        'elevation_axis': axis,
        'vertical_runs': runs,
        'major_vertical_runs': major,
        'major_vertical_run_count': len(major),
        'publication_policy': 'EVIDENCE_ONLY_NO_VERTICAL_QUANTITY_YET',
        'note': 'Vertical spans are calibrated from explicit level markers, not from nominal drawing scale. Dashed collinear pieces are joined only within one assigned class/column for diagnostic reconstruction.',
    }
