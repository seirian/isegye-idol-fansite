"""Production/preview metadata, external policy and release content integrity."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
URL=os.environ['RELEASE_URL'].rstrip('/')+'/'
OUT=ROOT/os.environ['RELEASE_OUT'];OUT.mkdir(parents=True,exist_ok=True)
MODE=os.getenv('RELEASE_MODE','preview');checks=[];errors=[]
def check(name,ok):
    checks.append({'name':name,'passed':bool(ok)})
    if not ok:raise AssertionError(name)
try:
    with sync_playwright() as p:
        opts={'headless':True}
        if os.getenv('CHROMIUM_PATH'):opts['executable_path']=os.environ['CHROMIUM_PATH']
        b=p.chromium.launch(**opts);c=b.new_context(viewport={'width':1440,'height':1080},locale='ko-KR',timezone_id='Asia/Seoul',reduced_motion='reduce');page=c.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        r=page.goto(URL,wait_until='networkidle');page.locator('#main h1').wait_for()
        check('HTTP200',r.status==200)
        meta=c.request.get(URL+'build-info.json').json()
        check('exact released commit',meta['commit']==os.environ['GITHUB_SHA'])
        check('mode and version',meta['mode']==MODE and meta['version']=='0.5.0')
        check('approved simple home release',meta.get('approvedHomeReview')=='c770c9d590c9e46a86c55d91d02d28d27da6ac05' and meta.get('operatorApprovedDeployment') is True and page.locator('.hm-page').count()==1)
        check('LIVE remains first',page.locator('#main>section').first.get_attribute('class')=='live-home')
        check('contribution banner absent',page.locator('#main a[href*=report]').count()==0)
        check('seven menus',page.locator('[data-nav]').count()==7)
        check('LIVE and member introductions',page.locator('[data-nav=live]').count()==1 and page.locator('[data-nav=members]').inner_text()=='멤버 소개')
        check('six original profile images',page.locator('.hm-members img').evaluate_all('(es)=>es.length===6&&es.every(e=>e.complete&&e.naturalWidth===600)'))
        check('group illustration preserved',page.locator('.hm-group').evaluate('(e)=>e.complete&&e.naturalWidth===800'))
        check('music/history included',meta['catalog']['songs']==154 and meta['musicVideoAudit']['linked']==151 and meta['visualHistory']['historyItems']==55)
        check('21 channel sections',meta['catalog']['channels']==21)
        check('robots metadata',page.locator('meta[name=robots]').get_attribute('content')==('index,follow' if MODE=='production' else 'noindex,nofollow'))
        if MODE=='production':
            check('canonical production URL',page.locator('link[rel=canonical]').get_attribute('href')=='https://isegye-idol.kr/')
            check('public beta not review label', '공개 베타' in page.locator('.preview-strip').inner_text() and '검토' not in page.locator('.preview-strip').inner_text())
            check('robots file permits crawl','Allow: /' in c.request.get(URL+'robots.txt').text())
        else:check('no production canonical',page.locator('link[rel=canonical]').count()==0)
        policy=page.locator('meta[http-equiv="Content-Security-Policy"]').get_attribute('content')
        check('only needed external connections',"connect-src 'self' https://chapi.sooplive.co.kr" in policy and 'https://i.ytimg.com' in policy and 'https://liveimg.sooplive.com' in policy)
        check('no automatic video player',page.locator('iframe,video,audio').count()==0)
        check('footer contains only terms and privacy',page.locator('.footer-links a').all_text_contents()==['이용약관','개인정보처리방침'])
        check('footer policy URLs preserved',page.locator('.footer-links a').evaluate_all('(xs)=>xs.map(x=>x.href)')==['https://isegye-idol.kr/auth/terms','https://isegye-idol.kr/auth/privacy'])
        page.locator('.footer').screenshot(path=str(OUT/'footer-desktop.png'))
        page.screenshot(path=str(OUT/'home-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844});check('mobile no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'));page.screenshot(path=str(OUT/'home-mobile.png'),full_page=True)
        page.locator('.footer').screenshot(path=str(OUT/'footer-mobile.png'))
        for width in (320,768,1440):
            page.set_viewport_size({'width':width,'height':900})
            check('footer two links at width '+str(width),page.locator('.footer-links a').count()==2 and page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.goto(URL+'#/guide',wait_until='networkidle')
        check('fan guide and policy remain accessible',page.locator('[data-nav=guide]').count()==1 and page.locator('#main a[href="#/record/fan-policy"]').count()>0)
        page.goto(URL+'#/report?type=rights',wait_until='networkidle')
        check('rights request screen preserved',page.locator('#report-form').count()==1)
        page.goto(URL+'#/about',wait_until='networkidle')
        check('about avoids implementation detail',all(t not in page.locator('#main').inner_text() for t in ('확인본(미러)','운영 소스','프로필.webp')))
        check('no page exceptions',not errors);b.close()
finally:
    (OUT/'result.json').write_text(json.dumps({'url':URL,'mode':MODE,'commit':os.getenv('GITHUB_SHA'),'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks,'browserErrors':errors},ensure_ascii=False,indent=2)+'\n')
