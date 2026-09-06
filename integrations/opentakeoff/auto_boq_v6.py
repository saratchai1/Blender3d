#!/usr/bin/env python3
"""v6 extension: conservative CAD-label sweeps on top of the v5 extractor.

This module deliberately keeps the existing generator/reference isolation. It
calls the base extractor first, then reads only drawing pages permitted by the
same profile fence and adds quantities from repeated visible CAD labels after
long wall/grid lines are removed. It never imports benchmark_reference.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import fitz
import numpy as np

import auto_boq as base

SCHEMA = base.SCHEMA


def _strip_long_lines(gray: np.ndarray, line_len: int = 16) -> np.ndarray:
    """Return binary ink with long orthogonal CAD construction/grid lines removed."""
    ink = 255 - gray
    _, bw = cv2.threshold(ink, 50, 255, cv2.THRESH_BINARY)
    horizontal = cv2.morphologyEx(
        bw, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(line_len)), 1)),
    )
    vertical = cv2.morphologyEx(
        bw, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(line_len)))),
    )
    return cv2.subtract(bw, cv2.max(horizontal, vertical))


def label_template_sweep(
    template_page: fitz.Page,
    template_rect_pt: list[float],
    target_pages: list[tuple[int, fitz.Page]],
    target_roi_pt: list[float],
    threshold: float,
    render_scale: float = 2.0,
    line_len: int = 16,
) -> list[dict[str, Any]]:
    """Count repeated visible CAD labels after suppressing wall/grid lines."""
    ref = _strip_long_lines(base.render_gray(template_page, render_scale), line_len)
    x0, y0, x1, y1 = [int(round(v * render_scale)) for v in template_rect_pt]
    crop = ref[y0:y1, x0:x1]
    ys, xs = np.where(crop > 0)
    if not len(xs):
        return []
    pad = 2
    tpl = crop[
        max(0, int(ys.min()) - pad):min(crop.shape[0], int(ys.max()) + pad + 1),
        max(0, int(xs.min()) - pad):min(crop.shape[1], int(xs.max()) + pad + 1),
    ]
    hits: list[dict[str, Any]] = []
    for page_no, page in target_pages:
        arr = _strip_long_lines(base.render_gray(page, render_scale), line_len)
        rx0, ry0, rx1, ry1 = [int(round(v * render_scale)) for v in target_roi_pt]
        target = arr[ry0:ry1, rx0:rx1]
        if target.shape[0] < tpl.shape[0] or target.shape[1] < tpl.shape[1]:
            continue
        res = cv2.matchTemplate(target, tpl, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(res >= threshold)
        raw = [
            (float(res[y, x]), x + rx0 + tpl.shape[1] / 2, y + ry0 + tpl.shape[0] / 2)
            for y, x in zip(ys, xs)
        ]
        for score, x, y in base.nms(raw, max(tpl.shape) * 0.80):
            hits.append({
                "page": page_no,
                "x_norm": x / arr.shape[1],
                "y_norm": y / arr.shape[0],
                "match_score": score,
            })
    return hits


def extract(pdf_path: Path, profile_path: Path) -> dict[str, Any]:
    result = base.extract(pdf_path, profile_path)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    labels = profile.get("label_templates")
    if not labels:
        return result

    max_page = int(profile["source_page_max"])
    doc = fitz.open(pdf_path)
    guarded = base.GuardedPdf(doc, max_page)
    render_scale = float(labels.get("render_scale", 2.0))
    default_line_len = int(labels.get("line_len", 16))

    for detector in labels.get("templates", []):
        source_p = int(detector["template_page"])
        target_pages = [(int(p), guarded.page(int(p))) for p in detector["target_pages"]]
        line_len = int(detector.get("line_len", default_line_len))
        hits = label_template_sweep(
            guarded.page(source_p), detector["template_rect_pt"], target_pages,
            detector["target_roi_pt"], float(detector["threshold"]), render_scale, line_len,
        )
        median = float(np.median([h["match_score"] for h in hits])) if hits else 0.0
        result["diagnostics"].append({
            "detector": f"label_template:{detector['id']}",
            "template_page": source_p,
            "target_pages": detector["target_pages"],
            "detections": len(hits),
            "median_score": median,
            "status": "DETECTED" if hits else "WITHHELD",
        })
        if hits:
            pages = sorted(set([source_p] + [h["page"] for h in hits]))
            if any(p > max_page for p in pages):
                raise AssertionError(f"reference leakage: {detector['id']} cites a source page after {max_page}")
            result["rows"].append(base.quantity_row(
                detector["id"], detector["description"], detector.get("category", "Sanitary"),
                "ea", len(hits), median, "raster:line-stripped CAD label sweep", pages,
                {
                    "template_page": source_p,
                    "template_rect_pt": detector["template_rect_pt"],
                    "detections": hits,
                    "threshold": detector["threshold"],
                    "line_len": line_len,
                },
            ))

    supported = result["coverage"].setdefault("supported_detectors", [])
    if "line-stripped CAD label sweeps" not in supported:
        supported.append("line-stripped CAD label sweeps")
    for item in result["coverage"].get("withheld_detectors", []):
        if item.get("name") == "sanitary fixtures beyond WC.1":
            item["name"] = "sanitary fixtures beyond validated bathroom accessories"
            item["reason"] = "floor drains/soap/floor faucets/valves still need stable fingerprints before publication"
    doc.close()
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--profile", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = extract(args.pdf, args.profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("AUTO_BOQ_V6_OK", json.dumps({
        "rows": len(result["rows"]),
        "ids": [r["id"] for r in result["rows"]],
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
