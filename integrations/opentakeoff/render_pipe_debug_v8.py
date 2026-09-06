#!/usr/bin/env python3
"""Render only source pipe pages for visual reconciliation QA.

Diagnostic utility. It never reads BOQ reference pages and never changes output
quantities. Images are CI artifacts used to validate view matching decisions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz

import auto_boq as base


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--profile", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--zoom", type=float, default=1.5)
    args = ap.parse_args()
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    specs = profile.get("sanitary_pipe_network", {}).get("page_specs", [])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(args.pdf)
    guarded = base.GuardedPdf(doc, int(profile["source_page_max"]))
    outputs = []
    for spec in specs:
        page_no = int(spec["page"])
        page = guarded.page(page_no)
        pix = page.get_pixmap(matrix=fitz.Matrix(args.zoom, args.zoom), alpha=False)
        sheet = str(spec.get("sheet") or f"page-{page_no}").replace("/", "-")
        path = args.output_dir / f"{sheet}-p{page_no}.png"
        pix.save(path)
        outputs.append(str(path))
    doc.close()
    print("AUTO_BOQ_V8_RENDER_DEBUG_OK", {"pages": outputs, "source_page_max": profile["source_page_max"]})


if __name__ == "__main__":
    main()
