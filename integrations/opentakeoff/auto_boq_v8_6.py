#!/usr/bin/env python3
"""v8.6 diagnostic baseline: strict tags + both leader stages + layer topology.

This version corrects the earlier wrapper composition ambiguity. It explicitly
uses v8.3 (which applies leaders on both primary tags and enlarged-detail source
tags), while also enabling v8.5 semantic-layer topology and a strict pipe-system
token parser. No pipe BOQ rows are published.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import auto_boq_v8 as v8
import auto_boq_v8_3 as v83
import layer_topology_v8 as layer_topology
import pipe_reconcile_v8 as reconcile
import strict_pipe_tags_v8 as strict_tags

SCHEMA = v83.SCHEMA


def extract(pdf_path: Path, profile_path: Path) -> dict:
    original_components = v8.style_components
    original_parser = reconcile.extract_pipe_tag_classes
    v8.style_components = layer_topology.layer_components
    reconcile.extract_pipe_tag_classes = strict_tags.extract_pipe_tag_classes
    try:
        result = v83.extract(pdf_path, profile_path)
    finally:
        v8.style_components = original_components
        reconcile.extract_pipe_tag_classes = original_parser

    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_3'),
        None,
    )
    if diag:
        diag['detector'] = 'sanitary_pipe_network_v8_6'
        diag['status'] = 'DIAGNOSTIC_STRICT_COMPOSED_RECONCILIATION_NO_PUBLISHED_PIPE_ROWS'
        diag['composition'] = {
            'tag_parser': 'STRICT_STANDALONE_SYSTEM_TOKENS',
            'primary_tag_association': 'EXPLICIT_LEADER_THEN_PROXIMITY_FALLBACK',
            'detail_tag_association': 'EXPLICIT_LEADER_THEN_PROXIMITY_FALLBACK',
            'detail_to_primary': 'AFFINE_DIAMETER_SEED_ONLY',
            'topology': 'SEMANTIC_LAYER_ENDPOINT_T_JUNCTION',
            'publication': 'WITHHELD_NO_SAN_PIPE_ROWS',
        }
        diag['note_v8_6'] = (
            'v8.6 rejects system abbreviations embedded inside ordinary words, composes both leader stages explicitly, '
            'and uses semantic-layer topology so stroke-style changes do not fragment physical networks. '
            'SN-04/SN-07 whole-view lengths remain non-additive and ambiguous evidence remains withheld.'
        )
        for page in diag.get('pages', []):
            page['tag_parser_version'] = 'v8.6-strict-system-boundary+primary-leader+detail-leader'
            page['topology_version'] = 'v8.6-semantic-layer-endpoint-T'
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
    diag = next((d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_6'), None)
    pages = (diag or {}).get('pages') or []
    rec = (diag or {}).get('reconciliation') or {}
    print('AUTO_BOQ_V8_6_OK', json.dumps({
        'rows': len(result.get('rows', [])),
        'primary_coverage': {
            p.get('sheet'): (p.get('diameter_coverage') or {}).get('assigned_fraction')
            for p in pages if p.get('contribution_policy') == 'PRIMARY_PLAN_HORIZONTAL'
        },
        'primary_components': {
            p.get('sheet'): p.get('component_count')
            for p in pages if p.get('contribution_policy') == 'PRIMARY_PLAN_HORIZONTAL'
        },
        'leader_primary': (diag or {}).get('primary_leader_association_count', {}),
        'detail_summary': (diag or {}).get('detail_leader_transfer_summary', {}),
        'horizontal_diameter_gate': rec.get('horizontal_diameter_gate'),
        'published_pipe_rows': sum(1 for row in result.get('rows', []) if str(row.get('id','')).startswith('SAN-PIPE-')),
        'output': str(args.output),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
