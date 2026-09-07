#!/usr/bin/env python3
"""Live public-site acceptance for Browser Automatic BOQ Alpha on a user-uploaded PDF."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

EXPECTED_SHA256 = 'f6db0f85e12113b31a545a5e881a75173938e011908ba1a4491016f77b302175'
EXPECTED_SIZE = 13_058_241
EXPECTED = {
    'Floor Cleanout (FCO) — size WITHHELD': 2,
    'Cleanout (CO) — size WITHHELD': 1,
    'Roof Floor Drain Ø2½"': 2,
    'Air Vent Cap Ø2"': 2,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True)
    ap.add_argument('--sample', type=Path, required=True)
    ap.add_argument('--output', type=Path, default=Path('.generated/user-runtime-live-qa'))
    a = ap.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    sample = a.sample.resolve()
    assert sample.stat().st_size == EXPECTED_SIZE
    assert hashlib.sha256(sample.read_bytes()).hexdigest() == EXPECTED_SHA256
    url = a.url.rstrip('/') + '/'
    report = {'url': url, 'status': 'IN_PROGRESS', 'checks': [], 'page_errors': []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 960})
        page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
        try:
            response = page.goto(url, wait_until='domcontentloaded', timeout=60000)
            assert response and response.status == 200
            runtime = page.evaluate("""async()=>{
              const paths=['./browser-runtime-info.json','./browser-auto-boq.mjs','./vendor/pdf.mjs','./vendor/pdf.worker.mjs'];
              const rs=await Promise.all(paths.map(p=>fetch(p,{cache:'no-store'})));
              const manifest=rs[0].ok?await rs[0].json():null;
              return {statuses:rs.map(r=>r.status),manifest};
            }""")
            assert runtime['statuses'] == [200, 200, 200, 200], runtime
            manifest = runtime['manifest']
            assert manifest['network_dependency'] is False, manifest
            assert manifest['reference_data_dependency'] is False, manifest
            assert manifest['pdfjs_version'].startswith('4.10.'), manifest

            page.locator('#workspace').select_option('user')
            page.locator('#status[data-state="ready"]').wait_for(timeout=60000)
            frame = page.frames[1]
            target = frame.locator('input[type="file"][accept*="pdf"]').first
            if target.count() == 0:
                target = frame.locator('input[type="file"][multiple]').first
            target.wait_for(state='attached', timeout=30000)
            target.set_input_files(str(sample))
            frame.locator('canvas').first.wait_for(timeout=120000)

            page.locator('[data-tab="auto"]').click()
            page.wait_for_function("document.querySelector('#auto-rows')?.textContent==='4'", timeout=120000)
            assert page.locator('#auto-rows-body tr').count() == 4
            text = page.locator('#auto-rows-body').inner_text()
            for label, qty in EXPECTED.items():
                row = page.locator('#auto-rows-body tr').filter(has_text=label)
                assert row.count() == 1, (label, text)
                assert row.locator('td').nth(1).inner_text().strip() == str(qty), label
                assert row.locator('td').nth(6).inner_text().strip() == '—', label
            assert 'Floor Cleanout Ø4"' not in text
            assert 'Cleanout Ø2½"' not in text

            note = page.locator('#auto-note').inner_text()
            assert 'Browser Runtime Alpha' in note and 'reference isolation = true' in note, note
            withheld = page.locator('#withheld-list').inner_text()
            for item in ('SAN-PIPE-LENGTH', 'SAN-FLOOR-DRAIN-2', 'SAN-FCO/CO-SIZE', 'NON-EXPLICIT-BOQ'):
                assert item in withheld, (item, withheld)

            hrefs = page.locator('#auto-rows-body .page-link').evaluate_all('(a)=>a.map(x=>x.getAttribute("href"))')
            pages = []
            for href in hrefs:
                m = re.search(r'%23(\d+)', href)
                if m:
                    pages.append(int(m.group(1)))
            assert pages and max(pages) <= 71, pages
            assert set(pages).issubset({59, 60}), pages
            assert not page.locator('#user-auto-json').is_disabled()
            assert page.locator('#auto-json-download').is_hidden()
            assert page.locator('#accuracy-download').is_hidden()
            assert not report['page_errors'], report['page_errors']

            page.screenshot(path=str(a.output / 'user-runtime-live.png'), full_page=True)
            report['checks'].append('Public Pages serves pinned PDF.js runtime assets with network/reference dependencies disabled')
            report['checks'].append('Fresh user workspace processes uploaded Family4 client-side into four fail-closed sanitary rows: FCO/CO unsized, RFD/AVC explicitly sized')
            report['checks'].append('Cross-view duplicates remain non-additive; pipe length, Floor Drain, FCO/CO size and non-explicit BOQ stay WITHHELD; evidence links stay on drawing pages 59/60')
            report['status'] = 'PASS'
        except Exception as exc:
            report['status'] = 'FAIL'
            report['error'] = str(exc)
            page.screenshot(path=str(a.output / 'failure.png'), full_page=True)
            raise
        finally:
            (a.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            browser.close()

    print('USER_PDF_BROWSER_RUNTIME_LIVE_PASS', json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
