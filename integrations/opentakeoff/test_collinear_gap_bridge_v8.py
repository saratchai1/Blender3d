#!/usr/bin/env python3
from __future__ import annotations

import collinear_gap_bridge_v8 as bridge


def seg(a,b,layer='CW'):
    return {'a':a,'b':b,'length_pt':((b[0]-a[0])**2+(b[1]-a[1])**2)**0.5,'layer':layer}


def main() -> None:
    # A--gap--B is collinear and same-layer. C is perpendicular and must not bridge.
    segments=[
        seg((0,0),(10,0)),
        seg((18,0),(28,0)),
        seg((36,0),(46,0)),
        seg((18,10),(18,20)),
        seg((60,0),(70,0),'WASTE'),
    ]
    components=[
        {'id':0,'layer':'CW','segment_indexes':[0],'length_pt':10},
        {'id':1,'layer':'CW','segment_indexes':[1],'length_pt':10},
        {'id':2,'layer':'CW','segment_indexes':[2],'length_pt':10},
        {'id':3,'layer':'CW','segment_indexes':[3],'length_pt':10},
        {'id':4,'layer':'WASTE','segment_indexes':[4],'length_pt':10},
    ]
    tags=[
        {'nearest_segment':0,'component_id':0,'system':'CW','diameter_key':'DN20','dn':20,'diameter_mm':20,'diameter_in':0.75},
    ]
    augmented,events=bridge.bridge_diameter_tags(segments,components,tags,max_gap_pt=9,max_angle_diff_deg=5)
    synthetic=[t for t in augmented if t.get('association_basis')=='COLLINEAR_ENDPOINT_GAP_BRIDGE']
    # B and C chain via 8 pt gaps, so both receive the only consistent DN20 class.
    assert {t['component_id'] for t in synthetic}=={1,2},synthetic
    assert all(t['diameter_key']=='DN20' for t in synthetic),synthetic
    assert not any(t['component_id']==3 for t in synthetic),synthetic
    assert not any(t['component_id']==4 for t in synthetic),synthetic
    assert all(t['bridge_gap_pt']<=9 for t in synthetic)
    assert all(t['bridge_angle_diff_deg']<=5 for t in synthetic)

    # Add a conflicting DN15 seed at C. The whole bridge group must be withheld;
    # B is no longer allowed to inherit either size.
    conflict_tags=tags+[
        {'nearest_segment':2,'component_id':2,'system':'CW','diameter_key':'DN15','dn':15,'diameter_mm':15,'diameter_in':0.5},
    ]
    augmented2,events2=bridge.bridge_diameter_tags(segments,components,conflict_tags,max_gap_pt=9,max_angle_diff_deg=5)
    synthetic2=[t for t in augmented2 if t.get('association_basis')=='COLLINEAR_ENDPOINT_GAP_BRIDGE']
    assert not synthetic2,synthetic2
    withheld=[e for e in events2 if e.get('status')=='WITHHELD_BRIDGE_GROUP_CONFLICTING_DIAMETERS']
    assert withheld and {x['diameter_key'] for x in withheld[0]['classes']}=={'DN15','DN20'},withheld

    # A 10 pt gap is beyond policy even if perfectly collinear.
    far_segments=[seg((0,0),(10,0)),seg((20.1,0),(30.1,0))]
    far_components=[{'id':0,'layer':'CW','segment_indexes':[0],'length_pt':10},{'id':1,'layer':'CW','segment_indexes':[1],'length_pt':10}]
    far_aug,_=bridge.bridge_diameter_tags(far_segments,far_components,tags,max_gap_pt=9,max_angle_diff_deg=5)
    assert len(far_aug)==1,far_aug
    print('COLLINEAR_GAP_BRIDGE_V8_TEST_PASS',{'same_layer_collinear':'bridged','conflict':'withheld','perpendicular':'withheld','gap_over_limit':'withheld'})


if __name__=='__main__':
    main()
