#!/usr/bin/env python3
"""v8.14 diagnostic: v8.13 + direct single-segment vertical branch evidence.

Only directly tagged single-segment vertical branches inside the explicit SN-04
level band may be promoted beyond level-interval candidates. This remains
non-publishing: no SAN-PIPE rows are emitted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import auto_boq_v8_13 as v813
import vertical_direct_branch_v8 as direct_branch

SCHEMA = v813.SCHEMA


def extract(pdf_path: Path, profile_path: Path) -> dict:
    result = v813.extract(pdf_path, profile_path)
    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_13'),
        None,
    )
    if not diag:
        return result
    schematic_analysis = next(
        (p for p in diag.get('pages', []) if p.get('view_role') == 'vertical_schematic'),
        None,
    )
    bounded = diag.get('vertical_level_bounded_reconciliation') or {}
    if schematic_analysis and bounded:
        bounded = direct_branch.promote_direct_single_segment_branches(
            bounded,
            schematic_analysis,
            min_branch_span_m=0.5,
            boundary_tolerance_m=0.05,
        )
        diag['vertical_level_bounded_reconciliation'] = bounded
    diag['detector'] = 'sanitary_pipe_network_v8_14'
    diag['status'] = 'DIAGNOSTIC_HORIZONTAL_PASS_VERTICAL_DIRECT_BRANCH_CANDIDATES'
    diag['note_v8_14'] = (
        'v8.14 keeps all v8.13 explicit-level safeguards and additionally accepts only a withheld vertical run that is exactly one segment, '
        'is directly labelled by an EXPLICIT_TAG_SEED, is at least 0.5 m long, and remains inside the explicit level band. '
        'The calibrated measured segment span is retained without snapping. Multi-segment service stubs, inferred classes and terminal extensions remain withheld. '
        'No vertical candidate is published as SAN-PIPE in this version.'
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
    diag = next((d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_14'), None)
    bounded = (diag or {}).get('vertical_level_bounded_reconciliation') or {}
    rec = (diag or {}).get('reconciliation') or {}
    print('AUTO_BOQ_V8_14_OK', json.dumps({
        'rows': len(result.get('rows', [])),
        'horizontal_gate': rec.get('horizontal_diameter_gate'),
        'vertical_candidate_runs': bounded.get('candidate_run_count', 0),
        'vertical_withheld_runs': bounded.get('withheld_run_count', 0),
        'direct_branch_promoted': bounded.get('direct_branch_promoted_count', 0),
        'vertical_candidate_rows': bounded.get('candidate_rows', []),
        'vertical_quantity_published': False,
        'published_pipe_rows': sum(1 for r in result.get('rows', []) if str(r.get('id','')).startswith('SAN-PIPE-')),
        'output': str(args.output),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
