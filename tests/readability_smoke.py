"""Public review UI checks. No submissions, external writes or credential use."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test-results/readability'
OUT.mkdir(parents=True,exist_ok=True)
URL=os.environ.get('READABILITY_URL','http://127.0.0.1:4180/').rstrip('/')+'/'
checks=[]
errors=[]
requests=[]
server=None

def check(name,value,detail=None):
    checks.append({'name':name,'passed':bool(value),**({'detail':detail} if detail is not None else {})})
    if not value: raise AssertionError(name+': '+str(detail))

def sample_fonts(page):
    return page.evaluate('''() => {
      const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT); const bad=[];let n;
      while(n=w.nextNode()){
        const e=n.parentElement;
        if(!n.textContent.trim()||!e||e.closest('script,style,svg,[aria-hidden="true"],.sr-only')||!e.checkVisibility({checkVisibilityCSS:true,checkOpacity:true}))continue;
        if(e.getBoundingClientRect().width<2||e.getBoundingClientRect().height<2)continue;
        const s=getComputedStyle(e);if(parseFloat(s.fontSize)<14)bad.push({text:n.textContent.trim().slice(0,50),size:s.fontSize,tag:e.tagName,cls:e.className});
      }return bad;
    }''')

def contrast(fg,bg):
    def lum(c):
        rgb=[int(c[i:i+2],16)/255 for i in (1,3,5)]
        rgb=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in rgb]
        return sum(a*b for a,b in zip(rgb,(.2126,.7152,.0722)))
    a,b=sorted((lum(fg),lum(bg)));return (b+.05)/(a+.05)

try:
    if 'READABILITY_URL' not in os.environ:
        server=subprocess.Popen(['python','-m','http.server','4180','--bind','127.0.0.1','--directory','readability-dist'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(30):
            try: urlopen(URL,timeout=1).close();break
            except Exception: time.sleep(.1)
    with sync_playwright() as p:
        options={'headless':True}
        if os.environ.get('CHROMIUM_PATH'):options['executable_path']=os.environ['CHROMIUM_PATH']
        b=p.chromium.launch(**options)
        c=b.new_context(viewport={'width':1440,'height':1050},locale='ko-KR',timezone_id='Asia/Seoul',reduced_motion='reduce',color_scheme='light')
        page=c.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:requests.append(r.url))
        res=page.goto(URL,wait_until='networkidle')
        page.locator('#main h1').wait_for()
        check('preview HTTP 200',res.status==200)
        check('readability review marker',page.locator('html').get_attribute('data-review')=='readability')
        check('preview noindex',page.locator('meta[name=robots]').get_attribute('content')=='noindex,nofollow')
        check('six pending profiles instead of outdated avatars',page.locator('.stage-lineup .portrait.pending').count()==6)
        check('no retired avatar images in member lineup',page.locator('.stage-lineup img').count()==0)
        page.screenshot(path=str(OUT/'home-desktop.png'),full_page=True)
        page.locator('.stage-lineup .save-button').first.click()
        expect(page.locator('.stage-lineup .save-button').first).to_have_attribute('aria-pressed','true')
        page.goto(URL+'#/saved',wait_until='networkidle')
        check('member heart still saves',page.locator('.result-row h3').first.inner_text()=='아이네')
        page.goto(URL+'#/about',wait_until='networkidle')
        text=page.locator('#main').inner_text()
        for forbidden in ('.webp','.jpg','.png','운영 소스','main','feature/','요청한 나무위키','SHA','403','503','이미지 출처와 확인 범위'):
            check('about omits '+forbidden,forbidden not in text)
        check('concise about has three sections',page.locator('.about-panel').count()==3)
        check('no repository/source file links on about',page.locator('#main a[href*="github.com"],#main a[href*="namu.wiki"]').count()==0)
        check('unofficial notice retained','공식 사이트가 아닙니다' in text)
        check('rights notice retained','권리자' in text)
        page.screenshot(path=str(OUT/'about-desktop.png'),full_page=True)
        page.goto(URL+'#/record/ine',wait_until='networkidle')
        check('member page omits raw image metadata',page.locator('.portrait-credit').count()==0)
        check('actual record sources retained',page.locator('.source-item').count()>0)
        routes=('home','members','music','schedule','videos','dictionary','history','guide','search','record/ine','about','privacy','report','saved')
        for width in (320,390,768,1440):
            page.set_viewport_size({'width':width,'height':950})
            for route in routes:
                page.goto(URL+'#/'+route,wait_until='networkidle')
                page.locator('#main h1').wait_for()
                bad=sample_fonts(page)
                check(f'{width}px {route}: meaningful text at least 14px',not bad,bad)
                check(f'{width}px {route}: no page overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        for theme in ('light','dark'):
            page.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
            for fg,bg in ([('#615968','#fcfaf7'),('#ffffff','#bd3558'),('#365b3a','#edf5ee'),('#654777','#f3eaf9')] if theme=='light' else [('#cdc2d3','#191723'),('#291621','#f3a0b6')]):
                ratio=contrast(fg,bg);check(f'{theme} text contrast {fg}/{bg}',ratio>=4.5,round(ratio,2))
        page.set_viewport_size({'width':390,'height':844})
        page.goto(URL+'#/home',wait_until='networkidle')
        page.evaluate("document.documentElement.dataset.theme='light'")
        page.screenshot(path=str(OUT/'home-mobile.png'),full_page=True)
        page.get_by_role('button',name='메뉴 열기',exact=True).click()
        check('mobile navigation expands',page.locator('#sidebar').is_visible())
        page.keyboard.press('Escape')
        check('Escape closes menu',page.locator('[data-action=menu]').get_attribute('aria-expanded')=='false')
        page.get_by_role('button',name='색상 테마 변경',exact=True).click()
        expect(page.locator('html')).to_have_attribute('data-theme','dark')
        page.screenshot(path=str(OUT/'home-dark-mobile.png'),full_page=True)
        page.goto(URL+'#/about',wait_until='networkidle')
        page.evaluate("document.documentElement.dataset.theme='light'")
        page.screenshot(path=str(OUT/'about-mobile.png'),full_page=True)
        page.set_viewport_size({'width':1280,'height':1000})
        page.evaluate("document.documentElement.style.fontSize='200%'")
        for route in ('home','members','music','schedule','record/ine','about'):
            page.goto(URL+'#/'+route,wait_until='networkidle')
            check('200% text / '+route+' reflows',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        check('no uncaught browser exceptions',not errors,errors)
        check('no old profile downloads',not any('/2026/04/' in x or x.endswith('.webp') for x in requests))
        if 'READABILITY_URL' not in os.environ:
            offline=c.new_page()
            offline.goto((ROOT/'readability-dist/review.html').as_uri(),wait_until='load')
            offline.locator('#main h1').wait_for()
            check('offline review has six honest profile placeholders',offline.locator('.stage-lineup .portrait.pending').count()==6)
            offline.evaluate("location.hash='#/search?q=ㅇㅇㄴ'")
            expect(offline.locator('.result-row h3').first).to_have_text('아이네')
            check('offline initial search preserved',True)
        b.close()
finally:
    (OUT/'result.json').write_text(json.dumps({'url':URL,'commit':os.environ.get('GITHUB_SHA','local'),'checks':checks,'passed':sum(x['passed'] for x in checks),'total':len(checks),'browser_errors':errors,'latestPortraitsApplied':False},ensure_ascii=False,indent=2))
    if server: server.terminate();server.wait(timeout=5)
print('Readability checks passed:',len(checks))
