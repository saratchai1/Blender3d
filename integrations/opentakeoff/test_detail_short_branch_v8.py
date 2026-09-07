#!/usr/bin/env python3
from __future__ import annotations

import detail_short_branch_v8 as short


def main() -> None:
    original_probe=short._BASE_PROBE
    original_lines=short.v8.line_segments
    original_components=short.v8.style_components
    try:
        short._BASE_PROBE=lambda *a,**k:{
            'status':'DIAGNOSTIC_TRANSFER_PROBED',
            'transfer_candidates':[
                {
                    'system':'CW','diameter_key':'DN20','expected_layer':'CW',
                    'predicted_target_segment_pt':[10.0,10.0,13.5,10.0],
                    'status':'WITHHELD_NO_TARGET_SEGMENT_MATCH',
                },
                {
                    'system':'W','diameter_key':'DN50','expected_layer':'WASTE',
                    'predicted_target_segment_pt':[0.0,0.0,20.0,0.0],
                    'status':'WITHHELD_NO_TARGET_SEGMENT_MATCH',
                },
            ],
        }
        target=[
            {'a':(4.0,5.0),'b':(4.0,10.0),'length_pt':5.0,'layer':'CW'},
            {'a':(30.0,30.0),'b':(30.0,35.0),'length_pt':5.0,'layer':'CW'},
            {'a':(1.0,1.0),'b':(2.0,1.0),'length_pt':1.0,'layer':'WASTE'},
        ]
        short.v8.line_segments=lambda *a,**k:target
        short.v8.style_components=lambda segments,snap:([{'id':0},{'id':1},{'id':2}],{0:10,1:11,2:12})
        result=short.probe_detail_transfer(
            None,None,{},min_segment_pt=3.0,max_stroke_width_pt=3.0,
            endpoint_snap_pt=1.5,tag_snap_max_pt=30.0,
        )
        cw=result['transfer_candidates'][0]
        assert cw['status']=='DETAIL_TRANSFER_CANDIDATE',cw
        assert cw['target_segment_index']==0,cw
        assert cw['transfer_basis']=='SHORT_BRANCH_UNIQUE_ENDPOINT_GAP',cw
        assert cw['short_branch_fallback_status']=='RECOVERED_UNIQUE_SHORT_BRANCH',cw
        # Long predicted source run must never use orientation-free fallback.
        waste=result['transfer_candidates'][1]
        assert waste['status']=='WITHHELD_NO_TARGET_SEGMENT_MATCH',waste
        assert waste['short_branch_fallback_status']=='WITHHELD_SOURCE_RUN_TOO_LONG',waste
        assert result['short_branch_recovered_count']==1,result
        print('DETAIL_SHORT_BRANCH_V8_TEST_PASS',{'recovered':1,'long_run':'withheld'})
    finally:
        short._BASE_PROBE=original_probe
        short.v8.line_segments=original_lines
        short.v8.style_components=original_components


if __name__=='__main__':
    main()
