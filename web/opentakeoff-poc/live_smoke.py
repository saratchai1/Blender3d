#!/usr/bin/env python3
"""Live public-site acceptance for the deployed Automatic BOQ surface."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from playwright.sync_api import sync_playwright

PIPE_EXPECTED={
    'SAN-PIPE-CW-DN15':8.524,
    'SAN-PIPE-CW-DN20':26.112,
    'SAN-PIPE-RL-DN65':3.57,
    'SAN-PIPE-S-DN100':2.27,
    'SAN-PIPE-SW-DN100':19.455,
    'SAN-PIPE-V-DN50':14.665,
    'SAN-PIPE-W-DN50':10.746,
    'SAN-PIPE-W-DN65':7.158,
}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--url',required=True); ap.add_argument('--output',type=Path,default=Path('.generated/takeoff-live-qa')); a=ap.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    url=a.url.rstrip('/')+'/'
    report={'url':url,'checks':[],'page_errors':[],'status':'IN_PROGRESS'}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True); page=browser.new_page(viewport={'width':1440,'height':960})
        page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
        try:
            res=page.goto(url,wait_until='domcontentloaded',timeout=60000); assert res and res.status==200
            page.locator('#auto-rows-body tr').first.wait_for(timeout=30000)
            page.wait_for_function("document.querySelector('#auto-rows')?.textContent==='27'",timeout=30000)
            assert page.locator('#auto-rows-body tr').count()==27
            assert float(page.locator('#auto-coverage').inner_text())>=95.0
            assert page.locator('#auto-accuracy').inner_text()=='100'
            assert float(page.locator('#auto-mae').inner_text())<0.15
            text=page.locator('#auto-rows-body').inner_text()
            for needle in ('Booster Pump','มาตรวัดน้ำ','Float Valve','WC.1','อ่างล้างหน้า','ฝักบัวอาบน้ำสายอ่อน','ฝักบัวชำระพร้อมสาย','ที่ใส่กระดาษชำระ','ราวแขวนผ้า','Floor Cleanout','Cleanout','Roof Floor Drain','Air Vent Cap','Cold Water DN15','Cold Water DN20','Vent DN50','Waste DN65'):
                assert needle in text
            hrefs=page.locator('#auto-rows-body .page-link').evaluate_all('(a)=>a.map(x=>x.getAttribute("href"))')
            pages=[int(re.search(r'%23(\d+)',h).group(1)) for h in hrefs]
            assert pages and max(pages)<=71 and all(p in pages for p in (13,23,24,25,57,58,59,60))
            data=page.evaluate("async()=>{const [a,b]=await Promise.all([fetch('./auto-boq.json',{cache:'no-store'}),fetch('./auto-boq-benchmark.json',{cache:'no-store'})]);return [a.status,await a.json(),b.status,await b.json()]}")
            assert data[0]==200 and data[2]==200
            auto,bench=data[1],data[3]
            assert auto['source_policy']['reference_used_for_generation'] is False
            assert len(auto['rows'])==27 and all(max(r['source_pages'])<=71 for r in auto['rows'])
            by={r['id']:r for r in auto['rows']}
            assert 'SAN-FLOOR-DRAIN-2' not in by
            for item,qty in {'SAN-FCO-4':2,'SAN-CO-2.5':1,'SAN-RFD-2.5':2,'SAN-AVC-2':2}.items():
                assert by[item]['quantity']==qty and by[item]['method']=='text:positioned sanitary drawing tag'
            for item,qty in PIPE_EXPECTED.items():
                assert abs(by[item]['quantity']-qty)<1e-6 and by[item]['unit']=='m',by[item]
                assert by[item]['evidence']['release_gate_status']=='PASS_VALIDATED_PIPE_RELEASE_CANDIDATE',by[item]
            assert set(by['SAN-PIPE-CW-DN15']['source_pages'])=={57,58},by['SAN-PIPE-CW-DN15']
            assert 13 in by['SAN-PIPE-V-DN50']['source_pages'],by['SAN-PIPE-V-DN50']
            assert abs(sum(by[k]['quantity'] for k in PIPE_EXPECTED)-92.5)<1e-6
            fd=next(d for d in auto['diagnostics'] if d.get('detector')=='positioned_tag_diagnostic:SAN-FLOOR-DRAIN-2')
            assert fd['status']=='WITHHELD_DIAGNOSTIC_ONLY' and fd['detections']==4
            pipe=next(d for d in auto['diagnostics'] if d.get('detector')=='sanitary_pipe_network_v8_19')
            assert pipe['reconciliation']['full_pipe_boq_publication_status']=='PUBLISHED_VALIDATED_PIPE_ROWS',pipe
            assert pipe['pipe_release_candidate']['release_blocker_count']==0,pipe
            assert pipe['vertical_level_bounded_reconciliation']['valve_leader_promoted_count']==1,pipe
            corroboration=pipe['equipment_valve_corroboration']
            assert corroboration['status']=='CORROBORATED_EQUIPMENT_VALVE_CLASS',corroboration
            assert corroboration['source_pages']==[57,58] and corroboration['diameter_key']=='DN15',corroboration
            assert corroboration['nearby_main_role']=='AUDIT_ONLY_NOT_BRANCH_SIZING_EVIDENCE',corroboration
            assert bench['scope']=='AUDIT_SUBSET_ONLY_NOT_FULL_BOQ' and bench['reference_rows']==20 and bench['detected_reference_rows']==19 and bench['coverage_pct']>=95.0
            page.screenshot(path=str(a.output/'automatic-boq-live.png'),full_page=True)
            report['checks'].append('Public HTTPS Automatic BOQ rendered 27 rows including eight validated sanitary pipe rows totaling 92.500 m; scored audit subset remains 95% coverage and 100% detected-row accuracy')
            report['checks'].append('Public generated JSON proves reference isolation, release blockers zero, A-06 roof provenance retained, and tank DN15 independently corroborated by SN-04 BALL VALVE plus SN-05 FLOAT VALVE half-inch evidence; all published evidence pages <= 71')
            page.set_viewport_size({'width':390,'height':844}); page.screenshot(path=str(a.output/'automatic-boq-live-mobile.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
            assert not report['page_errors'],report['page_errors']; report['status']='PASS'
        except Exception as e:
            report['status']='FAIL'; report['error']=str(e); page.screenshot(path=str(a.output/'failure.png'),full_page=True); raise
        finally:
            (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); browser.close()
    print('AUTO_BOQ_LIVE_PASS',json.dumps(report,ensure_ascii=False))

if __name__=='__main__': main()
