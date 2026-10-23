"""Profile, upload snapshot and music filtering checks on local or published preview."""
from pathlib import Path
import json,os,subprocess,time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];URL=os.environ.get('CATALOG_URL','http://127.0.0.1:4194/').rstrip('/')+'/'
OUT=ROOT/os.environ.get('CATALOG_OUT','test-results/catalog');OUT.mkdir(parents=True,exist_ok=True)
checks=[];errors=[];server=None

def check(name,ok,detail=None):
 checks.append({'name':name,'passed':bool(ok),**({'detail':detail} if detail is not None else {})})
 if not ok:raise AssertionError(name+': '+str(detail))

def sizes(page):
 return page.evaluate('''()=>{const w=document.createTreeWalker(document.querySelector('#main'),NodeFilter.SHOW_TEXT);let n;const b=[];while(n=w.nextNode()){const el=n.parentElement;if(!n.textContent.trim()||el.closest('script,style,svg,[aria-hidden=true],.sr-only')||!el.checkVisibility({checkVisibilityCSS:true,checkOpacity:true}))continue;if(parseFloat(getComputedStyle(el).fontSize)<14)b.push(n.textContent.trim());}return b;}''')
try:
 if 'CATALOG_URL' not in os.environ:
  server=subprocess.Popen(['python','-m','http.server','4194','--bind','127.0.0.1','--directory','live-dist'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(30):
   try:urlopen(URL,timeout=1).close();break
   except Exception:time.sleep(.1)
 with sync_playwright() as p:
  opts={'headless':True}
  if os.environ.get('CHROMIUM_PATH'):opts['executable_path']=os.environ['CHROMIUM_PATH']
  b=p.chromium.launch(**opts);c=b.new_context(viewport={'width':1440,'height':1050},locale='ko-KR',timezone_id='Asia/Seoul',reduced_motion='reduce')
  page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  # Catalog has no dependency on broadcast timing; SOOP is verified in live_browser separately.
  page.goto(URL+'#/members',wait_until='networkidle');page.locator('#main h1').wait_for()
  check('member introduction menu and heading',page.locator('[data-nav=members]').inner_text()=='멤버 소개' and page.locator('#main h1').inner_text()=='멤버 소개')
  check('six source-backed member cards',page.locator('[data-profile]').count()==6)
  check('no old onboarding or guide block',page.locator('#main .guide-steps,#main a[href*="fan-policy"],#main a[href*="getting-started"]').count()==0 and '처음이라면' not in page.locator('#main').inner_text())
  check('six profile images decode',page.locator('.catalog-member-card img').evaluate_all('(xs)=>xs.length===6&&xs.every(x=>x.complete&&x.naturalWidth===600)'))
  page.screenshot(path=str(OUT/'members-desktop.png'),full_page=True)
  meta=c.request.get(URL+'build-info.json').json();check('published catalog commit matches',meta['commit']==os.environ.get('GITHUB_SHA','local'));check('154 songs and 21 channels in build',meta['catalog']['songs']==154 and meta['catalog']['channels']==21)
  expected={'ine':3,'jingburger':3,'lilpa':5,'jururu':3,'gosegu':4,'viichan':3};total=0
  for mid,n in expected.items():
   page.goto(URL+'#/record/'+mid,wait_until='networkidle');page.locator('[data-profile-detail]').wait_for()
   check(mid+' basic facts and sources',page.locator('.catalog-facts>div').count()==7 and page.locator('.catalog-profile a[href*="namu.wiki"]').count()==1 and page.locator('.catalog-profile a[href*="namu.moe"]').count()==1)
   check(mid+' related channel count',page.locator('[data-channel]').count()==n)
   blocks=page.locator('[data-channel]')
   for i in range(n):
    block=blocks.nth(i);dates=block.locator('[data-video-date]').evaluate_all('(xs)=>xs.map(x=>x.dataset.videoDate)')
    check(mid+' channel '+str(i)+' three newest dated videos',len(dates)==3 and dates==sorted(dates,reverse=True),dates)
    total+=len(dates)
   check(mid+' no unwanted guide link',page.locator('#main a[href*="fan-policy"],#main a[href*="getting-started"]').count()==0)
  check('all 21 channels contain 63 entries',total==63)
  page.goto(URL+'#/record/lilpa',wait_until='networkidle');page.screenshot(path=str(OUT/'member-detail-desktop.png'),full_page=True)
  check('video target is YouTube and safe opener',page.locator('.catalog-video').evaluate_all('(xs)=>xs.every(x=>/^https:\/\/www.youtube.com\/watch\?v=[A-Za-z0-9_-]{11}$/.test(x.href)&&x.rel.includes("noopener"))'))
  page.goto(URL+'#/music',wait_until='networkidle');check('library 154 and page size24',page.locator('.catalog-result-heading strong').inner_text()=='154' and page.locator('[data-song]').count()==24)
  page.screenshot(path=str(OUT/'music-desktop.png'),full_page=True)
  page.locator('.catalog-type-tabs a').filter(has_text='커버').click();expect(page.locator('.catalog-result-heading strong')).to_have_text('133');check('133 cover songs',page.locator('.catalog-result-heading strong').inner_text()=='133')
  page.locator('[data-catalog-filter=scope]').select_option('group');expect(page.locator('[data-catalog-filter=scope]')).to_have_value('group');page.wait_for_function('location.hash.includes("scope=group")');check('group cover combination',page.locator('[data-song]').count()>0 and page.locator('.catalog-song-labels').evaluate_all('(xs)=>xs.every(x=>x.innerText.includes("커버")&&x.innerText.includes("단체"))'))
  page.locator('[data-catalog-filter=member]').select_option('ine');expect(page.locator('[data-catalog-filter=member]')).to_have_value('ine');page.wait_for_function('location.hash.includes("member=ine")');check('member filter retained',page.locator('.catalog-song-members').evaluate_all('(xs)=>xs.every(x=>x.innerText.includes("아이네"))'))
  page.goto(URL+'#/music?type=original&scope=solo',wait_until='networkidle');check('three solo original tracks',page.locator('[data-song]').count()==3)
  page.goto(URL+'#/music?type=remake',wait_until='networkidle');check('remake separated',page.locator('[data-song]').count()==1 and '화이트' in page.locator('.catalog-song h3').inner_text())
  page.goto(URL+'#/music?context=ost',wait_until='networkidle');check('OST context filter',page.locator('[data-song]').count()==3)
  page.goto(URL+'#/music',wait_until='networkidle');page.locator('#catalog-query').fill('고세구 NO CAT');page.locator('#catalog-search button').click();expect(page.locator('.catalog-result-heading strong')).to_have_text('3');check('music search member plus album',page.locator('[data-song]').count()==3)
  page.locator('#catalog-query').fill('<img src=x onerror=alert(1)>');page.locator('#catalog-search button').click();page.locator('.catalog-empty').wait_for();check('inert unmatched query and clear empty state',page.locator('.catalog-empty').count()==1 and page.locator('.catalog-result-heading img').count()==0)
  page.goto(URL+'#/music?page=2',wait_until='networkidle');check('pagination shows another set',page.locator('[data-song]').count()==24 and '2 / 7' in page.locator('.catalog-pagination').inner_text())
  page.goto(URL+'#/song/be-my-light',wait_until='networkidle');check('EP classification and track list',page.locator('.catalog-facts').inner_text().find('미니 앨범')>=0 and page.locator('.catalog-tracklist li').count()==7)
  page.goto(URL+'#/song/cover-TYB9ScXvq34',wait_until='networkidle');check('cover detail source and video link',page.locator('#main a[href="https://www.youtube.com/watch?v=TYB9ScXvq34"]').count()==1 and page.locator('.catalog-detail-sources a[href*="namu.wiki"]').count()==1)
  page.screenshot(path=str(OUT/'song-detail-desktop.png'),full_page=True)
  for theme in ('light','dark'):
   page.evaluate('(x)=>document.documentElement.dataset.theme=x',theme)
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':950})
    for route in ('members','record/lilpa','music','song/be-my-light'):
     page.goto(URL+'#/'+route,wait_until='networkidle');check(f'{theme}/{width}/{route} no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
     bad=sizes(page);check(f'{theme}/{width}/{route} readable text',not bad,bad)
  page.set_viewport_size({'width':390,'height':844});page.evaluate("document.documentElement.dataset.theme='light'")
  for route,name in [('members','members-mobile'),('record/ine','member-detail-mobile'),('music','music-mobile')]:
   page.goto(URL+'#/'+route,wait_until='networkidle');page.screenshot(path=str(OUT/(name+'.png')),full_page=True)
  page.evaluate("document.documentElement.dataset.theme='dark'");page.screenshot(path=str(OUT/'music-dark-mobile.png'),full_page=True)
  page.set_viewport_size({'width':1280,'height':1000});page.evaluate("document.documentElement.style.fontSize='200%'")
  for route in ('members','record/ine','music','song/be-my-light'):
   page.goto(URL+'#/'+route,wait_until='networkidle');check('200% '+route+' no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
  check('no uncaught exceptions',not errors,errors)
  if 'CATALOG_URL' not in os.environ:
   offline=c.new_page();offline.goto((ROOT/'live-dist/review.html').as_uri());offline.evaluate("location.hash='#/members'");offline.locator('[data-profile]').first.wait_for();check('offline includes profiles',offline.locator('[data-profile]').count()==6)
   offline.evaluate("location.hash='#/music?type=cover'");offline.locator('.catalog-result-heading').wait_for();check('offline music catalog',offline.locator('.catalog-result-heading strong').inner_text()=='133')
  b.close()
finally:
 (OUT/'result.json').write_text(json.dumps({'url':URL,'commit':os.environ.get('GITHUB_SHA','local'),'checks':checks,'passed':sum(c['passed'] for c in checks),'total':len(checks),'browserErrors':errors},ensure_ascii=False,indent=2))
 if server:server.terminate();server.wait(timeout=5)
print('Catalog browser checks passed:',len(checks))
