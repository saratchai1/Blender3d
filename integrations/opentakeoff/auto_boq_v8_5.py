#!/usr/bin/env python3
"""v8.5 diagnostic: semantic-layer topology instead of stroke-style fragmentation.

v8.5 composes v8.4 evidence but temporarily replaces v8's component builder with
layer-only endpoint/T-junction topology. Width/color/dash changes therefore do not
split a physical pipe network. Interior/interior X crossings remain disconnected,
and diameter differences are resolved by the existing multi-seed graph resolver.
No pipe rows are published.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import auto_boq_v8 as v8
import auto_boq_v8_4 as v84
import layer_topology_v8 as layer_topology

SCHEMA = v84.SCHEMA


def extract(pdf_path: Path, profile_path: Path) -> dict[str, Any]:
    original = v8.style_components
    v8.style_components = layer_topology.layer_components
    try:
        result = v84.extract(pdf_path, profile_path)
    finally:
        v8.style_components = original

    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_4'),
        None,
    )
    if diag:
        diag['detector'] = 'sanitary_pipe_network_v8_5'
        diag['status'] = 'DIAGNOSTIC_LAYER_TOPOLOGY_NO_PUBLISHED_PIPE_ROWS'
        diag['topology_policy'] = {
            'component_identity': 'PDF_CAD_LAYER + endpoint/T-junction geometry',
            'ignored_for_connectivity': ['stroke width', 'stroke color', 'dash pattern'],
            'x_crossing_policy': 'INTERIOR_INTERIOR_NOT_CONNECTED',
            'diameter_policy': 'MULTI_SEED_NETWORK_PROPAGATION_WITH_TIES_WITHHELD',
        }
        diag['note_v8_5'] = (
            'Semantic pipe networks are no longer fragmented merely by CAD stroke-style changes. '
            'Different layers never merge, interior X crossings remain disconnected, and competing diameter seeds '
            'are reconciled by graph distance with ambiguous ties withheld. SN-04/SN-07 remain non-additive evidence-only views.'
        )
        for page in diag.get('pages', []):
            page['topology_version'] = 'v8.5-semantic-layer-endpoint-T'
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
    diag = next((d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_5'), None)
    pages = (diag or {}).get('pages') or []
    rec = (diag or {}).get('reconciliation') or {}
    print('AUTO_BOQ_V8_5_OK', json.dumps({
        'rows': len(result.get('rows', [])),
        'primary_coverage': {
            p.get('sheet'): (p.get('diameter_coverage') or {}).get('assigned_fraction')
            for p in pages if p.get('contribution_policy') == 'PRIMARY_PLAN_HORIZONTAL'
        },
        'primary_components': {
            p.get('sheet'): p.get('component_count')
            for p in pages if p.get('contribution_policy') == 'PRIMARY_PLAN_HORIZONTAL'
        },
        'horizontal_diameter_gate': rec.get('horizontal_diameter_gate'),
        'published_pipe_rows': sum(1 for row in result.get('rows', []) if str(row.get('id','')).startswith('SAN-PIPE-')),
        'output': str(args.output),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
