#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from auto_boq_v6 import extract
from score_auto_boq import score

EXPECTED_SHA='f6db0f85e12113b31a545a5e881a75173938e011908ba1a4491016f77b302175'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pdf',type=Path,required=True); ap.add_argument('--profile',type=Path,required=True); ap.add_argument('--reference',type=Path,required=True); a=ap.parse_args()
    generated=extract(a.pdf,a.profile)
    assert generated['document']['sha256']==EXPECTED_SHA
    assert generated['source_policy']['reference_used_for_generation'] is False
    assert generated['source_policy']['drawing_pages']==[1,71]
    assert all(max(r['source_pages'])<=71 for r in generated['rows'])
    by={r['id']:r for r in generated['rows']}
    required={
      'ARCH-ROOF-METAL','ARCH-FASCIA','ARCH-DOOR-D2','ARCH-DOOR-D3',
      'SAN-BOOSTER-PUMP','SAN-WATER-METER','SAN-FLOAT-VALVE',
      'SAN-WC-BOWL','SAN-LAVATORY','SAN-SHOWER-SET',
      'SAN-BIDET-SPRAY','SAN-PAPER-HOLDER','SAN-TOWEL-RAIL',
      'ELEC-DOWNLIGHT','ELEC-T8-LONG'
    }
    assert required <= set(by), sorted(by)
    assert len(generated['rows'])==15
    assert by['ARCH-DOOR-D2']['quantity']==7
    assert by['ARCH-DOOR-D3']['quantity']==4
    assert by['ELEC-DOWNLIGHT']['quantity']==37
    assert by['ELEC-T8-LONG']['quantity']==1
    assert by['SAN-BOOSTER-PUMP']['quantity']==1
    assert by['SAN-WATER-METER']['quantity']==1
    assert by['SAN-FLOAT-VALVE']['quantity']==1
    assert all(by[i]['source_pages']==[58] for i in ('SAN-BOOSTER-PUMP','SAN-WATER-METER','SAN-FLOAT-VALVE'))
    assert by['SAN-WC-BOWL']['quantity']==3 and by['SAN-WC-BOWL']['source_pages']==[23,24,25]
    assert by['SAN-LAVATORY']['quantity']==3 and by['SAN-LAVATORY']['source_pages']==[23,24,25]
    assert by['SAN-SHOWER-SET']['quantity']==2 and by['SAN-SHOWER-SET']['source_pages']==[24,25]
    for item in ('SAN-BIDET-SPRAY','SAN-PAPER-HOLDER','SAN-TOWEL-RAIL'):
        assert by[item]['quantity']==3
        assert by[item]['source_pages']==[23,24,25]
        assert by[item]['method']=='raster:line-stripped CAD label sweep'
        assert by[item]['confidence']>=0.45
    assert 124 <= by['ARCH-ROOF-METAL']['quantity'] <= 132
    assert 43 <= by['ARCH-FASCIA']['quantity'] <= 47
    reference=json.loads(a.reference.read_text(encoding='utf-8'))
    result=score(generated,reference)
    assert result['reference_rows']==16
    assert result['detected_reference_rows']==15
    assert result['coverage_pct']>=93.75
    assert result['detected_rows_accuracy_pct']==100
    assert result['mean_absolute_error_pct']<0.20
    short=next(x for x in result['comparisons'] if x['id']=='ELEC-T8-SHORT')
    assert short['detected'] is False
    print('AUTO_BOQ_TEST_PASS',json.dumps({'rows':len(generated['rows']),'coverage_pct':result['coverage_pct'],'mae_pct':result['mean_absolute_error_pct']}))
if __name__=='__main__': main()
