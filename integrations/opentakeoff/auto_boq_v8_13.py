#!/usr/bin/env python3
"""v8.13 diagnostic: v8.12 + explicit-level-bounded vertical candidates.

The horizontal gate remains unchanged. Vertical quantity is still not published;
this version separates floor-to-floor/inter-level riser evidence from terminal
extensions and minor branches that do not match any explicit SN-04 level interval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import auto_boq_v8_12 as v812
import vertical_level_bounds_v8 as level_bounds

SCHEMA = v812.SCHEMA


def extract(pdf_path: Path, profile_path: Path) -> dict:
    result = v812.extract(pdf_path, profile_path)
    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_12'),
        None,
    )
    if not diag:
        return result
    probe = diag.get('vertical_schematic_reconstruction') or {}
    axis = probe.get('elevation_axis') or {}
    classification = level_bounds.classify_vertical_runs(
        probe.get('vertical_runs') or [],
        axis.get('markers') or [],
    )
    diag['detector'] = 'sanitary_pipe_network_v8_13'
    diag['status'] = 'DIAGNOSTIC_HORIZONTAL_PASS_LEVEL_BOUNDED_VERTICAL_CANDIDATES'
    diag['vertical_level_bounded_reconciliation'] = classification
    diag['note_v8_13'] = (
        'v8.13 does not extrapolate all SN-04 vertical geometry into BOQ. It recognizes only vertical spans corroborated by explicit level intervals '
        '(0.00, 0.60, 3.75 m) as candidate inter-level quantity. Vent/AVC extensions outside the highest explicit level and minor branches that do not '
        'match an explicit level-pair span remain withheld. No vertical candidate is published as SAN-PIPE in this version.'
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
    diag = next((d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_13'), None)
    bounded = (diag or {}).get('vertical_level_bounded_reconciliation') or {}
    rec = (diag or {}).get('reconciliation') or {}
    print('AUTO_BOQ_V8_13_OK', json.dumps({
        'rows': len(result.get('rows', [])),
        'horizontal_gate': rec.get('horizontal_diameter_gate'),
        'vertical_candidate_runs': bounded.get('candidate_run_count', 0),
        'vertical_withheld_runs': bounded.get('withheld_run_count', 0),
        'vertical_candidate_rows': bounded.get('candidate_rows', []),
        'vertical_quantity_published': False,
        'published_pipe_rows': sum(1 for r in result.get('rows', []) if str(r.get('id','')).startswith('SAN-PIPE-')),
        'output': str(args.output),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
