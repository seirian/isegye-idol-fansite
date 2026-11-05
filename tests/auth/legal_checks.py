"""Verify standalone maintenance notices and the unchanged authorized site shell."""
import hashlib
import json
import os
from pathlib import Path


def install(root, application):
    real = os.getenv('MEMBER_LEGAL_REAL') == '1'
    if real:
        for name in ('member-legal.json', 'member-legal.js', 'styles.css'):
            (application/'src'/name).write_bytes((root/'dist/src'/name).read_bytes())
    else:
        docs={k:(root/'auth'/f'{k}.html').read_text() for k in ('terms','privacy')}
        fixture={'schemaVersion':1,'documents':{k:'<!doctype html><title>MEMBER_POLICY_FIXTURE</title><article data-policy="'+k+'">'+v+'</article>' for k,v in docs.items()},
                 'sourceHashes':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in docs.items()}}
        (application/'src/member-legal.json').write_text(json.dumps(fixture))
        (application/'src/styles.css').write_text('body{margin:0}')
        (application/'src/member-legal.js').write_text('/* Legal-only fixture, no application data. */')


def verify_allowed(root, out, check, role, ctx, url, private):
    """Normal-site members and administrators keep the shared document chrome."""
    before=(private/'accounts.json').read_bytes()
    for kind in ('terms','privacy'):
        response=ctx.request.get(url+'/account/'+kind,max_redirects=0)
        check(role+' shared policy accessible '+kind,response.status==200 and 'data-policy="'+kind+'"' in response.text())
        check(role+' no application scripts or data '+kind,all(s not in response.text() for s in ('src/data.js','src/app.js','runtime-feeds.js','PROTECTED_DATA_FIXTURE')))
        check(role+' no cache or framing '+kind,'no-store' in response.headers['cache-control'] and response.headers['x-frame-options']=='DENY')
        check(role+' document cannot load data APIs '+kind,"connect-src 'none'" in response.headers['content-security-policy'])
        check(role+' HEAD read only '+kind,ctx.request.head(url+'/account/'+kind).body()==b'' and ctx.request.post(url+'/account/'+kind,data={}).status==405)
    check(role+' legal-only assets accessible',ctx.request.get(url+'/account/legal.js').status==200 and ctx.request.get(url+'/account/legal.css').status==200)
    if os.getenv('MEMBER_LEGAL_REAL')=='1':
        page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url+'/account/terms')
        for theme in ('dark','light'):
            page.evaluate('(t)=>localStorage.setItem("isegye:archive:prefs:v1",JSON.stringify({theme:t,favorites:["member:ine"],watched:["video:test"]}))',theme)
            for width in (390,1440):
                page.set_viewport_size({'width':width,'height':1000})
                for kind in ('terms','privacy'):
                    page.goto(url+'/account/'+kind,wait_until='load')
                    check(f'{role}/{theme}/{width}/{kind} retained palette',page.locator('html').get_attribute('data-theme')==theme)
                    check(f'{role}/{theme}/{width}/{kind} same seven menus',page.locator('.desktop-nav>a').all_text_contents()==['오늘의 이세돌','멤버 소개','소식·일정','음악','LIVE','콘텐츠','활동 기록'])
                    check(f'{role}/{theme}/{width}/{kind} no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                    check(f'{role}/{theme}/{width}/{kind} footer intact',page.locator('.footer-links a').all_text_contents()==['이용약관','개인정보처리방침','팬가이드','사이트소개'])
                    check(f'{role}/{theme}/{width}/{kind} document anchors',page.locator('.legal-toc a').evaluate_all('(xs)=>xs.every(a=>document.getElementById(a.hash.slice(1)))'))
                    page.screenshot(path=str(out/f'{role}-{kind}-{theme}-{width}.png'),full_page=False)
                    page.locator('[data-action=theme]').click()
                    check(f'{role}/{theme}/{width}/{kind} toggle updates common key',page.evaluate('(t)=>JSON.parse(localStorage.getItem("isegye:archive:prefs:v1")).theme!==t',theme))
                    page.locator('[data-action=theme]').click()
                    check(f'{role}/{theme}/{width}/{kind} no saved data loss',page.evaluate('JSON.parse(localStorage.getItem("isegye:archive:prefs:v1")).watched[0]==="video:test"'))
        check(role+' member page no JS errors',not errors);page.close()
    check(role+' legal reads preserve account store',(private/'accounts.json').read_bytes()==before)


def verify(root, out, check, guest, member, owner, url, private, application):
    before=(private/'accounts.json').read_bytes()
    for role,ctx in [('guest',guest),('maintenance-member',member)]:
        for kind in ('terms','privacy'):
            response=ctx.request.get(url+'/account/'+kind,max_redirects=0)
            check(role+' old shared URL redirects to standalone '+kind,response.status==303 and response.headers['location']=='/auth/'+kind)
            check(role+' member POST rejected '+kind,ctx.request.post(url+'/account/'+kind,data={}).status==405)
        for asset in ('legal.css','legal.js'):
            expected=401 if role=='guest' else 403
            check(role+' shared legal asset denied '+asset,ctx.request.get(url+'/account/'+asset).status==expected)
        page=ctx.new_page()
        for width in (390,1440):
            page.set_viewport_size({'width':width,'height':1000})
            page.goto(url+'/')
            check(f'{role}/{width} maintenance public links',page.locator('a[href="/auth/terms"],a[href="/auth/privacy"]').count()==2)
            for kind in ('terms','privacy'):
                page.goto(url+'/');page.locator('a[href="/auth/'+kind+'"]').click()
                check(f'{role}/{width}/{kind} correct standalone destination',page.url==url+'/auth/'+kind)
                check(f'{role}/{width}/{kind} no application chrome',page.locator('.site-header,.legal-site-header,.legal-site-nav,.desktop-nav,.mobile-nav').count()==0)
                check(f'{role}/{width}/{kind} no guide or about',page.locator('a[href*="/guide"],a[href*="/about"]').count()==0)
                check(f'{role}/{width}/{kind} only two document tabs',page.locator('.legal-tabs a').all_text_contents()==['이용약관','개인정보처리방침'])
                check(f'{role}/{width}/{kind} no scripts',page.locator('script').count()==0)
                check(f'{role}/{width}/{kind} anchors resolve',page.locator('.legal-toc a').evaluate_all('(xs)=>xs.every(a=>document.getElementById(a.hash.slice(1)))'))
                check(f'{role}/{width}/{kind} no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                check(f'{role}/{width}/{kind} canonical body',(root/'auth'/f'{kind}.html').read_text() in ctx.request.get(url+'/auth/'+kind).text())
                page.screenshot(path=str(out/f'{role}-{kind}-standalone-{width}.png'),full_page=False)
        page.close()
    # Direct shared-page requests are bounded independently of the maintenance links.
    check('member main still blocked',member.request.get(url+'/').status==503)
    check('member APIs still blocked',all(member.request.get(url+'/api/'+f).status==503 for f in ('music','schedule','history')))
    for path in ('/account/unknown','/account/../src/app.js'):
        response=member.request.get(url+path)
        check('no member bypass '+path,response.status in (404,503) and 'PROTECTED_DATA_FIXTURE' not in response.text())
    check('admin application remains available',owner.request.get(url+'/src/app.js').status==200)
    verify_allowed(root,out,check,'admin',owner,url,private)
    path=application/'src/member-legal.json';original=path.read_bytes();bad=json.loads(original);bad['sourceHashes']['terms']='0'*64;path.write_text(json.dumps(bad))
    check('mismatched canonical document fails closed',owner.request.get(url+'/account/terms').status==503)
    path.unlink();path.symlink_to(private/'accounts.json')
    check('shared document symlink refused',owner.request.get(url+'/account/terms').status==503)
    path.unlink();path.write_bytes(original)
    check('legal reads never change member store',(private/'accounts.json').read_bytes()==before)
