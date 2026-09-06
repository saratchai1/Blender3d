#!/usr/bin/env python3
from __future__ import annotations

import equipment_vertical_reconcile_v8 as equipment


def main() -> None:
    bounded={
        'candidate_runs':[],
        'withheld_runs':[
            {'system':'CW','diameter_key':'DN20','dn':20,'vertical_span_m':1.228,'segment_indexes':[1,2,3,4,5,6],'terminal_extension_above_m':0.0,'terminal_extension_below_m':0.0},
            {'system':'CW','diameter_key':'DN20','dn':20,'vertical_span_m':0.3,'segment_indexes':[7],'terminal_extension_above_m':0.0,'terminal_extension_below_m':0.0},
        ],
        'candidate_rows':[{'system':'CW','diameter_key':'DN20','dn':20,'vertical_length_m_candidate':6.3,'run_count':2,'sources':['SN-04_EXPLICIT_LEVEL_INTERVALS']}],
    }
    analysis={'diameter_assignments':[
        {'segment_index':1,'status':'COMPONENT_SINGLE_CLASS_PROPAGATION','classes':[{'system':'CW','diameter_key':'DN20'}]},
        {'segment_index':2,'status':'EXPLICIT_TAG_SEED','classes':[{'system':'CW','diameter_key':'DN20'}]},
        {'segment_index':3,'status':'EXPLICIT_TAG_SEED','classes':[{'system':'CW','diameter_key':'DN20'}]},
        {'segment_index':4,'status':'EXPLICIT_TAG_SEED','classes':[{'system':'CW','diameter_key':'DN20'}]},
        {'segment_index':5,'status':'EXPLICIT_TAG_SEED','classes':[{'system':'CW','diameter_key':'DN20'}]},
        {'segment_index':6,'status':'EXPLICIT_TAG_SEED','classes':[{'system':'CW','diameter_key':'DN20'}]},
    ]}
    evidence={
        'generation_allowed':True,'reference_used':False,'source_page':58,'source_page_max':71,
        'corroborates_schematic_page':57,'schematic_segment_indexes':[1,2,3,4,5,6],
        'system':'CW','diameter_key':'DN20','dn':20,'evidence_id':'TEST-TANK','plan_label':'Ø3/4"CW',
        'min_explicit_seed_fraction':0.8,'min_vertical_span_m':0.5,'max_vertical_span_m':2.0,'terminal_extension_allowed_m':0.05,
    }
    out=equipment.apply_equipment_vertical_evidence(bounded,analysis,evidence)
    assert out['equipment_vertical_status']=='APPLIED',out
    assert out['equipment_promoted_run_count']==1,out
    assert out['withheld_run_count']==1,out
    promoted=out['equipment_promoted_runs'][0]
    assert promoted['vertical_length_m_candidate']==1.228,promoted
    assert promoted['explicit_seed_fraction']==0.8333,promoted
    rows={(r['system'],r['diameter_key']):r for r in out['candidate_rows']}
    assert rows[('CW','DN20')]['vertical_length_m_candidate']==7.528,rows
    assert rows[('CW','DN20')]['source_pages']==[57,58],rows

    weak=dict(analysis)
    weak['diameter_assignments']=[dict(x,status='COMPONENT_SINGLE_CLASS_PROPAGATION') for x in analysis['diameter_assignments']]
    out_weak=equipment.apply_equipment_vertical_evidence(bounded,weak,evidence)
    assert out_weak['equipment_vertical_status']=='WITHHELD_EXPLICIT_SEED_FRACTION',out_weak
    print('EQUIPMENT_VERTICAL_RECONCILE_V8_TEST_PASS',{'promoted_m':1.228,'explicit_seed_fraction':0.8333})


if __name__=='__main__':
    main()
