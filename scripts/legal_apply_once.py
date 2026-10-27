"""One-time, hash-pinned edits for the owner-requested policy integration.
Writes only four source/test files in this feature checkout. No hosting or account access.
This temporary migration and its workflow are removed in the resulting source commit.
"""
from pathlib import Path
import hashlib
R=Path(__file__).resolve().parents[1]
OLD={'src/app.js': '8c0a7a4069b21e32ed5a597943fba2cde76470cc9d5d5f5d8c96757ab5a0cdf4', 'second/compose.py': '4875d4e84ac5405366db6069b1a9546154cf3666f20845c6c0653b84ea5d7ff0', 'tests/auth/browser.py': 'a33069f369b1c1693055e7820c3a7c65dc9ff25d6e37204f3c9722b227425856', 'tests/auth/production_browser.py': '1cc9d549a447d7ea2c56d0997284cd442615a2397e647210335763c57960b031'}
NEW={'src/app.js': '6e372805a68f611b323bdebf50a1851bc7824515743082cb31b6745febfeb52d', 'second/compose.py': '0cbb901e5297e761cedcac637ea08af4b61704a64357685de220993dc3579341', 'tests/auth/browser.py': 'fd333594f290ed4355dbfa994b3d209065050481178df991c9ef5af9ede638f3', 'tests/auth/production_browser.py': 'c43c48abf3a8d776658b805c43a4e5cd47ada2a5056aa05d66ce57264b7c4216'}
for name,digest in OLD.items():
    if hashlib.sha256((R/name).read_bytes()).hexdigest()!=digest:
        raise RuntimeError('Concurrent source change: '+name)
# Canonical links are full HTTPS so standalone review files do not invent local auth endpoints.
for filename in ['src/app.js','second/compose.py']:
 p=R/filename;s=p.read_text().replace('<a href="#/privacy">개인정보 안내</a>', '<a href="https://isegye-idol.kr/auth/terms">이용약관</a><a href="https://isegye-idol.kr/auth/privacy"><strong>개인정보처리방침</strong></a>');p.write_text(s)
p=R/'src/app.js';s=p.read_text();a=s.index('function privacyView(){');b=s.index('function notFound()',a)
s=s[:a]+'''function privacyView(){return heading('개인정보처리방침 · 저장정보 관리','회원정보의 처리 기준과 이 브라우저의 설정을 확인하세요.','PRIVACY')+`<div class="prose"><p>Google 로그인 식별값과 권한, 인증 과정 및 세션, 외부 서비스 연동과 권리 행사 방법은 최신 개인정보처리방침 전문에서 확인할 수 있습니다.</p><p><a class="button" href="https://isegye-idol.kr/auth/privacy">개인정보처리방침 전문</a> <a class="text-link" href="https://isegye-idol.kr/auth/terms">이용약관</a></p><h2>브라우저 저장정보 관리</h2><p>즐겨찾기와 화면 테마는 이 브라우저에 저장되며 계정과 연결해 서버에 동기화하지 않습니다. 아래 버튼은 이 사이트의 즐겨찾기·테마만 지웁니다. 회원 탈퇴, 로그인 세션 종료 또는 외부 서비스 데이터 삭제를 대신하지 않습니다.</p><button class="button secondary" data-action="clear-data">이 사이트의 저장 정보 지우기</button><h2>회원정보 요청</h2><p>열람·정정·삭제·탈퇴는 개인정보처리방침의 운영자 연락처로 요청할 수 있습니다. 개인정보와 비공개 증빙은 GitHub 공개 이슈에 올리지 마세요.</p></div>`;}
''' + s[b:]
p.write_text(s)
p=R/'tests/auth/browser.py';s=p.read_text()
anchor="            def prepare(page,subject,email,**changes):"
new='''            # Policy reading is public before/after maintenance and is not registration.
            for kind, count in [('terms',16),('privacy',13)]:
                response=gp.goto(url+'/auth/'+kind)
                check('policy before admin '+kind,response.status==200 and gp.locator('[data-policy="'+kind+'"]').count()==1)
                check('complete numbered policy '+kind,gp.locator('.legal-body>section').count()==count+1)
                check('policy has version '+kind,gp.locator('[data-version="1.0"]').count()==1)
                check('policy has no Google script '+kind,gp.locator('script').count()==0)
                check('policy does not set member cookies '+kind,not guest.cookies())
                check('policy HEAD has no body '+kind,guest.request.head(url+'/auth/'+kind).body()==b'')
                check('policy is read-only '+kind,guest.request.post(url+'/auth/'+kind,data={}).status==405)
            for alias,target in [('/terms','/auth/terms'),('/privacy','/auth/privacy'),('/settings/terms-of-service','/auth/terms'),('/settings/privacy-policy','/auth/privacy')]:
                response=guest.request.get(url+alias,max_redirects=0)
                check('policy alias '+alias,response.status==308 and response.headers.get('location')==target)
'''
s=s.replace(anchor,new+anchor)
anchor="            check('no-cache on maintenance','no-store' in response.headers['cache-control'])"
new='''            for ctx in (guest,member,owner):
                for kind in ('terms','privacy'):
                    r=ctx.request.get(url+'/auth/'+kind)
                    check('legal access during maintenance '+kind,r.status==200 and 'data-policy="'+kind+'"' in r.text())
            for kind in ('terms','privacy'):
                gp.goto(url+'/auth/'+kind)
                check('active policy tab '+kind,gp.locator('.legal-tabs [aria-current="page"]').get_attribute('href')=='/auth/'+kind)
                check('policy anchors resolve '+kind,gp.locator('.legal-toc a').evaluate_all('(xs)=>xs.every(x=>document.getElementById(x.hash.slice(1)))'))
                for width in (320,390,768,1440):
                    gp.set_viewport_size({'width':width,'height':900})
                    check('policy no overflow '+kind+str(width),gp.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                    check('policy readable font '+kind+str(width),gp.locator('.legal-document').evaluate('(x)=>parseFloat(getComputedStyle(x).fontSize)>=16'))
                gp.set_viewport_size({'width':1440,'height':1000});gp.screenshot(path=str(OUT/(kind+'-desktop.png')),full_page=True)
                gp.set_viewport_size({'width':390,'height':844});gp.screenshot(path=str(OUT/(kind+'-mobile.png')),full_page=True)
                gp.add_style_tag(content='html{font-size:200%} .legal-document{font-size:200%}')
                check('policy 200 percent no overflow '+kind,gp.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            gp.goto(url+'/')
'''
s=s.replace(anchor,anchor+'\n'+new)
s=s.replace("            (private/'accounts.json').write_text('invalid')", "            (private/'accounts.json').write_text('invalid')\n            check('legal disclosure survives corrupt account data',guest.request.get(url+'/auth/privacy').status==200 and guest.request.get(url+'/auth/terms').status==200)")
p.write_text(s)
p=R/'tests/auth/production_browser.py';s=p.read_text()
a="        check('privacy available',c.request.get(URL+'/auth/privacy').status==200)"
s=s.replace(a,'''        check('privacy available',c.request.get(URL+'/auth/privacy').status==200)
        legal_before=c.request.get(URL+'/auth/status').json()
        for kind,count in [('terms',16),('privacy',13)]:
            response=page.goto(URL+'/auth/'+kind,wait_until='networkidle')
            check('public full legal document '+kind,response.status==200 and page.locator('[data-policy="'+kind+'"]').count()==1)
            check('published legal body matches source '+kind,Path('auth/'+kind+'.html').read_text() in response.text())
            check('published sections complete '+kind,page.locator('.legal-body>section').count()==count+1)
            check('legal version '+kind,page.locator('[data-version="1.0"]').count()==1)
            check('legal table present '+kind,page.locator('table caption').count()>0)
            check('public legal text has no scripts '+kind,page.locator('script').count()==0)
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
        check('terms footer reachable from current home',page.locator('a[href="/auth/terms"],a[href="https://isegye-idol.kr/auth/terms"]').count()>0)
        check('privacy footer reachable from current home',page.locator('a[href="/auth/privacy"],a[href="https://isegye-idol.kr/auth/privacy"]').count()>0)''')
p.write_text(s)

for name,digest in NEW.items():
    if hashlib.sha256((R/name).read_bytes()).hexdigest()!=digest:
        raise RuntimeError('Generated source differs from reviewed bytes: '+name)
print('Four reviewed policy source/test files applied; no runtime data touched.')
