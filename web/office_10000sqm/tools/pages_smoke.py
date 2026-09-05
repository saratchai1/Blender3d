"""Verify real HTML/MIME, same-origin WebGL, touch-size layout and downloads.
Run with --root <built-pages-directory>. No external runtime requests required.
"""
from __future__ import annotations
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
from playwright.sync_api import sync_playwright

p = argparse.ArgumentParser()
p.add_argument('--root', type=Path, required=True)
p.add_argument('--output', type=Path, default=Path('.generated/pages-qa'))
args = p.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
errors = []
checks = []
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass
with tempfile.TemporaryDirectory() as tmp:
    shutil.copytree(args.root.resolve(), Path(tmp) / 'Blender3d')
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=tmp))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/Blender3d/'
    try:
        with sync_playwright() as pw:
            options = {'headless': True, 'args': ['--no-sandbox', '--enable-webgl', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']}
            if os.environ.get('CHROMIUM_EXECUTABLE'):
                options['executable_path'] = os.environ['CHROMIUM_EXECUTABLE']
            browser = pw.chromium.launch(**options)
            for name, size in [('desktop', {'width': 1440, 'height': 960}), ('mobile', {'width': 390, 'height': 844})]:
                page = browser.new_page(viewport=size, has_touch=name == 'mobile', device_scale_factor=1)
                page.on('pageerror', lambda e: errors.append(str(e)))
                response = page.goto(base, wait_until='networkidle')
                assert response.status == 200
                assert 'text/html' in response.headers.get('content-type', '')
                page.wait_for_url('**/office_10000sqm/presentation.html')
                page.wait_for_function('window.__presentation?.ready === true', timeout=40000)
                assert page.locator('#loading').is_hidden()
                model = page.frame_locator('#model')
                assert model.locator('canvas').is_visible()
                assert model.locator('.sidebar').is_hidden()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                summary = page.evaluate("document.getElementById('model').contentWindow.__office14__.summary()")
                assert summary['gfa'] == 10000 and summary['floors'] == 14
                page.wait_for_timeout(1200)
                page.screenshot(path=str(args.output / f'{name}.png'))
                page.locator('#night').click()
                assert page.evaluate("document.getElementById('model').contentWindow.__office14__.renderer.state.night")
                page.locator('#night').click()
                page.evaluate("document.documentElement.style.scrollBehavior='auto'; document.getElementById('floors').scrollIntoView()")
                page.wait_for_function("window.__presentation.activeChapter === 'floors'")
                assert page.evaluate("document.getElementById('model').contentWindow.__office14__.renderer.state.explode") == 1
                page.wait_for_timeout(800)
                page.screenshot(path=str(args.output / f'{name}-floors.png'))
                page.evaluate("document.getElementById('facade').scrollIntoView()")
                page.wait_for_function("window.__presentation.activeChapter === 'facade'")
                assert page.evaluate("document.getElementById('model').contentWindow.__office14__.renderer.state.explode") == 0
                page.locator('#full3d').click()
                page.wait_for_function("document.getElementById('full-model').contentWindow.__office14__?.summary().webgl === true")
                assert not page.locator('#full').is_hidden()
                page.locator('#close').click()
                assert page.locator('#full').is_hidden()
                page.evaluate("document.getElementById('hero').scrollIntoView()")
                with page.expect_download() as download:
                    page.locator('header a[download]').click()
                target = args.output / f'{name}-download.ifc'
                download.value.save_as(target)
                assert target.read_bytes().startswith(b'ISO-10303-21;')
                assert target.stat().st_size == (args.root / 'office_10000sqm/assets/solstice-14-office.ifc').stat().st_size
                checks.append({'viewport': name, 'http': 200, 'contentType': 'text/html', 'webgl': True, 'summary': summary, 'chapterNavigation': True, 'reverseScrollReset': True, 'exploreDialog': True, 'ifcDownloadBytes': target.stat().st_size})
                page.close()
            browser.close()
    finally:
        server.shutdown()
assert not errors, errors
report = {'status': 'PASS', 'scope': 'Chromium desktop and mobile viewport emulation; not a physical iPhone/Safari test', 'checks': checks, 'errors': errors}
(args.output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
