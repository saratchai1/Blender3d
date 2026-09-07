#!/usr/bin/env python3
from __future__ import annotations

import dashed_network_partition_v8 as partition


def seg(x0,x1,layer='CW'):
    return {'a':(x0,0.0),'b':(x1,0.0),'length_pt':x1-x0,'layer':layer}


def main()->None:
    # Four dash components with 8 pt gaps. DN20 at left, DN15 at right.
    segments=[seg(0,10),seg(18,28),seg(36,46),seg(54,64)]
    components=[{'id':i,'layer':'CW','segment_indexes':[i],'length_pt':10.0} for i in range(4)]
    tags=[
        {'nearest_segment':0,'component_id':0,'system':'CW','diameter_key':'DN20','dn':20,'diameter_mm':20,'diameter_in':0.75},
        {'nearest_segment':3,'component_id':3,'system':'CW','diameter_key':'DN15','dn':15,'diameter_mm':15,'diameter_in':0.5},
    ]
    augmented,events=partition.partition_diameter_tags(segments,components,tags,max_gap_pt=9,max_angle_diff_deg=5,tie_tolerance_pt=0.5)
    synthetic=[t for t in augmented if t.get('association_basis')=='DASHED_NETWORK_NEAREST_DIAMETER_SEED']
    got={int(t['component_id']):t['diameter_key'] for t in synthetic}
    assert got=={1:'DN20',2:'DN15'},got
    assert all(t['evidence_role']=='DIAMETER_SEED_ONLY_NO_GAP_LENGTH' for t in synthetic)
    summary=[e for e in events if e.get('status')=='DASHED_NETWORK_PARTITION_SUMMARY'][-1]
    assert summary['resolved_unseeded_components']==2,summary
    assert summary['tied_unseeded_components']==0,summary

    # One exact middle dash between two seed dashes must be withheld on a distance tie.
    tie_segments=[seg(0,10),seg(18,28),seg(36,46)]
    tie_components=[{'id':i,'layer':'CW','segment_indexes':[i],'length_pt':10.0} for i in range(3)]
    tie_tags=[
        {'nearest_segment':0,'component_id':0,'system':'CW','diameter_key':'DN20','dn':20,'diameter_mm':20,'diameter_in':0.75},
        {'nearest_segment':2,'component_id':2,'system':'CW','diameter_key':'DN15','dn':15,'diameter_mm':15,'diameter_in':0.5},
    ]
    tie_aug,tie_events=partition.partition_diameter_tags(tie_segments,tie_components,tie_tags,max_gap_pt=9,max_angle_diff_deg=5,tie_tolerance_pt=0.5)
    assert not [t for t in tie_aug if t.get('association_basis')=='DASHED_NETWORK_NEAREST_DIAMETER_SEED'],tie_aug
    assert any(e.get('status')=='WITHHELD_DASH_PARTITION_DISTANCE_TIE' and e.get('component_id')==1 for e in tie_events),tie_events

    # Different pipe systems on the same CAD layer are never partitioned by distance.
    system_tags=[
        {'nearest_segment':0,'component_id':0,'system':'S','diameter_key':'DN100','dn':100},
        {'nearest_segment':2,'component_id':2,'system':'SW','diameter_key':'DN100','dn':100},
    ]
    sys_aug,sys_events=partition.partition_diameter_tags(tie_segments,tie_components,system_tags,max_gap_pt=9,max_angle_diff_deg=5)
    assert not [t for t in sys_aug if t.get('association_basis')=='DASHED_NETWORK_NEAREST_DIAMETER_SEED'],sys_aug
    assert any(e.get('status')=='WITHHELD_DASH_PARTITION_MULTIPLE_SYSTEMS' for e in sys_events),sys_events
    print('DASHED_NETWORK_PARTITION_V8_TEST_PASS',{'multi_size':'nearest seed','distance_tie':'withheld','multiple_systems':'withheld'})


if __name__=='__main__':main()
