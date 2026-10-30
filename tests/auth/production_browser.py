"""Read-only live checks. Never supply a credential, create a member or fake a session."""
import json,os,re
from pathlib import Path
from playwright.sync_api import sync_playwright
URL='https://isegye-idol.kr'
OUT=Path('test-results/google-access-live');OUT.mkdir(parents=True,exist_ok=True)
checks=[];errors=[];notes=[]
report={'status':'failed','commit':os.environ['GITHUB_SHA'],'realGoogleAccountLoginPerformed':False,'googleButtonRendered':False,'googleAccountChooserReached':False}
def check(name,ok):
    checks.append({'name':name,'passed':bool(ok)})
    if not ok: raise AssertionError(name)
try:
    with sync_playwright() as p:
        b=p.chromium.launch();c=b.new_context(viewport={'width':1440,'height':1000},locale='ko-KR',timezone_id='Asia/Seoul')
        page=c.new_page();page.on('pageerror',lambda e:errors.append(type(e).__name__))
        initial=c.request.get(URL+'/auth/status').json()
        check('anonymous is not granted membership',not initial['authenticated'] and not initial['administrator'])
        response=page.goto(URL+'/',wait_until='networkidle')
        check('dynamic document is not cacheable','no-store' in response.headers.get('cache-control',''))
        if not initial['maintenance']:
            page.locator('#main h1').wait_for()
            check('public home before administrator',response.status==200 and page.locator('.hm-page').count()==1)
            check('existing top LIVE preserved',page.locator('#main>section').first.get_attribute('class')=='live-home')
            check('login entry reachable',page.locator('.isegye-account-link').get_attribute('href')=='/auth/login')
            meta=c.request.get(URL+'/build-info.json').json();check('deployed commit matches',meta['commit']==os.environ['GITHUB_SHA'])
        else:
            check('maintenance for anonymous',response.status==503 and '현재 사이트는 공사중입니다.' in ' '.join(page.locator('h1').inner_text().split()))
        page.screenshot(path=str(OUT/'home-desktop.png'),full_page=True)
        response=page.goto(URL+'/auth/login',wait_until='networkidle')
        check('Google login page HTTP200',response.status==200)
        check('configured client ID used',page.locator('#google-signin').get_attribute('data-client-id')==os.environ['ISEGYE_GOOGLE_CLIENT_ID'])
        check('nonce and csrf generated',all(re.fullmatch('[0-9a-f]{64}',page.locator('#google-signin').get_attribute(x) or '') for x in ('data-nonce','data-csrf')))
        cookies=[x for x in c.cookies() if x['name']=='__Host-ISEGYE']
        check('secure session cookie',len(cookies)==1 and cookies[0]['secure'] and cookies[0]['httpOnly'] and cookies[0]['path']=='/' and cookies[0]['sameSite']=='Lax')
        check('popup opener policy compatible',response.headers.get('cross-origin-opener-policy')=='same-origin-allow-popups')
        check('Google compatible referrer policy',response.headers.get('referrer-policy')=='strict-origin-when-cross-origin')
        button=page.frame_locator('iframe[src*="accounts.google.com/gsi/button"]').get_by_role('button')
        button.wait_for(timeout=30000)
        check('official Google button visible',button.is_visible());report['googleButtonRendered']=True
        try:
            with page.expect_popup(timeout=20000) as pending:
                button.click()
            popup=pending.value;popup.wait_for_load_state('domcontentloaded',timeout=20000)
            for _ in range(40):
                if popup.url.startswith('https://accounts.google.com/') and popup.url!='about:blank':break
                page.wait_for_timeout(250)
            report['googleAccountChooserReached']=popup.url.startswith('https://accounts.google.com/') and 'oauth/error' not in popup.url
            notes.append('Google popup reached' if report['googleAccountChooserReached'] else 'Google popup could not be confirmed')
            popup.close()
        except Exception:
            notes.append('Popup could not be confirmed in headless browser; actual user sign-in remains required')
        page.screenshot(path=str(OUT/'login-desktop.png'),full_page=True)
        for width in (320,390,768,1440):
            page.set_viewport_size({'width':width,'height':844})
            check('login no overflow '+str(width),page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(OUT/'login-mobile.png'),full_page=True)
        check('privacy available',c.request.get(URL+'/auth/privacy').status==200)
        legal_before=c.request.get(URL+'/auth/status').json()
        if legal_before['maintenance']:
            check('anonymous schedule API remains protected',c.request.get(URL+'/api/schedule').status==503)
        check('private schedule store not public',c.request.get(URL+'/.schedule-feed/current.json').status in (403,404,503))
        for kind,count in [('terms',16),('privacy',13)]:
            response=page.goto(URL+'/auth/'+kind,wait_until='networkidle')
            check('public full legal document '+kind,response.status==200 and page.locator('[data-policy="'+kind+'"]').count()==1)
            check('published legal body matches source '+kind,Path('auth/'+kind+'.html').read_text() in response.text())
            check('published sections complete '+kind,page.locator('.legal-body>section').count()==count+1)
            check('legal version '+kind,page.locator('[data-version="1.0"]').count()==1)
            check('legal table present '+kind,page.locator('table caption').count()>0)
            check('public legal text has no scripts '+kind,page.locator('script').count()==0)
            check('legal top navigation omits account link '+kind,page.locator('.legal-navigation a[href="/auth/login"]').count()==0)
            check('legal operator label '+kind,page.locator('.legal-meta dd').first.inner_text()=='운영자')
            check('legal operator nickname removed '+kind,'seirian' not in page.locator('.legal-document').inner_text().replace('seirian@gmail.com',''))
            check('legal active tab '+kind,page.locator('.legal-tabs [aria-current="page"]').get_attribute('href')=='/auth/'+kind)
            check('legal table of contents '+kind,page.locator('.legal-toc a').evaluate_all('(xs)=>xs.every(x=>document.getElementById(x.hash.slice(1)))'))
            for width in (320,390,768,1440):
                page.set_viewport_size({'width':width,'height':900})
                check('legal mobile no overflow '+kind+str(width),page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            page.set_viewport_size({'width':1440,'height':1000});page.screenshot(path=str(OUT/(kind+'-desktop.png')),full_page=True)
            page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(OUT/(kind+'-mobile.png')),full_page=True)
        check('legal reading preserves access state',c.request.get(URL+'/auth/status').json()==legal_before)
        for alias,target in [('/terms','/auth/terms'),('/privacy','/auth/privacy')]:
            r=c.request.get(URL+alias,max_redirects=0)
            check('legal canonical alias '+alias,r.status==308 and r.headers.get('location')==target)
        page.goto(URL+'/',wait_until='networkidle')
        if legal_before['maintenance']:
            check('maintenance omits terms and privacy links',page.locator('a[href="/auth/terms"],a[href="/auth/privacy"],a[href="https://isegye-idol.kr/auth/terms"],a[href="https://isegye-idol.kr/auth/privacy"]').count()==0)
            check('maintenance retains login entry',page.locator('a[href="/auth/login"]').count()==1)
            page.set_viewport_size({'width':1440,'height':1000});page.screenshot(path=str(OUT/'maintenance-clean-desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(OUT/'maintenance-clean-mobile.png'),full_page=True)
        else:
            check('home footer contains legal links then fan guide',page.locator('.footer-links a').all_text_contents()==['이용약관','개인정보처리방침','팬가이드'])
        for suffix in ('/.auth-private/accounts.json','/.auth-private/config.json','/access.php','/_isegye_releases/r000000000000/index.html','/_mir_site/index.html'):
            response=c.request.get(URL+suffix)
            check('private or legacy URL denied '+suffix,response.status in (403,404,503))
        final=c.request.get(URL+'/auth/status').json()
        check('visit does not sign in user',not final['authenticated'] and not final['administrator'])
        check('no browser exceptions',not errors)
        report.update(status='verified',maintenanceActive=final['maintenance'],browserErrors=errors,notes=notes)
        b.close()
finally:
    report.update(passed=sum(x['passed'] for x in checks),total=len(checks),checks=checks)
    (OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
