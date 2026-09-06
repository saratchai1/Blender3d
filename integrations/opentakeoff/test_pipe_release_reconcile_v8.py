#!/usr/bin/env python3
from __future__ import annotations

import pipe_release_reconcile_v8 as release


def main() -> None:
    reconciliation = {
        'horizontal_diameter_gate':'PASS',
        'horizontal_primary_rows':[
            {'system':'CW','diameter_key':'DN20','dn':20,'diameter_mm':20.0,'diameter_in':0.75,'length_m_candidate':10.0,'source_pages':[58,59]},
            {'system':'V','diameter_key':'DN50','dn':50,'diameter_mm':50.0,'diameter_in':2.0,'length_m_candidate':1.0,'source_pages':[58]},
        ],
    }
    vertical = {
        'roof_terminal_status':'APPLIED',
        'roof_extended_runs':[{'system':'V','diameter_key':'DN50'}],
        'candidate_rows':[
            {'system':'CW','diameter_key':'DN20','dn':20,'vertical_length_m_candidate':6.3,'sources':['SN-04_EXPLICIT_LEVEL_INTERVALS']},
            {'system':'V','diameter_key':'DN50','dn':50,'vertical_length_m_candidate':13.3,'sources':['SN-04_CALIBRATED_PLUS_A-06_ROOF_LEVEL']},
        ],
        'withheld_runs':[
            {'system':'V','diameter_key':'DN50','terminal_extension_above_m':0.6,'terminal_extension_below_m':0.0},
            {'system':'CW','diameter_key':'DN20','terminal_extension_above_m':0.0,'terminal_extension_below_m':0.0},
        ],
    }
    out = release.build_pipe_release_candidate(reconciliation, vertical)
    assert out['status']=='PASS_VALIDATED_PIPE_RELEASE_CANDIDATE',out
    assert out['release_blocker_count']==0,out
    assert out['excluded_non_quantity_run_count']==2,out
    rows={(r['system'],r['diameter_key']):r for r in out['candidate_rows']}
    assert rows[('CW','DN20')]['horizontal_length_m']==10.0,rows
    assert rows[('CW','DN20')]['vertical_length_m']==6.3,rows
    assert rows[('CW','DN20')]['total_length_m']==16.3,rows
    assert rows[('V','DN50')]['total_length_m']==14.3,rows

    bad = dict(vertical)
    bad['withheld_runs'] = list(vertical['withheld_runs']) + [
        {'system':'W','diameter_key':'DN65','terminal_extension_above_m':0.0,'terminal_extension_below_m':0.0}
    ]
    out_bad = release.build_pipe_release_candidate(reconciliation, bad)
    assert out_bad['status']=='WITHHELD_PIPE_RELEASE_BLOCKERS',out_bad
    assert out_bad['release_blocker_count']==1,out_bad
    print('PIPE_RELEASE_RECONCILE_V8_TEST_PASS',{'ready_rows':len(rows),'unknown_blocker':'withheld'})


if __name__=='__main__':
    main()
