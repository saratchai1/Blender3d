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
        'exact_segment_evidence_required':True,
        'exact_segment_evidence_status':'PASS_EXACT_SOURCE_GEOMETRY_RECONCILED',
        'exact_segment_evidence_contract':'test exact geometry contract',
        'excluded_non_quantity_run_count':2,
        'non_additive_contract':'test contract',
        'candidate_rows':[
            {
                'system':'CW','diameter_key':'DN20','dn':20,
                'horizontal_length_m':10.0,'vertical_length_m':6.3,'total_length_m':16.3,
                'source_pages':[57,58,59],
                'evidence_roles':['PRIMARY_PLAN_HORIZONTAL','SN-04_EXPLICIT_LEVEL_INTERVALS'],
                'exact_horizontal_length_m':10.0,
                'exact_vertical_length_m':6.3,
                'exact_horizontal_segment_count':1,
                'exact_vertical_run_count':1,
                'published_segments':[
                    {'page':58,'segment_index':7,'x0_pt':1.0,'y0_pt':2.0,'x1_pt':3.0,'y1_pt':4.0,'segment_length_m':10.0,'source_role':'PRIMARY_PLAN_HORIZONTAL','publish_reason':'EXPLICIT_TAG_SEED'},
                ],
                'published_vertical_runs':[
                    {'source_page':57,'published_vertical_length_m':6.3,'source_segments':[{'page':57,'segment_index':8,'x0_pt':5.0,'y0_pt':6.0,'x1_pt':5.0,'y1_pt':10.0}]},
                ],
            },
            {
                'system':'V','diameter_key':'DN50','dn':50,
                'horizontal_length_m':1.0,'vertical_length_m':13.3,'total_length_m':14.3,
                'source_pages':[57,58],
                'evidence_roles':['PRIMARY_PLAN_HORIZONTAL','SN-04_CALIBRATED_PLUS_A-06_ROOF_LEVEL'],
                'exact_horizontal_length_m':1.0,
                'exact_vertical_length_m':13.3,
                'exact_horizontal_segment_count':1,
                'exact_vertical_run_count':1,
                'published_segments':[{'page':58,'segment_index':9,'x0_pt':1.0,'y0_pt':2.0,'x1_pt':2.0,'y1_pt':2.0,'segment_length_m':1.0}],
                'published_vertical_runs':[{'source_page':57,'published_vertical_length_m':13.3,'source_segments':[{'page':57,'segment_index':10,'x0_pt':8.0,'y0_pt':1.0,'x1_pt':8.0,'y1_pt':20.0}]}],
            },
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
    assert pipes[0]['evidence']['exact_segment_evidence_status']=='PASS_EXACT_SOURCE_GEOMETRY_RECONCILED',pipes[0]
    assert pipes[0]['evidence']['published_segments'][0]['segment_index']==7,pipes[0]
    assert pipes[0]['evidence']['published_vertical_runs'][0]['published_vertical_length_m']==6.3,pipes[0]
    assert not any(x.get('name')=='sanitary piping' for x in out['coverage']['withheld_detectors']),out['coverage']
    assert 'validated sanitary pipe takeoff' in out['coverage']['supported_detectors'],out['coverage']

    failed = dict(release)
    failed['status']='WITHHELD_PIPE_RELEASE_BLOCKERS'
    try:
        publish.publish_validated_pipe_rows(base, failed)
    except ValueError:
        pass
    else:
        raise AssertionError('publisher must fail closed when release gate is withheld')

    missing_exact = dict(release)
    missing_exact.pop('exact_segment_evidence_status')
    try:
        publish.publish_validated_pipe_rows(base, missing_exact)
    except ValueError:
        pass
    else:
        raise AssertionError('publisher must fail closed when required exact geometry gate is absent')

    legacy_release = dict(release)
    legacy_release.pop('exact_segment_evidence_required')
    legacy_release.pop('exact_segment_evidence_status')
    legacy_release['candidate_rows'] = [
        {'system':'CW','diameter_key':'DN20','dn':20,'horizontal_length_m':1.0,'vertical_length_m':0.0,'total_length_m':1.0,'source_pages':[58],'evidence_roles':['PRIMARY_PLAN_HORIZONTAL']},
    ]
    legacy = publish.publish_validated_pipe_rows(base, legacy_release)
    assert any(r.get('id')=='SAN-PIPE-CW-DN20' for r in legacy['rows']),legacy
    print('PIPE_PUBLISH_V8_TEST_PASS',{'published':2,'release_fail_closed':True,'exact_geometry_fail_closed':True,'legacy_control_compatible':True})


if __name__=='__main__':
    main()
