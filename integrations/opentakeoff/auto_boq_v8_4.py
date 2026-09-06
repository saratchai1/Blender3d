#!/usr/bin/env python3
"""v8.4 diagnostic: combined detail-leader + primary-leader reconciliation.

v8.4 deliberately composes the latest v8.1 detail-transfer logic with the v8.2
primary-plan leader override. It remains diagnostic-only: no SAN-PIPE rows are
published, SN-04/SN-07 whole-view lengths remain non-additive, and unresolved
size evidence stays withheld.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import auto_boq_v8_2 as v82

SCHEMA = v82.SCHEMA


def extract(pdf_path: Path, profile_path: Path) -> dict[str, Any]:
    result = v82.extract(pdf_path, profile_path)
    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_2'),
        None,
    )
    if diag:
        diag['detector'] = 'sanitary_pipe_network_v8_4'
        diag['status'] = 'DIAGNOSTIC_COMBINED_LEADER_RECONCILIATION_NO_PUBLISHED_PIPE_ROWS'
        diag['version_evidence'] = {
            'detail_reconciliation': 'v8.3 leader-resolved enlarged-detail transfer inherited through auto_boq_v8_1',
            'primary_reconciliation': 'v8.2 explicit leader-to-semantic-layer override',
            'publication': 'WITHHELD_NO_SAN_PIPE_ROWS',
        }
        diag['note_v8_4'] = (
            'v8.4 combines leader-resolved enlarged-detail diameter evidence with explicit primary-plan leader association. '
            'Only primary-plan geometry can contribute horizontal candidate length. SN-04 and SN-07 remain evidence-only; '
            'ambiguous diameter evidence is withheld rather than guessed.'
        )
        for page in diag.get('pages', []):
            page['tag_parser_version'] = 'v8.4-normalized-diameter+detail-leader+primary-leader'
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = extract(args.pdf, args.profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    diag = next((d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_4'), None)
    pages = (diag or {}).get('pages') or []
    rec = (diag or {}).get('reconciliation') or {}
    print('AUTO_BOQ_V8_4_OK', json.dumps({
        'rows': len(result.get('rows', [])),
        'primary_coverage': {
            p.get('sheet'): (p.get('diameter_coverage') or {}).get('assigned_fraction')
            for p in pages if p.get('contribution_policy') == 'PRIMARY_PLAN_HORIZONTAL'
        },
        'leader_summary': (diag or {}).get('leader_association_summary', {}),
        'detail_probe_count': len((diag or {}).get('detail_view_reconciliation') or []),
        'horizontal_diameter_gate': rec.get('horizontal_diameter_gate'),
        'published_pipe_rows': sum(1 for row in result.get('rows', []) if str(row.get('id','')).startswith('SAN-PIPE-')),
        'output': str(args.output),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
