#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

EXPECTED_SHA256 = 'f6db0f85e12113b31a545a5e881a75173938e011908ba1a4491016f77b302175'
EXPECTED_SIZE = 13_058_241


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True)
    ap.add_argument('--out', type=Path, default=Path('.generated/evidence-live-qa'))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    url = args.url.rstrip('/') + '/'
    report = {'url': url, 'checks': [], 'page_errors': [], 'status': 'IN_PROGRESS'}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1512, 'height': 1000})
        page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
        try:
            response = page.goto(url, wait_until='domcontentloaded', timeout=60000)
            assert response and response.status == 200
            page.locator('#auto-rows-body tr').first.wait_for(timeout=30000)
            page.wait_for_function("document.querySelectorAll('.evidence-open').length===27", timeout=30000)

            pdf_response = page.request.get(url + 'demo/family4.pdf')
            assert pdf_response.status == 200, pdf_response.status
            pdf_bytes = pdf_response.body()
            assert len(pdf_bytes) == EXPECTED_SIZE, len(pdf_bytes)
            assert hashlib.sha256(pdf_bytes).hexdigest() == EXPECTED_SHA256
            report['checks'].append('Embedded evidence viewer uses the exact 13,058,241-byte Family4 source PDF')

            page.locator('#evidence-canvas').wait_for(state='visible', timeout=60000)
            page.wait_for_function("document.querySelectorAll('#evidence-overlay .evidence-shape.area').length>=1", timeout=30000)
            assert page.locator('#evidence-id').inner_text() == 'ARCH-ROOF-METAL'
            assert '128.349' in page.locator('#evidence-quantity').inner_text()
            formula = page.locator('#evidence-formula').inner_text()
            assert 'projected' in formula.lower() and 'cos' in formula and '128.349' in formula, formula
            assert 'drawing pages ≤ 71' in page.locator('#evidence-facts').inner_text()
            report['checks'].append('Roof p.13 visibly proves projected geometry plus slope correction → 128.349 m²')

            pipe_row = page.locator('#auto-rows-body tr[data-evidence-id="SAN-PIPE-CW-DN20"]')
            pipe_row.locator('.evidence-open').click()
            page.wait_for_function("document.querySelector('#evidence-id')?.textContent==='SAN-PIPE-CW-DN20'", timeout=30000)
            page.wait_for_function("document.querySelector('#evidence-page-label')?.textContent.includes('p.58')", timeout=30000)
            formula = page.locator('#evidence-formula').inner_text()
            assert '19.812' in formula and '6.300' in formula and '26.112' in formula, formula
            assert page.locator('#evidence-overlay .evidence-shape.tag').count() >= 1
            assert page.locator('#evidence-overlay .evidence-shape.pipe').count() >= 1
            pipe_facts = page.locator('#evidence-facts').inner_text()
            assert 'vector segments' in pipe_facts and 'กันนับซ้ำ' in pipe_facts
            report['checks'].append('CW DN20 p.58 visibly shows drawing tag/CAD network seed plus 19.812 m horizontal + 6.300 m vertical = 26.112 m')

            door_row = page.locator('#auto-rows-body tr[data-evidence-id="ARCH-DOOR-D2"]')
            door_row.locator('.evidence-open').click()
            page.wait_for_function("document.querySelector('#evidence-id')?.textContent==='ARCH-DOOR-D2'", timeout=30000)
            page.wait_for_function("document.querySelectorAll('#evidence-overlay .evidence-shape.detection').length>=1", timeout=30000)
            assert '7 จุดหลักฐาน' in page.locator('#evidence-formula').inner_text()
            report['checks'].append('D2 visibly exposes seven detected door-swing evidence boxes on the source plans')

            page.screenshot(path=str(args.out / 'public-boq-evidence-viewer.png'), full_page=True)
            assert not report['page_errors'], report['page_errors']
            report['status'] = 'PASS'
        except Exception as exc:
            report['status'] = 'FAIL'
            report['error'] = str(exc)
            page.screenshot(path=str(args.out / 'failure.png'), full_page=True)
            raise
        finally:
            (args.out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            browser.close()

    print('PUBLIC_BOQ_EVIDENCE_VIEWER_PASS', json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
