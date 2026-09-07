#!/usr/bin/env python3
"""v8.18: valve-reconciled, fail-closed sanitary pipe publication.

This version intentionally bypasses the superseded v8.16 blanket-CW release path.
It starts from validated v8.15 evidence, resolves substantive unresolved CW vertical
branches using explicit valve leaders from SN-04, runs the conservative release
reconciler, and publishes only when that reconciled release has zero blockers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import auto_boq_v8_15 as v815
import pipe_publish_v8 as publish
import pipe_release_reconcile_v8 as release
import probe_cw_valve_leaders_v8 as valve_probe
import vertical_valve_leader_reconcile_v8 as valve_reconcile

SCHEMA = v815.SCHEMA


def extract(pdf_path: Path, profile_path: Path, roof_evidence_path: Path) -> dict:
    result = v815.extract(pdf_path, profile_path, roof_evidence_path)
    roof_evidence = json.loads(roof_evidence_path.read_text(encoding='utf-8'))
    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_15'),
        None,
    )
    if not diag:
        return result

    probe = valve_probe.probe(pdf_path, profile_path)
    vertical = valve_reconcile.apply_valve_leader_evidence(
        diag.get('vertical_level_bounded_reconciliation') or {},
        probe,
        allowed_system='CW',
        min_span_m=0.5,
    )
    final = release.build_pipe_release_candidate(
        diag.get('reconciliation') or {},
        vertical,
        roof_source_page=int(roof_evidence['source_page']),
        max_excludable_cw_offset_m=0.5,
    )

    diag['vertical_level_bounded_reconciliation'] = vertical
    diag['cw_valve_leader_evidence'] = probe
    diag['pipe_release_candidate'] = final
    diag['detector'] = 'sanitary_pipe_network_v8_18'
    diag['status'] = (
        'VALIDATED_VALVE_RECONCILED_PIPE_RELEASE_READY'
        if final.get('status') == 'PASS_VALIDATED_PIPE_RELEASE_CANDIDATE'
        else 'WITHHELD_VALVE_RECONCILED_PIPE_RELEASE_BLOCKERS'
    )
    diag['reconciliation']['full_pipe_boq_publication_status'] = final.get('status')
    diag['note_v8_18'] = (
        'v8.18 starts from v8.15, then resolves only an unresolved vertical CW run touched by a unique explicit valve leader. '
        'For Family4, BALL VALVE Ø1/2 in SN-04 lands on segment 183 inside run 182-187, so that calibrated 1.228 m run is reclassified from inferred DN20 to explicit DN15. '
        'Remaining CW schematic offsets shorter than 0.5 m are non-quantity drawing offsets; roof V terminal pieces are already represented by the A-06-corroborated main vent risers. '
        'Publication remains fail-closed: rows are emitted only when the conservative release reconciler reports zero blockers.'
    )

    published = publish.publish_validated_pipe_rows(result, final)
    pdiag = next(
        (d for d in published.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_18'),
        None,
    )
    if pdiag:
        pdiag['status'] = 'PUBLISHED_VALIDATED_VALVE_RECONCILED_SANITARY_PIPE_ROWS'
        pdiag['reconciliation']['full_pipe_boq_publication_status'] = 'PUBLISHED_VALIDATED_PIPE_ROWS'
    return published


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
    pipe_rows = [r for r in result.get('rows', []) if str(r.get('id','')).startswith('SAN-PIPE-')]
    diag = next((d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_18'), None)
    vertical = (diag or {}).get('vertical_level_bounded_reconciliation') or {}
    final = (diag or {}).get('pipe_release_candidate') or {}
    print('AUTO_BOQ_V8_18_OK', json.dumps({
        'rows': len(result.get('rows', [])),
        'valve_promoted': vertical.get('valve_leader_promoted_count', 0),
        'release_status': final.get('status'),
        'release_blockers': final.get('release_blocker_count', 0),
        'excluded_non_quantity_runs': final.get('excluded_non_quantity_run_count', 0),
        'published_pipe_rows': len(pipe_rows),
        'published_pipe_total_m': round(sum(float(r.get('quantity') or 0.0) for r in pipe_rows), 3),
        'pipe_ids': [r['id'] for r in pipe_rows],
        'publication_status': ((diag or {}).get('reconciliation') or {}).get('full_pipe_boq_publication_status'),
        'output': str(args.output),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
