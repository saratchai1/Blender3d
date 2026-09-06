#!/usr/bin/env python3
from __future__ import annotations

import pipe_publish_v8 as publish


def main() -> None:
    base = {
        'rows':[{'id':'OLD','quantity':1.0}],
        'coverage':{
            'supported_detectors':[],
            'withheld_detectors':[{'name':'sanitary piping','status':'WITHHELD','reason':'old'}],
        },
        'diagnostics':[],
    }
    release = {
        'status':'PASS_VALIDATED_PIPE_RELEASE_CANDIDATE',
        'publication_policy':'READY_FOR_PIPE_ROW_PUBLICATION',
        'release_blocker_count':0,
        'excluded_non_quantity_run_count':2,
        'non_additive_contract':'test contract',
        'candidate_rows':[
            {'system':'CW','diameter_key':'DN20','dn':20,'horizontal_length_m':10.0,'vertical_length_m':6.3,'total_length_m':16.3,'source_pages':[57,58,59],'evidence_roles':['PRIMARY_PLAN_HORIZONTAL','SN-04_EXPLICIT_LEVEL_INTERVALS']},
            {'system':'V','diameter_key':'DN50','dn':50,'horizontal_length_m':1.0,'vertical_length_m':13.3,'total_length_m':14.3,'source_pages':[57,58],'evidence_roles':['PRIMARY_PLAN_HORIZONTAL','SN-04_CALIBRATED_PLUS_A-06_ROOF_LEVEL']},
        ],
    }
    out = publish.publish_validated_pipe_rows(base, release)
    assert len(base['rows'])==1,base
    assert len(out['rows'])==3,out
    pipes=[r for r in out['rows'] if r['id'].startswith('SAN-PIPE-')]
    assert [r['id'] for r in pipes]==['SAN-PIPE-CW-DN20','SAN-PIPE-V-DN50'],pipes
    assert pipes[0]['quantity']==16.3,pipes[0]
    assert pipes[0]['evidence']['horizontal_length_m']==10.0,pipes[0]
    assert pipes[0]['evidence']['vertical_length_m']==6.3,pipes[0]
    assert not any(x.get('name')=='sanitary piping' for x in out['coverage']['withheld_detectors']),out['coverage']
    assert 'validated sanitary pipe takeoff' in out['coverage']['supported_detectors'],out['coverage']

    failed = dict(release)
    failed['status']='WITHHELD_PIPE_RELEASE_BLOCKERS'
    try:
        publish.publish_validated_pipe_rows(base, failed)
    except ValueError:
        pass
    else:
        raise AssertionError('publisher must fail closed when gate is withheld')
    print('PIPE_PUBLISH_V8_TEST_PASS',{'published':2,'fail_closed':True})


if __name__=='__main__':
    main()
