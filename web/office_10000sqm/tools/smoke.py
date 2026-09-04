"""Real WebGL smoke checks. pip install playwright==1.57.0; playwright install chromium."""
from __future__ import annotations
import argparse
import json
import os
import struct
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--html', type=Path, required=True)
parser.add_argument('--output', type=Path, default=Path('.generated/office-tests'))
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
html = args.html.read_text(encoding='utf-8')
errors: list[str] = []
with sync_playwright() as p:
    options = dict(headless=True, args=['--no-sandbox', '--enable-webgl', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    if os.getenv('CHROMIUM_EXECUTABLE'):
        options['executable_path'] = os.environ['CHROMIUM_EXECUTABLE']
    browser = p.chromium.launch(**options)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.set_content(html)
    page.wait_for_function('window.__office14__?.summary().webgl === true')
    page.wait_for_timeout(700)
    summary = page.evaluate('window.__office14__.summary()')
    assert summary['gfa'] == 10000 and summary['floors'] == 14 and summary['pvPanels'] == 96
    assert page.locator('#error').is_hidden()
    assert page.evaluate('window.__office14__.renderer.gl.getError()') == 0
    assert page.evaluate('window.__office14__.renderer.canvas.width') > 0
    page.screenshot(path=str(args.output / 'desktop.png'))
    before = page.evaluate('window.__office14__.renderer.batches.reduce((s,b)=>s+b.instances,0)')
    page.locator('#facade').uncheck()
    after = page.evaluate('window.__office14__.renderer.batches.reduce((s,b)=>s+b.instances,0)')
    assert after < before
    page.locator('#facade').check()
    page.locator('#finDepth').fill('1.4')
    page.locator('#finDepth').dispatch_event('change')
    assert page.locator('#fin-value').inner_text() == '1.40 m'
    page.locator('#explode').click()
    assert page.evaluate('window.__office14__.renderer.state.explode') == 1
    page.wait_for_timeout(1000)
    page.screenshot(path=str(args.output / 'exploded.png'))
    page.locator('#reset').click()
    page.locator('#section').click()
    assert page.evaluate('window.__office14__.renderer.state.cutoff') == 8
    page.locator('#cutoff').fill('6')
    page.locator('#cutoff').dispatch_event('input')
    assert page.evaluate('window.__office14__.renderer.state.cutoff') == 6
    page.wait_for_timeout(1000)
    page.screenshot(path=str(args.output / 'section.png'))
    page.locator('#reset').click()
    page.locator('#tab-floors').click()
    page.locator('[data-floor="10"]').click()
    assert page.locator('#selected-area').inner_text() == '680 m²'
    assert page.evaluate('window.__office14__.renderer.state.selected') == 10
    page.locator('#clear-selection').click()
    page.locator('#night').click()
    assert page.evaluate('window.__office14__.renderer.state.night') is True
    page.locator('#sun-hour').fill('16')
    page.locator('#sun-hour').dispatch_event('input')
    assert page.locator('#sun-time').inner_text() == '16:00'
    page.locator('#sun-season').select_option('355')
    assert page.evaluate('window.__office14__.renderer.state.day') == 355
    page.bring_to_front()
    page.locator('#orbit').click()
    theta = page.evaluate('window.__office14__.renderer.goal.theta')
    page.wait_for_timeout(400)
    page.wait_for_function('(t) => window.__office14__.renderer.goal.theta > t', arg=theta, timeout=10000)
    page.locator('#reset').click()
    with page.expect_download() as event:
        page.locator('#export').click()
    dest = args.output / 'export.glb'
    event.value.save_as(dest)
    data = dest.read_bytes()
    magic, version, length = struct.unpack('<III', data[:12])
    assert magic == 0x46546C67 and version == 2 and length == len(data)
    mobile = browser.new_page(viewport={'width': 390, 'height': 844}, device_scale_factor=1, is_mobile=True, has_touch=True)
    mobile.on('pageerror', lambda e: errors.append(str(e)))
    mobile.set_content(html)
    mobile.wait_for_function('window.__office14__?.summary().webgl === true')
    mobile.wait_for_timeout(700)
    assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
    mobile.screenshot(path=str(args.output / 'mobile.png'), full_page=True)
    assert not errors, errors
    browser.close()
report = {'status': 'PASS', 'summary': summary, 'pageErrors': errors, 'glbBytes': len(data), 'checks': ['geometry', 'desktop WebGL', 'facade toggle', 'fin depth', 'explode', 'cutoff', 'floor selection', 'night', 'solar time/date', 'orbit', 'reset', 'GLB download', 'mobile layout']}
(args.output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
