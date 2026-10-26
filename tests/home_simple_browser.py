"""Home proposal regression. Fixtures test transitions; optional separate real pass has no interception."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json,os,subprocess,time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
URL=os.getenv('HOME_URL','http://127.0.0.1:4198/').rstrip('/')+'/'
OUT=ROOT/os.getenv('HOME_OUT','test-results/home-simple');OUT.mkdir(parents=True,exist_ok=True)
CHANNELS=['inehine','jingburger1','lilpa0309','cotton1217','gosegu2','viichan6']
NAMES=['아이네','징버거','릴파','주르르','고세구','비챤']
MODE=os.getenv('HOME_EXPECT_MODE','preview');APPROVED=os.getenv('HOME_EXPECT_APPROVED')=='true'
checks=[];errors=[];server=None;actual=None
SVG=b'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" fill="#dce9f4"/><text x="320" y="180" text-anchor="middle" font-size="24">LAYOUT TEST IMAGE</text></svg>'
def check(name,ok,detail=None):
 checks.append({'name':name,'passed':bool(ok),**({'detail':detail} if detail is not None else {})})
 if not ok:raise AssertionError(name+': '+str(detail))
try:
 if 'HOME_URL' not in os.environ:
  server=subprocess.Popen(['python','-m','http.server','4198','--bind','127.0.0.1','--directory','home-dist'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(30):
   try:urlopen(URL,timeout=1).close();break
   except Exception:time.sleep(.1)
 with sync_playwright() as p:
  b=p.chromium.launch(**({'executable_path':os.environ['CHROMIUM_PATH']} if os.getenv('CHROMIUM_PATH') else {}))
  c=b.new_context(viewport={'width':1440,'height':1000},locale='ko-KR',timezone_id='Asia/Seoul',reduced_motion='reduce')
  page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  scenario={'value':'mixed'};calls=[]
  def station(route):
   cid=route.request.url.split('/api/')[1].split('/')[0];calls.append(cid);i=CHANNELS.index(cid)
   stamp=datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')
   if scenario['value']=='error':route.fulfill(status=503,body='test-only',headers={'Access-Control-Allow-Origin':'*'});return
   broad={'broad_no':123456789+i,'broad_title':'[테스트 전용] 방송 상태','current_sum_viewer':100,'broad_grade':0,'is_password':'N'} if scenario['value']=='mixed' and i in (0,4) else None
   route.fulfill(json={'station':{'user_id':cid,'user_nick':NAMES[i],'broad_start':stamp},'broad':broad,'current_timestamp':stamp},headers={'Access-Control-Allow-Origin':'*'})
  page.route('https://chapi.sooplive.co.kr/**',station)
  for url in ('https://liveimg.sooplive.com/**','https://i.ytimg.com/**'):page.route(url,lambda r:r.fulfill(status=200,content_type='image/svg+xml',body=SVG))
  page.goto(URL,wait_until='networkidle');page.wait_for_function('document.querySelectorAll(".live-mini[data-state=loading]").length===0')
  meta=c.request.get(URL+'build-info.json').json()
  check('home review metadata',meta['review']=='home-simple' and meta['operatorApprovedDeployment']==APPROVED)
  check('exact commit',meta['commit']==os.getenv('GITHUB_SHA',meta['commit']))
  check('expected indexing mode',page.locator('meta[name=robots]').get_attribute('content')==('index,follow' if MODE=='production' else 'noindex,nofollow') and page.locator('link[rel=canonical]').count()==(1 if MODE=='production' else 0))
  check('seven menus unchanged',page.locator('[data-nav]').count()==7)
  check('LIVE is first visible section',page.locator('#main>section').first.get_attribute('class')=='live-home')
  check('six LIVE statuses retained',page.locator('.live-mini').count()==6)
  check('live thumbnails and offline portraits unchanged',page.locator('.live-mini[data-state=live] .live-broadcast-thumb').count()==2 and page.locator('.live-mini[data-state=offline]>img').count()==4)
  check('single clear heading',page.locator('#main h1').count()==1 and page.locator('#main h1').inner_text()=='오늘의 이세돌')
  check('home has no submission link',page.locator('#main a[href*="report"]').count()==0)
  for phrase in ('오늘의 플레이리스트','취향 따라','다시 꺼내보는','기록 함께 채우기','발견한 기록과 공개된 출처'):
   check('removed '+phrase,phrase not in page.locator('#main').inner_text())
  check('six member shortcuts',page.locator('[data-home-member-link]').count()==6)
  check('group image retains whole aspect',page.locator('.hm-group').evaluate('(x)=>x.naturalWidth===800&&getComputedStyle(x).objectFit==="contain"'))
  check('three real-data video links',page.locator('[data-home-video]').count()==3 and page.locator('[data-home-video]').evaluate_all(r'(xs)=>xs.every(x=>/^https:\/\/www.youtube.com\/watch\?v=[A-Za-z0-9_-]{11}$/.test(x.href))'))
  dates=page.locator('[data-published]').evaluate_all('(xs)=>xs.map(x=>Date.parse(x.dataset.published))')
  check('video publication order',dates==sorted(dates,reverse=True))
  check('snapshot timing disclosed','목록 확인' in page.locator('#hm-videos').inner_text() and '반영 전' in page.locator('#hm-videos').inner_text())
  page.evaluate('window.keptLiveNode=document.querySelector(".live-home")')
  page.locator('[data-home-member=gosegu]').click()
  check('member filter works',page.locator('.hm-video-meta b').evaluate_all('(xs)=>xs.length===3&&xs.every(x=>x.textContent==="고세구")'))
  check('filter leaves LIVE DOM intact',page.evaluate('window.keptLiveNode===document.querySelector(".live-home")'))
  check('selected filter and focus retained',page.locator('[data-home-member=gosegu]').get_attribute('aria-pressed')=='true' and page.locator('[data-home-member=gosegu]').evaluate('(x)=>x===document.activeElement'))
  page.locator('[data-home-member=all]').click();page.locator('[data-home-music=cover]').click()
  check('cover choice retains source badges',page.locator('.hm-song-grid [data-song]').count()==3 and page.locator('.hm-song-grid .catalog-song-labels').evaluate_all('(xs)=>xs.every(x=>x.textContent.includes("커버"))'))
  page.locator('[data-home-music=remake]').click();check('remake not padded with invented items',page.locator('.hm-song-grid [data-song]').count()==1)
  page.locator('[data-home-music=original]').click();check('one featured song per album',page.locator('.hm-song-grid [data-song=cat-save-world]').count()==1 and page.locator('.hm-song-grid [data-song=your-turn]').count()==0)
  check('all songs still available',page.locator('#hm-all-music').get_attribute('href')=='#/music' and '154' in page.locator('#hm-all-music').inner_text())
  check('schedule and history one compact row',page.locator('.hm-more a').count()==2)
  page.locator('[data-home-image]').first.evaluate('(x)=>x.dispatchEvent(new Event("error"))')
  check('image failure does not remove the video link',page.locator('.hm-video-image[data-image-error=true] img[hidden]').count()==1 and page.locator('[data-home-video]').count()==3)
  page.screenshot(path=str(OUT/'fixture-home-desktop.png'),full_page=True)
  page.goto(URL+'#/about',wait_until='networkidle');check('about no community content intake','함께 채우는 기록' not in page.locator('#main').inner_text() and page.locator('#main a[href="#/report"]').count()==0)
  page.goto(URL+'#/record/gosegu',wait_until='networkidle');check('member detail still works',page.locator('[data-profile-detail=gosegu]').count()==1 and page.locator('[data-channel]').count()==4)
  page.goto(URL+'#/music',wait_until='networkidle');check('full music catalog retained',page.locator('[data-song]').count()==24 and page.locator('.catalog-result-heading strong').inner_text()=='154')
  page.goto(URL+'#/history',wait_until='networkidle');check('all history retained',page.locator('[data-history-event]').count()==55)
  for theme in ('light','dark'):
   page.evaluate('(v)=>document.documentElement.dataset.theme=v',theme)
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':950});page.goto(URL+'#/home',wait_until='networkidle')
    check(f'{theme}/{width} no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    check(f'{theme}/{width} all member shortcuts',page.locator('.hm-member').count()==6)
    bad=page.evaluate('''()=>{const w=document.createTreeWalker(document.querySelector('.hm-page'),NodeFilter.SHOW_TEXT);let n;const bad=[];while(n=w.nextNode()){const el=n.parentElement;if(!n.textContent.trim()||el.closest('[aria-hidden=true],.sr-only,svg')||!el.checkVisibility({checkVisibilityCSS:true,checkOpacity:true}))continue;if(parseFloat(getComputedStyle(el).fontSize)<14)bad.push(n.textContent.trim());}return bad;}''')
    check(f'{theme}/{width} text at least 14px',not bad,bad)
  page.set_viewport_size({'width':1280,'height':1000});page.evaluate('document.documentElement.style.fontSize="200%"');check('200% text no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
  page.evaluate('document.documentElement.style.fontSize=""');page.evaluate('document.documentElement.dataset.theme="light"')
  scenario['value']='offline';page.reload(wait_until='networkidle');page.wait_for_function('document.querySelectorAll(".live-mini[data-state=offline]").length===6')
  check('offline retains all original portraits',page.locator('.live-mini[data-state=offline]>img').count()==6 and page.locator('.live-broadcast-thumb').count()==0)
  scenario['value']='error';page.reload(wait_until='networkidle');page.wait_for_function('document.querySelectorAll(".live-mini[data-state=unknown]").length===6')
  check('errors never called offline',page.locator('.live-mini[data-state=offline]').count()==0)
  check('no browser exceptions',not errors,errors)
  if os.getenv('HOME_REAL_CHECK')=='true':
   real=b.new_context(viewport={'width':1440,'height':1050},locale='ko-KR',timezone_id='Asia/Seoul',reduced_motion='reduce');rp=real.new_page();real_errors=[];rp.on('pageerror',lambda x:real_errors.append(str(x)))
   rp.goto(URL,wait_until='networkidle');rp.wait_for_timeout(1100)
   rp.screenshot(path=str(OUT/'actual-home-desktop.png'),full_page=True)
   rp.screenshot(path=str(OUT/'actual-home-top.png'),full_page=False)
   actual={'checkedAt':datetime.now(timezone.utc).isoformat(),'intercepted':False,'live':rp.locator('.live-mini[data-state=live]').count(),'offline':rp.locator('.live-mini[data-state=offline]').count(),'unknown':rp.locator('.live-mini[data-state=unknown]').count(),'videoImages':rp.locator('[data-home-image]').evaluate_all('(xs)=>xs.map(x=>({src:x.src,loaded:x.complete&&x.naturalWidth>0}))')}
   rp.set_viewport_size({'width':390,'height':844});rp.screenshot(path=str(OUT/'actual-home-mobile.png'),full_page=True)
   rp.evaluate('document.documentElement.dataset.theme="dark"');rp.screenshot(path=str(OUT/'actual-home-dark-mobile.png'),full_page=True)
   actual['browserErrors']=real_errors;check('real page has no exceptions',not real_errors)
   real.close()
  b.close()
finally:
 (OUT/'result.json').write_text(json.dumps({'url':URL,'commit':os.getenv('GITHUB_SHA'),'scope':'synthetic state/image tests plus separately labelled actual pass','passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'browserErrors':errors,'actual':actual},ensure_ascii=False,indent=2))
 if server:server.terminate();server.wait(timeout=5)
print('Home checks passed:',len(checks))
