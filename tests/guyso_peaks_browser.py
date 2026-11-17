"""Local browser proof for all 24 actual reviewed references; no live accounts."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
import json, os, threading
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test-results/guyso-peaks';OUT.mkdir(parents=True,exist_ok=True)
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'dist')))
threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}/'
data=json.loads((ROOT/'albums/peak-reference/guyso-20261118.json').read_text())
keys=['top100','hot100','realtime','hot100_30','daily','new_week','new_month'];checks=[]
def check(name,value):
 checks.append({'name':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path=os.getenv('BROWSER_PATH') or None)
  ctx=browser.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith(url) else r.abort())
  for endpoint in ('schedule','music','history','albums'):ctx.route('**/api/'+endpoint,lambda r:r.fulfill(status=503,content_type='application/json',body='{}'))
  page.goto(url,wait_until='domcontentloaded');expect(page.locator('#main h1')).to_be_visible()
  page.evaluate("""(rows)=>{for(const [sid,e] of Object.entries(rows)){const t=albumInsights.tracks[sid]||={};t.melon={...(t.melon||{}),...e.identity,state:'ok'};t.melonPeakFallback=e.reference;}}""",data['tracks'])
  for sid,entry in data['tracks'].items():
   page.goto(url+'#/song/'+sid,wait_until='domcontentloaded');expect(page.locator('.ai-peaks')).to_be_visible()
   panel=page.locator('.ai-peaks');values=[str(entry['reference']['records'][k]['rank'])+'위' if entry['reference']['records'][k]['rank'] is not None else '—' for k in keys]
   check(sid+' exact seven source ranks',panel.locator('.ai-peak strong').all_text_contents()==values)
   check(sid+' no card attribution',panel.locator('.ai-peak a, .ai-peak-source').count()==0)
   check(sid+' no legacy provider text','이세계차트' not in panel.inner_text())
   details=panel.locator('details');expect(details.locator('summary')).to_have_text('최고 성적 출처와 확인 시각')
   check(sid+' details closed by default',details.get_attribute('open') is None)
   details.locator('summary').click()
   check(sid+' seven correct provenance links',details.locator('tbody a').evaluate_all('(xs)=>xs.map(a=>a.href)')==[entry['reference']['source']]*7)
   check(sid+' confirmation timestamp retained',details.locator('tbody tr').count()==7 and '가이섬' in details.inner_text())
   details.locator('summary').click()
  page.goto(url+'#/song/love-cells',wait_until='domcontentloaded')
  for width in (320,390,1440):
   page.set_viewport_size({'width':width,'height':1000});page.wait_for_timeout(100)
   check(str(width)+' no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
   if width in (390,1440):page.locator('.ai-peaks').screenshot(path=str(OUT/f'peaks-{width}.png'))
  page.locator('.ai-peaks summary').click();page.locator('.ai-peaks').screenshot(path=str(OUT/'peaks-details.png'))
  for sid in ('but-you-want-more','isegye-cypher'):
   page.goto(url+'#/song/'+sid,wait_until='domcontentloaded');check(sid+' no invented ranking',page.locator('.ai-peak strong').all_text_contents()==['—']*7)
  check('no page exceptions',not errors);browser.close()
finally:
 server.shutdown();(OUT/'report.json').write_text(json.dumps({'checks':checks,'passed':sum(c['passed'] for c in checks),'sourceEvidence':'actual 24-song reviewed dataset injected locally, not a live account session'},ensure_ascii=False,indent=2))
print(json.dumps({'passed':len(checks)}))
