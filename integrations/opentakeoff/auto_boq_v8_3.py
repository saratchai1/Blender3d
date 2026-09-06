#!/usr/bin/env python3
"""v8.3 diagnostic: leader-aware primary tags and enlarged-detail transfer.

v8.3 A/B tests whether explicit leaders inside SN-07 recover additional diameter
seeds before detail geometry is transformed onto SN-05/SN-06. v8.1/v8.2 remain
unchanged. Detail lengths are still non-additive and no pipe BOQ rows are published.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import auto_boq_v8_1 as v81
import auto_boq_v8_2 as v82
import detail_view_transfer_v8 as detail_transfer
import leader_association_v8 as leader

SCHEMA = v81.SCHEMA
_BASE_DETAIL_ASSOCIATE = detail_transfer._associate_source_tags


def _associate_detail_source_tags_with_leaders(
    tags: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    component_by_segment: dict[int, int],
    present_layers: set[str],
    max_distance_pt: float,
) -> None:
    _BASE_DETAIL_ASSOCIATE(tags, segments, component_by_segment, present_layers, max_distance_pt)
    for tag in tags:
        tag['detail_proximity_association'] = {
            'association_status': tag.get('association_status'),
            'nearest_segment': tag.get('nearest_segment'),
            'component_id': tag.get('component_id'),
            'distance_pt': tag.get('distance_pt'),
            'associated_layer': tag.get('associated_layer'),
        }
        expected_layer = str(tag.get('expected_layer') or '').strip().upper()
        if not expected_layer or expected_layer not in present_layers:
            tag['detail_leader_association'] = {'status': 'WITHHELD_EXPECTED_LAYER_ABSENT'}
            continue
        resolved = leader.find_leader_target(
            tag_bbox_pt=list(map(float, tag['bbox_pt'])),
            segments=segments,
            component_by_segment=component_by_segment,
            expected_layer=expected_layer,
        )
        tag['detail_leader_association'] = resolved
        if resolved.get('status') != 'ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER':
            continue
        index = int(resolved['target_segment_index'])
        tag['nearest_segment'] = index
        tag['component_id'] = int(resolved['component_id'])
        tag['distance_pt'] = round(float(resolved.get('terminal_distance_pt', 0.0)), 3)
        tag['associated_layer'] = str(segments[index].get('layer') or '')
        tag['association_basis'] = 'DETAIL_LEADER_TO_PDF_CAD_LAYER'
        tag['association_status'] = 'ASSOCIATED_BY_DETAIL_LEADER_TO_PDF_CAD_LAYER'


def extract(pdf_path: Path, profile_path: Path) -> dict[str, Any]:
    original_primary = v81._associate_tags
    original_detail = detail_transfer._associate_source_tags
    v81._associate_tags = v82._associate_tags_with_leaders
    detail_transfer._associate_source_tags = _associate_detail_source_tags_with_leaders
    try:
        result = v81.extract(pdf_path, profile_path)
    finally:
        v81._associate_tags = original_primary
        detail_transfer._associate_source_tags = original_detail

    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_1'),
        None,
    )
    if not diag:
        return result
    diag['detector'] = 'sanitary_pipe_network_v8_3'
    diag['status'] = 'DIAGNOSTIC_DETAIL_LEADER_RECONCILED_NO_PUBLISHED_PIPE_ROWS'

    primary_leader_summary = {}
    for page in diag.get('pages', []):
        tags = page.get('tags_direct') or page.get('tags') or []
        accepted = [t for t in tags if t.get('association_basis') == 'LEADER_TO_PDF_CAD_LAYER']
        primary_leader_summary[str(page.get('sheet') or page.get('page'))] = len(accepted)
        page['tag_parser_version'] = 'v8.3-normalized-diameter+primary-leader+detail-leader+detail-transfer'

    detail_summary = {}
    for probe in diag.get('detail_view_reconciliation', []):
        source_tags = probe.get('source_tags') or []
        # Older probe payloads do not expose source_tags; transfer candidates still
        # let us quantify the effect with source/candidate/unmatched counters.
        detail_summary[str(probe.get('id'))] = {
            'match_score': (probe.get('match') or {}).get('match_score'),
            'source_tag_count': int(probe.get('source_tag_count', 0)),
            'transfer_candidates': int(probe.get('candidate_count', 0)),
            'ambiguous': int(probe.get('ambiguous_count', 0)),
            'unmatched': int(probe.get('unmatched_count', 0)),
            'source_tags_exposed': len(source_tags),
        }

    diag['primary_leader_association_count'] = primary_leader_summary
    diag['detail_leader_transfer_summary'] = detail_summary
    diag['note_v8_3'] = (
        'v8.3 applies the same conservative explicit-leader resolver inside the SN-07 enlarged details before affine transfer. '
        'Only unique leader-to-expected-layer paths can change the source detail segment. Ambiguous paths keep the existing detail proximity result. '
        'Transformed detail evidence remains diameter-seed-only; enlarged detail lengths are never added to primary-plan quantities.'
    )
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
    diag = next((d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_3'), None)
    pages = (diag or {}).get('pages') or []
    rec = (diag or {}).get('reconciliation') or {}
    print('AUTO_BOQ_V8_3_OK', json.dumps({
        'rows': len(result.get('rows', [])),
        'detail_summary': (diag or {}).get('detail_leader_transfer_summary', {}),
        'primary_coverage': {
            p.get('sheet'): (p.get('diameter_coverage') or {}).get('assigned_fraction')
            for p in pages if p.get('contribution_policy') == 'PRIMARY_PLAN_HORIZONTAL'
        },
        'accepted_detail_seeds': {
            p.get('sheet'): p.get('accepted_detail_seed_count', 0)
            for p in pages if p.get('contribution_policy') == 'PRIMARY_PLAN_HORIZONTAL'
        },
        'horizontal_diameter_gate': rec.get('horizontal_diameter_gate'),
        'published_pipe_rows': sum(1 for row in result.get('rows', []) if str(row.get('id','')).startswith('SAN-PIPE-')),
        'output': str(args.output),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
