#!/usr/bin/env python3
"""v8.16 diagnostic: v8.15 + final validated pipe release candidate.

This version still emits no SAN-PIPE rows. It proves that the additive horizontal
and validated physical vertical evidence can be combined without unresolved
physical-quantity blockers or double counting.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import auto_boq_v8_15 as v815
import pipe_release_reconcile_v8 as release

SCHEMA = v815.SCHEMA


def extract(pdf_path: Path, profile_path: Path, roof_evidence_path: Path) -> dict:
    result = v815.extract(pdf_path, profile_path, roof_evidence_path)
    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_15'),
        None,
    )
    if not diag:
        return result
    final = release.build_pipe_release_candidate(
        diag.get('reconciliation') or {},
        diag.get('vertical_level_bounded_reconciliation') or {},
    )
    diag['pipe_release_candidate'] = final
    diag['detector'] = 'sanitary_pipe_network_v8_16'
    diag['status'] = (
        'DIAGNOSTIC_PIPE_RELEASE_CANDIDATE_PASS_NO_PUBLISHED_PIPE_ROWS'
        if final.get('status') == 'PASS_VALIDATED_PIPE_RELEASE_CANDIDATE'
        else 'DIAGNOSTIC_PIPE_RELEASE_CANDIDATE_WITHHELD'
    )
    if final.get('status') == 'PASS_VALIDATED_PIPE_RELEASE_CANDIDATE':
        diag['reconciliation']['full_pipe_boq_publication_status'] = 'PASS_VALIDATED_PIPE_RELEASE_CANDIDATE'
    diag['note_v8_16'] = (
        'v8.16 combines only SN-05/SN-06 primary horizontal lengths with SN-04 vertical lengths already validated by explicit levels, direct tags and/or A-06 roof corroboration. '
        'SN-07 remains sizing/matching evidence only. Remaining V terminal drawing pieces are excluded because the roof-corroborated main riser already represents that height; '
        'remaining CW local schematic offsets are excluded because they do not map an explicit physical elevation interval. Every exclusion remains in the audit payload. '
        'This version proves the release gate but intentionally emits zero SAN-PIPE rows.'
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
    diag = next((d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_16'), None)
    final = (diag or {}).get('pipe_release_candidate') or {}
    print('AUTO_BOQ_V8_16_OK', json.dumps({
        'rows': len(result.get('rows', [])),
        'release_status': final.get('status'),
        'candidate_rows': final.get('candidate_rows', []),
        'excluded_non_quantity_runs': final.get('excluded_non_quantity_run_count', 0),
        'release_blockers': final.get('release_blocker_count', 0),
        'published_pipe_rows': sum(1 for r in result.get('rows', []) if str(r.get('id','')).startswith('SAN-PIPE-')),
        'output': str(args.output),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
