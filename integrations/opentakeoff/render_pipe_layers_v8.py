#!/usr/bin/env python3
"""Render semantic CAD pipe layers for v8 reconciliation QA.

Diagnostic-only. It emits one black-on-white PNG per semantic layer and a JSON
segment/component inventory. No BOQ reference data is read and no quantities are
changed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import fitz
import numpy as np

import auto_boq as base
import auto_boq_v8 as v8


def rotated_point(page: fitz.Page, point: tuple[float, float]) -> tuple[float, float]:
    p = fitz.Point(float(point[0]), float(point[1])) * page.rotation_matrix
    return float(p.x), float(p.y)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--profile", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--render-scale", type=float, default=1.5)
    args = ap.parse_args()

    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    cfg = profile.get("sanitary_pipe_network", {})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(args.pdf)
    guarded = base.GuardedPdf(doc, int(profile["source_page_max"]))
    inventory = []

    for spec in cfg.get("page_specs", []):
        if spec.get("contribution_policy") != "PRIMARY_PLAN_HORIZONTAL":
            continue
        page_no = int(spec["page"])
        sheet = str(spec.get("sheet") or page_no)
        page = guarded.page(page_no)
        segments = v8.line_segments(
            page,
            spec.get("bounds_pt"),
            float(cfg.get("min_segment_pt", 3.0)),
            float(cfg.get("max_stroke_width_pt", 3.0)),
        )
        components, component_by_segment = v8.style_components(
            segments,
            float(cfg.get("endpoint_snap_pt", 1.5)),
        )
        width = int(round(float(page.rect.width) * args.render_scale))
        height = int(round(float(page.rect.height) * args.render_scale))
        page_rows = []
        for layer in v8.SEMANTIC_PIPE_LAYERS:
            canvas = np.full((height, width, 3), 255, dtype=np.uint8)
            layer_rows = []
            for index, segment in enumerate(segments):
                if segment.get("layer") != layer:
                    continue
                a = rotated_point(page, segment["a"])
                b = rotated_point(page, segment["b"])
                pa = (int(round(a[0] * args.render_scale)), int(round(a[1] * args.render_scale)))
                pb = (int(round(b[0] * args.render_scale)), int(round(b[1] * args.render_scale)))
                cv2.line(canvas, pa, pb, (0, 0, 0), 2, cv2.LINE_AA)
                mid = ((pa[0] + pb[0]) // 2, (pa[1] + pb[1]) // 2)
                if float(segment["length_pt"]) >= 8.0:
                    cv2.putText(canvas, str(index), mid, cv2.FONT_HERSHEY_SIMPLEX, 0.28, (0, 0, 0), 1, cv2.LINE_AA)
                row = {
                    "segment_index": index,
                    "component_id": component_by_segment.get(index),
                    "layer": layer,
                    "a_pt": [round(float(v), 3) for v in segment["a"]],
                    "b_pt": [round(float(v), 3) for v in segment["b"]],
                    "a_rotated_pt": [round(float(v), 3) for v in a],
                    "b_rotated_pt": [round(float(v), 3) for v in b],
                    "length_pt": round(float(segment["length_pt"]), 3),
                    "width_pt": round(float(segment["width_pt"]), 3),
                    "color": segment.get("color"),
                    "dash": segment.get("dash"),
                }
                layer_rows.append(row)
            if layer_rows:
                path = args.output_dir / f"{sheet}-{layer}.png"
                cv2.imwrite(str(path), canvas)
                page_rows.append({
                    "layer": layer,
                    "render": str(path),
                    "segments": layer_rows,
                })
        inventory.append({
            "page": page_no,
            "sheet": sheet,
            "page_rotation": int(page.rotation),
            "page_rect": [round(float(page.rect.width), 3), round(float(page.rect.height), 3)],
            "components": components,
            "layers": page_rows,
        })

    doc.close()
    output = args.output_dir / "semantic-layer-segments.json"
    output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    print("AUTO_BOQ_V8_LAYER_RENDER_OK", {
        "pages": [row["sheet"] for row in inventory],
        "layer_renders": sum(len(row["layers"]) for row in inventory),
        "inventory": str(output),
    })


if __name__ == "__main__":
    main()
