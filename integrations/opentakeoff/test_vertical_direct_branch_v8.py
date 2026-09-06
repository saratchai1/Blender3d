#!/usr/bin/env python3
from __future__ import annotations

import vertical_direct_branch_v8 as direct


def main() -> None:
    bounded = {
        'status': 'LEVEL_BOUNDED_VERTICAL_CANDIDATES',
        'candidate_runs': [
            {'system':'V','diameter_key':'DN50','dn':50,'vertical_length_m_candidate':3.75,'classification_status':'CANDIDATE_COVERS_FULL_EXPLICIT_LEVEL_BAND'},
        ],
        'withheld_runs': [
            # Safe: explicit, one segment, >0.5 m, inside explicit level band.
            {'system':'W','diameter_key':'DN65','dn':65,'vertical_span_m':1.2,'segment_indexes':[10],'terminal_extension_above_m':0.0,'terminal_extension_below_m':0.0},
            # Not direct evidence.
            {'system':'CW','diameter_key':'DN20','dn':20,'vertical_span_m':1.1,'segment_indexes':[11],'terminal_extension_above_m':0.0,'terminal_extension_below_m':0.0},
            # Too short.
            {'system':'CW','diameter_key':'DN20','dn':20,'vertical_span_m':0.4,'segment_indexes':[12],'terminal_extension_above_m':0.0,'terminal_extension_below_m':0.0},
            # Terminal extension outside explicit band.
            {'system':'V','diameter_key':'DN50','dn':50,'vertical_span_m':0.8,'segment_indexes':[13],'terminal_extension_above_m':0.2,'terminal_extension_below_m':0.0},
            # Multi-segment run cannot use the narrow rule.
            {'system':'W','diameter_key':'DN65','dn':65,'vertical_span_m':1.3,'segment_indexes':[14,15],'terminal_extension_above_m':0.0,'terminal_extension_below_m':0.0},
        ],
        'candidate_rows': [],
    }
    analysis = {'diameter_assignments': [
        {'segment_index':10,'status':'EXPLICIT_TAG_SEED','classes':[{'system':'W','diameter_key':'DN65','dn':65}]},
        {'segment_index':11,'status':'NETWORK_NEAREST_TAG_PROPAGATION','classes':[{'system':'CW','diameter_key':'DN20','dn':20}]},
        {'segment_index':12,'status':'EXPLICIT_TAG_SEED','classes':[{'system':'CW','diameter_key':'DN20','dn':20}]},
        {'segment_index':13,'status':'EXPLICIT_TAG_SEED','classes':[{'system':'V','diameter_key':'DN50','dn':50}]},
        {'segment_index':14,'status':'EXPLICIT_TAG_SEED','classes':[{'system':'W','diameter_key':'DN65','dn':65}]},
        {'segment_index':15,'status':'EXPLICIT_TAG_SEED','classes':[{'system':'W','diameter_key':'DN65','dn':65}]},
    ]}
    result = direct.promote_direct_single_segment_branches(bounded, analysis)
    assert result['status'] == 'LEVEL_BOUNDED_PLUS_DIRECT_BRANCH_VERTICAL_CANDIDATES', result
    assert result['direct_branch_promoted_count'] == 1, result
    promoted = result['direct_branch_promoted_runs'][0]
    assert promoted['system'] == 'W' and promoted['diameter_key'] == 'DN65', promoted
    assert promoted['vertical_length_m_candidate'] == 1.2, promoted
    assert promoted['classification_status'] == 'CANDIDATE_EXPLICIT_SINGLE_SEGMENT_VERTICAL_BRANCH', promoted
    assert len(result['withheld_runs']) == 4, result['withheld_runs']
    rows = {(r['system'],r['diameter_key']):r for r in result['candidate_rows']}
    assert rows[('V','DN50')]['vertical_length_m_candidate'] == 3.75, rows
    assert rows[('W','DN65')]['vertical_length_m_candidate'] == 1.2, rows
    assert 'SN-04_EXPLICIT_DIRECT_SINGLE_SEGMENT' in rows[('W','DN65')]['sources'], rows
    print('VERTICAL_DIRECT_BRANCH_V8_TEST_PASS', {'promoted':1,'withheld':4})


if __name__ == '__main__':
    main()
