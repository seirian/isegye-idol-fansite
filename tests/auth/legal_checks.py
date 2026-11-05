"""Exercise both member roles without changing the maintenance/content gate."""
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


def verify(root, out, check, guest, member, owner, url, private, application):
    before=(private/'accounts.json').read_bytes()
    for kind in ('terms','privacy'):
        response=guest.request.get(url+'/account/'+kind,max_redirects=0)
        check('guest member document redirects to public '+kind,response.status==303 and response.headers['location']=='/auth/'+kind)
        check('guest member POST rejected '+kind,guest.request.post(url+'/account/'+kind,data={}).status==405)
    for asset in ('legal.css','legal.js'):
        check('anonymous legal asset denied '+asset,guest.request.get(url+'/account/'+asset).status==401)
    for role,ctx in [('member',member),('admin',owner)]:
        for kind in ('terms','privacy'):
            response=ctx.request.get(url+'/account/'+kind)
            check(role+' policy accessible during maintenance '+kind,response.status==200 and 'data-policy="'+kind+'"' in response.text())
            check(role+' policy canonical body '+kind,'제1조' in response.text() if kind=='terms' else '개인정보처리방침' in response.text())
            check(role+' no application scripts or data '+kind,all(s not in response.text() for s in ('src/data.js','src/app.js','runtime-feeds.js','PROTECTED_DATA_FIXTURE')))
            check(role+' no cache or framing '+kind,'no-store' in response.headers['cache-control'] and response.headers['x-frame-options']=='DENY')
            check(role+' document cannot load data APIs '+kind,"connect-src 'none'" in response.headers['content-security-policy'])
            check(role+' HEAD read only '+kind,ctx.request.head(url+'/account/'+kind).body()==b'' and ctx.request.post(url+'/account/'+kind,data={}).status==405)
        check(role+' legal-only assets accessible',ctx.request.get(url+'/account/legal.js').status==200 and ctx.request.get(url+'/account/legal.css').status==200)
        for path in ('/account/unknown','/account/../src/app.js'):
            response=ctx.request.get(url+path)
            if role=='member':check('no member bypass '+path,response.status in (404,503) and 'PROTECTED_DATA_FIXTURE' not in response.text())
    check('member main still blocked',member.request.get(url+'/').status==503)
    check('member APIs still blocked',all(member.request.get(url+'/api/'+f).status==503 for f in ('music','schedule','history')))
    check('admin application remains available',owner.request.get(url+'/src/app.js').status==200)
    path=application/'src/member-legal.json';original=path.read_bytes();bad=json.loads(original);bad['sourceHashes']['terms']='0'*64;path.write_text(json.dumps(bad))
    check('mismatched canonical document fails closed',member.request.get(url+'/account/terms').status==503)
    path.unlink();path.symlink_to(private/'accounts.json')
    check('member document symlink refused',member.request.get(url+'/account/terms').status==503)
    path.unlink();path.write_bytes(original)
    if os.getenv('MEMBER_LEGAL_REAL')=='1':
        for role,ctx in [('member',member),('admin',owner)]:
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
                        if role=='member':page.screenshot(path=str(out/f'member-{kind}-{theme}-{width}.png'),full_page=True)
                        page.locator('[data-action=theme]').click()
                        check(f'{role}/{theme}/{width}/{kind} toggle updates common key',page.evaluate('(t)=>JSON.parse(localStorage.getItem("isegye:archive:prefs:v1")).theme!==t',theme))
                        page.locator('[data-action=theme]').click()
                        check(f'{role}/{theme}/{width}/{kind} no saved data loss',page.evaluate('JSON.parse(localStorage.getItem("isegye:archive:prefs:v1")).watched[0]==="video:test"'))
            check(role+' member page no JS errors',not errors);page.close()
    check('legal reads never change member store',(private/'accounts.json').read_bytes()==before)
