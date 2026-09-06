#!/usr/bin/env python3
"""Chromium acceptance test for Automatic BOQ + the real OpenTakeoff review canvas."""
from __future__ import annotations
import argparse, functools, hashlib, http.server, json, re, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

EXPECTED_SHA256='f6db0f85e12113b31a545a5e881a75173938e011908ba1a4491016f77b302175'; EXPECTED_SIZE=13_058_241
READ_DB='''async (kind) => { const name=kind==='demo'?'blender3d-opentakeoff-poc-v2-demo':'blender3d-opentakeoff-poc-v1-user'; const db=await new Promise((yes,no)=>{const r=indexedDB.open(name);r.onsuccess=()=>yes(r.result);r.onerror=()=>no(r.error)}); try{return await new Promise((yes,no)=>{const t=db.transaction(['meta','pdfs'],'readonly');const a=t.objectStore('meta').get('annotations');const p=t.objectStore('pdfs').getAll();t.oncomplete=()=>yes({annotations:a.result,pdfs:p.result.map(x=>({name:x.name,size:x.bytes.byteLength,head:Array.from(new Uint8Array(x.bytes.slice(0,5)))}))});t.onerror=()=>no(t.error)})}finally{db.close()}}'''

def large_canvas(frame):
    for i in range(frame.locator('canvas').count()):
        b=frame.locator('canvas').nth(i).bounding_box()
        if b and b['width']>=500 and b['height']>=300:return True
    return False

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,default=Path('.generated/takeoff-qa'));a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    sample=a.root/'takeoff/demo/family4.pdf'; auto=json.loads((a.root/'takeoff/auto-boq.json').read_text()); bench=json.loads((a.root/'takeoff/auto-boq-benchmark.json').read_text())
    assert sample.stat().st_size==EXPECTED_SIZE and hashlib.sha256(sample.read_bytes()).hexdigest()==EXPECTED_SHA256
    assert auto['source_policy']['reference_used_for_generation'] is False and all(max(r['source_pages'])<=71 for r in auto['rows'])
    assert len(auto['rows'])==10; assert bench['reference_rows']==11 and bench['detected_reference_rows']==10; assert bench['coverage_pct']>=90.9; assert bench['detected_rows_accuracy_pct']==100 and bench['mean_absolute_error_pct']<0.5
    by={r['id']:r for r in auto['rows']}; assert by['SAN-BOOSTER-PUMP']['quantity']==1 and by['SAN-WATER-METER']['quantity']==1 and by['SAN-FLOAT-VALVE']['quantity']==1
    assert all(by[k]['source_pages']==[58] for k in ('SAN-BOOSTER-PUMP','SAN-WATER-METER','SAN-FLOAT-VALVE'))
    assert by['SAN-WC-BOWL']['quantity']==3 and by['SAN-WC-BOWL']['source_pages']==[23,24,25]
    handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(a.root.resolve()));server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}/takeoff/'; evidence={'checks':[],'page_errors':[]}
    with sync_playwright() as p:
      browser=p.chromium.launch(headless=True);ctx=browser.new_context(viewport={'width':1512,'height':982},accept_downloads=True);page=ctx.new_page();page.on('pageerror',lambda e:evidence['page_errors'].append(str(e)))
      try:
        page.goto(url,wait_until='domcontentloaded',timeout=60000);page.locator('#auto-rows-body tr').first.wait_for(timeout=30000);page.wait_for_function("document.querySelector('#auto-rows')?.textContent==='10'")
        assert page.locator('#auto-rows-body tr').count()==10; assert float(page.locator('#auto-coverage').inner_text())>=90.9; assert page.locator('#auto-accuracy').inner_text()=='100'; assert float(page.locator('#auto-mae').inner_text())<0.5
        text=page.locator('#auto-rows-body').inner_text(); assert 'หลังคาเหล็กรีดลอน' in text and '128.349' in text and '37' in text; assert 'Booster Pump' in text and 'มาตรวัดน้ำ' in text and 'Float Valve' in text and 'WC.1' in text
        hrefs=page.locator('#auto-rows-body .page-link').evaluate_all('(a)=>a.map(x=>x.getAttribute("href"))'); pages=[int(re.search(r'%23(\d+)',h).group(1)) for h in hrefs]; assert pages and max(pages)<=71 and 58 in pages and all(p in pages for p in (23,24,25))
        assert page.locator('#withheld-list .withheld').count()==7
        page.screenshot(path=str(a.out/'01-automatic-boq.png'),full_page=True);evidence['checks'].append('Automatic BOQ renders ten generated rows; audit subset coverage >=90.9%; all ten detected rows within ±5%; WC.1 evidence is on drawing pages 23-25 and sanitary equipment evidence on page 58; no evidence link exceeds page 71')
        page.locator('[data-tab="plan"]').click();page.locator('#status[data-state="ready"]').wait_for(timeout=120000);engine=page.frames[1];engine.locator('canvas').first.wait_for(timeout=120000);page.wait_for_timeout(1500);saved=engine.evaluate(READ_DB,'demo');pdf=saved['pdfs'][0]
        assert pdf['name']=='family4.pdf' and pdf['size']==EXPECTED_SIZE and bytes(pdf['head'])==b'%PDF-';ann=saved['annotations'];assert ann['shapes']==[] and ann['sheet_tabs']==['family4.pdf#11'];assert large_canvas(engine)
        evidence['checks'].append('Exact Family4 PDF opens in native OpenTakeoff review canvas; Automatic BOQ rows are not injected as manual shapes')
        page.locator('[data-tab="boq"]').click();assert page.locator('#csv').is_disabled();assert page.locator('#rows').inner_text().startswith('ยังไม่มี Manual Takeoff');assert float(page.locator('#floor-total').inner_text().replace(',',''))==0
        evidence['checks'].append('Manual BOQ remains independently empty, preventing automatic/manual double counting')
        page.locator('#workspace').select_option('user');page.locator('#status[data-state="ready"]').wait_for(timeout=60000);assert page.locator('[data-tab="auto"]').is_disabled();engine=page.frames[1];own=engine.evaluate(READ_DB,'user');assert len(own['pdfs'])==0 and (own.get('annotations') is None or own['annotations']['shapes']==[])
        engine.locator('input[type="file"]').first.wait_for(state='attached',timeout=30000);target=engine.locator('input[type="file"][accept*="pdf"]').first
        if target.count()==0:target=engine.locator('input[type="file"][multiple]').first
        target.set_input_files(str(sample.resolve()));engine.locator('canvas').first.wait_for(timeout=120000);page.wait_for_timeout(2000);own=engine.evaluate(READ_DB,'user');assert any(x['name']=='family4.pdf' and x['size']==EXPECTED_SIZE for x in own['pdfs']);assert own['annotations']['shapes']==[]
        evidence['checks'].append('User PDF upload remains isolated; Automatic tab is disabled for arbitrary user PDFs until runtime extraction is implemented')
        page.locator('#workspace').select_option('demo');page.locator('[data-tab="auto"]').click();page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(a.out/'02-automatic-boq-mobile.png'),full_page=True);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');assert not evidence['page_errors'],evidence['page_errors'];evidence['status']='passed'
      except Exception as e:
        evidence['status']='failed';evidence['error']=str(e);page.screenshot(path=str(a.out/'failure.png'),full_page=True);raise
      finally:
        (a.out/'qa.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False));browser.close();server.shutdown()
    print('POC_BROWSER_QA_PASSED',json.dumps(evidence,ensure_ascii=False))
if __name__=='__main__':main()
