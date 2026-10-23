"""Thumbnail and history UI tests. Synthetic broadcasts/media are explicitly labelled.
The optional real-source pass uses a separate context with no interception.
"""
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
URL=os.environ.get('VISUAL_URL','http://127.0.0.1:4196/').rstrip('/')+'/'
OUT=ROOT/os.environ.get('VISUAL_OUT','test-results/visual');OUT.mkdir(parents=True,exist_ok=True)
CHANNELS=[('inehine','ine','아이네'),('jingburger1','jingburger','징버거'),('lilpa0309','lilpa','릴파'),('cotton1217','jururu','주르르'),('gosegu2','gosegu','고세구'),('viichan6','viichan','비챤')]
checks=[];errors=[];server=None;actual=None
SVG=b'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" fill="#a9345e"/><text x="320" y="175" text-anchor="middle" fill="white" font-size="28">THUMBNAIL TEST FIXTURE</text><text x="320" y="220" text-anchor="middle" fill="white" font-size="20">Synthetic media - not an actual broadcast</text></svg>'
def check(name,ok,detail=None):
 checks.append({'name':name,'passed':bool(ok),**({'detail':detail} if detail is not None else {})})
 if not ok:raise AssertionError(name+': '+str(detail))
def readable(page):
 return page.evaluate('''()=>{const w=document.createTreeWalker(document.querySelector('#main'),NodeFilter.SHOW_TEXT);let n;const bad=[];while(n=w.nextNode()){const e=n.parentElement;if(!n.textContent.trim()||e.closest('script,style,svg,[aria-hidden=true],.sr-only')||!e.checkVisibility({checkVisibilityCSS:true,checkOpacity:true}))continue;if(parseFloat(getComputedStyle(e).fontSize)<14)bad.push(n.textContent.trim());}return bad;}''')
def wait(page):page.wait_for_function('document.querySelectorAll(".live-card[data-state=loading],.live-mini[data-state=loading]").length===0')
try:
 if 'VISUAL_URL' not in os.environ:
  server=subprocess.Popen(['python','-m','http.server','4196','--bind','127.0.0.1','--directory','live-dist'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(30):
   try:urlopen(URL,timeout=1).close();break
   except Exception:time.sleep(.1)
 with sync_playwright() as p:
  options={'headless':True}
  if os.environ.get('CHROMIUM_PATH'):options['executable_path']=os.environ['CHROMIUM_PATH']
  b=p.chromium.launch(**options)
  c=b.new_context(viewport={'width':1440,'height':1000},locale='ko-KR',timezone_id='Asia/Seoul',reduced_motion='reduce')
  page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  page.clock.install(time=datetime.now(timezone.utc))
  scenario={'value':'mixed'}
  def station(route):
   cid=route.request.url.split('/api/')[1].split('/')[0];_,mid,name=next(m for m in CHANNELS if m[0]==cid)
   stamp=datetime.fromtimestamp(page.evaluate('Date.now()')/1000,timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')
   if mid=='lilpa' and scenario['value']=='mixed':route.fulfill(status=503,body='test unavailable',headers={'Access-Control-Allow-Origin':'*'});return
   data={'station':{'user_id':cid,'user_nick':name,'broad_start':stamp},'broad':None,'current_timestamp':stamp}
   if scenario['value']=='mixed' and mid in ('ine','gosegu'):
    data['broad']={'broad_no':123456789 if mid=='ine' else 123456790,'broad_title':'[검증용 응답] 썸네일·상태 처리 테스트','current_sum_viewer':100,'broad_grade':0,'is_password':'N'}
   route.fulfill(json=data,headers={'Access-Control-Allow-Origin':'*'})
  page.route('https://chapi.sooplive.co.kr/**',station)
  page.route('https://liveimg.sooplive.com/**',lambda r:r.fulfill(status=200,content_type='image/svg+xml',body=SVG))
  page.route('https://i.ytimg.com/**',lambda r:r.fulfill(status=200,content_type='image/svg+xml',body=SVG))
  page.goto(URL+'#/live',wait_until='networkidle');wait(page)
  meta=c.request.get(URL+'build-info.json').json()
  check('artifact commit matches',meta['commit']==os.environ.get('GITHUB_SHA',meta['commit']))
  check('visual history build marker',meta['visualHistory']['historyItems']==55)
  check('seven menus and no video menu',page.locator('[data-nav]').count()==7 and page.locator('[data-nav=videos]').count()==0)
  check('two current broadcast thumbnails',page.locator('.live-card .live-broadcast-thumb').count()==2)
  check('offline and unknown retain portraits',page.locator('.live-card:not([data-state=live]) .live-card-art>img').count()==4 and page.locator('.live-card:not([data-state=live]) .live-broadcast-thumb').count()==0)
  check('official thumbnail host and ID mapping',page.locator('[data-member=ine] .live-broadcast-thumb').get_attribute('src').startswith('https://liveimg.sooplive.com/m/123456789?v='))
  check('broadcast image is linked to official live',page.locator('[data-member=ine] .live-thumb-media').get_attribute('href')=='https://play.sooplive.com/inehine')
  check('fixture images render',page.locator('.live-broadcast-thumb').evaluate_all('(xs)=>xs.every(x=>x.complete&&x.naturalWidth>0)'))
  page.screenshot(path=str(OUT/'mock-live-desktop.png'),full_page=True)
  page.locator('[data-member=ine] .live-broadcast-thumb').evaluate("e=>e.dispatchEvent(new Event('error'))")
  check('failed live image falls back without changing status',page.locator('[data-member=ine] .live-thumb-media[data-media-error=true]').count()==1 and page.locator('[data-member=ine]').get_attribute('data-state')=='live')
  page.goto(URL+'#/home',wait_until='networkidle');wait(page)
  check('home has same two live thumbnails',page.locator('.live-mini .live-broadcast-thumb').count()==2)
  check('home offline original images preserved',page.locator('.live-mini[data-state=offline]>img').count()==3)
  check('retired home video tile removed',page.locator('a[href="#/videos"]').count()==0 and page.locator('.explore-card').count()==3)
  page.screenshot(path=str(OUT/'mock-home-desktop.png'),full_page=True)
  scenario['value']='offline';page.clock.run_for(31000);page.wait_for_timeout(100);wait(page)
  check('broadcast ending removes thumbnails',page.locator('.live-broadcast-thumb').count()==0 and page.locator('.live-mini[data-state=offline]').count()==6)
  page.goto(URL+'#/videos',wait_until='networkidle');check('legacy videos route goes to LIVE',page.locator('.live-card').count()==6)
  for _,mid,_ in CHANNELS:
   page.goto(URL+'#/record/'+mid,wait_until='networkidle')
   check(mid+' has only original wiki citation',page.locator('.catalog-profile a[href*="namu.wiki"]').count()==1 and page.locator('.catalog-profile a[href*="namu.moe"]').count()==0 and '확인본(미러)' not in page.locator('#main').inner_text())
  page.goto(URL+'#/music?type=cover',wait_until='networkidle')
  check('covers show 24 video thumbnails',page.locator('.music-video-art>img').count()==24)
  check('song image URL matches safe video id',page.locator('.music-video-art>img').evaluate_all('(xs)=>xs.every(x=>/^https:\/\/i.ytimg.com\/vi\/[A-Za-z0-9_-]{11}\/hqdefault.jpg$/.test(x.src))'))
  check('fallback text stays below replacement image',page.locator('.music-video-art').first.evaluate('(x)=>Number(getComputedStyle(x.querySelector(":scope>img")).zIndex)>Number(getComputedStyle(x.querySelector(".music-video-fallback")).zIndex)'))
  page.locator('.music-video-art>img').first.evaluate("e=>e.dispatchEvent(new Event('error'))")
  check('failed song image restores original artwork',page.locator('.music-video-art[data-media-error=true] .catalog-song-art').count()==1)
  page.goto(URL+'#/song/cover-TYB9ScXvq34',wait_until='networkidle')
  check('song detail shows video thumbnail label',page.locator('.catalog-song-detail-visual .music-video-art').count()==1 and 'YouTube 영상 썸네일' in page.locator('.catalog-song-detail-visual').inner_text())
  page.locator('.music-video-art>img').first.evaluate("e=>{Object.defineProperty(e,'naturalWidth',{get:()=>120});Object.defineProperty(e,'naturalHeight',{get:()=>90});e.dispatchEvent(new Event('load'));}")
  check('generic tiny YouTube response becomes fallback',page.locator('.music-video-art[data-media-error=true]>img[hidden]').count()==1)
  page.goto(URL+'#/song/cover-q8iiUYJsOUM',wait_until='networkidle')
  check('no-video item retains abstract art',page.locator('.catalog-song-detail-visual .music-video-art').count()==0 and page.locator('.catalog-song-detail-visual .catalog-song-art').count()==1)
  page.goto(URL+'#/history',wait_until='networkidle')
  check('55 dated history events and six year groups',page.locator('[data-history-event]').count()==55 and page.locator('.history-year').count()==6)
  dates=page.locator('[data-history-date]').evaluate_all('(xs)=>xs.map(x=>x.dataset.historyDate)')
  check('timeline starts with audition recruitment in chronological order',dates[0]=='2021-06-22' and dates==sorted(dates))
  check('all timeline items have accessible sources',page.locator('.history-events .history-sources').count()==55)
  check('timeline omits mirror links',page.locator('.history-events a[href*="namu.moe"]').count()==0)
  page.screenshot(path=str(OUT/'history-desktop.png'),full_page=True)
  page.locator('.history-year-nav a').filter(has_text='2021').click();expect(page.locator('[data-history-event]')).to_have_count(6);check('2021 filter has six events',page.locator('[data-history-event]').count()==6)
  page.locator('[data-history-filter=type]').select_option('audition');expect(page.locator('.history-results strong')).to_have_text('5개 기록')
  check('year and category filters compose',page.locator('[data-history-event]').count()==5)
  page.goto(URL+'#/history?member=lilpa&type=performance&q=LILPACON',wait_until='networkidle');check('member and title search compose',page.locator('[data-history-event]').count()==1 and '2024.07.12' in page.locator('.history-date').inner_text(),page.locator('.history-date').inner_text())
  page.goto(URL+'#/history?order=new',wait_until='networkidle');check('newest first sort',page.locator('[data-history-date]').first.get_attribute('data-history-date')=='2026-09-28')
  page.locator('#history-query').fill('<img src=x onerror=alert(1)>');page.locator('#history-search button').click();page.locator('.catalog-empty').wait_for();check('search is inert text and clear empty state',page.locator('.history-results img').count()==0)
  for theme in ('light','dark'):
   page.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':950})
    for route in ('live','music?type=cover','history?year=2021','record/ine'):
     page.goto(URL+'#/'+route,wait_until='networkidle')
     check(f'{theme}/{width}/{route} no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
     bad=readable(page);check(f'{theme}/{width}/{route} readable labels',not bad,bad)
  page.set_viewport_size({'width':390,'height':844});page.evaluate("document.documentElement.dataset.theme='light'")
  for route,name in [('history?year=2021','history-mobile'),('music?type=cover','mock-music-mobile'),('record/ine','member-mobile')]:
   page.goto(URL+'#/'+route,wait_until='networkidle');page.screenshot(path=str(OUT/(name+'.png')),full_page=True)
  page.set_viewport_size({'width':1280,'height':1000});page.evaluate("document.documentElement.style.fontSize='200%'")
  for route in ('history?year=2021','music?type=cover','live'):
   page.goto(URL+'#/'+route,wait_until='networkidle');check('200% '+route+' no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
  check('no uncaught errors',not errors,errors)
  if os.environ.get('VISUAL_REAL_CHECK')=='true':
   real=b.new_context(viewport={'width':1440,'height':1000},locale='ko-KR',timezone_id='Asia/Seoul',reduced_motion='reduce');rp=real.new_page();real_errors=[];rp.on('pageerror',lambda e:real_errors.append(str(e)))
   rp.goto(URL+'#/live',wait_until='networkidle');wait(rp)
   rp.screenshot(path=str(OUT/'actual-live-desktop.png'),full_page=True)
   thumbs=rp.locator('.live-card .live-broadcast-thumb').evaluate_all('(xs)=>xs.map(x=>({src:x.src,loaded:x.complete&&x.naturalWidth>0,hidden:x.hidden,width:x.naturalWidth,height:x.naturalHeight}))')
   actual={'checkedAt':datetime.now(timezone.utc).isoformat(),'url':URL,'intercepted':False,'live':rp.locator('.live-card[data-state=live]').count(),'offline':rp.locator('.live-card[data-state=offline]').count(),'unknown':rp.locator('.live-card[data-state=unknown]').count(),'broadcastThumbnails':thumbs}
   rp.goto(URL+'#/music?type=cover',wait_until='networkidle');rp.screenshot(path=str(OUT/'actual-music-desktop.png'),full_page=True)
   actual['youtubeThumbnails']=rp.locator('.music-video-art>img').evaluate_all('(xs)=>xs.map(x=>({src:x.src,loaded:x.complete&&x.naturalWidth>0,hidden:x.hidden,width:x.naturalWidth,height:x.naturalHeight}))')
   rp.goto(URL+'#/history?year=2021',wait_until='networkidle');rp.screenshot(path=str(OUT/'actual-history-desktop.png'),full_page=True)
   rp.set_viewport_size({'width':390,'height':844});rp.goto(URL,wait_until='networkidle');rp.screenshot(path=str(OUT/'actual-home-mobile.png'),full_page=True)
   actual['browserErrors']=real_errors;check('real source page has no uncaught error',not real_errors,real_errors)
   check('real source YouTube visible thumbnails decode',any(x['loaded'] and not x['hidden'] for x in actual['youtubeThumbnails']))
   real.close()
  b.close()
finally:
 (OUT/'result.json').write_text(json.dumps({'url':URL,'commit':os.environ.get('GITHUB_SHA'),'scope':'synthetic-broadcast-and-image-ui-tests','checks':checks,'passed':sum(c['passed'] for c in checks),'total':len(checks),'browserErrors':errors,'actual':actual},ensure_ascii=False,indent=2))
 if server:server.terminate();server.wait(timeout=5)
print('Visual/history checks passed:',len(checks))
