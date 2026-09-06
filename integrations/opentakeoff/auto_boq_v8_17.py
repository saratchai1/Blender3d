#!/usr/bin/env python3
"""v8.17: publish validated sanitary pipe BOQ rows after the v8.16 release gate.

Publication is fail-closed. The publisher refuses to emit SAN-PIPE rows unless the
full validated release candidate has PASS status, zero blockers, and an explicit
READY_FOR_PIPE_ROW_PUBLICATION policy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import auto_boq_v8_16 as v816
import pipe_publish_v8 as publish

SCHEMA = v816.SCHEMA


def extract(pdf_path: Path, profile_path: Path, roof_evidence_path: Path) -> dict:
    result = v816.extract(pdf_path, profile_path, roof_evidence_path)
    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_16'),
        None,
    )
    if not diag:
        return result
    release = diag.get('pipe_release_candidate') or {}
    published = publish.publish_validated_pipe_rows(result, release)
    diag2 = next(
        (d for d in published.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_16'),
        None,
    )
    if diag2:
        diag2['detector'] = 'sanitary_pipe_network_v8_17'
        diag2['status'] = 'PUBLISHED_VALIDATED_SANITARY_PIPE_ROWS'
        diag2['reconciliation']['full_pipe_boq_publication_status'] = 'PUBLISHED_VALIDATED_PIPE_ROWS'
        diag2['note_v8_17'] = (
            'v8.17 publishes the v8.16 validated release candidate as SAN-PIPE rows. Horizontal quantities come only from SN-05/SN-06 primary plans. '
            'Vertical quantities come only from SN-04 runs validated by explicit levels/direct labels and, for main vent tops, A-06 roof corroboration. '
            'SN-07 remains sizing/matching evidence only. The ten residual schematic/terminal runs remain fully traceable as non-quantity exclusions and add zero metres.'
        )
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
    diag = next((d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_17'), None)
    print('AUTO_BOQ_V8_17_OK', json.dumps({
        'rows': len(result.get('rows', [])),
        'published_pipe_rows': len(pipe_rows),
        'published_pipe_total_m': round(sum(float(r.get('quantity') or 0.0) for r in pipe_rows), 3),
        'pipe_ids': [r['id'] for r in pipe_rows],
        'publication_status': ((diag or {}).get('reconciliation') or {}).get('full_pipe_boq_publication_status'),
        'output': str(args.output),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
