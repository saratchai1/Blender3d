#!/usr/bin/env python3
"""Pure regression tests for v8.1 diameter normalization and view reconciliation."""
from __future__ import annotations

import pipe_reconcile_v8 as p


def main() -> None:
    cases = {
        '2-1/2"': 'DN65',
        '21/2"': 'DN65',
        'DN50': 'DN50',
        '50 mm': 'DN50',
        'Ø2': 'DN50',
        '25': 'DN25',
    }
    for raw, expected in cases.items():
        assert p.normalize_diameter(raw)['diameter_key'] == expected, raw

    for text in ('Ø2" W', 'W Ø2"', 'DIA. 50 mm CW', 'CW DN25', 'Ø21/2 SW'):
        assert p.extract_pipe_tag_classes(text), text

    segments = [
        {'a': (0, 0), 'b': (100, 0), 'length_pt': 100, 'layer': 'WASTE'},
        {'a': (100, 0), 'b': (200, 0), 'length_pt': 100, 'layer': 'WASTE'},
        {'a': (200, 0), 'b': (300, 0), 'length_pt': 100, 'layer': 'WASTE'},
    ]
    components = [{'id': 0, 'segment_indexes': [0, 1, 2]}]
    tags = [
        {'component_id': 0, 'nearest_segment': 0, 'system': 'W', 'diameter_key': 'DN25', 'dn': 25, 'diameter_mm': 25, 'diameter_in': 1.0},
        {'component_id': 0, 'nearest_segment': 2, 'system': 'W', 'diameter_key': 'DN50', 'dn': 50, 'diameter_mm': 50, 'diameter_in': 2.0},
    ]
    assigned = p.assign_segment_diameters(segments, components, tags, endpoint_snap_pt=0.1)
    assert assigned[0]['classes'][0]['diameter_key'] == 'DN25', assigned
    assert assigned[2]['classes'][0]['diameter_key'] == 'DN50', assigned
    # The middle run is equidistant from two contradictory size seeds. Never guess.
    assert assigned[1]['status'] == 'WITHHELD_DIAMETER_TIE', assigned
    rows, coverage = p.aggregate_diameter_rows(assigned, 100)
    assert coverage['assigned_fraction'] == 0.6667, coverage
    assert {row['diameter_key'] for row in rows} == {'DN25', 'DN50'}, rows

    pages = [
        {
            'page': 58,
            'sheet': 'SN-05',
            'view_role': 'ground_floor_plan',
            'contribution_policy': 'PRIMARY_PLAN_HORIZONTAL',
            'effective_scale_candidates': [100],
            'diameter_coverage': {'assigned_fraction': 1.0},
            'diameter_rows': [{'system': 'W', 'diameter_key': 'DN50', 'dn': 50, 'diameter_mm': 50, 'diameter_in': 2.0, 'length_m_candidate': 10.0, 'segment_count': 3}],
        },
        {
            'page': 57,
            'sheet': 'SN-04',
            'view_role': 'vertical_schematic',
            'contribution_policy': 'DIAGNOSTIC_VERTICAL_ONLY_DO_NOT_ADD_WHOLE_VIEW',
            'diameter_coverage': {'assigned_fraction': 1.0},
            'diameter_rows': [{'system': 'W', 'diameter_key': 'DN50', 'length_m_candidate': 30.0, 'segment_count': 9}],
        },
        {
            'page': 60,
            'sheet': 'SN-07',
            'view_role': 'enlarged_bathroom_details',
            'contribution_policy': 'DETAIL_OVERLAY_DO_NOT_ADD_TO_PRIMARY_PLANS',
            'diameter_coverage': {'assigned_fraction': 1.0},
            'diameter_rows': [{'system': 'W', 'diameter_key': 'DN50', 'length_m_candidate': 8.0, 'segment_count': 2}],
        },
    ]
    reconciled = p.reconcile_pages(pages)
    assert reconciled['horizontal_primary_rows'][0]['length_m_candidate'] == 10.0, reconciled
    assert reconciled['cross_view_policy_status'] == 'PASS_NON_ADDITIVE_BY_VIEW_ROLE', reconciled
    assert reconciled['horizontal_diameter_gate'] == 'PASS', reconciled
    assert reconciled['full_pipe_boq_publication_status'].startswith('WITHHELD_'), reconciled
    excluded = {row['sheet']: row['reason'] for row in reconciled['excluded_non_additive_views']}
    assert excluded['SN-04'] == 'VERTICAL_SCHEMATIC_EVIDENCE_ONLY', excluded
    assert excluded['SN-07'] == 'DETAIL_OVERLAY_EVIDENCE_ONLY', excluded

    print('AUTO_BOQ_V8_1_RECONCILE_TEST_PASS', {
        'diameter': 'inch/mm/DN normalized',
        'split': 'network nearest-tag + tie withheld',
        'views': 'schematic/detail non-additive',
    })


if __name__ == '__main__':
    main()
