"""Browser acceptance: moving 3D cameras plus real paused frames and controls."""
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
report = {'status': 'IN_PROGRESS', 'url': url, 'checks': checks, 'shots': shots, 'consoleErrors': errors, 'externalRuntimeRequests': external, 'nativeTwinmotionOr3dsMax': False}
def save():
    (args.output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
def record(message):
    checks.append(message)
    save()
    print(message, flush=True)
def bind(page):
    page.set_default_timeout(60000)
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.on('request', lambda r: external.append(r.url) if r.url.startswith('http') and urlparse(r.url).netloc != urlparse(url).netloc else None)
def pause_at(page, time):
    page.evaluate('(t)=>window.__cinematic.seek(t,false)', time)
    page.wait_for_function('(t)=>window.__cinematic.state.renderedTime===t', arg=time, timeout=90000)
    page.wait_for_timeout(300)

try:
    with sync_playwright() as pw:
        options = dict(headless=True, args=['--no-sandbox', '--enable-webgl', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        if os.environ.get('CHROMIUM_EXECUTABLE'):
            options['executable_path'] = os.environ['CHROMIUM_EXECUTABLE']
        browser = pw.chromium.launch(**options)
        page = browser.new_page(viewport={'width':1440,'height':960},device_scale_factor=1)
        bind(page)
        res = page.goto(url, wait_until='domcontentloaded', timeout=60000)
        assert res.status == 200 and 'text/html' in res.headers.get('content-type','')
        page.wait_for_function('window.__cinematic?.state.ready===true', timeout=120000)
        before = page.evaluate('window.__cinematic.getState()')
        page.wait_for_function('(n)=>window.__cinematic.state.frames>n+3', arg=before['frames'], timeout=90000)
        after = page.evaluate('window.__cinematic.getState()')
        assert before['camera'] != after['camera']
        assert after['windTime'] > before['windTime']
        assert after['stats']['conceptArea'] == 10000 and after['stats']['storeys'] == 14
        assert after['stats']['sourceObjects'] == 4504 and after['glError'] == 0
        report['desktop'] = after
        record('HTTP 200 HTML; WebGL 2; actual autoplay camera and wind advance; source 14/10000 preserved')
        for i, name in enumerate(['overview','arrival','facade','garden','roof','bluehour']):
            pause_at(page, i*12+4)
            state = page.evaluate('window.__cinematic.getState()')
            assert state['shot'] == i and state['glError'] == 0
            image = page.screenshot(path=str(args.output/f'{i+1}-{name}.png'), timeout=90000, animations='disabled')
            shots.append({'shot':name,'camera':state['camera'],'sha256':hashlib.sha256(image).hexdigest()})
            record(f'Rendered {name}')
        assert len({x['sha256'] for x in shots}) == 6
        pause_at(page, 4)
        frames = page.evaluate('window.__cinematic.state.frames')
        page.wait_for_timeout(500)
        assert frames == page.evaluate('window.__cinematic.state.frames'), 'Paused movie must not waste rendering frames'
        page.locator('[data-look="day"]').click()
        assert page.evaluate('window.__cinematic.state.look') == 'day'
        page.locator('[data-look="golden"]').click()
        page.locator('#play').click()
        assert page.evaluate('window.__cinematic.state.playing')
        assert page.locator('#pause-icon').is_visible()
        page.locator('#play').click()
        assert not page.evaluate('window.__cinematic.state.playing')
        assert page.locator('#play-icon').is_visible()
        page.locator('#explore').click()
        assert page.evaluate('window.__cinematic.state.exploring')
        previous = page.evaluate('window.__cinematic.getState().camera')
        page.mouse.move(770,360);page.mouse.down();page.mouse.move(970,400,steps=4);page.mouse.up()
        page.wait_for_timeout(500)
        assert page.evaluate('window.__cinematic.getState().camera') != previous
        page.locator('#film').click()
        assert page.evaluate('window.__cinematic.state.playing')
        page.locator('#play').click()
        page.locator('#timeline').fill('27')
        assert page.evaluate('window.__cinematic.state.time') == 27
        page.locator('#quality').click()
        assert page.evaluate('window.__cinematic.state.quality') == 'balanced'
        page.locator('#info').click()
        assert page.locator('#details').is_visible()
        page.locator('#close-info').click()
        page.locator('#hide-ui').click()
        assert page.locator('#restore-ui').is_visible()
        page.locator('#restore-ui').click()
        record('Pause, seek, free orbit, looks, quality, information and clean cinema controls passed')
        page.close()
        phone = browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1,has_touch=True,is_mobile=True)
        bind(phone)
        phone.goto(url,wait_until='domcontentloaded',timeout=60000)
        phone.wait_for_function('window.__cinematic?.state.ready===true',timeout=120000)
        pause_at(phone, 3)
        assert phone.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert phone.locator('#play').is_visible() and phone.locator('#explore').is_visible()
        assert phone.evaluate('window.__cinematic.getState().glError') == 0
        phone.screenshot(path=str(args.output/'mobile.png'),timeout=90000)
        record('Mobile viewport real WebGL and controls passed; not a physical iPhone test')
        assert not errors, errors
        assert not external, external
        browser.close()
    report['status'] = 'PASS'
    save()
    print(json.dumps(report,indent=2))
except Exception as exc:
    report['status'] = 'FAIL'
    report['exception'] = str(exc)
    save()
    print(json.dumps(report,indent=2),flush=True)
    raise
finally:
    if server: server.shutdown()
