#!/usr/bin/env python3
"""v8.2 diagnostic extension: explicit leader paths before tag proximity.

v8.2 intentionally leaves v8.1 intact for A/B evidence. It temporarily wraps the
v8.1 tag association step so a unique short non-pipe leader reaching the expected
semantic CAD layer may override proximity. Ambiguous/no-leader cases retain v8.1
behavior. Pipe BOQ publication remains withheld.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import auto_boq_v8_1 as v81
import leader_association_v8 as leader

SCHEMA = v81.SCHEMA
_BASE_ASSOCIATE = v81._associate_tags


def _associate_tags_with_leaders(
    tags: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    component_by_segment: dict[int, int],
    present_layers: set[str],
    max_distance_pt: float,
) -> None:
    # Preserve the complete v8.1 proximity result as fallback/audit evidence.
    _BASE_ASSOCIATE(tags, segments, component_by_segment, present_layers, max_distance_pt)
    for tag in tags:
        proximity = {
            'association_status': tag.get('association_status'),
            'association_basis': tag.get('association_basis'),
            'nearest_segment': tag.get('nearest_segment'),
            'component_id': tag.get('component_id'),
            'distance_pt': tag.get('distance_pt'),
            'associated_layer': tag.get('associated_layer'),
        }
        tag['proximity_association_v8_1'] = proximity
        expected_layer = str(tag.get('expected_layer') or '').strip().upper()
        if not expected_layer or expected_layer not in present_layers:
            tag['leader_association'] = {'status': 'WITHHELD_EXPECTED_LAYER_ABSENT'}
            continue
        resolved = leader.find_leader_target(
            tag_bbox_pt=list(map(float, tag['bbox_pt'])),
            segments=segments,
            component_by_segment=component_by_segment,
            expected_layer=expected_layer,
        )
        tag['leader_association'] = resolved
        if resolved.get('status') != 'ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER':
            continue
        index = int(resolved['target_segment_index'])
        tag['nearest_segment'] = index
        tag['component_id'] = int(resolved['component_id'])
        tag['distance_pt'] = round(float(resolved.get('terminal_distance_pt', 0.0)), 3)
        tag['associated_layer'] = str(segments[index].get('layer') or '')
        tag['association_basis'] = 'LEADER_TO_PDF_CAD_LAYER'
        tag['association_status'] = 'ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER'


def extract(pdf_path: Path, profile_path: Path) -> dict[str, Any]:
    original = v81._associate_tags
    v81._associate_tags = _associate_tags_with_leaders
    try:
        result = v81.extract(pdf_path, profile_path)
    finally:
        v81._associate_tags = original

    diag = next(
        (d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_1'),
        None,
    )
    if diag:
        diag['detector'] = 'sanitary_pipe_network_v8_2'
        diag['status'] = 'DIAGNOSTIC_LEADER_RECONCILED_NO_PUBLISHED_PIPE_ROWS'
        leader_summary = {}
        for page in diag.get('pages', []):
            tags = page.get('tags_direct') or page.get('tags') or []
            accepted = [t for t in tags if t.get('association_basis') == 'LEADER_TO_PDF_CAD_LAYER']
            changed = [
                t for t in accepted
                if (t.get('proximity_association_v8_1') or {}).get('component_id') is not None
                and int((t.get('proximity_association_v8_1') or {}).get('component_id')) != int(t.get('component_id'))
            ]
            recovered = [
                t for t in accepted
                if (t.get('proximity_association_v8_1') or {}).get('component_id') is None
            ]
            leader_summary[str(page.get('sheet') or page.get('page'))] = {
                'accepted_leader_tags': len(accepted),
                'changed_from_proximity': len(changed),
                'recovered_unassociated': len(recovered),
            }
        diag['leader_association_summary'] = leader_summary
        diag['note_v8_2'] = (
            'Unique explicit leader paths may override v8.1 text-center proximity only when they terminate on the expected semantic CAD layer. '
            'Ambiguous leader targets are withheld and fall back to the prior diagnostic association. Direct primary tags still outrank detail seeds; '
            'schematic/detail whole-view lengths remain non-additive.'
        )
        for page in diag.get('pages', []):
            page['tag_parser_version'] = 'v8.2-normalized-diameter+leader+detail-transfer'
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
    diag = next((d for d in result.get('diagnostics', []) if d.get('detector') == 'sanitary_pipe_network_v8_2'), None)
    pages = (diag or {}).get('pages') or []
    rec = (diag or {}).get('reconciliation') or {}
    print('AUTO_BOQ_V8_2_OK', json.dumps({
        'rows': len(result.get('rows', [])),
        'leader_summary': (diag or {}).get('leader_association_summary', {}),
        'primary_coverage': {
            p.get('sheet'): (p.get('diameter_coverage') or {}).get('assigned_fraction')
            for p in pages if p.get('contribution_policy') == 'PRIMARY_PLAN_HORIZONTAL'
        },
        'horizontal_diameter_gate': rec.get('horizontal_diameter_gate'),
        'published_pipe_rows': sum(1 for row in result.get('rows', []) if str(row.get('id','')).startswith('SAN-PIPE-')),
        'output': str(args.output),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
