#!/usr/bin/env python3
"""v8.15 diagnostic: v8.14 + architectural roof corroboration for main vents.

A Family4 source-evidence file records the raster A-06 roof-plan level. Only main
vent risers already accepted through the explicit level band can be extended when
their independently calibrated SN-04 top agrees with that roof level. Short AVC
geometry remains withheld to prevent double counting. No SAN-PIPE rows publish.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import auto_boq_v8_14 as v814
import roof_terminal_reconcile_v8 as roof_terminal

SCHEMA = v814.SCHEMA


def extract(pdf_path: Path, profile_path: Path, roof_evidence_path: Path) -> dict:
    result = v814.extract(pdf_path, profile_path)
    evidence = json.loads(roof_evidence_path.read_text(encoding='utf-8'))
    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_14'),
        None,
    )
    if not diag:
        return result
    bounded = diag.get('vertical_level_bounded_reconciliation') or {}
    reconciled = roof_terminal.apply_roof_terminal_evidence(
        bounded,
        evidence,
        base_elevation_m=0.0,
    )
    diag['vertical_level_bounded_reconciliation'] = reconciled
    diag['detector'] = 'sanitary_pipe_network_v8_15'
    diag['status'] = 'DIAGNOSTIC_HORIZONTAL_PASS_ROOF_CORROBORATED_VERTICAL_CANDIDATES'
    diag['architectural_roof_evidence'] = evidence
    diag['note_v8_15'] = (
        'v8.15 preserves v8.14 direct-branch safeguards and uses A-06 source-page roof elevation only to corroborate full-band V main risers. '
        'The SN-04 calibrated raw tops must independently agree with the architectural roof level within the evidence tolerance. '
        'Short AVC/terminal geometry remains withheld and is not added again. No vertical candidate is published as SAN-PIPE in this version.'
    )
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', type=Path, required=True)
    ap.add_argument('--profile', type=Path, required=True)
    ap.add_argument('--roof-evidence', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    result = extract(args.pdf, args.profile, args.roof_evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    diag = next((d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_15'), None)
    bounded = (diag or {}).get('vertical_level_bounded_reconciliation') or {}
    rec = (diag or {}).get('reconciliation') or {}
    print('AUTO_BOQ_V8_15_OK', json.dumps({
        'rows': len(result.get('rows', [])),
        'horizontal_gate': rec.get('horizontal_diameter_gate'),
        'roof_terminal_status': bounded.get('roof_terminal_status'),
        'roof_extended_runs': bounded.get('roof_extended_run_count', 0),
        'vertical_candidate_rows': bounded.get('candidate_rows', []),
        'vertical_withheld_runs': bounded.get('withheld_run_count', 0),
        'vertical_quantity_published': False,
        'published_pipe_rows': sum(1 for r in result.get('rows', []) if str(r.get('id','')).startswith('SAN-PIPE-')),
        'output': str(args.output),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
