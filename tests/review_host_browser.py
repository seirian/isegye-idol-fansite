"""Reuse every original TLS/Google fixture assertion against the generated runtime.

Only synthetic identities on loopback. The real review HTML is served by PHP
through the normal signed JWT, account, session and administrator gate.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'tests/auth/browser.py').read_text()

def once(before,after):
    global source
    assert source.count(before)==1,'Auth fixture anchor changed: '+before[:60]
    source=source.replace(before,after,1)

once("OUT=ROOT/'test-results/auth'", "OUT=ROOT/'test-results/review-host'")
once("str(ROOT/'tests/auth/fixture_router.php')", "str(ROOT/'tests/review_host_fixture.php')")
once("from playwright.sync_api import sync_playwright", "from playwright.sync_api import sync_playwright, expect")
once("    signing=base/'signing.pem';cert=base/'cert.pem'", """    import sys
    sys.path.insert(0,str(ROOT/'scripts'))
    from deploy_review_1st import payload,MARKER
    artifact_commit=json.loads((ROOT/'review-1st-dist/build-info.json').read_text())['commit']
    review_release,review_html,review_meta,review_pointer=payload(ROOT/'review-1st-dist',artifact_commit)
    preview=base/'.review-1st'; preview.mkdir(mode=0o700)
    (preview/'.owner').write_bytes(MARKER);(preview/'active.json').write_bytes(review_pointer)
    review_folder=preview/'releases'/review_release;review_folder.mkdir(parents=True)
    review_file=review_folder/'review.html';review_file.write_bytes(review_html)
    (review_folder/'build-info.json').write_bytes(review_meta)
    signing=base/'signing.pem';cert=base/'cert.pem'""")
once("            check('public visit does not create member cookie',not guest.cookies())", """            check('public visit does not create member cookie',not guest.cookies())
            check('review blocked before first administrator',guest.request.get(url+'/review-1st/').status==403)
            check('review before administrator does not create a cookie',not guest.cookies())""")
once("            check('member is not administrator',member.request.get(url+'/auth/status').json()['administrator'] is False)", """            check('member is not administrator',member.request.get(url+'/auth/status').json()['administrator'] is False)
            check('ordinary member cannot view review before maintenance',member.request.get(url+'/review-1st/').status==403)""")
once("            op.goto(url+'/auth/login');csrf=op.locator('input[name=csrf]').input_value()", """            # Exact review artifact through the same server-side gate as production.
            check('review anonymous maintenance gate',guest.request.get(url+'/review-1st/').status==503)
            check('review ordinary member maintenance gate',member.request.get(url+'/review-1st/').status==503)
            check('admin review exact byte response',owner.request.get(url+'/review-1st/').body()==review_html)
            check('admin review metadata exact',owner.request.get(url+'/review-1st/build-info.json').body()==review_meta)
            check('review HEAD has no body',owner.request.head(url+'/review-1st/').body()==b'')
            check('review POST is rejected',owner.request.post(url+'/review-1st/',data={}).status==405)
            check('review canonical slash',owner.request.get(url+'/review-1st',max_redirects=0).status==308)
            check('review noindex header','noindex' in owner.request.get(url+'/review-1st/').headers['x-robots-tag'])
            check('review cannot be framed',owner.request.get(url+'/review-1st/').headers['x-frame-options']=='DENY')
            for suffix in ['assets/private.json','../../.auth-private/config.json','%252e%252e/config.json']:
                response=owner.request.get(url+'/review-1st/'+suffix)
                check('unknown preview path blocked '+suffix,response.status in (404,503) and response.body()!=review_html)
            check('private preview path blocked',owner.request.get(url+'/.review-1st/releases/'+review_release+'/review.html').status==404)
            review_file.write_bytes(review_html+b'changed')
            check('changed review bytes fail closed',owner.request.get(url+'/review-1st/').status==503)
            review_file.write_bytes(review_html)
            review_file.unlink();review_file.symlink_to(private/'accounts.json')
            check('review symlink fails closed',owner.request.get(url+'/review-1st/').status==503)
            review_file.unlink();review_file.write_bytes(review_html)
            owner.route('https://chapi.sooplive.co.kr/**',lambda r:r.abort())
            owner.route('https://i.ytimg.com/**',lambda r:r.abort())
            review_errors=[];op.on('pageerror',lambda e:review_errors.append(str(e)))
            r=op.goto(url+'/review-1st/#/home',wait_until='load')
            expect(op.locator('#main h1')).to_have_text('오늘의 이세돌')
            check('authorized preview renders through real local gate',r.status==200 and op.locator('.desktop-nav>a').count()==6)
            op.locator('#header-query').fill('릴파 11월 3일');op.locator('#header-query').press('Enter')
            expect(op.locator('#global-query')).to_have_value('릴파 11월 3일')
            check('authorized review search finds restored notice','오늘은 휴방입니다!' in op.locator('#main').inner_text())
            for width in (390,1440):
                op.set_viewport_size({'width':width,'height':1000})
                op.goto(url+'/review-1st/#/home',wait_until='load')
                expect(op.locator('#main h1')).to_have_text('오늘의 이세돌')
                check('gated preview no overflow '+str(width),op.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                op.screenshot(path=str(OUT/('preview-'+str(width)+'.png')),full_page=True)
            check('gated preview has no JavaScript exceptions',not review_errors)
            check('production root remains separate',owner.request.get(url+'/').text().count('PROTECTED_SITE_FIXTURE')==1)
            op.goto(url+'/auth/login');csrf=op.locator('input[name=csrf]').input_value()""")
once("            check('logout never disables maintenance',guest.request.get(url+'/').status==503)","""            check('logout never disables maintenance',guest.request.get(url+'/').status==503)
            check('logged-out administrator loses review access',owner.request.get(url+'/review-1st/').status==503)""")
once("'scope':'loopback TLS; synthetic RSA-signed Google-claim fixtures only; no real Google users'", "'scope':'generated preview runtime; real loopback TLS/PHP/session gate; synthetic signed Google claims only; no real users'")
exec(compile(source,str(ROOT/'tests/auth/browser.py'),'exec'),{'__name__':'__main__','__file__':str(ROOT/'tests/auth/browser.py')})
