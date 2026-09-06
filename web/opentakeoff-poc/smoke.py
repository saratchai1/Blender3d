#!/usr/bin/env python3
"""Actual Chromium smoke test of the built OpenTakeoff engine with the real Thai benchmark PDF."""
from __future__ import annotations
import argparse, functools, hashlib, http.server, json, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

EXPECTED_SHA256='f6db0f85e12113b31a545a5e881a75173938e011908ba1a4491016f77b302175'
EXPECTED_SIZE=13_058_241
READ_DB='''async (kind) => {
 const name=kind==='demo'?'blender3d-opentakeoff-poc-v2-demo':'blender3d-opentakeoff-poc-v1-user';
 const db=await new Promise((yes,no)=>{const r=indexedDB.open(name);r.onsuccess=()=>yes(r.result);r.onerror=()=>no(r.error);});
 try {return await new Promise((yes,no)=>{const t=db.transaction(['meta','pdfs'],'readonly');const a=t.objectStore('meta').get('annotations');const p=t.objectStore('pdfs').getAll();t.oncomplete=()=>yes({annotations:a.result,pdfs:p.result.map(x=>({name:x.name,size:x.bytes.byteLength,head:Array.from(new Uint8Array(x.bytes.slice(0,5)))}))});t.onerror=()=>no(t.error);});}finally{db.close();}
}'''

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,default=Path('.generated/takeoff-qa'));args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    sample=args.root/'takeoff/demo/family4.pdf'
    assert sample.stat().st_size==EXPECTED_SIZE
    assert hashlib.sha256(sample.read_bytes()).hexdigest()==EXPECTED_SHA256
    handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(args.root.resolve()))
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}/takeoff/'
    evidence={'checks':[],'page_errors':[]}
    with sync_playwright() as p:
      browser=p.chromium.launch(headless=True);ctx=browser.new_context(viewport={'width':1512,'height':982},accept_downloads=True);page=ctx.new_page();page.on('pageerror',lambda e:evidence['page_errors'].append(str(e)))
      try:
        page.goto(url,wait_until='domcontentloaded',timeout=60000);page.locator('#status[data-state="ready"]').wait_for(timeout=120000)
        engine=page.frames[1];engine.locator('canvas').first.wait_for(timeout=120000);page.wait_for_timeout(2500)
        saved=engine.evaluate(READ_DB,'demo');assert len(saved['pdfs'])==1
        pdf=saved['pdfs'][0];assert pdf['name']=='family4.pdf' and pdf['size']==EXPECTED_SIZE and bytes(pdf['head'])==b'%PDF-'
        ann=saved['annotations'];assert ann and ann['project_name'].startswith('บ้านครอบครัวไทยร่วมสมัย 4')
        assert ann['shapes']==[],'Reference BOQ must never be pre-seeded as generated takeoff'
        assert ann['sheet_tabs']==['family4.pdf#11']
        assert 'family4.pdf' in engine.locator('body').inner_text()
        page.screenshot(path=str(args.out/'01-family4-canvas-desktop.png'),full_page=True)
        evidence['checks'].append('Verified exact 13,058,241-byte Family4 PDF loaded into isolated demo DB; starts on page 11; zero fake takeoff shapes')
        page.locator('[data-tab="boq"]').click();page.wait_for_timeout(400)
        assert page.locator('#csv').is_disabled();assert page.locator('#rows').inner_text().startswith('ยังไม่มี Generated Takeoff')
        assert float(page.locator('#floor-total').inner_text().replace(',',''))==0
        assert 'family4.pdf%2372' in page.locator('#reference-boq').get_attribute('href')
        page.screenshot(path=str(args.out/'02-family4-empty-generated-boq.png'),full_page=True)
        evidence['checks'].append('Generated BOQ starts honestly empty; official BOQ is a separate reference link beginning at PDF page 72')
        page.reload(wait_until='domcontentloaded');page.locator('#status[data-state="ready"]').wait_for(timeout=120000)
        saved2=page.frames[1].evaluate(READ_DB,'demo');assert len(saved2['pdfs'])==1 and saved2['annotations']['shapes']==[]
        evidence['checks'].append('Reload preserves the real benchmark without duplicate seeding')
        page.locator('#workspace').select_option('user');page.locator('#status[data-state="ready"]').wait_for(timeout=60000);engine=page.frames[1]
        own=engine.evaluate(READ_DB,'user');assert len(own['pdfs'])==0 and (own.get('annotations') is None or own['annotations']['shapes']==[])
        engine.locator('input[type="file"]').first.wait_for(state='attached',timeout=30000)
        target=engine.locator('input[type="file"][accept*="pdf"]').first
        if target.count()==0: target=engine.locator('input[type="file"][multiple]').first
        assert target.count()>0;target.set_input_files(str(sample.resolve()));engine.locator('canvas').first.wait_for(timeout=120000);page.wait_for_timeout(3000)
        own=engine.evaluate(READ_DB,'user');assert any(x['name']=='family4.pdf' and x['size']==EXPECTED_SIZE for x in own['pdfs']);assert own['annotations']['shapes']==[]
        evidence['checks'].append('Native upload accepts the same 99-page Thai PDF in the user workspace with no inherited demo quantities')
        page.locator('#workspace').select_option('demo');page.locator('#status[data-state="ready"]').wait_for(timeout=120000);page.locator('[data-tab="guide"]').click()
        assert page.get_by_text('สิ่งที่ไฟล์นี้ช่วยทดสอบจริง',exact=True).is_visible()
        page.set_viewport_size({'width':390,'height':844});page.locator('[data-tab="boq"]').click();page.screenshot(path=str(args.out/'03-family4-boq-mobile.png'),full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
        assert not evidence['page_errors'],evidence['page_errors'];evidence['status']='passed'
      except Exception as error:
        evidence['status']='failed';evidence['error']=str(error);page.screenshot(path=str(args.out/'failure.png'),full_page=True);(args.out/'failure.html').write_text(page.content());raise
      finally:
        (args.out/'qa.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False));browser.close();server.shutdown()
    print('POC_BROWSER_QA_PASSED',json.dumps(evidence,ensure_ascii=False))
if __name__=='__main__':main()
