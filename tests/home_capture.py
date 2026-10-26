"""Capture the actual review, scrolling lazy images into view; no mocked responses."""
from pathlib import Path
import os,json,subprocess,time
from datetime import datetime,timezone
from urllib.request import urlopen
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
URL=os.getenv('HOME_URL','http://127.0.0.1:4200/').rstrip('/')+'/'
OUT=ROOT/os.getenv('HOME_OUT','test-results/home-simple');OUT.mkdir(parents=True,exist_ok=True)
server=None
try:
 if 'HOME_URL' not in os.environ:
  server=subprocess.Popen(['python','-m','http.server','4200','--bind','127.0.0.1','--directory','home-dist'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(30):
   try:urlopen(URL,timeout=1).close();break
   except Exception:time.sleep(.1)
 with sync_playwright() as p:
  b=p.chromium.launch();ctx=b.new_context(viewport={'width':1440,'height':1050},locale='ko-KR',timezone_id='Asia/Seoul',reduced_motion='reduce');page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(URL,wait_until='networkidle');page.locator('.hm-page').wait_for()
  for width,theme,name in [(1440,'light','review-desktop'),(390,'light','review-mobile'),(390,'dark','review-dark-mobile')]:
   page.set_viewport_size({'width':width,'height':1050 if width==1440 else 844});page.evaluate('(x)=>document.documentElement.dataset.theme=x',theme)
   for selector in ('.hm-video-grid','.hm-song-grid','.hm-more'):
    page.locator(selector).scroll_into_view_if_needed();page.wait_for_timeout(400)
   page.evaluate('scrollTo(0,0)');page.wait_for_timeout(250)
   assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
   page.screenshot(path=str(OUT/(name+'.png')),full_page=True)
   if width==1440:page.screenshot(path=str(OUT/'review-top.png'))
  assert not errors
  meta=ctx.request.get(URL+'build-info.json').json();assert meta['commit']==os.environ['GITHUB_SHA']
  (OUT/'capture.json').write_text(json.dumps({'url':URL,'commit':meta['commit'],'checkedAt':datetime.now(timezone.utc).isoformat(),'intercepted':False,'browserErrors':errors,'images':page.locator('[data-home-image]').evaluate_all('(xs)=>xs.map(x=>({src:x.src,loaded:x.complete&&x.naturalWidth>0,hidden:x.hidden}))')},ensure_ascii=False,indent=2))
  b.close()
finally:
 if server:server.terminate();server.wait(timeout=5)
