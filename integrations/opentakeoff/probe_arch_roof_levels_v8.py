#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import fitz

ELEV_RX = re.compile(r'^[+\-]?\d+(?:\.\d+)?$')
KEYWORDS = ('ROOF','ELEV','LEVEL','RIDGE','EAVE','PARAPET','SECTION','R.L','RL')


def page_probe(page: fitz.Page, page_no: int, output_dir: Path, dpi: int = 150) -> dict[str, Any]:
    scale = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, annots=False)
    png = output_dir / f'ARCH-p{page_no}.png'
    pix.save(str(png))
    words = page.get_text('words') or []
    numeric = []
    keyword_hits = []
    for word in words:
        text = str(word[4]).strip()
        upper = text.upper()
        if ELEV_RX.match(text):
            try:
                value = float(text)
            except ValueError:
                value = None
            if value is not None and -10 <= value <= 30:
                numeric.append({
                    'text': text,
                    'value': value,
                    'bbox_pt': [round(float(word[i]), 3) for i in range(4)],
                })
        if any(k in upper for k in KEYWORDS):
            keyword_hits.append({
                'text': text,
                'bbox_pt': [round(float(word[i]), 3) for i in range(4)],
            })
    text = page.get_text('text') or ''
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    context_lines = [
        line for line in lines
        if any(k in line.upper() for k in KEYWORDS)
        or re.search(r'[+\-]\d+(?:\.\d+)', line)
    ]
    return {
        'page': page_no,
        'render': str(png),
        'rotation': int(page.rotation),
        'numeric_candidates': numeric,
        'keyword_hits': keyword_hits,
        'context_lines': context_lines[:200],
        'word_count': len(words),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--pages', default='11,12,13')
    ap.add_argument('--source-page-max', type=int, default=71)
    args = ap.parse_args()
    pages = [int(x.strip()) for x in args.pages.split(',') if x.strip()]
    assert pages and max(pages) <= args.source_page_max
    args.output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(args.pdf)
    probes = []
    for page_no in pages:
        if not (1 <= page_no <= len(doc)):
            raise ValueError(f'page {page_no} outside PDF')
        probes.append(page_probe(doc[page_no - 1], page_no, args.output_dir))
    doc.close()
    payload = {
        'status': 'DIAGNOSTIC_ARCHITECTURAL_LEVEL_PROBE_ONLY',
        'source_pages': pages,
        'source_page_max': args.source_page_max,
        'reference_used': False,
        'pages': probes,
        'publication_policy': 'EVIDENCE_ONLY_NO_PIPE_QUANTITY_CHANGE',
    }
    out = args.output_dir / 'arch-roof-level-probe.json'
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print('ARCH_ROOF_LEVEL_PROBE_OK', json.dumps({
        'pages': pages,
        'numeric_candidates': {str(p['page']): len(p['numeric_candidates']) for p in probes},
        'keyword_hits': {str(p['page']): len(p['keyword_hits']) for p in probes},
        'output': str(out),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
