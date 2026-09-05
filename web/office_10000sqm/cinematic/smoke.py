"""Real-browser film checks, including camera motion; never substitutes stills for the app."""
from __future__ import annotations
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import threading
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
p = argparse.ArgumentParser()
p.add_argument('--root', type=Path)
p.add_argument('--url')
p.add_argument('--output', type=Path, default=Path('.generated/cinematic-qa'))
args = p.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
server = None
if args.url:
    url = args.url
elif args.root:
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *_): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(args.root.resolve())))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/cinematic/'
else:
    p.error('Supply --root or --url')
errors, external, shots, checks = [], [], [], []
try:
    with sync_playwright() as pw:
        options = dict(headless=True, args=['--no-sandbox', '--enable-webgl', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        if os.environ.get('CHROMIUM_EXECUTABLE'):
            options['executable_path'] = os.environ['CHROMIUM_EXECUTABLE']
        browser = pw.chromium.launch(**options)
        page = browser.new_page(viewport={'width': 1440, 'height': 960}, device_scale_factor=1)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('request', lambda r: external.append(r.url) if r.url.startswith('http') and urlparse(r.url).netloc != urlparse(url).netloc else None)
        res = page.goto(url, wait_until='domcontentloaded', timeout=60000)
        assert res.status == 200 and 'text/html' in res.headers.get('content-type','')
        page.wait_for_function('window.__cinematic?.state.ready === true', timeout=120000)
        before = page.evaluate('window.__cinematic.getState()')
        page.wait_for_function('(n)=>window.__cinematic.state.frames > n+3', arg=before['frames'], timeout=30000)
        after = page.evaluate('window.__cinematic.getState()')
        assert before['camera'] != after['camera'] and after['time'] > before['time'], 'Film must move the 3D camera automatically'
        assert after['windTime'] > before['windTime']
        assert after['stats']['conceptArea'] == 10000 and after['stats']['storeys'] == 14
        assert after['stats']['sourceObjects'] == 4504 and after['glError'] == 0
        checks += ['HTTP 200 HTML', 'WebGL 2 initialized', 'autoplay advances actual camera', 'environment animation advances', 'source 14 storeys / 10000 sqm preserved']
        for i, name in enumerate(['overview','arrival','facade','garden','roof','bluehour']):
            page.evaluate('(t)=>window.__cinematic.seek(t,false)', i*12+4)
            f = page.evaluate('window.__cinematic.state.frames')
            page.wait_for_function('(n)=>window.__cinematic.state.frames > n+1', arg=f, timeout=30000)
            state = page.evaluate('window.__cinematic.getState()')
            assert state['shot'] == i and state['glError'] == 0
            image = page.screenshot(path=str(args.output / f'{i+1}-{name}.png'))
            shots.append({'shot': name, 'camera': state['camera'], 'sha256': hashlib.sha256(image).hexdigest()})
        assert len({x['sha256'] for x in shots}) == 6
        checks.append('six distinct rendered 3D shots')
        page.locator('[data-look="day"]').click()
        assert page.evaluate('window.__cinematic.state.look') == 'day'
        page.locator('[data-look="golden"]').click()
        page.locator('#play').click()
        assert page.evaluate('window.__cinematic.state.playing')
        page.locator('#play').click()
        assert not page.evaluate('window.__cinematic.state.playing')
        page.locator('#explore').click()
        assert page.evaluate('window.__cinematic.state.exploring')
        before = page.evaluate('window.__cinematic.getState().camera')
        page.mouse.move(770,360);page.mouse.down();page.mouse.move(970,400,steps=8);page.mouse.up()
        page.wait_for_timeout(500)
        assert page.evaluate('window.__cinematic.getState().camera') != before
        page.locator('#film').click()
        assert page.evaluate('window.__cinematic.state.playing')
        page.locator('#timeline').fill('27')
        assert 26.9 <= page.evaluate('window.__cinematic.state.time') < 31
        page.locator('#quality').click()
        assert page.evaluate('window.__cinematic.state.quality') == 'balanced'
        page.locator('#info').click()
        assert page.locator('#details').is_visible()
        page.locator('#close-info').click()
        page.locator('#hide-ui').click()
        assert page.locator('#restore-ui').is_visible()
        page.locator('#restore-ui').click()
        checks += ['play / pause', 'seek', 'free orbit changes camera', 'lighting controls', 'quality controls', 'information dialog', 'clean cinema mode']
        phone = browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1,has_touch=True,is_mobile=True)
        phone.on('pageerror',lambda e:errors.append(str(e)))
        phone.goto(url,wait_until='domcontentloaded',timeout=60000)
        phone.wait_for_function('window.__cinematic?.state.ready === true',timeout=120000)
        phone.evaluate('window.__cinematic.seek(3,false)')
        phone.wait_for_timeout(1000)
        assert phone.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert phone.locator('#play').is_visible() and phone.locator('#explore').is_visible()
        assert phone.evaluate('window.__cinematic.getState().glError') == 0
        phone.screenshot(path=str(args.output / 'mobile.png'))
        checks.append('mobile viewport real WebGL and controls; not a physical iPhone test')
        assert not errors, errors
        assert not external, external
        browser.close()
    report={'status':'PASS','url':url,'checks':checks,'desktop':after,'shots':shots,'consoleErrors':errors,'externalRuntimeRequests':external,'nativeTwinmotionOr3dsMax':False}
    (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
finally:
    if server: server.shutdown()
