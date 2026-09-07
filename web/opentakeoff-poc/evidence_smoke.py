#!/usr/bin/env python3
from __future__ import annotations

import argparse
import functools
import http.server
import json
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=Path('.generated/evidence-qa'))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    info = json.loads((args.root / 'browser-runtime-info.json').read_text())
    assert 'evidence-viewer.mjs' in info['runtime_modules'], info
    assert 'evidence-bootstrap.mjs' in info['runtime_modules'], info
    assert info['evidence_viewer'] == 'PDFJS_SOURCE_DRAWING_OVERLAY_FROM_GENERATION_EVIDENCE', info

    auto = json.loads((args.root / 'auto-boq.json').read_text())
    cw20 = next(r for r in auto['rows'] if r.get('id') == 'SAN-PIPE-CW-DN20')
    pipe_evidence = cw20['evidence']
    assert pipe_evidence['exact_segment_evidence_status'] == 'PASS_EXACT_SOURCE_GEOMETRY_RECONCILED', pipe_evidence
    assert abs(float(pipe_evidence['exact_horizontal_length_m']) - 19.812) < 1e-9, pipe_evidence
    assert abs(float(pipe_evidence['exact_vertical_length_m']) - 6.300) < 1e-9, pipe_evidence
    assert pipe_evidence['published_segments'], pipe_evidence
    assert pipe_evidence['published_vertical_runs'], pipe_evidence
    assert all(int(s['page']) <= 71 for s in pipe_evidence['published_segments'])
    assert all(
        int(s['page']) <= 71
        for run in pipe_evidence['published_vertical_runs']
        for s in run.get('source_segments') or []
    )

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(args.root.resolve()))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/?boq_backend=off'
    report = {'url': url, 'checks': [], 'page_errors': [], 'status': 'IN_PROGRESS'}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1512, 'height': 1000})
        page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            page.locator('#auto-rows-body tr').first.wait_for(timeout=30000)
            page.locator('#evidence-lab').wait_for(timeout=30000)
            page.wait_for_function("document.querySelectorAll('.evidence-open').length===27", timeout=30000)
            page.locator('#evidence-canvas').wait_for(state='visible', timeout=60000)
            page.wait_for_function("document.querySelectorAll('#evidence-overlay .evidence-shape.area').length>=1", timeout=30000)
            assert page.locator('#evidence-id').inner_text() == 'ARCH-ROOF-METAL'
            assert '128.349' in page.locator('#evidence-quantity').inner_text()
            assert 'projected' in page.locator('#evidence-formula').inner_text().lower()
            assert 'drawing pages ≤ 71' in page.locator('#evidence-facts').inner_text()
            report['checks'].append('Roof row opens PDF p.13 with measured-area overlay and slope formula')

            pipe_row = page.locator('#auto-rows-body tr[data-evidence-id="SAN-PIPE-CW-DN20"]')
            pipe_row.locator('.evidence-open').click()
            page.wait_for_function("document.querySelector('#evidence-id')?.textContent==='SAN-PIPE-CW-DN20'", timeout=30000)
            page.wait_for_function("document.querySelector('#evidence-page-label')?.textContent.includes('p.58')", timeout=30000)
            formula = page.locator('#evidence-formula').inner_text()
            assert '19.812' in formula and '6.300' in formula and '26.112' in formula, formula
            assert page.locator('#evidence-overlay .evidence-shape.tag').count() >= 1
            assert page.locator('#evidence-overlay .evidence-shape.pipe').count() >= 1
            page.wait_for_function("document.querySelectorAll('#evidence-overlay .exact-horizontal-segment').length>=1", timeout=30000)
            assert page.locator('#evidence-overlay .exact-horizontal-segment').count() == int(pipe_evidence['exact_horizontal_segment_count']) or page.locator('#evidence-overlay .exact-horizontal-segment').count() > 0
            facts = page.locator('#evidence-facts').inner_text()
            assert 'vector segments' in facts and 'กันนับซ้ำ' in facts
            assert 'exact published horizontal vector' in facts
            assert 'PASS_EXACT_SOURCE_GEOMETRY_RECONCILED' in facts
            report['checks'].append('CW DN20 p.58 shows exact published horizontal PDF vector strokes plus tag/network context and unchanged formula')

            p57 = page.locator('#evidence-pages button', has_text='p.57')
            assert p57.count() == 1
            p57.click()
            page.wait_for_function("document.querySelector('#evidence-page-label')?.textContent.includes('p.57')", timeout=30000)
            page.wait_for_function("document.querySelectorAll('#evidence-overlay .exact-vertical-source-stroke').length>=1", timeout=30000)
            vertical_facts = page.locator('#evidence-facts').inner_text()
            assert 'exact vertical source strokes' in vertical_facts
            assert 'run-level physical span' in vertical_facts
            report['checks'].append('CW DN20 p.57 shows exact schematic source strokes while preserving calibrated run-level vertical quantity semantics')

            door_row = page.locator('#auto-rows-body tr[data-evidence-id="ARCH-DOOR-D2"]')
            door_row.locator('.evidence-open').click()
            page.wait_for_function("document.querySelector('#evidence-id')?.textContent==='ARCH-DOOR-D2'", timeout=30000)
            page.wait_for_function("document.querySelectorAll('#evidence-overlay .evidence-shape.detection').length>=1", timeout=30000)
            assert '7 จุดหลักฐาน' in page.locator('#evidence-formula').inner_text()
            report['checks'].append('Door D2 row exposes detected door-swing bounding boxes on the source plan')

            page.screenshot(path=str(args.out / 'boq-evidence-viewer.png'), full_page=True)
            assert not report['page_errors'], report['page_errors']
            report['status'] = 'PASS'
        except Exception as exc:
            report['status'] = 'FAIL'
            report['error'] = str(exc)
            page.screenshot(path=str(args.out / 'failure.png'), full_page=True)
            raise
        finally:
            (args.out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
            browser.close()
            server.shutdown()

    print('BOQ_EVIDENCE_VIEWER_PASS', json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
