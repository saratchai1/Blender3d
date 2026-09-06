#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import fitz

import auto_boq as base
import auto_boq_v8 as v8
import layer_topology_v8 as topology
import leader_association_v8 as leader
import pipe_reconcile_v8 as diameter

VALVE_NAMES = ('BALL VALVE', 'FLOAT VALVE')
ANCHORS = ('BALL', 'FLOAT')
DEBUG_TOKENS = ('BALL', 'FLOAT', 'VALVE', 'PASS')
DIA_RX = re.compile(r'(?:Ø|∅)\s*(\d+(?:\s*/\s*\d+|\.\d+)?)')


def _center(word: Any) -> tuple[float, float]:
    return ((float(word[0]) + float(word[2])) / 2.0, (float(word[1]) + float(word[3])) / 2.0)


def _visible_center(page: fitz.Page, word: Any) -> tuple[float, float]:
    x, y = _center(word)
    p = fitz.Point(x, y) * page.rotation_matrix
    return float(p.x), float(p.y)


def _spatial_records(page: fitz.Page) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    words = list(page.get_text('words') or [])
    visible = {id(word): _visible_center(page, word) for word in words}
    debug = []
    for word in words:
        upper = str(word[4]).upper()
        if any(token in upper for token in DEBUG_TOKENS):
            vx, vy = visible[id(word)]
            debug.append({
                'text': str(word[4]),
                'bbox_pt': [round(float(v), 3) for v in word[:4]],
                'visible_center_pt': [round(vx, 3), round(vy, 3)],
                'block': int(word[5]) if len(word) > 5 else None,
                'line': int(word[6]) if len(word) > 6 else None,
            })

    rows: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for seed in words:
        seed_text = str(seed[4]).upper()
        anchor = next((a for a in ANCHORS if a in seed_text), None)
        if not anchor:
            continue
        sx, sy = visible[id(seed)]
        nearby = []
        for word in words:
            wx, wy = visible[id(word)]
            if abs(wy - sy) <= 10.0 and (sx - 25.0) <= wx <= (sx + 180.0):
                nearby.append(word)
        nearby.sort(key=lambda w: visible[id(w)][0])
        text = ' '.join(str(w[4]) for w in nearby)
        upper = text.upper()
        name = next((n for n in VALVE_NAMES if n in upper), None)
        if not name or name in seen_names:
            continue
        m = DIA_RX.search(upper)
        normalized = None
        if m:
            try:
                normalized = diameter.normalize_diameter(f'{m.group(1)}"')
            except ValueError:
                normalized = None
        bbox = [
            min(float(w[0]) for w in nearby), min(float(w[1]) for w in nearby),
            max(float(w[2]) for w in nearby), max(float(w[3]) for w in nearby),
        ]
        rows.append({
            'name': name,
            'text': text,
            'bbox_pt': bbox,
            'diameter': normalized,
            'visible_seed_center_pt': [round(sx, 3), round(sy, 3)],
        })
        seen_names.add(name)
    return rows, debug


def probe(pdf_path: Path, profile_path: Path) -> dict[str, Any]:
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    cfg = profile.get('sanitary_pipe_network', {})
    doc = fitz.open(pdf_path)
    guarded = base.GuardedPdf(doc, int(profile['source_page_max']))
    page = guarded.page(57)
    page_rotation = int(page.rotation)
    segments = v8.line_segments(
        page, None,
        float(cfg.get('min_segment_pt', 3.0)),
        float(cfg.get('max_stroke_width_pt', 3.0)),
    )
    _, component_by_segment = topology.layer_components(
        segments, float(cfg.get('endpoint_snap_pt', 1.5)),
    )
    callouts, debug_words = _spatial_records(page)
    rows = []
    for callout in callouts:
        resolved = leader.find_leader_target(
            tag_bbox_pt=list(map(float, callout['bbox_pt'])),
            segments=segments,
            component_by_segment=component_by_segment,
            expected_layer='CW',
        )
        target = None
        if resolved.get('target_segment_index') is not None:
            idx = int(resolved['target_segment_index'])
            seg = segments[idx]
            target = {
                'segment_index': idx,
                'component_id': component_by_segment.get(idx),
                'layer': seg.get('layer'),
                'a': [round(float(seg['a'][0]), 3), round(float(seg['a'][1]), 3)],
                'b': [round(float(seg['b'][0]), 3), round(float(seg['b'][1]), 3)],
                'length_pt': round(float(seg.get('length_pt', 0.0)), 3),
            }
        rows.append({**callout, 'leader': resolved, 'target_segment': target})
    search_rects = {
        token: [[round(float(r.x0),3), round(float(r.y0),3), round(float(r.x1),3), round(float(r.y1),3)] for r in page.search_for(token)]
        for token in DEBUG_TOKENS
    }
    doc.close()
    return {
        'status': 'DIAGNOSTIC_ONLY_NO_QUANTITY_CHANGE',
        'source_page': 57,
        'source_page_max': int(profile['source_page_max']),
        'page_rotation_deg': page_rotation,
        'expected_layer': 'CW',
        'callouts': rows,
        'callout_count': len(rows),
        'associated_count': sum(1 for r in rows if (r['leader'] or {}).get('status') == 'ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER'),
        'debug_keyword_words': debug_words,
        'search_rects': search_rects,
        'publication_policy': 'EVIDENCE_ONLY_NO_PIPE_LENGTH_ADDITION',
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', type=Path, required=True)
    ap.add_argument('--profile', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    result = probe(args.pdf, args.profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('CW_VALVE_LEADER_PROBE_OK', json.dumps({
        'callouts': result['callout_count'],
        'associated': result['associated_count'],
        'rotation': result['page_rotation_deg'],
        'debug_keyword_words': len(result['debug_keyword_words']),
        'output': str(args.output),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
