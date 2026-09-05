#!/usr/bin/env python3
"""Actual Chromium smoke test of the built engine, not a mocked measurement canvas."""
from __future__ import annotations
import argparse
import functools
import http.server
import json
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright

READ_DB = '''async (kind) => {
 const db=await new Promise((yes,no)=>{const r=indexedDB.open('blender3d-opentakeoff-poc-v1-'+kind);r.onsuccess=()=>yes(r.result);r.onerror=()=>no(r.error);});
 try {return await new Promise((yes,no)=>{const t=db.transaction(['meta','pdfs'],'readonly');const a=t.objectStore('meta').get('annotations');const p=t.objectStore('pdfs').getAll();t.oncomplete=()=>yes({annotations:a.result,pdfs:p.result.map(x=>({name:x.name,bytes:Array.from(new Uint8Array(x.bytes))}))});t.onerror=()=>no(t.error);});}finally{db.close();}
}'''

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,default=Path('.generated/takeoff-qa'));args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(args.root.resolve()))
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}/takeoff/'
    evidence={'checks':[],'page_errors':[]}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1512,'height':982},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda e:evidence['page_errors'].append(str(e)))
        try:
            page.goto(url,wait_until='domcontentloaded',timeout=60000)
            page.locator('#status[data-state="ready"]').wait_for(timeout=90000)
            frame=page.locator('#engine').content_frame
            frame.locator('canvas').first.wait_for(timeout=60000)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(args.out/'01-canvas-desktop.png'),full_page=True)
            engine=page.frames[1]
            saved=engine.evaluate(READ_DB,'demo')
            assert len(saved['pdfs'])==1
            assert len(saved['annotations']['shapes'])==12, len(saved['annotations']['shapes'])
            assert saved['pdfs'][0]['bytes'][:5]==list(b'%PDF-')
            pdf=bytes(saved['pdfs'][0]['bytes']);(args.out/'synthetic-plan.pdf').write_bytes(pdf)
            evidence['checks'].append('Real PDF stored, rendered by upstream PDF.js, 12 seeded review proposals')
            page.locator('[data-tab="boq"]').click();page.wait_for_timeout(500)
            for key,expected in [('floor',240),('wall',60),('linear',20),('count',6)]:
                actual=float(page.locator(f'#{key}-total').inner_text().replace(',',''))
                assert abs(actual-expected)<.011,(key,actual,expected)
            assert page.locator('#rows tr').count()==7
            with page.expect_download() as d:page.locator('#csv').click()
            csv_path=args.out/'demo-quantities.csv';d.value.save_as(csv_path)
            text=csv_path.read_text(encoding='utf-8-sig')
            assert '2D_OPEN_TAKEOFF' in text and 'PENDING_REVIEW' in text
            with page.expect_download() as d:page.locator('#json').click()
            json_path=args.out/'demo-takeoff.json';d.value.save_as(json_path)
            takeoff=json.loads(json_path.read_text());assert len(takeoff['shapes'])==12
            assert takeoff['schema']=='opentakeoff.takeoff_canvas.v1'
            page.screenshot(path=str(args.out/'02-boq-desktop.png'),full_page=True)
            evidence['checks'].append('Upstream quantities convert to 240m2 floor, 60m2 wall, 20m linear, 6 counts; 7 BOQ rows; CSV+JSON downloads verified')
            page.reload(wait_until='domcontentloaded');page.locator('#status[data-state="ready"]').wait_for(timeout=60000)
            page.locator('[data-tab="boq"]').click();assert page.locator('#rows tr').count()==7
            evidence['checks'].append('Reload preserves measurements without duplicate seeding')
            page.locator('#workspace').select_option('user');page.locator('#status[data-state="ready"]').wait_for(timeout=60000)
            engine=page.frames[1]
            own=engine.evaluate(READ_DB,'user')
            assert len(own['pdfs'])==0
            # loadAnnotations returns emptyAnnotations in memory on a pristine DB.
            # Until the first save, there is correctly no raw 'annotations' record.
            assert own.get('annotations') is None or own['annotations']['shapes']==[]
            page.locator('[data-tab="boq"]').click()
            assert page.locator('#csv').is_disabled()
            assert float(page.locator('#floor-total').inner_text().replace(',',''))==0
            page.locator('[data-tab="plan"]').click()
            evidence['checks'].append('Pristine user workspace has no PDFs, no inherited annotations and an empty BOQ')
            engine.locator('input[type="file"]').first.wait_for(state='attached',timeout=30000)
            inputs=engine.locator('input[type="file"]')
            accepted=inputs.evaluate_all('(els)=>els.map(x=>x.accept)')
            print('NATIVE_UPLOAD_ACCEPTS',json.dumps(accepted),flush=True)
            target=engine.locator('input[type="file"][accept*="pdf"]').first
            if target.count()==0:
                target=engine.locator('input[type="file"][multiple]').first
            assert target.count()>0,'Native PDF file input missing'
            target.set_input_files({'name':'My-test-plan.pdf','mimeType':'application/pdf','buffer':pdf})
            engine.locator('canvas').first.wait_for(timeout=60000)
            page.wait_for_timeout(2500)
            own=engine.evaluate(READ_DB,'user')
            assert any(x['name']=='My-test-plan.pdf' for x in own['pdfs'])
            assert len(own['annotations']['shapes'])==0,'User upload must not inherit demo traces'
            evidence['checks'].append('Native PDF upload works; user drawing does not inherit sample measurements')
            page.locator('#workspace').select_option('demo');page.locator('#status[data-state="ready"]').wait_for(timeout=60000)
            page.locator('[data-tab="guide"]').click();assert page.get_by_text('ขอบเขตของ POC นี้',exact=True).is_visible()
            page.set_viewport_size({'width':390,'height':844});page.locator('[data-tab="boq"]').click()
            page.screenshot(path=str(args.out/'03-boq-mobile.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2'),'Page-level horizontal overflow'
            evidence['checks'].append('Thai guide and 390px responsive BOQ shell work; native canvas remains best used on desktop')
            assert not evidence['page_errors'],evidence['page_errors']
            evidence['status']='passed'
        except Exception as error:
            evidence['status']='failed';evidence['error']=str(error)
            page.screenshot(path=str(args.out/'failure.png'),full_page=True)
            (args.out/'failure.html').write_text(page.content())
            print('QA_FAILURE',json.dumps(evidence,ensure_ascii=False),flush=True)
            for f in page.frames:
                try: print('FRAME_TEXT',f.url,f.locator('body').inner_text()[:7000],flush=True)
                except Exception: pass
            raise
        finally:
            (args.out/'qa.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False))
            browser.close();server.shutdown()
    print('POC_BROWSER_QA_PASSED',json.dumps(evidence,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
