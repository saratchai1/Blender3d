#!/usr/bin/env python3
"""Render source pipe pages and retain text evidence for reconciliation QA.

Diagnostic utility. It never reads BOQ reference pages and never changes output
quantities. Images/text are CI artifacts used to validate room/detail matching and
fixture branch-size schedule parsing before those rules can affect a BOQ.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import fitz

import auto_boq as base

INTERESTING = ("ห้อง", "สุข", "WC", "LAV", "UR", "SINK", "FD", "CW", "SW", "RL", "AVC", "Ø", "∅")
ROOM_RX = re.compile(r"(?:ห้อง\s*น้ำ|ห้องน้ำ)\s*([123])")


def _block_json(block: tuple) -> dict:
    return {
        "bbox_pt": [round(float(block[i]), 2) for i in range(4)],
        "text": str(block[4]).strip(),
    }


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
    text_probe = []
    for spec in specs:
        page_no = int(spec["page"])
        page = guarded.page(page_no)
        pix = page.get_pixmap(matrix=fitz.Matrix(args.zoom, args.zoom), alpha=False)
        sheet = str(spec.get("sheet") or f"page-{page_no}").replace("/", "-")
        path = args.output_dir / f"{sheet}-p{page_no}.png"
        pix.save(path)
        outputs.append(str(path))

        blocks = page.get_text("blocks") or []
        text = page.get_text("text") or ""
        interesting_lines = [
            line.strip() for line in text.splitlines()
            if line.strip() and any(marker in line for marker in INTERESTING)
        ]
        room_blocks = []
        for block in blocks:
            block_text = str(block[4]).strip()
            matches = ROOM_RX.findall(block_text)
            if matches or "ห้อง" in block_text:
                room_blocks.append({**_block_json(block), "room_numbers": matches})
        schedule_blocks = []
        if sheet == "SN-07":
            for block in blocks:
                x0, y0, x1, y1 = map(float, block[:4])
                if x0 >= 360 and y0 >= 620:
                    schedule_blocks.append(_block_json(block))

        token_words = []
        for word in page.get_text("words") or []:
            token = str(word[4])
            upper = token.upper()
            if any(key in upper for key in ("WC", "LAV", "UR", "SINK", "FD", "CW", "SW", "RL", "AVC")) or "Ø" in token or "∅" in token:
                token_words.append({
                    "text": token,
                    "bbox_pt": [round(float(word[i]), 2) for i in range(4)],
                })
        text_probe.append({
            "page": page_no,
            "sheet": sheet,
            "view_role": spec.get("view_role"),
            "page_size_pt": [round(float(page.rect.width), 2), round(float(page.rect.height), 2)],
            "room_blocks": room_blocks,
            "interesting_lines": interesting_lines,
            "schedule_blocks": schedule_blocks,
            "token_words": token_words,
        })
    doc.close()
    text_path = args.output_dir / "text-probe.json"
    text_path.write_text(json.dumps(text_probe, ensure_ascii=False, indent=2), encoding="utf-8")
    print("AUTO_BOQ_V8_RENDER_DEBUG_OK", {
        "pages": outputs,
        "text_probe": str(text_path),
        "room_blocks": {row["sheet"]: len(row["room_blocks"]) for row in text_probe},
        "source_page_max": profile["source_page_max"],
    })


if __name__ == "__main__":
    main()
