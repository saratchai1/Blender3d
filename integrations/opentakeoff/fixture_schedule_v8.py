from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable

import pipe_reconcile_v8 as diameters

FIXTURE_CODES = ("WC", "WC1", "LAV", "UR", "SH", "C", "SINK", "FD")
SYSTEM_CODES = ("CW", "S", "V", "W")
VALUE_RX = re.compile(r"^(?:-|\d+(?:\s*/\s*\d+)?|\d+(?:\.\d+)?)$")


def _record(word: Any) -> dict[str, Any]:
    if isinstance(word, dict):
        bbox = word.get("bbox_pt") or word.get("bbox")
        text = str(word.get("text", ""))
    else:
        bbox = list(map(float, word[:4]))
        text = str(word[4])
    if not bbox or len(bbox) != 4:
        raise ValueError("word must contain a 4-value bbox")
    x0, y0, x1, y1 = map(float, bbox)
    return {
        "text": text.strip(),
        "bbox_pt": [x0, y0, x1, y1],
        "cx": (x0 + x1) / 2.0,
        "cy": (y0 + y1) / 2.0,
    }


def _code(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(text or "").upper())


def _within(record: dict[str, Any], bounds: list[float] | None) -> bool:
    if not bounds:
        return True
    x0, y0, x1, y1 = map(float, bounds)
    return x0 <= record["cx"] <= x1 and y0 <= record["cy"] <= y1


def _nearest(value: float, anchors: dict[str, float]) -> tuple[str, float]:
    key = min(anchors, key=lambda name: abs(value - anchors[name]))
    return key, abs(value - anchors[key])


def _min_spacing(values: Iterable[float]) -> float:
    ordered = sorted(float(v) for v in values)
    gaps = [b - a for a, b in zip(ordered, ordered[1:]) if b - a > 1e-6]
    return min(gaps) if gaps else 0.0


def parse_fixture_schedule_words(
    words: Iterable[Any],
    *,
    bounds_pt: list[float] | None = None,
) -> dict[str, Any]:
    """Parse the rotated vector fixture branch-size table used on Family4 SN-07.

    The PDF encodes the table text rotated: fixture rows align on the PDF X axis
    while pipe-system columns align on the PDF Y axis. We use the printed English
    fixture/system headers as anchors and assign numeric/fraction cells by nearest
    grid coordinate. No OCR and no benchmark/reference page is involved.
    """
    records = [_record(word) for word in words]
    records = [record for record in records if _within(record, bounds_pt)]

    fixture_records: dict[str, dict[str, Any]] = {}
    system_records: dict[str, dict[str, Any]] = {}
    for record in records:
        code = _code(record["text"])
        if code in FIXTURE_CODES:
            fixture_records.setdefault(code, record)
        if code in SYSTEM_CODES:
            system_records.setdefault(code, record)

    missing_fixtures = [code for code in FIXTURE_CODES if code not in fixture_records]
    missing_systems = [code for code in SYSTEM_CODES if code not in system_records]
    if missing_fixtures or missing_systems:
        return {
            "status": "WITHHELD_GRID_HEADERS_INCOMPLETE",
            "missing_fixture_headers": missing_fixtures,
            "missing_system_headers": missing_systems,
            "rows": [],
        }

    fixture_x = {code: fixture_records[code]["cx"] for code in FIXTURE_CODES}
    system_y = {code: system_records[code]["cy"] for code in SYSTEM_CODES}
    fixture_spacing = _min_spacing(fixture_x.values())
    system_spacing = _min_spacing(system_y.values())
    fixture_tol = fixture_spacing * 0.48 if fixture_spacing else 8.0
    system_tol = system_spacing * 0.36 if system_spacing else 16.0

    anchor_ids = {id(record) for record in fixture_records.values()} | {id(record) for record in system_records.values()}
    cells: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    rejected: list[dict[str, Any]] = []
    for record in records:
        if id(record) in anchor_ids:
            continue
        text = record["text"].strip()
        if not VALUE_RX.fullmatch(text):
            continue
        fixture, dx = _nearest(record["cx"], fixture_x)
        system, dy = _nearest(record["cy"], system_y)
        if dx > fixture_tol or dy > system_tol:
            rejected.append({"text": text, "bbox_pt": record["bbox_pt"], "nearest_fixture": fixture, "dx": round(dx, 3), "nearest_system": system, "dy": round(dy, 3)})
            continue
        cells[(fixture, system)].append(record)

    rows: list[dict[str, Any]] = []
    matrix: dict[str, dict[str, Any]] = {}
    ambiguous_cells: list[dict[str, Any]] = []
    for fixture in FIXTURE_CODES:
        matrix[fixture] = {}
        for system in SYSTEM_CODES:
            tokens = cells.get((fixture, system), [])
            # Mixed fractions such as 1 1/2 are split into two rotated PDF words.
            # Descending Y restores the visual reading order for this table.
            tokens = sorted(tokens, key=lambda row: (-row["cy"], row["cx"]))
            values = [row["text"] for row in tokens]
            raw = " ".join(values).strip()
            if not raw:
                matrix[fixture][system] = {"status": "WITHHELD_CELL_MISSING"}
                ambiguous_cells.append({"fixture": fixture, "system": system, "reason": "cell missing"})
                continue
            if raw == "-":
                matrix[fixture][system] = {"status": "NO_CONNECTION", "raw": raw}
                continue
            if "-" in values:
                matrix[fixture][system] = {"status": "WITHHELD_MIXED_DASH_AND_VALUE", "raw": raw}
                ambiguous_cells.append({"fixture": fixture, "system": system, "reason": "dash mixed with numeric value", "raw": raw})
                continue
            try:
                normalized = diameters.normalize_diameter(raw)
            except ValueError as exc:
                matrix[fixture][system] = {"status": "WITHHELD_DIAMETER_PARSE", "raw": raw, "reason": str(exc)}
                ambiguous_cells.append({"fixture": fixture, "system": system, "reason": str(exc), "raw": raw})
                continue
            evidence_bbox = [
                min(row["bbox_pt"][0] for row in tokens),
                min(row["bbox_pt"][1] for row in tokens),
                max(row["bbox_pt"][2] for row in tokens),
                max(row["bbox_pt"][3] for row in tokens),
            ]
            cell = {
                "status": "PARSED_VECTOR_CELL",
                "raw": raw,
                **normalized,
                "evidence_bbox_pt": [round(float(v), 2) for v in evidence_bbox],
            }
            matrix[fixture][system] = cell
            rows.append({
                "fixture": fixture,
                "system": system,
                **cell,
            })

    return {
        "status": "PARSED" if not ambiguous_cells else "PARSED_WITH_WITHHELD_CELLS",
        "fixture_headers": {code: [round(v, 3) for v in fixture_records[code]["bbox_pt"]] for code in FIXTURE_CODES},
        "system_headers": {code: [round(v, 3) for v in system_records[code]["bbox_pt"]] for code in SYSTEM_CODES},
        "fixture_spacing_pt": round(fixture_spacing, 3),
        "system_spacing_pt": round(system_spacing, 3),
        "fixture_tolerance_pt": round(fixture_tol, 3),
        "system_tolerance_pt": round(system_tol, 3),
        "rows": rows,
        "matrix": matrix,
        "connection_count": len(rows),
        "ambiguous_cells": ambiguous_cells,
        "rejected_value_tokens": rejected,
        "publication_status": "EVIDENCE_ONLY_NO_PIPE_LENGTH_ADDITION",
    }


def parse_fixture_schedule_page(page: Any, bounds_pt: list[float]) -> dict[str, Any]:
    return parse_fixture_schedule_words(page.get_text("words") or [], bounds_pt=bounds_pt)
