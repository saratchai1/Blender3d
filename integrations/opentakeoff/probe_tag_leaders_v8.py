#!/usr/bin/env python3
"""Diagnostic comparison of explicit leader paths vs current tag proximity.

No BOQ quantity changes. This probe scans source drawing pages only, follows
short non-pipe linework from each size/system text box to the expected semantic
CAD layer, and records whether that explicit leader would agree with or change
v8.1's current proximity association.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz

import auto_boq as base
import auto_boq_v8 as v8
import auto_boq_v8_1 as v81
import leader_association_v8 as leader


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', type=Path, required=True)
    ap.add_argument('--profile', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()

    profile = json.loads(args.profile.read_text(encoding='utf-8'))
    cfg = profile.get('sanitary_pipe_network', {})
    doc = fitz.open(args.pdf)
    guarded = base.GuardedPdf(doc, int(profile['source_page_max']))
    pages = []

    for spec in cfg.get('page_specs', []):
        page_no = int(spec['page'])
        page = guarded.page(page_no)
        segments = v8.line_segments(
            page,
            spec.get('bounds_pt'),
            float(cfg.get('min_segment_pt', 3.0)),
            float(cfg.get('max_stroke_width_pt', 3.0)),
        )
        components, component_by_segment = v8.style_components(
            segments,
            float(cfg.get('endpoint_snap_pt', 1.5)),
        )
        del components
        present_layers = v8.declared_layers(page)
        tags = v81.pipe_tag_anchors(page, spec.get('bounds_pt'))
        v81._associate_tags(
            tags,
            segments,
            component_by_segment,
            present_layers,
            float(cfg.get('tag_snap_max_pt', 30.0)),
        )

        rows = []
        for tag in tags:
            expected_layer = str(tag.get('expected_layer') or '')
            lead = leader.find_leader_target(
                tag_bbox_pt=list(map(float, tag['bbox_pt'])),
                segments=segments,
                component_by_segment=component_by_segment,
                expected_layer=expected_layer,
                source_snap_pt=float(cfg.get('leader_source_snap_pt', 3.0)),
                leader_snap_pt=float(cfg.get('leader_segment_snap_pt', 1.5)),
                target_snap_pt=float(cfg.get('leader_target_snap_pt', 2.5)),
                max_leader_segment_pt=float(cfg.get('leader_max_segment_pt', 80.0)),
                max_path_pt=float(cfg.get('leader_max_path_pt', 120.0)),
                max_hops=int(cfg.get('leader_max_hops', 4)),
                ambiguity_margin_pt=float(cfg.get('leader_ambiguity_margin_pt', 1.0)),
            )
            current_segment = tag.get('nearest_segment')
            current_component = tag.get('component_id')
            leader_segment = lead.get('target_segment_index')
            leader_component = lead.get('component_id')
            if lead.get('status') == 'ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER':
                comparison = (
                    'AGREES_CURRENT_COMPONENT'
                    if current_component is not None and int(current_component) == int(leader_component)
                    else 'LEADER_PROPOSES_DIFFERENT_COMPONENT'
                    if current_component is not None
                    else 'LEADER_RECOVERS_UNASSOCIATED_TAG'
                )
            else:
                comparison = 'NO_ACCEPTED_LEADER_ASSOCIATION'
            rows.append({
                'text': tag.get('text'),
                'system': tag.get('system'),
                'diameter_key': tag.get('diameter_key'),
                'bbox_pt': tag.get('bbox_pt'),
                'expected_layer': expected_layer,
                'current': {
                    'association_status': tag.get('association_status'),
                    'segment_index': current_segment,
                    'component_id': current_component,
                    'distance_pt': tag.get('distance_pt'),
                },
                'leader': lead,
                'comparison': comparison,
                'proposed_segment_index': leader_segment,
                'proposed_component_id': leader_component,
            })

        pages.append({
            'page': page_no,
            'sheet': spec.get('sheet'),
            'view_role': spec.get('view_role'),
            'contribution_policy': spec.get('contribution_policy'),
            'tag_count': len(tags),
            'leader_associated': sum(1 for row in rows if row['leader'].get('status') == 'ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER'),
            'leader_changes': sum(1 for row in rows if row['comparison'] == 'LEADER_PROPOSES_DIFFERENT_COMPONENT'),
            'leader_recovers': sum(1 for row in rows if row['comparison'] == 'LEADER_RECOVERS_UNASSOCIATED_TAG'),
            'rows': rows,
        })

    doc.close()
    result = {
        'status': 'DIAGNOSTIC_ONLY_NO_QUANTITY_CHANGE',
        'source_policy': 'drawing pages only; no benchmark/reference quantities',
        'pages': pages,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('AUTO_BOQ_V8_LEADER_PROBE_OK', json.dumps({
        row['sheet']: {
            'tags': row['tag_count'],
            'leader_associated': row['leader_associated'],
            'changes': row['leader_changes'],
            'recovers': row['leader_recovers'],
        }
        for row in pages
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
