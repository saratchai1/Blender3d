#!/usr/bin/env python3
from __future__ import annotations

import vertical_level_bounds_v8 as levels


def main() -> None:
    markers = [
        {'elevation_m': 0.0},
        {'elevation_m': 0.6},
        {'elevation_m': 3.75},
    ]
    runs = [
        # Vent stack spans through the whole building and continues above the top level.
        {'system':'V','diameter_key':'DN50','dn':50,'vertical_span_m':6.70,'elevation_span_m':[6.58,-0.11]},
        # Soil stack nearly equals the full explicit 0.00->3.75 interval.
        {'system':'SW','diameter_key':'DN100','dn':100,'vertical_span_m':3.72,'elevation_span_m':[3.59,-0.12]},
        # Cold-water riser matches +0.60->+3.75 despite small drafting offset.
        {'system':'CW','diameter_key':'DN20','dn':20,'vertical_span_m':3.139,'elevation_span_m':[3.372,0.234]},
        # Ground-to-lower-floor soil stub matches 0.00->0.60.
        {'system':'SW','diameter_key':'DN100','dn':100,'vertical_span_m':0.765,'elevation_span_m':[0.639,-0.125]},
        # A short waste branch has no explicit level-pair span and must remain withheld.
        {'system':'W','diameter_key':'DN65','dn':65,'vertical_span_m':1.225,'elevation_span_m':[3.59,2.365]},
        # A vent terminal piece lies mostly above +3.75 and must not be mistaken for 0.60 m floor spacing.
        {'system':'V','diameter_key':'DN50','dn':50,'vertical_span_m':0.743,'elevation_span_m':[4.334,3.59]},
    ]
    result = levels.classify_vertical_runs(runs, markers)
    assert result['status'] == 'LEVEL_BOUNDED_VERTICAL_CANDIDATES', result
    candidates = result['candidate_runs']
    withheld = result['withheld_runs']
    assert len(candidates) == 4, candidates
    assert len(withheld) == 2, withheld
    vmain = next(r for r in candidates if r['system']=='V')
    assert vmain['classification_status'] == 'CANDIDATE_COVERS_FULL_EXPLICIT_LEVEL_BAND', vmain
    assert vmain['vertical_length_m_candidate'] == 3.75, vmain
    assert vmain['terminal_extension_above_m'] > 2.8, vmain
    cw = next(r for r in candidates if r['system']=='CW')
    assert cw['matched_level_interval_m'] == [0.6,3.75], cw
    assert cw['vertical_length_m_candidate'] == 3.15, cw
    sw_short = next(r for r in candidates if r['system']=='SW' and r['vertical_length_m_candidate']==0.6)
    assert sw_short['matched_level_interval_m'] == [0.0,0.6], sw_short
    assert {r['system'] for r in withheld} == {'W','V'}, withheld
    grouped = {(r['system'],r['diameter_key']):r['vertical_length_m_candidate'] for r in result['candidate_rows']}
    assert grouped[('V','DN50')] == 3.75, grouped
    assert grouped[('CW','DN20')] == 3.15, grouped
    assert grouped[('SW','DN100')] == 4.35, grouped
    print('VERTICAL_LEVEL_BOUNDS_V8_TEST_PASS', {'candidates':len(candidates),'withheld':len(withheld),'rows':grouped})


if __name__ == '__main__':
    main()
