#!/usr/bin/env python3
from __future__ import annotations

import rainwater_page_evidence_v8 as rl


def main()->None:
    text='A-3 1:100 Ø21/2"RL Ø21/2"RFD Ø21/2"RFD+RL Ø2"V+AVC SN-06'
    e=rl.corroborated_rl_class(text)
    assert e['status']=='CORROBORATED_RL_DIAMETER',e
    assert e['diameter_key']=='DN65',e
    assert e['standalone_rl_count']>=1 and e['rfd_plus_rl_count']>=1,e
    assignments=[
        {'layer':'RL','length_pt':34.2,'status':'WITHHELD_NO_DIAMETER_EVIDENCE','classes':[]},
        {'layer':'RL','length_pt':10.6,'status':'EXPLICIT_TAG_SEED','classes':[{'system':'RL','diameter_key':'DN65'}]},
        {'layer':'CW','length_pt':7.2,'status':'WITHHELD_NO_DIAMETER_EVIDENCE','classes':[]},
    ]
    out,applied=rl.apply_to_assignments(assignments,e)
    assert out[0]['status']=='PAGE_CORROBORATED_RL_DIAMETER',out
    assert out[0]['classes'][0]['diameter_key']=='DN65',out
    assert out[1]['status']=='EXPLICIT_TAG_SEED',out
    assert out[2]['status'].startswith('WITHHELD'),out
    assert applied['seeded_segment_count']==1 and applied['seeded_length_pt']==34.2,applied

    missing=rl.corroborated_rl_class('Ø21/2"RL only')
    assert missing['status']=='WITHHELD_RL_CORROBORATION_INCOMPLETE',missing
    conflict=rl.corroborated_rl_class('Ø21/2"RL Ø3"RFD+RL')
    assert conflict['status']=='WITHHELD_RL_CORROBORATION_CONFLICT',conflict
    print('RAINWATER_PAGE_EVIDENCE_V8_TEST_PASS',{'corroborated':'DN65','incomplete':'withheld','conflict':'withheld'})


if __name__=='__main__':main()
