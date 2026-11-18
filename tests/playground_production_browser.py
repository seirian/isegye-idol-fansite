"""Real HTTP tests of the integrated operating app, not the standalone preview."""
from pathlib import Path
import http.server,socketserver,threading,json,os,sys,subprocess
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
# Exercise the real canonical on-disk representation, then the served wire bytes.
wire=bank.published_bytes(json.loads(bank.encoded(feed)))
expected_daily=json.loads(subprocess.check_output(['node','--input-type=module','-e',"import fs from 'node:fs';import {chooseQuestions,kstDate} from './playground/core.js';const d=JSON.parse(fs.readFileSync('playground/catalog.json'));console.log(JSON.stringify(chooseQuestions(d,{mode:'daily',count:5,seed:d.version+':'+kstDate()})));"],cwd=ROOT,text=True))
COURIER_PATH='/games/starlight-courier/'
COURIER_KEY='isegye:playground:courier:v2'
PRESERVED_KEYS=('isegye:playground:v1','isegye:playground:review:v1','isegye:bookmarks:v1','isegye:review:courier:v2')
def stored(page):
 return page.evaluate('(keys)=>Object.fromEntries(keys.map(k=>[k,localStorage.getItem(k)]))',PRESERVED_KEYS)
def ready_courier(page):
 page.wait_for_function('()=>window.CourierApp?.ready===true',timeout=20000)
 expect(page.locator('#start-button')).to_be_enabled()
def courier_start(page):
 page.locator('#start-button').click()
 page.wait_for_function('()=>CourierApp.state?.elapsed>0',timeout=7000)
def courier_position(page):
 return page.evaluate('()=>({x:CourierApp.state.x,y:CourierApp.state.y,elapsed:CourierApp.state.elapsed})')
def courier_touch(page):
 page.locator('#joystick').scroll_into_view_if_needed()
 box=page.locator('#joystick').bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']/2
 cdp=page.context.new_cdp_session(page)
 try:
  cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
  cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+box['width']*.32,'y':y}]})
  page.wait_for_timeout(300)
  cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
 finally:cdp.detach()
def courier_integration(browser,page,apis,errors):
 """Only operating-site integration; the game has its own full mechanics suite."""
 before=stored(page);feedback=page.locator('.feedback').text_content();external=[];watch=[False]
 def request(req):
  if watch[0] and req.url.startswith(('http://','https://')) and not req.url.startswith(url+'/'):external.append(req.url)
 page.on('request',request)
 try:
  page.goto(url+'/#/playground',wait_until='networkidle')
  launch=page.locator('a[data-courier-launch]');expect(launch).to_be_visible()
  check('courier card opens same-tab operating game',launch.get_attribute('href')==COURIER_PATH and launch.get_attribute('target') in (None,'','_self'))
  watch[0]=True;launch.click();page.wait_for_url(url+COURIER_PATH);ready_courier(page)
  check('courier has one document without iframe',len(page.context.pages)==1 and page.locator('iframe').count()==0)
  check('courier operating screen has no review wording','검토' not in page.locator('body').inner_text() and '검토' not in page.title())
  expect(page.locator('a.wordmark')).to_have_text('← 놀이터')
  check('courier has an operating playground return link',page.locator('a.wordmark').get_attribute('href')=='/#/playground')
  check('courier generated scene is loaded',page.locator('#hero-background').evaluate("c=>{const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;return d.some((v,i)=>i%4===3&&v>0)}"))
  check('courier preview records are not imported',page.locator('#member-name').inner_text()=='아이네' and '1,234' not in page.locator('#best-label').inner_text())
  expect(page.locator('.member-card')).to_have_count(6)
  for name in ('아이네','징버거','릴파','주르르','비챤','고세구'):
   page.get_by_role('button',name=name+' 선택',exact=True).click()
   expect(page.locator('#member-name')).to_have_text(name)
   check('operating courier selection '+name,page.locator('.member-card[aria-pressed=true]').count()==1 and name in page.locator('#hero-character').get_attribute('aria-label'))
  check('courier selected member uses isolated operating storage',page.evaluate('(key)=>JSON.parse(localStorage.getItem(key)).selected',COURIER_KEY)=='gosegu' and stored(page)==before)
  page.reload(wait_until='networkidle');ready_courier(page)
  expect(page.locator('#member-name')).to_have_text('고세구')
  check('courier direct reload restores chosen member',page.evaluate('CourierApp.screen==="lobby"&&CourierApp.state===null'))
  page.screenshot(path=str(OUT/'courier-lobby-1440.png'),full_page=True)
  courier_start(page);initial=courier_position(page)
  page.keyboard.down('ArrowRight');page.wait_for_timeout(300);page.keyboard.up('ArrowRight')
  check('operating courier keyboard movement',courier_position(page)['x']>initial['x']+30)
  page.keyboard.press('Space')
  check('operating courier keyboard dash',page.evaluate('CourierApp.state.stats.dashes===1&&CourierApp.state.dashCooldown>0'))
  page.screenshot(path=str(OUT/'courier-playing-1440.png'),full_page=True)
  page.locator('#pause-button').click();expect(page.locator('#resume-button')).to_be_visible()
  paused=courier_position(page);page.wait_for_timeout(250)
  check('operating courier pause freezes motion and time',courier_position(page)==paused)
  page.locator('#resume-button').click();watch[0]=False
  page.locator('a.wordmark').click();page.wait_for_url(url+'/#/playground')
  expect(page.locator('.playground-component h1')).to_have_text('놀이터')
  check('courier return restores operating shell',page.locator('header').count()==1 and page.locator('.desktop-nav a').count()==8 and page.evaluate('typeof CourierApp==="undefined"'))
  check('courier round trip preserves quiz bookmarks and preview records',stored(page)==before)
  page.locator('a[href="#/playground/play"]').first.click();expect(page.locator('.feedback')).to_have_text(feedback)
  expect(page.locator('[data-action=next]')).to_be_visible()
  check('courier return resumes the existing answered quiz',stored(page)==before)
  # Leaving this independent document ends the current round. Reentry starts at
  # member selection, preserving only the game's own selected member/records.
  watch[0]=True;page.goto(url+COURIER_PATH);ready_courier(page);courier_start(page)
  watch[0]=False;page.goto(url+'/#/music');expect(page.get_by_role('heading',name='한 곡에서 시작되는 이야기',exact=True)).to_be_visible()
  watch[0]=True;page.goto(url+COURIER_PATH);ready_courier(page)
  check('leaving for another menu ends the courier round',page.evaluate('CourierApp.screen==="lobby"&&CourierApp.state===null') and page.locator('#member-name').inner_text()=='고세구')
  watch[0]=False;page.goto(url+'/#/playground/play');expect(page.locator('.feedback')).to_have_text(feedback)
  check('quiz survives repeated independent game visits',stored(page)==before)
 finally:page.remove_listener('request',request)
 for width,height in ((320,720),(390,844),(768,1024)):
  ctx=browser.new_context(viewport={'width':width,'height':height},is_mobile=True,has_touch=True,device_scale_factor=1)
  mobile=ctx.new_page();mobile.on('pageerror',lambda e:errors.append(str(e)))
  mobile.route('**/api/**',apis);mobile.route('**/auth/status',apis)
  def remote(route):
   if route.request.frame.url.startswith(url+COURIER_PATH):external.append(route.request.url)
   route.abort()
  mobile.route('https://**',remote)
  try:
   mobile.goto(url+'/#/playground');expect(mobile.locator('a[data-courier-launch]')).to_be_visible()
   check('operating game card fits '+str(width),mobile.evaluate('document.documentElement.scrollWidth')<=width+1)
   mobile.locator('a[data-courier-launch]').click();ready_courier(mobile)
   check('operating courier lobby fits '+str(width),mobile.evaluate('document.documentElement.scrollWidth')<=width+1)
   mobile.screenshot(path=str(OUT/f'courier-lobby-{width}.png'),full_page=True)
   courier_start(mobile);check('operating courier playfield fits '+str(width),mobile.evaluate('document.documentElement.scrollWidth')<=width+1)
   expect(mobile.locator('#joystick')).to_be_visible()
   if width in (390,768):
    initial=courier_position(mobile);courier_touch(mobile)
    check('operating courier actual touch movement '+str(width),courier_position(mobile)['x']>initial['x']+30)
    released=courier_position(mobile);mobile.wait_for_timeout(150)
    check('operating courier touch release stops '+str(width),abs(courier_position(mobile)['x']-released['x'])<1)
   mobile.screenshot(path=str(OUT/f'courier-playing-{width}.png'),full_page=True)
   mobile.locator('a.wordmark').click();expect(mobile.locator('.playground-component h1')).to_have_text('놀이터')
   check('mobile courier returns to operating playground '+str(width),mobile.url==url+'/#/playground' and mobile.locator('header').count()==1)
  except Exception:
   mobile.screenshot(path=str(OUT/f'courier-failure-{width}.png'),full_page=True);raise
  finally:ctx.close()
 check('courier game requires no external network',not external)
try:
 with sync_playwright() as p:
  opt={'headless':True}
  if os.getenv('CHROMIUM_PATH'):opt['executable_path']=os.environ['CHROMIUM_PATH']
  b=p.chromium.launch(**opt);ctx=b.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  def apis(route):
   if route.request.url.endswith('/api/playground'):route.fulfill(body=wire,content_type='application/json')
   elif route.request.url.endswith('/auth/status'):route.fulfill(json={'authenticated':False,'administrator':False,'maintenance':False,'allowed':True})
   else:route.fulfill(status=503,json={'error':'fixture_offline'})
  page.route('**/api/**',apis);page.route('**/auth/status',apis);page.route('https://**',lambda r:r.abort())
  try:
   page.goto(url+'/#/playground',wait_until='networkidle');expect(page.locator('.playground-component h1')).to_have_text('놀이터')
   # Seed once: resetting these on every document load would hide navigation loss.
   page.evaluate("localStorage.setItem('isegye:playground:review:v1','REVIEW_KEEP');localStorage.setItem('isegye:bookmarks:v1','BOOKMARK_KEEP');localStorage.setItem('isegye:review:courier:v2',JSON.stringify({version:2,best:1234,runs:2,selected:'lilpa',sound:false}))")
   expect(page.locator('.hero')).to_have_css('display','grid');check('production scoped stylesheet loaded',True)
   check('eight operating navigation entries',page.locator('.desktop-nav a').count()==8)
   check('mobile more menu contains playground',page.locator('#more-menu a[href="#/playground"]').count()==1)
   check('no second site header or iframe',page.locator('header').count()==1 and page.locator('iframe').count()==0)
   page.screenshot(path=str(OUT/'home-1440.png'),full_page=True)
   page.locator('[data-start=daily]').click();expect(page.locator('[data-answer]')).to_have_count(4);check('production deep link',page.url.endswith('#/playground/play'))
   page.locator('[data-action=hint]').click();expect(page.locator('[data-action=hint]')).to_be_disabled()
   current=page.evaluate("JSON.parse(localStorage.getItem('isegye:playground:v1'))")
   check('canonical bank preserves reviewed daily question selection',current['session']['ids']==expected_daily)
   hint=next(q['hint'] for q in feed['catalog']['questions'] if q['id']==current['session']['ids'][0]);expect(page.get_by_text(hint,exact=False).last).to_be_visible()
   page.locator('[data-answer]').first.click();expect(page.locator('[data-action=next]')).to_be_visible()
   check('answered round persisted before reload',page.evaluate("JSON.parse(localStorage.getItem('isegye:playground:v1')).session.answers.length===1"))
   page.reload(wait_until='networkidle');expect(page.locator('[data-action=next]')).to_be_visible();check('production resume survives reload',page.locator('.feedback').count()==1)
   courier_integration(b,page,apis,errors)
   for i in range(5):
    if i:page.locator('[data-action=skip]').click()
    page.locator('[data-action=next]').click()
   expect(page.locator('.score')).to_be_visible();check('five questions finish','/ 5' in page.locator('.score').inner_text())
   page.locator('[data-share-result]').click();expect(page.locator('#share')).to_be_visible();check('result shares operating route','https://isegye-idol.kr/#/playground' in page.locator('#share-text').input_value() and 'review-playground' not in page.locator('#share-text').input_value());page.locator('[data-action=close-share]').click()
   check('preview and bookmarks preserved',page.evaluate("localStorage.getItem('isegye:playground:review:v1')==='REVIEW_KEEP'&&localStorage.getItem('isegye:bookmarks:v1')==='BOOKMARK_KEEP'"))
   page.evaluate("location.hash='#/playground/records'");expect(page.locator('.record-row')).to_have_count(1)
   page.locator('.desktop-nav a[href="#/music"]').click()
   expect(page.get_by_role('heading',name='한 곡에서 시작되는 이야기',exact=True)).to_be_visible()
   expect(page.locator('.playground-component')).to_have_count(0)
   check('existing music still works',page.locator('#music-q').count()==1)
   page.locator('.desktop-nav a[href="#/playground"]').click();expect(page.locator('[data-start=daily]')).to_be_visible()
   page.locator('[data-start=order]').click();expect(page.locator('[data-answer]')).to_have_count(2);page.locator('[data-answer]').first.click();check('order feedback distinguishes audio dates','국내 음원 발매' in page.locator('.feedback').inner_text())
   page.goto(url+'/#/playground/quiz');expect(page.locator('[data-category]')).to_have_count(5)
   titles={'playground':'놀이터','playground/quiz':'좋아하는 주제부터','playground/play':'먼저 발매된 곡은 무엇일까요?','playground/records':'내 플레이 기록','playground/sources':'관리자 전용 페이지입니다'}
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':1000})
    for route,title in titles.items():
     page.goto(url+'/#/'+route);expect(page.locator('.playground-component h1')).to_have_text(title)
     check('no overflow '+str(width)+' '+route,page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
     if width in (390,1440) and route=='playground':page.screenshot(path=str(OUT/f'home-{width}.png'),full_page=True)
   check('no JavaScript runtime errors',not errors)
   ctx2=b.new_context();p2=ctx2.new_page();p2.route('**/api/**',lambda r:r.fulfill(status=503,json={'error':'offline'}));p2.route('https://**',lambda r:r.abort());p2.goto(url+'/#/playground');expect(p2.locator('[data-start=daily]')).to_be_visible();check('network failure uses seed','기본 문제' in p2.locator('#bank-note').inner_text());ctx2.close()
   ctx3=b.new_context();ctx3.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new DOMException('blocked','SecurityError')}})");p3=ctx3.new_page();p3.route('**/api/**',apis);p3.route('https://**',lambda r:r.abort());p3.goto(url+'/#/playground');p3.locator('[data-start=daily]').click();p3.locator('[data-answer]').first.click();p3.evaluate("location.hash='#/playground/records'");expect(p3.get_by_role('heading',name='내 플레이 기록')).to_be_visible();p3.evaluate("location.hash='#/playground'");p3.locator('a[href="#/playground/play"]').first.click();expect(p3.locator('.feedback')).to_be_visible();check('blocked storage preserves in-tab play across menu routes',True);ctx3.close()
  except Exception as e:
   debug={'error':str(e),'url':page.url,'errors':errors,'state':page.evaluate("localStorage.getItem('isegye:playground:v1')"),'body':page.locator('body').inner_text(),'shadow':page.locator('.playground-component').evaluate('(e)=>e.shadowRoot.innerHTML') if page.locator('.playground-component').count() else None}
   (OUT/'failure.json').write_text(json.dumps(debug,ensure_ascii=False,indent=2));page.screenshot(path=str(OUT/'failure.png'),full_page=True);raise
  finally:b.close()
finally:
 server.shutdown();(OUT/'browser.json').write_text(json.dumps({'mode':'real HTTP operating SPA','checks':checks},ensure_ascii=False,indent=2))
print(json.dumps({'passed':len(checks),'mode':'HTTP production'}))
