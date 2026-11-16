"""Real HTTP tests of the integrated operating app, not the standalone preview."""
from pathlib import Path
import http.server,socketserver,threading,json,os,sys
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import playground_bank as bank
from datetime import datetime,timezone
OUT=ROOT/'test-results/playground-production';OUT.mkdir(parents=True,exist_ok=True);checks=[]
def check(n,v):
 checks.append({'name':n,'passed':bool(v)})
 if not v:raise AssertionError(n)
class Handler(http.server.SimpleHTTPRequestHandler):
 def __init__(self,*a,**k):super().__init__(*a,directory=str(ROOT/'dist'),**k)
 def log_message(self,*a):pass
server=socketserver.TCPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://127.0.0.1:'+str(server.server_address[1])
feed,_=bank.assemble(None,[],datetime.now(timezone.utc))
try:
 with sync_playwright() as p:
  opt={'headless':True}
  if os.getenv('CHROMIUM_PATH'):opt['executable_path']=os.environ['CHROMIUM_PATH']
  b=p.chromium.launch(**opt);ctx=b.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  def apis(route):
   if route.request.url.endswith('/api/playground'):route.fulfill(json=feed)
   elif route.request.url.endswith('/auth/status'):route.fulfill(json={'authenticated':False,'administrator':False,'maintenance':False,'allowed':True})
   else:route.fulfill(status=503,json={'error':'fixture_offline'})
  page.route('**/api/**',apis);page.route('**/auth/status',apis);page.route('https://**',lambda r:r.abort())
  page.add_init_script("localStorage.setItem('isegye:playground:review:v1','REVIEW_KEEP');localStorage.setItem('isegye:bookmarks:v1','BOOKMARK_KEEP')")
  try:
   page.goto(url+'/#/playground',wait_until='networkidle');expect(page.locator('.playground-component h1')).to_have_text('놀이터')
   expect(page.locator('.hero')).to_have_css('display','grid');check('production scoped stylesheet loaded',True)
   check('eight operating navigation entries',page.locator('.desktop-nav a').count()==8)
   check('mobile more menu contains playground',page.locator('#more-menu a[href="#/playground"]').count()==1)
   check('no second site header or iframe',page.locator('header').count()==1 and page.locator('iframe').count()==0)
   page.screenshot(path=str(OUT/'home-1440.png'),full_page=True)
   page.locator('[data-start=daily]').click();expect(page.locator('[data-answer]')).to_have_count(4);check('production deep link',page.url.endswith('#/playground/play'))
   page.locator('[data-action=hint]').click();expect(page.locator('[data-action=hint]')).to_be_disabled()
   current=page.evaluate("JSON.parse(localStorage.getItem('isegye:playground:v1'))")
   hint=next(q['hint'] for q in feed['catalog']['questions'] if q['id']==current['session']['ids'][0]);expect(page.get_by_text(hint,exact=False).last).to_be_visible()
   page.locator('[data-answer]').first.click();expect(page.locator('[data-action=next]')).to_be_visible()
   check('answered round persisted before reload',page.evaluate("JSON.parse(localStorage.getItem('isegye:playground:v1')).session.answers.length===1"))
   page.reload(wait_until='networkidle');expect(page.locator('[data-action=next]')).to_be_visible();check('production resume survives reload',page.locator('.feedback').count()==1)
   for i in range(5):
    if i:page.locator('[data-action=skip]').click()
    page.locator('[data-action=next]').click()
   expect(page.locator('.score')).to_be_visible();check('five questions finish','/ 5' in page.locator('.score').inner_text())
   page.locator('[data-share-result]').click();expect(page.locator('#share')).to_be_visible();check('result shares operating route','https://isegye-idol.kr/#/playground' in page.locator('#share-text').input_value() and 'review-playground' not in page.locator('#share-text').input_value());page.locator('[data-action=close-share]').click()
   check('preview and bookmarks preserved',page.evaluate("localStorage.getItem('isegye:playground:review:v1')==='REVIEW_KEEP'&&localStorage.getItem('isegye:bookmarks:v1')==='BOOKMARK_KEEP'"))
   page.locator('.pg-tools a[href="#/playground/records"]').click();expect(page.locator('.record-row')).to_have_count(1)
   page.locator('.desktop-nav a[href="#/music"]').click();expect(page.locator('#main h1')).to_be_visible();check('existing music still works','음악' in page.locator('#main').inner_text())
   page.locator('.desktop-nav a[href="#/playground"]').click();expect(page.locator('[data-start=daily]')).to_be_visible()
   page.locator('[data-start=order]').click();expect(page.locator('[data-answer]')).to_have_count(2);page.locator('[data-answer]').first.click();check('order feedback distinguishes audio dates','국내 음원 발매' in page.locator('.feedback').inner_text())
   page.goto(url+'/#/playground/quiz');expect(page.locator('[data-category]')).to_have_count(5)
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':1000})
    for route in ('playground','playground/quiz','playground/play','playground/records','playground/sources'):
     page.goto(url+'/#/'+route);expect(page.locator('.playground-component')).to_be_visible();page.wait_for_timeout(120)
     check('no overflow '+str(width)+' '+route,page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
     if width in (390,1440) and route=='playground':page.screenshot(path=str(OUT/f'home-{width}.png'),full_page=True)
   check('no JavaScript runtime errors',not errors)
   ctx2=b.new_context();p2=ctx2.new_page();p2.route('**/api/**',lambda r:r.fulfill(status=503,json={'error':'offline'}));p2.route('https://**',lambda r:r.abort());p2.goto(url+'/#/playground');expect(p2.locator('[data-start=daily]')).to_be_visible();check('network failure uses seed','기본 문제' in p2.locator('#bank-note').inner_text());ctx2.close()
   ctx3=b.new_context();ctx3.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new DOMException('blocked','SecurityError')}})");p3=ctx3.new_page();p3.route('**/api/**',apis);p3.route('https://**',lambda r:r.abort());p3.goto(url+'/#/playground');p3.locator('[data-start=daily]').click();p3.locator('[data-answer]').first.click();p3.locator('.pg-tools a[href="#/playground/records"]').click();p3.locator('.pg-tools a[href="#/playground"]').click();p3.locator('a[href="#/playground/play"]').first.click();expect(p3.locator('.feedback')).to_be_visible();check('blocked storage preserves in-tab play across menu routes',True);ctx3.close()
  except Exception as e:
   debug={'error':str(e),'url':page.url,'errors':errors,'state':page.evaluate("localStorage.getItem('isegye:playground:v1')"),'body':page.locator('body').inner_text(),'shadow':page.locator('.playground-component').evaluate('(e)=>e.shadowRoot.innerHTML') if page.locator('.playground-component').count() else None}
   (OUT/'failure.json').write_text(json.dumps(debug,ensure_ascii=False,indent=2));page.screenshot(path=str(OUT/'failure.png'),full_page=True);raise
  finally:b.close()
finally:
 server.shutdown();(OUT/'browser.json').write_text(json.dumps({'mode':'real HTTP operating SPA','checks':checks},ensure_ascii=False,indent=2))
print(json.dumps({'passed':len(checks),'mode':'HTTP production'}))
