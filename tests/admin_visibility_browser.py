"""Public/member/admin rendering and revocation. The actual PHP boundary is unit-tested.
IN_MEMORY=1 is a local DOM-only fallback, never used by CI or deployed.
"""
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
import json,os,re,sys,threading
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from compose_admin_visibility import POLICY,project
OUT=ROOT/'test-results/admin-visibility';OUT.mkdir(parents=True,exist_ok=True)
MEMORY=os.getenv('IN_MEMORY')=='1';state={'role':'guest','fail':False}
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  path=self.path.split('?',1)[0];role=state['role']
  if path=='/auth/status':
   raw=json.dumps({'authenticated':role!='guest','administrator':role=='admin','allowed':True,'maintenance':False}).encode()
   self.send_response(503 if state['fail'] else 200);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw);return
  if path in POLICY['protectedPaths'] and role!='admin':self.send_error(401 if role=='guest' else 403);return
  if path.startswith('/api/'):
   self.send_error(503);return
  if role!='admin':self.path='/'+POLICY['publicFiles'].get(path.lstrip('/'),path.lstrip('/'))
  super().do_GET()
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'dist')))
threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}/'
checks=[];errors=[];audit={}
def check(name,value):
 checks.append({'name':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path=os.getenv('BROWSER_PATH') or None)
  context=browser.new_context(viewport={'width':1440,'height':1000})
  context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(url) else route.abort())
  page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
  def mount(role,route='status'):
   state.update(role=role,fail=False)
   if not MEMORY:
    page.goto('about:blank')  # Role fixtures must start a fresh document, not a hash-only navigation.
    page.goto(url+'#/'+route,wait_until='domcontentloaded')
   else:
    page.goto('about:blank');html=(ROOT/'dist/index.html').read_text()
    files=re.findall(r'<script[^>]+src="([^"]+)"[^>]*></script>',html)
    html=re.sub(r'<script\b.*?</script>','',html,flags=re.S);html=re.sub(r'<meta[^>]+http-equiv=[^>]+>','',html,flags=re.I);html=re.sub(r'<link[^>]+>','',html)
    page.set_content(html)
    page.add_style_tag(content=(ROOT/'dist/src/styles.css').read_text())
    page.evaluate("(s)=>{location.hash='#/'+s;window.__fixtureRole='"+role+"';window.__fixtureFail=false;window.fetch=async u=>new Response(String(u)==='/auth/status'?JSON.stringify({authenticated:__fixtureRole!=='guest',administrator:__fixtureRole==='admin',allowed:true}):'{}',{status:String(u)==='/auth/status'&&!__fixtureFail?200:503,headers:{'Content-Type':'application/json'}})}",route)
    private=(ROOT/'dist/src/admin-operations.js').read_text().replace('export function createViews','function createViews')
    page.add_script_tag(content='window.__adminFixtureFactory=(()=>{'+private+';return createViews;})();')
    for relative in files:
     if not (ROOT/'dist'/relative).is_file():continue
     name=relative if role=='admin' else POLICY['publicFiles'].get(relative,relative)
     code=(ROOT/'dist'/name).read_text()
     if relative=='src/app.js':
      code=code.replace("!/^https?:$/.test(location.protocol)",'false').replace("await import('/src/admin-operations.js')","await Promise.resolve({createViews:window.__adminFixtureFactory})")
     page.add_script_tag(content=code)
   expect(page.locator('#main h1')).to_be_visible()
   if role=='admin':page.wait_for_function('IsegyeOps.allowed()===true')
   else:page.wait_for_timeout(80)
  def go(route):
   page.evaluate('(r)=>{location.hash="#/"+r;render()}',route)
   expect(page.locator('#main h1')).to_be_visible()
  forbidden=['저장 시점 확인 성공','운영 연동 시 구분할 항목','마지막 시도','서비스 연결 상태','무료 API 키 설정 필요','그래프 예시 보기','주간 미수집','게시본 반영','20분·40분','00시 및 07~23시','운영 연동 검토 항목','전체 과거 영상 수집','검토본입니다','검토용 목록','공개 API 확인값']
  mount('guest')
  check('public status retains original source links',page.locator('#main a[href^="https://berriz.in/"]').count()>=1)
  check('public source dates visible','출처별 마지막 확인' in page.locator('#main').inner_text())
  check('no operations flash before authorization',page.locator('[data-admin-only]').count()==0)
  notice=page.evaluate('D.notices[0].id');album=page.evaluate('D.albums[0].id');record=page.evaluate('D.history[0].id')
  routes=['status','home','members','member/ine','schedule','notice/'+notice,'music','music?tab=albums','album/'+album,'song/rewind','song/kidding','song/cat-save-world?demo=1&admin=true','song/rebels','content','content?tab=replay','content?tab=series','video/sy40EGkSfRA','series/music-beginning','history','history/'+record,'search?q=이세돌','saved','guide','guide?tab=participate','about','review','report','terms','privacy','live']
  for route in routes:
   go(route);text=page.locator('#main').text_content();audit[route]=page.locator('#main').inner_text()
   check('public diagnostics absent '+route,not any(word in text for word in forbidden))
   check('public has no admin markup '+route,page.locator('[data-admin-only]').count()==0)
  go('song/cat-save-world?demo=1')
  check('query cannot enable example graph',page.locator('.ai-demo').count()==0)
  check('real graphs and music links retained',page.locator('.ai-flow-panel').count()==1 and page.locator('.ai-platform-logo').count()==6)
  check('seven historical peaks retained',page.locator('.ai-peak').count()==7)
  check('no provider diagnostics in public seed',page.evaluate('Object.keys(albumInsights.providers).length')==0)
  check('source attempts not in public data',page.evaluate('D.sources.every(s=>(!("lastAttemptAt" in s))&&!("state" in s))'))
  # A forged local preference does not grant access.
  page.evaluate("try{localStorage.setItem('administrator','true');localStorage.setItem('role','admin')}catch{};render()")
  check('local flags cannot enable admin',not page.evaluate('IsegyeOps.allowed()') and page.locator('.ai-demo').count()==0)
  for width in (390,1440):
   page.set_viewport_size({'width':width,'height':1000})
   for route,label in [('status','public-status'),('song/cat-save-world','public-song')]:
    go(route);check(label+' no overflow '+str(width),page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    page.locator('#main').screenshot(path=str(OUT/f'{label}-{width}.png'))
  mount('member')
  check('signed-in member still public view',page.locator('[data-admin-only]').count()==0)
  if not MEMORY:
   for role in ('guest','member'):
    state['role']=role
    for path in POLICY['protectedPaths']:
     check(role+' direct admin request denied '+path,context.request.get(url+path.lstrip('/')).status in (401,403))
  mount('admin')
  check('admin sees source attempts and integration diagnostics',all(word in page.locator('#main').inner_text() for word in ('마지막 시도','운영 연동 시 구분할 항목','출처 수집 진단')))
  page.locator('#main').screenshot(path=str(OUT/'admin-status-1440.png'))
  go('song/cat-save-world?demo=1')
  check('admin keeps connection state',page.locator('.ai-provider-panel').count()==1)
  check('admin can inspect example graph',page.locator('.ai-demo').count()==1 and page.locator('.ai-flow-line').count()>0)
  go('song/cat-save-world')
  check('admin keeps batch diagnostics','게시본 반영' in page.locator('#main').inner_text())
  # Public catalog and ordinary features remain available after failures/expiry.
  state['fail']=True
  if MEMORY:page.evaluate('window.__fixtureFail=true')
  page.evaluate("window.dispatchEvent(new Event('focus'))")
  page.wait_for_function('IsegyeOps.allowed()===false')
  check('status request failure removes privileged markup',page.locator('[data-admin-only]').count()==0)
  state['fail']=False
  if MEMORY:page.evaluate('window.__fixtureFail=false')
  page.evaluate("window.dispatchEvent(new Event('focus'))");page.wait_for_function('IsegyeOps.allowed()===true')
  state['role']='member'
  if MEMORY:page.evaluate("window.__fixtureRole='member'")
  page.evaluate("window.dispatchEvent(new Event('focus'))");page.wait_for_function('IsegyeOps.allowed()===false')
  check('role loss removes admin diagnostics',page.locator('[data-admin-only]').count()==0)
  go('song/cat-save-world?demo=1');check('expired administrator cannot keep example graph',page.locator('.ai-demo').count()==0)
  go('series/music-beginning');check('six official introductory videos preserved',page.locator('[data-music-beginning-video]').count()==6)
  go('song/rebels');check('external performances preserved',page.locator('a[href="#/video/sy40EGkSfRA"]').count()>0)
  check('no JavaScript exceptions',not errors)
  browser.close()
finally:
 server.shutdown()
 (OUT/'report.json').write_text(json.dumps({'mode':'local-in-memory' if MEMORY else 'HTTP-browser','passed':sum(x['passed'] for x in checks),'total':len(checks),'errors':errors,'checks':checks},ensure_ascii=False,indent=2)+'\n')
 (OUT/'page-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':sum(x['passed'] for x in checks),'total':len(checks),'mode':'local-in-memory' if MEMORY else 'HTTP-browser'}))
