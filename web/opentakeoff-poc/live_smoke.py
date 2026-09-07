#!/usr/bin/env python3
"""Live public-site acceptance for deployed Automatic BOQ + user PDF browser runtime."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from playwright.sync_api import sync_playwright

EXPECTED_SHA256='f6db0f85e12113b31a545a5e881a75173938e011908ba1a4491016f77b302175'
EXPECTED_SIZE=13_058_241
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
USER_RUNTIME_EXPECTED={
    'Floor Cleanout (FCO) — size WITHHELD':2,
    'Cleanout (CO) — size WITHHELD':1,
    'Roof Floor Drain Ø2½"':2,
    'Air Vent Cap Ø2"':2,
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
            data=page.evaluate("async()=>{const [a,b,c]=await Promise.all([fetch('./auto-boq.json',{cache:'no-store'}),fetch('./auto-boq-benchmark.json',{cache:'no-store'}),fetch('./browser-runtime-info.json',{cache:'no-store'})]);return [a.status,await a.json(),b.status,await b.json(),c.status,await c.json()]}")
            assert data[0]==200 and data[2]==200 and data[4]==200
            auto,bench,runtime_info=data[1],data[3],data[5]
            assert runtime_info['network_dependency'] is False and runtime_info['reference_data_dependency'] is False,runtime_info
            assert str(runtime_info['pdfjs_version']).startswith('4.10.'),runtime_info
            for asset in ('browser-auto-boq.mjs','vendor/pdf.mjs','vendor/pdf.worker.mjs'):
                asset_res=page.request.get(url+asset); assert asset_res.status==200,(asset,asset_res.status)
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

            # Public user-upload finish line: download the exact public sample bytes,
            # then feed them through the user workspace as a normal uploaded PDF.
            pdf_res=page.request.get(url+'demo/family4.pdf'); assert pdf_res.status==200,pdf_res.status
            pdf_bytes=pdf_res.body(); assert len(pdf_bytes)==EXPECTED_SIZE,len(pdf_bytes)
            assert hashlib.sha256(pdf_bytes).hexdigest()==EXPECTED_SHA256
            live_pdf=a.output/'live-family4.pdf'; live_pdf.write_bytes(pdf_bytes)
            page.locator('#workspace').select_option('user')
            page.locator('#status[data-state="ready"]').wait_for(timeout=60000)
            engine=page.frames[1]
            target=engine.locator('input[type="file"][accept*="pdf"]').first
            if target.count()==0: target=engine.locator('input[type="file"][multiple]').first
            target.wait_for(state='attached',timeout=30000)
            target.set_input_files(str(live_pdf.resolve()))
            engine.locator('canvas').first.wait_for(timeout=120000)
            page.locator('[data-tab="auto"]').click()
            page.wait_for_function("document.querySelector('#auto-rows')?.textContent==='4'",timeout=120000)
            assert page.locator('#auto-rows-body tr').count()==4
            user_text=page.locator('#auto-rows-body').inner_text()
            for label,qty in USER_RUNTIME_EXPECTED.items():
                row=page.locator('#auto-rows-body tr').filter(has_text=label); assert row.count()==1,(label,user_text)
                assert row.locator('td').nth(1).inner_text().strip()==str(qty),(label,row.locator('td').nth(1).inner_text())
            assert 'Floor Cleanout Ø4"' not in user_text and 'Cleanout Ø2½"' not in user_text
            withheld=page.locator('#withheld-list').inner_text()
            for token in ('SAN-PIPE-LENGTH','SAN-FLOOR-DRAIN-2','SAN-FCO/CO-SIZE','NON-EXPLICIT-BOQ'): assert token in withheld,withheld
            assert not page.locator('#user-auto-json').is_disabled()
            assert page.locator('#auto-json-download').is_hidden()
            assert page.locator('#accuracy-download').is_hidden()
            assert page.locator('#reference-boq').is_hidden()
            page.screenshot(path=str(a.output/'user-runtime-live.png'),full_page=True)
            report['checks'].append('Public HTTPS user workspace accepted an uploaded PDF and Browser Runtime Alpha returned exactly four safe rows: RFD/AVC explicit sizes plus unsized FCO/CO, with pipe length/FD/non-explicit quantities still WITHHELD and demo exports hidden')

            page.locator('#workspace').select_option('demo'); page.locator('[data-tab="auto"]').click(); page.wait_for_function("document.querySelector('#auto-rows')?.textContent==='27'",timeout=30000)
            page.set_viewport_size({'width':390,'height':844}); page.screenshot(path=str(a.output/'automatic-boq-live-mobile.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
            assert not report['page_errors'],report['page_errors']; report['status']='PASS'
        except Exception as e:
            report['status']='FAIL'; report['error']=str(e); page.screenshot(path=str(a.output/'failure.png'),full_page=True); raise
        finally:
            (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); browser.close()
    print('AUTO_BOQ_LIVE_PASS',json.dumps(report,ensure_ascii=False))

if __name__=='__main__': main()
