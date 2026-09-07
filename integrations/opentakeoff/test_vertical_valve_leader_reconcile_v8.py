#!/usr/bin/env python3
from __future__ import annotations

import vertical_valve_leader_reconcile_v8 as valve


def main() -> None:
    bounded = {
        'candidate_runs': [
            {
                'system':'CW','diameter_key':'DN20','dn':20,
                'vertical_length_m_candidate':6.3,
                'classification_status':'CANDIDATE_COVERS_EXPLICIT_LEVEL_INTERVALS',
            },
        ],
        'withheld_runs': [
            {
                'system':'CW','diameter_key':'DN20','dn':20,'vertical_span_m':1.228,
                'segment_indexes':[182,183,184,185,186,187],
                'classification_status':'WITHHELD_NO_EXPLICIT_LEVEL_INTERVAL_MATCH',
            },
            {
                'system':'CW','diameter_key':'DN20','dn':20,'vertical_span_m':0.3,
                'segment_indexes':[210],
                'classification_status':'WITHHELD_NO_EXPLICIT_LEVEL_INTERVAL_MATCH',
            },
            {
                'system':'V','diameter_key':'DN50','dn':50,'vertical_span_m':0.8,
                'segment_indexes':[340],
                'classification_status':'WITHHELD_NO_EXPLICIT_LEVEL_INTERVAL_MATCH',
            },
        ],
    }
    probe = {
        'callouts': [
            {
                'name':'BALL VALVE','text':'BALL VALVE Ø1/2"',
                'diameter':{'diameter_key':'DN15','dn':15},
                'leader':{'status':'ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER','leader_hops':3,'terminal_distance_pt':0.9},
                'target_segment':{'segment_index':183,'layer':'CW'},
            },
            # Explicit evidence on another component must not affect the target run.
            {
                'name':'FLOAT VALVE','text':'FLOAT VALVE Ø1/2"',
                'diameter':{'diameter_key':'DN15','dn':15},
                'leader':{'status':'ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER','leader_hops':1,'terminal_distance_pt':1.2},
                'target_segment':{'segment_index':190,'layer':'CW'},
            },
        ],
    }
    out = valve.apply_valve_leader_evidence(bounded, probe, min_span_m=0.5)
    assert out['valve_leader_promoted_count'] == 1, out
    promoted = out['valve_leader_promoted_runs'][0]
    assert promoted['segment_indexes'] == [182,183,184,185,186,187], promoted
    assert promoted['diameter_key'] == 'DN15' and promoted['dn'] == 15, promoted
    assert promoted['superseded_inferred_diameter_key'] == 'DN20', promoted
    assert promoted['vertical_length_m_candidate'] == 1.228, promoted
    assert promoted['valve_evidence'][0]['target_segment_index'] == 183, promoted
    rows = {(r['system'],r['diameter_key']):r for r in out['candidate_rows']}
    assert rows[('CW','DN15')]['vertical_length_m_candidate'] == 1.228, rows
    assert rows[('CW','DN20')]['vertical_length_m_candidate'] == 6.3, rows
    assert out['withheld_run_count'] == 2, out
    print('VERTICAL_VALVE_LEADER_RECONCILE_V8_TEST_PASS', {'promoted':1,'withheld':2})


if __name__ == '__main__':
    main()
