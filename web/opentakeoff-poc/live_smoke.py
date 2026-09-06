#!/usr/bin/env python3
"""Live public-site acceptance for the deployed Automatic BOQ surface."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from playwright.sync_api import sync_playwright


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
            page.wait_for_function("document.querySelector('#auto-rows')?.textContent==='10'",timeout=30000)
            assert page.locator('#auto-rows-body tr').count()==10
            assert float(page.locator('#auto-coverage').inner_text())>=90.9
            assert page.locator('#auto-accuracy').inner_text()=='100'
            assert float(page.locator('#auto-mae').inner_text())<0.5
            text=page.locator('#auto-rows-body').inner_text(); assert 'Booster Pump' in text and 'มาตรวัดน้ำ' in text and 'Float Valve' in text and 'WC.1' in text
            hrefs=page.locator('#auto-rows-body .page-link').evaluate_all('(a)=>a.map(x=>x.getAttribute("href"))')
            pages=[int(re.search(r'%23(\d+)',h).group(1)) for h in hrefs]
            assert pages and max(pages)<=71 and 58 in pages and all(p in pages for p in (23,24,25))
            data=page.evaluate("async()=>{const [a,b]=await Promise.all([fetch('./auto-boq.json',{cache:'no-store'}),fetch('./auto-boq-benchmark.json',{cache:'no-store'})]);return [a.status,await a.json(),b.status,await b.json()]}")
            assert data[0]==200 and data[2]==200
            auto,bench=data[1],data[3]
            assert auto['source_policy']['reference_used_for_generation'] is False
            assert len(auto['rows'])==10 and all(max(r['source_pages'])<=71 for r in auto['rows'])
            by={r['id']:r for r in auto['rows']}; assert by['SAN-BOOSTER-PUMP']['quantity']==1 and by['SAN-WATER-METER']['quantity']==1 and by['SAN-FLOAT-VALVE']['quantity']==1 and by['SAN-WC-BOWL']['quantity']==3
            assert by['SAN-WC-BOWL']['source_pages']==[23,24,25]
            assert bench['scope']=='AUDIT_SUBSET_ONLY_NOT_FULL_BOQ' and bench['reference_rows']==11 and bench['detected_reference_rows']==10 and bench['coverage_pct']>=90.9
            page.screenshot(path=str(a.output/'automatic-boq-live.png'),full_page=True)
            report['checks'].append('Public HTTPS Automatic BOQ rendered ten generated rows with >=90.9% audit-subset coverage, WC.1 evidence on drawing pages 23-25 and sanitary-equipment evidence on page 58')
            report['checks'].append('Public generated JSON proves reference isolation and all evidence pages <= 71')
            page.set_viewport_size({'width':390,'height':844}); page.screenshot(path=str(a.output/'automatic-boq-live-mobile.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
            assert not report['page_errors'],report['page_errors']; report['status']='PASS'
        except Exception as e:
            report['status']='FAIL'; report['error']=str(e); page.screenshot(path=str(a.output/'failure.png'),full_page=True); raise
        finally:
            (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); browser.close()
    print('AUTO_BOQ_LIVE_PASS',json.dumps(report,ensure_ascii=False))

if __name__=='__main__': main()
