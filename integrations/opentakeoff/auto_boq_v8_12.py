#!/usr/bin/env python3
"""v8.12 diagnostic: v8.11 horizontal gate + calibrated SN-04 riser probe.

Vertical schematic geometry is reconstructed against explicit elevation markers.
This version does not yet add vertical quantity to BOQ; it exists to validate the
vertical evidence independently before publication logic is changed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz

import auto_boq as base
import auto_boq_v8_11 as v811
import vertical_schematic_v8 as vertical

SCHEMA = v811.SCHEMA


def extract(pdf_path: Path, profile_path: Path) -> dict:
    result = v811.extract(pdf_path, profile_path)
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_11'),
        None,
    )
    if not diag:
        return result
    schematic_analysis = next(
        (p for p in diag.get('pages', []) if p.get('view_role') == 'vertical_schematic'),
        None,
    )
    if not schematic_analysis:
        return result

    cfg = profile.get('sanitary_pipe_network', {})
    doc = fitz.open(pdf_path)
    guarded = base.GuardedPdf(doc, int(profile['source_page_max']))
    probe = vertical.probe_vertical_schematic(
        guarded.page(int(schematic_analysis['page'])),
        schematic_analysis,
        min_segment_pt=float(cfg.get('min_segment_pt', 3.0)),
        max_stroke_width_pt=float(cfg.get('max_stroke_width_pt', 3.0)),
    )
    doc.close()

    diag['detector'] = 'sanitary_pipe_network_v8_12'
    diag['status'] = 'DIAGNOSTIC_HORIZONTAL_GATE_PASS_VERTICAL_CALIBRATION_PROBED'
    diag['vertical_schematic_reconstruction'] = probe
    diag['note_v8_12'] = (
        'v8.12 keeps the v8.11 horizontal quantities unchanged and calibrates SN-04 vertical geometry from explicit level markers before any vertical quantity is allowed into BOQ. '
        'Major riser spans remain diagnostic-only in this version; schematic horizontal branches and enlarged-detail lengths remain non-additive.'
    )
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', type=Path, required=True)
    ap.add_argument('--profile', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    result = extract(args.pdf, args.profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_12'),
        None,
    )
    probe = (diag or {}).get('vertical_schematic_reconstruction') or {}
    axis = probe.get('elevation_axis') or {}
    print('AUTO_BOQ_V8_12_OK', json.dumps({
        'rows': len(result.get('rows', [])),
        'horizontal_gate': ((diag or {}).get('reconciliation') or {}).get('horizontal_diameter_gate'),
        'axis_status': axis.get('status'),
        'level_markers': axis.get('markers', []),
        'major_vertical_run_count': probe.get('major_vertical_run_count', 0),
        'major_vertical_runs': probe.get('major_vertical_runs', []),
        'vertical_quantity_published': False,
        'published_pipe_rows': sum(1 for r in result.get('rows', []) if str(r.get('id','')).startswith('SAN-PIPE-')),
        'output': str(args.output),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
