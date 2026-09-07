#!/usr/bin/env python3
from __future__ import annotations

import equipment_valve_corroboration_v8 as corroboration


def main() -> None:
    evidence={
        'reference_used':False,'generation_allowed':True,
        'source_page':58,'source_page_max':71,'corroborates_schematic_page':57,
        'schematic_segment_indexes':[182,183,184,185,186,187],
        'system':'CW','diameter_key':'DN15','dn':15,
        'primary_plan_equipment_label':'FLOAT VALVE Ø1/2"',
        'schematic_explicit_label':'BALL VALVE Ø1/2"',
        'nearby_main_label':'Ø3/4"CW','evidence_id':'TEST-TANK',
    }
    probe={'callouts':[
        {
            'name':'BALL VALVE','text':'BALL VALVE Ø1/2"',
            'diameter':{'diameter_key':'DN15','dn':15},
            'leader':{'status':'ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER','leader_hops':3,'terminal_distance_pt':0.9},
            'target_segment':{'segment_index':183,'layer':'CW'},
        },
        {
            'name':'FLOAT VALVE','text':'FLOAT VALVE Ø1/2"',
            'diameter':{'diameter_key':'DN15','dn':15},
            'leader':{'status':'ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER'},
            'target_segment':{'segment_index':190,'layer':'CW'},
        },
    ]}
    plan='''GROUND FLOOR PLAN\nØ3/4"CW\nFLOAT VALVE Ø1/2"\nØ1/2"CW'''
    out=corroboration.corroborate_equipment_valve(plan,probe,evidence)
    assert out['status']=='CORROBORATED_EQUIPMENT_VALVE_CLASS',out
    assert out['diameter_key']=='DN15',out
    assert out['source_pages']==[57,58],out
    assert out['accepted_valve_leader']['target_segment_index']==183,out
    assert out['nearby_main_role']=='AUDIT_ONLY_NOT_BRANCH_SIZING_EVIDENCE',out

    missing=corroboration.corroborate_equipment_valve('Ø3/4"CW only',probe,evidence)
    assert missing['status']=='WITHHELD_PRIMARY_PLAN_VALVE_LABEL_NOT_FOUND',missing

    conflict_probe={'callouts':[{
        'name':'BALL VALVE','text':'BALL VALVE Ø3/4"',
        'diameter':{'diameter_key':'DN20','dn':20},
        'leader':{'status':'ASSOCIATED_BY_LEADER_TO_PDF_CAD_LAYER'},
        'target_segment':{'segment_index':183,'layer':'CW'},
    }]}
    conflict=corroboration.corroborate_equipment_valve(plan,conflict_probe,evidence)
    assert conflict['status']=='WITHHELD_CONFLICTING_TARGET_RUN_VALVE_CLASSES',conflict
    print('EQUIPMENT_VALVE_CORROBORATION_V8_TEST_PASS',{'class':'DN15','source_pages':[57,58],'main_DN20':'audit_only'})


if __name__=='__main__':
    main()
