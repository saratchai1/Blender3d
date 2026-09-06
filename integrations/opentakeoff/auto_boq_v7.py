#!/usr/bin/env python3
"""v7 extension: count repeated sanitary drawing tags from drawing pages only.

The module wraps v6. It never imports or opens the benchmark reference. New
quantities are derived from visible plan tags such as FCO/RFD/AVC/CO on sanitary
drawing sheets. Ambiguous tags such as FD can be retained as diagnostics without
publishing a BOQ quantity.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import fitz

import auto_boq as base
from auto_boq_v6 import extract as extract_v6

SCHEMA = base.SCHEMA


def _inside(cx: float, cy: float, bounds: list[float] | None) -> bool:
    if not bounds:
        return True
    x0, y0, x1, y1 = map(float, bounds)
    return x0 <= cx <= x1 and y0 <= cy <= y1


def count_positioned_tag(
    guarded: base.GuardedPdf,
    token: str,
    page_specs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find token as an alpha tag inside positioned PDF words.

    Alpha boundaries make FD not match RFD and CO not match FCO. Tokens may be
    embedded in dimension strings such as Ø2\"FD or Ø2\"V+AVC.
    """
    token = token.upper().strip()
    rx = re.compile(rf"(?<![A-Z]){re.escape(token)}(?![A-Z])")
    hits: list[dict[str, Any]] = []
    for spec in page_specs:
        page_no = int(spec["page"])
        bounds = spec.get("bounds_pt")
        page = guarded.page(page_no)
        for word in page.get_text("words") or []:
            x0, y0, x1, y1, text = word[:5]
            cx, cy = (float(x0) + float(x1)) / 2, (float(y0) + float(y1)) / 2
            if not _inside(cx, cy, bounds):
                continue
            raw = str(text).upper().replace(" ", "")
            if not rx.search(raw):
                continue
            hits.append({
                "page": page_no,
                "text": str(text),
                "bbox_pt": [round(float(x0), 2), round(float(y0), 2), round(float(x1), 2), round(float(y1), 2)],
            })
    return hits


def pipe_tag_inventory(guarded: base.GuardedPdf, pages: list[int]) -> dict[str, Any]:
    """Diagnostic inventory only; never converted to pipe length in v7."""
    rx = re.compile(r"(?:Ø|DIA\.?)[^\s]{0,16}", re.IGNORECASE)
    out: dict[str, list[str]] = {}
    for page_no in pages:
        text = guarded.page(int(page_no)).get_text("text") or ""
        tags = []
        for match in rx.finditer(text):
            value = match.group(0).replace("\n", " ").strip()
            if value and value not in tags:
                tags.append(value)
        out[str(page_no)] = tags[:80]
    return out


def extract(pdf_path: Path, profile_path: Path) -> dict[str, Any]:
    result = extract_v6(pdf_path, profile_path)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    cfg = profile.get("drawing_tag_counts")
    max_page = int(profile["source_page_max"])
    if not cfg:
        return result

    doc = fitz.open(pdf_path)
    guarded = base.GuardedPdf(doc, max_page)
    existing = {row["id"] for row in result["rows"]}

    for detector in cfg.get("items", []):
        hits = count_positioned_tag(guarded, detector["token"], detector["page_specs"])
        confidence = float(detector.get("confidence", 0.96))
        result["diagnostics"].append({
            "detector": f"positioned_tag:{detector['id']}",
            "token": detector["token"],
            "pages": [int(x["page"]) for x in detector["page_specs"]],
            "detections": len(hits),
            "status": "DETECTED" if hits else "WITHHELD",
            "hits": hits,
        })
        if not hits or detector["id"] in existing:
            continue
        pages = sorted({int(h["page"]) for h in hits})
        if any(p > max_page for p in pages):
            raise AssertionError(f"reference leakage: {detector['id']} cites a source page after {max_page}")
        result["rows"].append(base.quantity_row(
            detector["id"], detector["description"], detector.get("category", "Sanitary"),
            "ea", len(hits), confidence, "text:positioned sanitary drawing tag", pages,
            {"token": detector["token"], "detections": hits, "page_specs": detector["page_specs"]},
        ))
        existing.add(detector["id"])

    for detector in cfg.get("diagnostic_only", []):
        page_specs = detector.get("page_specs", [])
        hits = count_positioned_tag(guarded, detector["token"], page_specs) if page_specs else []
        result["diagnostics"].append({
            "detector": f"positioned_tag_diagnostic:{detector['id']}",
            "token": detector["token"],
            "pages": [int(x["page"]) for x in page_specs],
            "detections": len(hits),
            "status": "WITHHELD_DIAGNOSTIC_ONLY",
            "reason": detector.get("reason", "not validated for publication"),
            "hits": hits,
        })

    inv_pages = [int(p) for p in cfg.get("pipe_tag_inventory_pages", [])]
    if inv_pages:
        result["diagnostics"].append({
            "detector": "pipe_tag_inventory_only",
            "status": "DIAGNOSTIC_ONLY_NO_QUANTITY",
            "pages": inv_pages,
            "inventory": pipe_tag_inventory(guarded, inv_pages),
            "note": "v7 inventories diameter/system tags but intentionally withholds pipe lengths until network tracing is validated.",
        })

    supported = result["coverage"].setdefault("supported_detectors", [])
    if "positioned sanitary drawing-tag counts" not in supported:
        supported.append("positioned sanitary drawing-tag counts")
    for item in result["coverage"].get("withheld_detectors", []):
        if item.get("name") == "sanitary piping":
            item["reason"] = "diameter/system tags are inventoried in v7, but network-line tracing and length reconciliation are still under validation"
        if item.get("name") == "sanitary fixtures beyond validated bathroom accessories":
            item["name"] = "sanitary fixtures/accessories beyond validated tags"
            item["reason"] = "floor drain remains unresolved at 4 explicit drawing tags versus 5 BOQ reference; soap/floor faucets/valves also need stable fingerprints"

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
    print("AUTO_BOQ_V7_OK", json.dumps({
        "rows": len(result["rows"]),
        "ids": [r["id"] for r in result["rows"]],
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
