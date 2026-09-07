#!/usr/bin/env python3
from __future__ import annotations
import argparse, functools, hashlib, http.server, json, re, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

EXPECTED_SHA256='f6db0f85e12113b31a545a5e881a75173938e011908ba1a4491016f77b302175'
EXPECTED_SIZE=13_058_241
EXPECTED={
    'Floor Cleanout (FCO) — size WITHHELD':2,
    'Cleanout (CO) — size WITHHELD':1,
    'Roof Floor Drain Ø2½"':2,
    'Air Vent Cap Ø2"':2,
}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=Path('.generated/user-runtime-qa'))
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    root=a.root.resolve(); sample=root/'takeoff/demo/family4.pdf'
    assert sample.stat().st_size==EXPECTED_SIZE
    assert hashlib.sha256(sample.read_bytes()).hexdigest()==EXPECTED_SHA256
    manifest=json.loads((root/'takeoff/browser-runtime-info.json').read_text())
    assert manifest['network_dependency'] is False
    assert manifest['reference_data_dependency'] is False
    assert manifest['pdfjs_version'].startswith('4.10.')
    assert (root/'takeoff/browser-auto-boq.mjs').is_file()
    assert (root/'takeoff/browser-pipe-geometry.mjs').is_file()
    assert 'browser-pipe-geometry.mjs' in manifest.get('runtime_modules',[])
    assert manifest.get('pipe_geometry_release')=='DIAGNOSTIC_ONLY_UNTIL_GENERIC_GATES_PASS'
    assert (root/'takeoff/vendor/pdf.mjs').is_file()
    assert (root/'takeoff/vendor/pdf.worker.mjs').is_file()

    handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(root))
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}/takeoff/'
    report={'status':'IN_PROGRESS','checks':[],'page_errors':[]}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':960},accept_downloads=True)
        page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
        try:
            page.goto(url,wait_until='domcontentloaded',timeout=60000)
            page.locator('#workspace').select_option('user')
            page.locator('#status[data-state="ready"]').wait_for(timeout=60000)
            frame=page.frames[1]
            target=frame.locator('input[type="file"][accept*="pdf"]').first
            if target.count()==0:
                target=frame.locator('input[type="file"][multiple]').first
            target.wait_for(state='attached',timeout=30000)
            target.set_input_files(str(sample))
            frame.locator('canvas').first.wait_for(timeout=120000)

            page.locator('[data-tab="auto"]').click()
            page.wait_for_function("document.querySelector('#auto-rows')?.textContent==='4'",timeout=120000)
            assert page.locator('#auto-rows-body tr').count()==4
            text=page.locator('#auto-rows-body').inner_text()
            for label,qty in EXPECTED.items():
                assert label in text,(label,text)
                row=page.locator('#auto-rows-body tr').filter(has_text=label)
                assert row.count()==1,label
                cells=row.locator('td')
                assert cells.nth(1).inner_text().strip()==str(qty),(label,cells.nth(1).inner_text())
                assert cells.nth(6).inner_text().strip()=='—',label
            assert 'Floor Cleanout Ø4"' not in text and 'Cleanout Ø2½"' not in text
            note=page.locator('#auto-note').inner_text()
            assert 'Browser Runtime Alpha' in note and 'reference isolation = true' in note,note
            withheld=page.locator('#withheld-list .withheld')
            assert withheld.count()==4
            withheld_text=page.locator('#withheld-list').inner_text()
            assert 'SAN-PIPE-LENGTH' in withheld_text
            assert 'SAN-FLOOR-DRAIN-2' in withheld_text
            assert 'SAN-FCO/CO-SIZE' in withheld_text
            assert 'NON-EXPLICIT-BOQ' in withheld_text
            hrefs=page.locator('#auto-rows-body .page-link').evaluate_all('(a)=>a.map(x=>x.getAttribute("href"))')
            pages=[]
            for href in hrefs:
                m=re.search(r'%23(\d+)',href)
                if m: pages.append(int(m.group(1)))
            assert pages and max(pages)<=71,pages
            assert set(pages).issubset({59,60}),pages
            assert not page.locator('#user-auto-json').is_disabled()
            assert page.locator('#accuracy-download').is_hidden()
            assert page.locator('#auto-json-download').is_hidden()

            with page.expect_download(timeout=30000) as dl_info:
                page.locator('#user-auto-json').click()
            dl=dl_info.value
            runtime_path=Path(dl.path())
            runtime=json.loads(runtime_path.read_text(encoding='utf-8'))
            assert runtime['source_policy']['reference_used_for_generation'] is False
            assert runtime['source_policy']['generic_pipe_length_min_primary_diameter_coverage']==0.95
            assert runtime['source_policy']['generic_pipe_length_release_status']=='WITHHELD_ALPHA2_DIAGNOSTIC_ONLY'
            geometry=runtime['diagnostics']['pipe_geometry_alpha2']
            assert geometry['detector']=='browser_pipe_geometry_alpha2'
            assert geometry['release_status']=='WITHHELD_ALPHA2_DIAGNOSTIC_ONLY'
            assert geometry['reference_used_for_generation'] is False
            assert all(int(p)<=71 for p in geometry.get('analyzed_primary_pages',[]))
            metrics=[{
                'page':p.get('page'),
                'segments':p.get('vector_segment_count'),
                'components':p.get('component_count'),
                'coverage':(p.get('diameter_coverage') or {}).get('assigned_fraction'),
                'scale':(p.get('scale') or {}).get('unique_ratio'),
                'accepted_tags':len(((p.get('tag_associations') or {}).get('accepted') or [])),
                'withheld_tags':len(((p.get('tag_associations') or {}).get('withheld') or [])),
                'blockers':p.get('blockers') or [],
            } for p in geometry.get('pages',[])]
            report['pipe_geometry_alpha2']=metrics
            (a.out/'user-runtime-alpha.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2),encoding='utf-8')
            print('USER_PIPE_GEOMETRY_ALPHA2',json.dumps(metrics,ensure_ascii=False))

            page.screenshot(path=str(a.out/'user-runtime-alpha.png'),full_page=True)
            report['checks'].append('User-uploaded Family4 is processed client-side with pinned PDF.js: RFD/AVC retain explicit sizes while FCO/CO counts publish only with size WITHHELD')
            report['checks'].append('Schematic/detail duplicate AVC evidence is reconciled non-additively; Floor Drain, pipe length, FCO/CO size and non-explicit BOQ remain WITHHELD')
            report['checks'].append('Alpha2 emits OCG/vector pipe-network, scale, component, tag-association and diameter-coverage diagnostics but cannot publish a pipe row until the generic 95% release gate passes')
            report['checks'].append('No reference quantity is loaded in user runtime; all published runtime evidence links resolve only to drawing-like pages 59/60')
            report['status']='PASS'
            assert not report['page_errors'],report['page_errors']
        except Exception as exc:
            report['status']='FAIL'; report['error']=str(exc)
            page.screenshot(path=str(a.out/'failure.png'),full_page=True)
            raise
        finally:
            (a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            browser.close(); server.shutdown()
    print('USER_PDF_BROWSER_RUNTIME_PASS',json.dumps(report,ensure_ascii=False))

if __name__=='__main__': main()
