#!/usr/bin/env python3
from __future__ import annotations

import cross_view_system_consensus_v8 as consensus


def page(page_no: int, tags: list[dict]) -> dict:
    return {'page': page_no, 'tags_direct': tags}


def tag(system: str, diameter: str, layer: str, dn: int) -> dict:
    return {
        'system': system,
        'diameter_key': diameter,
        'expected_layer': layer,
        'dn': dn,
        'diameter_mm': float(dn),
        'diameter_in': None,
    }


def probe(detail_id: str, target_page: int, rows: list[dict]) -> dict:
    return {
        'id': detail_id,
        'target_page': target_page,
        'status': 'DIAGNOSTIC_TRANSFER_PROBED',
        'transfer_candidates': rows,
    }


def main() -> None:
    schematic = page(57, [
        tag('S', 'DN100', 'SOIL', 100),
        tag('SW', 'DN100', 'SOIL', 100),
        tag('V', 'DN50', 'V', 50),
        tag('W', 'DN65', 'WASTE', 65),
    ])

    # Primary + detail agreement is enough.
    p58 = page(58, [tag('W', 'DN50', 'WASTE', 50)])
    details = [probe('BATHROOM-1', 58, [tag('W', 'DN50', 'WASTE', 50)])]
    got = consensus.derive_consensus(p58, details, schematic)
    assert got['WASTE']['status'] == 'CORROBORATED_PAGE_LOCAL_MULTI_VIEW_CLASS', got
    assert got['WASTE']['system'] == 'W' and got['WASTE']['diameter_key'] == 'DN50', got

    # Two different matched details can corroborate even without a primary tag.
    p59 = page(59, [])
    details = [
        probe('BATHROOM-2', 59, [tag('CW', 'DN20', 'CW', 20)]),
        probe('BATHROOM-3', 59, [tag('CW', 'DN20', 'CW', 20)]),
    ]
    got = consensus.derive_consensus(p59, details, schematic)
    assert got['CW']['status'] == 'CORROBORATED_PAGE_LOCAL_MULTI_VIEW_CLASS', got

    # One local detail needs an exact single-diameter schematic corroboration.
    details = [probe('BATHROOM-3', 59, [tag('S', 'DN100', 'SOIL', 100)])]
    got = consensus.derive_consensus(p59, details, schematic)
    assert got['SOIL']['status'] == 'CORROBORATED_PAGE_LOCAL_PLUS_SCHEMATIC_CLASS', got
    assert got['SOIL']['basis'] == 'PAGE_LOCAL_PLUS_SCHEMATIC_CORROBORATION', got

    # A local conflict is terminal and schematic evidence may not override it.
    details = [probe('BATHROOM-1', 58, [
        tag('V', 'DN40', 'V', 40),
        tag('V', 'DN50', 'V', 50),
    ])]
    got = consensus.derive_consensus(page(58, []), details, schematic)
    assert got['V']['status'] == 'WITHHELD_CONFLICTING_LOCAL_CLASSES', got

    # Schematic must itself be single-class for the exact system.
    bad_schematic = page(57, [
        tag('S', 'DN100', 'SOIL', 100),
        tag('S', 'DN50', 'SOIL', 50),
    ])
    got = consensus.derive_consensus(
        p59,
        [probe('BATHROOM-3', 59, [tag('S', 'DN100', 'SOIL', 100)])],
        bad_schematic,
    )
    assert got['SOIL']['status'] == 'WITHHELD_INSUFFICIENT_INDEPENDENT_CORROBORATION', got

    # Application only changes evidence-free rows, never an existing class or tie.
    evidence = {
        'SOIL': {
            'status': 'CORROBORATED_PAGE_LOCAL_MULTI_VIEW_CLASS',
            'basis': 'PAGE_LOCAL_MULTI_VIEW_CONSENSUS',
            'system': 'SW', 'diameter_key': 'DN100', 'dn': 100,
            'diameter_mm': 100.0, 'diameter_in': 4.0,
        }
    }
    rows = [
        {'segment_index': 1, 'component_id': 1, 'layer': 'SOIL', 'length_pt': 10.0,
         'status': 'WITHHELD_NO_DIAMETER_EVIDENCE', 'classes': []},
        {'segment_index': 2, 'component_id': 2, 'layer': 'SOIL', 'length_pt': 7.0,
         'status': 'WITHHELD_DIAMETER_TIE', 'classes': [{'system':'S','diameter_key':'DN50'}]},
        {'segment_index': 3, 'component_id': 3, 'layer': 'SOIL', 'length_pt': 5.0,
         'status': 'EXPLICIT_TAG_SEED', 'classes': [{'system':'S','diameter_key':'DN100'}]},
    ]
    applied, summary = consensus.apply_consensus_to_assignments(rows, evidence)
    assert applied[0]['status'] == 'CROSS_VIEW_CORROBORATED_SYSTEM_CLASS', applied
    assert applied[0]['classes'][0]['diameter_key'] == 'DN100', applied
    assert applied[1] == rows[1], applied
    assert applied[2] == rows[2], applied
    assert summary[0]['seeded_segment_count'] == 1 and summary[0]['seeded_length_pt'] == 10.0, summary
    print('CROSS_VIEW_SYSTEM_CONSENSUS_V8_TEST_PASS')


if __name__ == '__main__':
    main()
