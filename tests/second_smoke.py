"""Second-concept checks against local, preview or approved production URLs.
No form submission, account access, or production writes.
"""
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
URL=os.environ.get('SECOND_BASE_URL','http://127.0.0.1:4174/').rstrip('/')+'/'
OUT=ROOT/('test-results/production/second' if os.environ.get('SECOND_EXPECT_MODE')=='production' else 'test-results/second')
OUT.mkdir(parents=True,exist_ok=True)
checks=[]
def check(name,value):
    checks.append({'name':name,'passed':bool(value)})
    assert value,name
with sync_playwright() as p:
    browser=p.chromium.launch(**({'executable_path':os.environ['CHROMIUM_PATH']} if os.environ.get('CHROMIUM_PATH') else {}))
    context=browser.new_context(viewport={'width':1440,'height':1080},locale='ko-KR',timezone_id='Asia/Seoul',reduced_motion='reduce',color_scheme='light')
    page=context.new_page()
    errors=[];external=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('request',lambda request:external.append(request.url) if request.url.startswith('http') and urlparse(request.url).netloc!=urlparse(URL).netloc else None)
    response=page.goto(URL,wait_until='networkidle')
    page.locator('#main h1').wait_for()
    check('preview HTTP 200',response.status==200)
    check('second-concept marker',page.locator('html').get_attribute('data-concept')=='second')
    expected_robots='index,follow' if os.environ.get('SECOND_EXPECT_MODE')=='production' else 'noindex,nofollow'
    check('mode-specific indexing metadata',page.locator('meta[name=robots]').get_attribute('content')==expected_robots)
    check('six member cards',page.locator('.stage-lineup .polaroid').count()==6)
    check('six decoded local portraits',page.locator('.stage-lineup img').evaluate_all('(els)=>els.length===6&&els.every(e=>e.complete&&e.naturalWidth>100)'))
    check('temporary portrait disclosure', '임시본' in page.locator('.hero-footnote').inner_text())
    page.screenshot(path=str(OUT/'home-desktop.png'),full_page=True)
    page.locator('.stage-lineup .save-button').first.click()
    expect(page.locator('.stage-lineup .save-button').first).to_have_attribute('aria-pressed','true')
    page.goto(URL+'#/saved',wait_until='networkidle')
    check('photocard heart saves member',page.locator('.result-row h3').first.inner_text()=='아이네')
    page.reload(wait_until='networkidle')
    check('photocard bookmark persists',page.locator('.result-row').count()==1)
    page.goto(URL+'#/record/ine',wait_until='networkidle')
    check('member profile portrait',page.locator('.member-detail-portrait img').count()==1)
    check('member portrait provenance','나무위키' in page.locator('.portrait-credit').inner_text())
    page.screenshot(path=str(OUT/'member-detail.png'),full_page=True)
    page.goto(URL+'#/about',wait_until='networkidle')
    check('six source credit cards',page.locator('.image-credit-row').count()==6)
    check('Namu requirement openly pending','동일하다고 확인된 이미지가 아닙니다' in page.locator('#main').inner_text())
    for width in (320,390,768,1440):
        page.set_viewport_size({'width':width,'height':900})
        for route in ('home','members','music','schedule','search','record/ine','about'):
            page.goto(URL+'#/'+route,wait_until='networkidle')
            page.locator('#main h1').wait_for()
            check(str(width)+'px / '+route+' no overflow',page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'))
    page.set_viewport_size({'width':390,'height':844})
    page.goto(URL+'#/home',wait_until='networkidle')
    page.screenshot(path=str(OUT/'home-mobile.png'),full_page=True)
    page.get_by_role('button',name='메뉴 열기',exact=True).click()
    expect(page.locator('#sidebar')).to_have_class('nav sidebar open')
    page.keyboard.press('Escape')
    check('Escape closes mobile navigation',page.get_by_role('button',name='메뉴 열기',exact=True).get_attribute('aria-expanded')=='false')
    page.get_by_role('button',name='색상 테마 변경',exact=True).click()
    expect(page.locator('html')).to_have_attribute('data-theme','dark')
    page.screenshot(path=str(OUT/'home-dark-mobile.png'),full_page=True)
    check('dark mode does not alter portraits',page.locator('.portrait img').first.evaluate('(e)=>getComputedStyle(e).filter')=='none')
    check('no automatic external asset requests',not external)
    check('no uncaught browser exceptions',not errors)
    context.close()
    if not os.environ.get('SECOND_SKIP_OFFLINE'):
        context=browser.new_context(viewport={'width':390,'height':844},locale='ko-KR',reduced_motion='reduce')
        offline=context.new_page();offline_errors=[];requests=[]
        offline.on('pageerror',lambda error:offline_errors.append(str(error)))
        offline.on('request',lambda req:requests.append(req.url) if req.url.startswith('http') else None)
        offline.goto((ROOT/'second-dist/review-second.html').as_uri(),wait_until='load')
        offline.locator('.stage-lineup img').last.wait_for()
        check('offline six images decode',offline.locator('.stage-lineup img').evaluate_all('(els)=>els.length===6&&els.every(e=>e.complete&&e.naturalWidth>100)'))
        offline.evaluate("location.hash='#/search?q=ㅇㅇㄴ'")
        expect(offline.locator('.result-row h3').first).to_have_text('아이네')
        check('offline initial search',True)
        check('offline zero external requests',not requests)
        check('offline zero browser exceptions',not offline_errors)
        context.close()
    browser.close()
(OUT/'result.json').write_text(json.dumps({'url':URL,'passed':len(checks),'checks':checks,'browser_errors':errors,'external_assets':external},ensure_ascii=False,indent=2),encoding='utf-8')
print('Second-concept checks passed:',len(checks))
