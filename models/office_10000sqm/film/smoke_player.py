"""Verify the actual completed MP4 and player locally or over public HTTPS."""
from __future__ import annotations
import argparse, functools, hashlib, json, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();group=p.add_mutually_exclusive_group(required=True);group.add_argument('--root',type=Path);group.add_argument('--url');p.add_argument('--output',type=Path,default=Path('.generated/film-player-qa'));a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
server=None
if a.root:
 folder=a.root/'office_10000sqm/film'
 if not (folder/'SOLSTICE-14-Architectural-Film.mp4').exists():
  print('No finished offline film in this build; MP4 player checks not applicable.');raise SystemExit(0)
 class Handler(SimpleHTTPRequestHandler):
  def log_message(self,*args):pass
 server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(a.root.resolve())))
 threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}/office_10000sqm/film/'
else:url=a.url.rstrip('/')+'/'
with urlopen(url,timeout=30) as r:
 assert 'text/html' in r.headers.get('Content-Type','');assert b'<video' in r.read()
with urlopen(url+'render-report.json',timeout=30) as r:report=json.load(r)
with urlopen(url+'SOLSTICE-14-Architectural-Film.mp4',timeout=90) as r:
 assert 'video/mp4' in r.headers.get('Content-Type',''),r.headers;movie=r.read()
assert report['status']=='PASS' and hashlib.sha256(movie).hexdigest()==report['sha256']
checks=[];errors=[]
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,args=['--no-sandbox','--autoplay-policy=no-user-gesture-required'])
 try:
  for mobile in [False,True]:
   context=browser.new_context(viewport={'width':390 if mobile else 1440,'height':844 if mobile else 1000},is_mobile=mobile,has_touch=mobile)
   page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(url,wait_until='domcontentloaded');page.locator('#start').click()
   page.wait_for_function('film.currentTime>0.5 && film.getVideoPlaybackQuality().totalVideoFrames>10',timeout=45000)
   assert page.locator('#cover').is_hidden()
   values=page.evaluate('({duration:film.duration,width:film.videoWidth,height:film.videoHeight,frames:film.getVideoPlaybackQuality().totalVideoFrames})')
   assert abs(values['duration']-24)<.05 and values['width']==1280 and values['height']==720,values
   page.locator('[data-time="20"]').click();page.wait_for_function('film.currentTime>=20 && !film.seeking',timeout=30000)
   assert page.locator('[data-time="20"]').get_attribute('class')=='active'
   assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
   page.evaluate('film.pause()');page.screenshot(path=str(a.output/('mobile.png' if mobile else 'desktop.png')))
   checks.append({'mobile_viewport':mobile,'real_video_playback':'PASS','chapter_seek':'PASS','layout':'PASS',**values});context.close()
  assert not errors,errors
 finally:browser.close()
if server:server.shutdown()
result={'status':'PASS','url':url,'video_sha256':report['sha256'],'checks':checks,'errors':errors,'limitation':'Desktop/mobile Chromium emulation, not a physical iPhone certification.'}
(a.output/'player-report.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
