#!/usr/bin/env python3
from __future__ import annotations

import roof_terminal_reconcile_v8 as roof


def main() -> None:
    bounded = {
        'candidate_runs': [
            {'system':'V','diameter_key':'DN50','dn':50,'classification_status':'CANDIDATE_COVERS_FULL_EXPLICIT_LEVEL_BAND','elevation_span_m':[6.585,-0.113],'vertical_length_m_candidate':3.75},
            {'system':'V','diameter_key':'DN50','dn':50,'classification_status':'CANDIDATE_COVERS_FULL_EXPLICIT_LEVEL_BAND','elevation_span_m':[6.59,-0.10],'vertical_length_m_candidate':3.75},
            {'system':'SW','diameter_key':'DN100','dn':100,'classification_status':'CANDIDATE_COVERS_FULL_EXPLICIT_LEVEL_BAND','elevation_span_m':[3.59,-0.12],'vertical_length_m_candidate':3.75},
            {'system':'W','diameter_key':'DN65','dn':65,'classification_status':'CANDIDATE_EXPLICIT_SINGLE_SEGMENT_VERTICAL_BRANCH','elevation_span_m':[3.59,2.365],'vertical_length_m_candidate':1.225},
        ],
        'withheld_runs': [
            {'system':'V','diameter_key':'DN50','dn':50,'classification_status':'WITHHELD_NO_EXPLICIT_LEVEL_INTERVAL_MATCH','elevation_span_m':[4.334,3.59],'vertical_span_m':0.743},
        ],
        'candidate_rows': [],
        'publication_policy':'DIAGNOSTIC_ONLY_NO_VERTICAL_PUBLICATION',
    }
    evidence = {
        'evidence_id':'FAMILY4-ARCH-ROOF-LEVEL',
        'source_page':13,
        'source_page_max':71,
        'roof_elevation_m':6.65,
        'reference_used':False,
        'generation_allowed':True,
        'allowed_systems':['V'],
        'max_calibrated_top_error_m':0.15,
    }
    result = roof.apply_roof_terminal_evidence(bounded, evidence)
    assert result['roof_terminal_status']=='APPLIED', result
    assert result['roof_extended_run_count']==2, result
    assert all(r['classification_status']=='CANDIDATE_CORROBORATED_TO_ARCHITECTURAL_ROOF' for r in result['roof_extended_runs']), result
    assert all(r['vertical_length_m_candidate']==6.65 for r in result['roof_extended_runs']), result
    assert all(r['roof_top_error_m']<=0.065 for r in result['roof_extended_runs']), result
    rows={(r['system'],r['diameter_key']):r for r in result['candidate_rows']}
    assert rows[('V','DN50')]['vertical_length_m_candidate']==13.3, rows
    assert rows[('SW','DN100')]['vertical_length_m_candidate']==3.75, rows
    assert rows[('W','DN65')]['vertical_length_m_candidate']==1.225, rows
    # Short terminal geometry is evidence only and remains withheld; it is not added again.
    assert len(result['withheld_runs'])==1 and result['withheld_runs'][0]['vertical_span_m']==0.743, result

    bad = dict(evidence); bad['reference_used']=True
    rejected = roof.apply_roof_terminal_evidence(bounded,bad)
    assert rejected['roof_terminal_status']=='WITHHELD_ROOF_EVIDENCE_POLICY', rejected
    print('ROOF_TERMINAL_RECONCILE_V8_TEST_PASS', {'extended':2,'V_DN50_m':13.3,'duplicate_terminal':'withheld'})


if __name__=='__main__':
    main()
