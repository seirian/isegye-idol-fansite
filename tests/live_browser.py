"""Deterministic UI cases use synthetic responses; real CORS checks are separate."""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
import hashlib,json,os,subprocess,time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
URL=os.environ.get('LIVE_URL','http://127.0.0.1:4190/').rstrip('/')+'/'
OUT=ROOT/os.environ.get('LIVE_TEST_OUT','test-results/live');OUT.mkdir(parents=True,exist_ok=True)
MEMBERS=[('inehine','ine','아이네'),('jingburger1','jingburger','징버거'),('lilpa0309','lilpa','릴파'),('cotton1217','jururu','주르르'),('gosegu2','gosegu','고세구'),('viichan6','viichan','비챤')]
checks=[];errors=[];server=None

def check(name,ok,detail=None):
 checks.append({'name':name,'passed':bool(ok),**({'detail':detail} if detail is not None else {})})
 if not ok:raise AssertionError(name+': '+str(detail))
def text_sizes(page):
 return page.evaluate('''() => {const w=document.createTreeWalker(document.querySelector('#main'),NodeFilter.SHOW_TEXT);const bad=[];let n;while(n=w.nextNode()){const el=n.parentElement;if(!n.textContent.trim()||el.closest('script,style,svg,[aria-hidden=true],.sr-only')||!el.checkVisibility({checkVisibilityCSS:true,checkOpacity:true}))continue;if(parseFloat(getComputedStyle(el).fontSize)<14)bad.push(n.textContent.trim());}return bad;}''')
def wait_state(page):
 page.wait_for_function('document.querySelectorAll(".live-mini[data-state=loading],.live-card[data-state=loading]").length===0')
try:
 if 'LIVE_URL' not in os.environ:
  server=subprocess.Popen(['python','-m','http.server','4190','--bind','127.0.0.1','--directory','live-dist'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(30):
   try:urlopen(URL,timeout=1).close();break
   except Exception:time.sleep(.1)
 with sync_playwright() as p:
  options={'headless':True}
  if os.environ.get('CHROMIUM_PATH'):options['executable_path']=os.environ['CHROMIUM_PATH']
  browser=p.chromium.launch(**options)
  c=browser.new_context(viewport={'width':1440,'height':1000},locale='ko-KR',timezone_id='Asia/Seoul',reduced_motion='reduce')
  page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  page.clock.install(time=datetime.now(timezone.utc))
  calls=[];scenario={'value':'mixed'}
  def handler(route):
   cid=route.request.url.split('/api/')[1].split('/')[0];member=next(m for m in MEMBERS if m[0]==cid);calls.append(cid)
   if scenario['value']=='error' or scenario['value']=='mixed' and member[1]=='lilpa':route.fulfill(status=503,body='Unavailable',headers={'Access-Control-Allow-Origin':'*'});return
   nowms=page.evaluate('Date.now()');stamp=datetime.fromtimestamp(nowms/1000,timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')
   on=scenario['value'] in ('mixed','all-live') and (member[1] in ('ine','gosegu') or scenario['value']=='all-live')
   payload={'station':{'user_id':cid,'user_nick':member[2],'broad_start':stamp},'broad':None,'current_timestamp':stamp}
   if on:payload['broad']={'broad_no':12345,'broad_title':'[테스트 데이터] <img src=x onerror="window.bad=1"> 노래와 이야기','current_sum_viewer':321 if member[1]=='ine' else 4321}
   route.fulfill(json=payload,headers={'Access-Control-Allow-Origin':'*'})
  page.route('https://chapi.sooplive.co.kr/**',handler)
  page.goto(URL,wait_until='networkidle');wait_state(page)
  check('LIVE menu replaces glossary',page.locator('[data-nav=live]').count()==1 and page.locator('[data-nav=dictionary]').count()==0)
  check('six primary navigation menus',page.locator('[data-nav]').count()==6)
  check('home has six live status summaries',page.locator('.live-mini').count()==6)
  check('live summary precedes hero',page.locator('.live-home').bounding_box()['y']<page.locator('.hero,.hm-intro').bounding_box()['y'])
  check('mixed home reports 2 live / 1 unknown / 3 offline',page.locator('.live-mini[data-state=live]').count()==2 and page.locator('.live-mini[data-state=unknown]').count()==1 and page.locator('.live-mini[data-state=offline]').count()==3)
  check('first refresh requests exactly six endpoints',len(calls)==6,len(calls))
  page.screenshot(path=str(OUT/'mock-home-desktop.png'),full_page=True)
  page.locator('[data-nav=live]').click();page.locator('.live-card').first.wait_for()
  check('state shared with home without refetch',len(calls)==6 and page.locator('.live-card').count()==6)
  check('live cards rank before unknown and offline',page.locator('.live-card').evaluate_all('(xs)=>xs.slice(0,3).map(x=>x.dataset.state)').__eq__(['live','live','unknown']))
  check('partial failure is explicitly explained','방송 종료를 뜻하지' in page.locator('[data-live-notice]').inner_text())
  check('untrusted title is inert text',page.locator('.live-card-title img').count()==0 and page.evaluate('window.bad===undefined'))
  check('live target is fixed official SOOP',page.locator('.live-card[data-member=ine] .button').get_attribute('href')=='https://play.sooplive.com/inehine')
  check('unknown target is official channel not pretend live',page.locator('.live-card[data-member=lilpa] .button').inner_text().startswith('공식 채널'))
  check('external links isolate opener',page.locator('.live-card a[target=_blank]').evaluate_all('(xs)=>xs.every(x=>x.rel.includes("noopener")&&x.rel.includes("noreferrer"))'))
  page.screenshot(path=str(OUT/'mock-live-desktop.png'),full_page=True)
  page.locator('[data-live-filter=live]').click();check('live-only filter yields 2',page.locator('.live-card').count()==2)
  page.locator('[data-live-search]').fill('고세구');check('member search',page.locator('.live-card').count()==1 and page.locator('.live-card').get_attribute('data-member')=='gosegu')
  page.locator('[data-live-search]').fill('없는 이름');check('empty search clear state',page.locator('.live-empty').count()==1)
  page.locator('[data-live-action=reset]').click();check('reset restores all six',page.locator('.live-card').count()==6)
  page.locator('[data-live-sort]').select_option('viewers');check('viewer order',page.locator('.live-card').first.get_attribute('data-member')=='gosegu')
  page.locator('[data-live-sort]').select_option('name');check('name order',page.locator('.live-card h2').first.inner_text()=='고세구')
  page.locator('[data-live-sort]').select_option('default')
  page.clock.run_for(31000);page.wait_for_timeout(100);wait_state(page)
  check('30-second auto refresh one six-request batch',len(calls)==12,len(calls))
  page.clock.run_for(11000);page.locator('[data-live-action=refresh]').click();page.wait_for_timeout(50);wait_state(page)
  check('manual refresh requests one batch',len(calls)==18,len(calls))
  check('manual cooldown prevents repeated requests',page.locator('[data-live-action=refresh]').is_disabled())
  page.locator('[data-live-auto]').uncheck();page.clock.run_for(35000);check('auto pause stops network polling',len(calls)==18)
  page.clock.run_for(60000);check('expired statuses all become unknown',page.locator('.live-card[data-state=unknown]').count()==6)
  check('expired state never says all offline','현재 방송 중' not in page.locator('[data-live-count-label]').inner_text())
  scenario['value']='offline';page.locator('[data-live-action=refresh]').click();page.wait_for_timeout(100);wait_state(page)
  check('confirmed offline all six',page.locator('.live-card[data-state=offline]').count()==6)
  page.locator('[data-live-filter=live]').click();check('all-offline empty message','방송 중인 멤버가 없어요' in page.locator('.live-empty h2').inner_text());page.locator('[data-live-action=reset]').click()
  scenario['value']='error';page.clock.run_for(11000);page.locator('[data-live-action=refresh]').click();page.wait_for_timeout(100)
  check('total API failure gives six unknowns',page.locator('.live-card[data-state=unknown]').count()==6)
  check('total failure does not claim offline',page.locator('.live-card[data-state=offline]').count()==0)
  page.screenshot(path=str(OUT/'mock-source-failure.png'),full_page=True)
  scenario['value']='all-live';page.clock.run_for(11000);page.locator('[data-live-action=refresh]').click();page.wait_for_timeout(100);wait_state(page)
  check('recovery displays six broadcasts',page.locator('.live-card[data-state=live]').count()==6)
  for theme in ('light','dark'):
   page.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
   for width in (320,390,768,1024,1440):
    page.set_viewport_size({'width':width,'height':950})
    for route in ('home','live','members','about'):
     page.goto(URL+'#/'+route,wait_until='networkidle');page.locator('#main h1').wait_for()
     check(f'{theme} {width}px {route} no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
     bad=text_sizes(page);check(f'{theme} {width}px {route} readable text',not bad,bad)
  page.set_viewport_size({'width':390,'height':844});page.goto(URL+'#/live',wait_until='networkidle');page.evaluate("document.documentElement.dataset.theme='light'");page.screenshot(path=str(OUT/'mock-live-mobile.png'),full_page=True)
  page.goto(URL+'#/home',wait_until='networkidle');page.screenshot(path=str(OUT/'mock-home-mobile.png'),full_page=True)
  page.set_viewport_size({'width':1280,'height':1000});page.evaluate("document.documentElement.style.fontSize='200%'")
  for route in ('home','live'):
   page.goto(URL+'#/'+route,wait_until='networkidle');check('200 percent text '+route+' no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
  page.evaluate("document.documentElement.style.fontSize=''")
  page.goto(URL+'#/dictionary',wait_until='networkidle');check('legacy glossary route serves LIVE',page.locator('.live-card').count()==6)
  page.goto(URL+'#/music',wait_until='networkidle');n=len(calls);page.clock.run_for(60000);check('non-live routes stop polling',len(calls)==n)
  page.goto(URL+'#/live',wait_until='networkidle');page.locator('[data-live-auto]').check();page.wait_for_timeout(100);wait_state(page)
  # Visibility suspension is explicit and does not reset the confirmed state timer.
  page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'))")
  n=len(calls);page.clock.run_for(60000);check('hidden tab does not poll',len(calls)==n)
  page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'))");page.wait_for_timeout(100);wait_state(page);check('visible tab resumes one batch',len(calls)==n+6)
  check('no browser exceptions in mock cases',not errors,errors)
  if 'LIVE_URL' not in os.environ:
   offline=c.new_page();offline.goto((ROOT/'live-dist/review.html').as_uri());offline.locator('#main h1').wait_for();check('offline does not invent live state',offline.locator('.live-mini[data-state=unknown]').count()==6);check('offline explains online requirement','온라인 사이트' in offline.locator('[data-live-update]').inner_text())
  (OUT/'mock-result.json').write_text(json.dumps({'scope':'synthetic-responses-not-current-broadcasts','checks':checks,'passed':sum(x['passed'] for x in checks),'total':len(checks),'browserErrors':errors},ensure_ascii=False,indent=2))
  c.close()
  # Live source test: absolutely no intercepted requests or synthetic data here.
  if os.environ.get('LIVE_REAL_CHECK')=='true':
   c=browser.new_context(viewport={'width':1440,'height':1000},locale='ko-KR',timezone_id='Asia/Seoul');page=c.new_page();real_errors=[];real_requests=[]
   page.on('pageerror',lambda e:real_errors.append(str(e)));page.on('request',lambda r:real_requests.append(r.url))
   page.goto(URL+'#/live',wait_until='networkidle',timeout=45000);page.locator('.live-card').first.wait_for();wait_state(page)
   cards=page.locator('.live-card').evaluate_all('(xs)=>xs.map(x=>({id:x.dataset.member,state:x.dataset.state,title:x.querySelector(".live-card-title").innerText}))')
   real={'scope':'actual-public-SOOP-no-fixtures','url':URL,'checkedAt':datetime.now(timezone.utc).isoformat(),'cards':cards,'browserErrors':real_errors,'sourceRequests':[u for u in real_requests if 'chapi.sooplive' in u]}
   real['allSixVerified']=len(cards)==6 and all(x['state'] in ('live','offline') for x in cards)
   meta=c.request.get(URL+'build-info.json').json();real['commit']=meta['commit'];real['commitMatches']=meta['commit']==os.environ.get('GITHUB_SHA','local')
   page.screenshot(path=str(OUT/'actual-live-desktop.png'),full_page=True)
   page.goto(URL+'#/home',wait_until='networkidle');page.screenshot(path=str(OUT/'actual-home-desktop.png'),full_page=True)
   page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(OUT/'actual-home-mobile.png'),full_page=True);page.goto(URL+'#/live',wait_until='networkidle');page.screenshot(path=str(OUT/'actual-live-mobile.png'),full_page=True)
   (OUT/'actual-result.json').write_text(json.dumps(real,ensure_ascii=False,indent=2))
   assert real['allSixVerified'], 'Real CORS failed or source unavailable: '+str(cards)
   assert real['commitMatches'],'Published version mismatch'
   assert not real_errors
   c.close()
  browser.close()
finally:
 (OUT/'result.json').write_text(json.dumps({'url':URL,'checks':checks,'passed':sum(x['passed'] for x in checks),'total':len(checks),'errors':errors},ensure_ascii=False,indent=2))
 if server:server.terminate();server.wait(timeout=5)
print('LIVE deterministic checks passed:',len(checks))
