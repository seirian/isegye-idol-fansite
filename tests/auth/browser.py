"""Local TLS browser fixtures. Google responses are synthetic signed tokens, never real accounts."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import base64, hashlib, http.client, json, os, secrets, shutil, socket, ssl, subprocess, tempfile, threading, time
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'test-results/auth';OUT.mkdir(parents=True,exist_ok=True)
checks=[]
def check(name,ok):
    checks.append({'name':name,'passed':bool(ok)})
    if not ok:
        (OUT/'failure.json').write_text(json.dumps({'checks':checks},ensure_ascii=False,indent=2))
        raise AssertionError(name)
def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
with tempfile.TemporaryDirectory(prefix='isegye-auth-http-') as temp:
    base=Path(temp);private=base/'.auth-private';private.mkdir(mode=0o700);(private/'sessions').mkdir(mode=0o700)
    key=secrets.token_bytes(32);client='123456789-fixture.apps.googleusercontent.com'
    email_digest=hashlib.sha256(b'owner.fixture@gmail.com').hexdigest()
    import hmac
    config={'origin':'https://isegye-idol.kr','clientId':client,'siteKey':base64.b64encode(key).decode(),
            'adminEmailDigest':hmac.new(key,b'admin-email\0'+email_digest.encode(),hashlib.sha256).hexdigest()}
    (private/'config.json').write_text(json.dumps(config));(private/'accounts.json').write_text(json.dumps({'schema':1,'administrator':None,'accounts':{}}));(private/'accounts.lock').touch()
    for p in private.iterdir():p.chmod(0o700 if p.is_dir() else 0o600)
    release='r123456abcdef';app=base/'_isegye_releases'/release;(app/'src').mkdir(parents=True)
    (base/'.htaccess').write_text('# ISEGYE-AUTH-ROOT-V1 '+release+'\n')
    (app/'index.html').write_text('<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>Fixture</title></head><body><main id="app">PROTECTED_SITE_FIXTURE</main></body></html>')
    (app/'src/app.js').write_text('const PROTECTED_DATA_FIXTURE=1;')
    schedule_fixture={'schemaVersion':1,'timezone':'Asia/Seoul','generatedAt':'2026-10-30T00:00:00Z','sources':[],'events':[],'news':[],'forecasts':[]}
    (app/'src/schedule.json').write_text(json.dumps(schedule_fixture))
    signing=base/'signing.pem';cert=base/'cert.pem'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-keyout',str(signing),'-out',str(cert),'-days','1','-nodes','-subj','/CN=localhost'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    from cryptography.hazmat.primitives import serialization
    pub=serialization.load_pem_private_key(signing.read_bytes(),password=None).public_key().public_numbers()
    b64=lambda v:base64.urlsafe_b64encode(v.to_bytes((v.bit_length()+7)//8,'big')).decode().rstrip('=')
    jwk={'kty':'RSA','use':'sig','alg':'RS256','kid':'fixture-key','n':b64(pub.n),'e':b64(pub.e)}
    (private/'google-jwks.json').write_text(json.dumps({'fetched':int(time.time()),'expires':int(time.time())+3600,'keys':[jwk]}));(private/'google-jwks.json').chmod(0o600)
    backend_port,tls_port=port(),port();url=f'https://localhost:{tls_port}'
    env=dict(os.environ,ISEGYE_FIXTURE_ROOT=str(base),ISEGYE_FIXTURE_ORIGIN=url)
    php=subprocess.Popen(['php','-S',f'127.0.0.1:{backend_port}',str(ROOT/'tests/auth/fixture_router.php')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    class Proxy(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def forward(self):
            body=self.rfile.read(int(self.headers.get('Content-Length','0')))
            conn=http.client.HTTPConnection('127.0.0.1',backend_port,timeout=15)
            conn.request(self.command,self.path,body,dict(self.headers));r=conn.getresponse()
            data=r.read();self.send_response(r.status)
            for k,v in r.getheaders():
                if k.lower() not in ('connection','transfer-encoding','content-length'):self.send_header(k,v)
            self.send_header('Content-Length',str(len(data)));self.end_headers()
            if self.command!='HEAD':self.wfile.write(data)
            conn.close()
        do_GET=do_POST=do_HEAD=forward
    server=ThreadingHTTPServer(('127.0.0.1',tls_port),Proxy)
    sslctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);sslctx.load_cert_chain(cert,signing)
    server.socket=sslctx.wrap_socket(server.socket,server_side=True)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    mock="window.google={accounts:{id:{initialize:(x)=>{window.__login=x;},renderButton:(el)=>{const b=document.createElement('button');b.textContent='TEST GOOGLE';b.id='fixture-signin';b.onclick=()=>window.__login.callback({credential:window.__credential});el.appendChild(b);}}}};"
    shutil.copyfile(ROOT/'review/isegye-group-hero.webp',ROOT/'auth/background.webp')
    def token(nonce,subject,email,**changes):
        claims={'iss':'https://accounts.google.com','aud':client,'sub':subject,'email':email,'email_verified':True,'iat':int(time.time()),'exp':int(time.time())+3600,'nonce':nonce,'name':'DO_NOT_STORE','picture':'https://example.test/private.jpg'}
        claims.update(changes)
        return subprocess.check_output(['php',str(ROOT/'tests/auth/token.php'),str(signing)],input=json.dumps({'claims':claims}).encode()).decode()
    try:
        for _ in range(30):
            try:
                c=http.client.HTTPConnection('127.0.0.1',backend_port,timeout=1);c.request('GET','/');c.getresponse().read();c.close();break
            except OSError:time.sleep(.1)
        with sync_playwright() as p:
            browser=p.chromium.launch(**({'executable_path':os.getenv('CHROMIUM_PATH')} if os.getenv('CHROMIUM_PATH') else {}))
            contexts=[]
            def new():
                c=browser.new_context(ignore_https_errors=True,viewport={'width':1440,'height':1000},locale='ko-KR');contexts.append(c)
                c.route('https://accounts.google.com/gsi/client',lambda r:r.fulfill(body=mock,content_type='text/javascript'))
                return c,c.new_page()
            guest,gp=new();member,mp=new();owner,op=new()
            check('public root remains before administrator',gp.goto(url+'/').status==200 and 'PROTECTED_SITE_FIXTURE' in gp.content())
            check('public visit does not create member cookie',not guest.cookies())
            check('before admin there is no construction text','현재 사이트는' not in gp.content())
            check('schedule public only before first admin',guest.request.get(url+'/api/schedule').json()==schedule_fixture)
            check('schedule HEAD omits body',guest.request.head(url+'/api/schedule').body()==b'')
            check('schedule API never creates cookie',not guest.cookies())
            check('schedule POST rejected',guest.request.post(url+'/api/schedule',data={}).status==405)
            # Policy reading is public before/after maintenance and is not registration.
            for kind, count in [('terms',16),('privacy',13)]:
                response=gp.goto(url+'/auth/'+kind)
                check('policy before admin '+kind,response.status==200 and gp.locator('[data-policy="'+kind+'"]').count()==1)
                check('complete numbered policy '+kind,gp.locator('.legal-body>section').count()==count+1)
                check('policy has version '+kind,gp.locator('[data-version="1.0"]').count()==1)
                check('policy has no Google script '+kind,gp.locator('script').count()==0)
                check('policy top navigation has no account link '+kind,gp.locator('.legal-navigation a[href="/auth/login"]').count()==0)
                check('policy operator uses generic label '+kind,gp.locator('.legal-meta dd').first.inner_text()=='운영자')
                check('policy contains no standalone operator nickname '+kind,'seirian' not in gp.locator('.legal-document').inner_text().replace('seirian@gmail.com',''))
                check('policy does not set member cookies '+kind,not guest.cookies())
                check('policy HEAD has no body '+kind,guest.request.head(url+'/auth/'+kind).body()==b'')
                check('policy is read-only '+kind,guest.request.post(url+'/auth/'+kind,data={}).status==405)
            for alias,target in [('/terms','/auth/terms'),('/privacy','/auth/privacy'),('/settings/terms-of-service','/auth/terms'),('/settings/privacy-policy','/auth/privacy')]:
                response=guest.request.get(url+alias,max_redirects=0)
                check('policy alias '+alias,response.status==308 and response.headers.get('location')==target)
            def prepare(page,subject,email,**changes):
                page.goto(url+'/auth/login');page.locator('#fixture-signin').wait_for()
                nonce=page.locator('#google-signin').get_attribute('data-nonce')
                return token(nonce,subject,email,**changes)
            credential=prepare(mp,'member-subject','member.fixture@gmail.com')
            before=member.cookies()[0]['value']
            mp.evaluate('(t)=>window.__credential=t',credential);mp.locator('#fixture-signin').click();mp.wait_for_url(url+'/')
            check('Google callback automatically registers member','PROTECTED_SITE_FIXTURE' in mp.content())
            check('session rotated after login',member.cookies()[0]['value']!=before)
            cookie=member.cookies()[0]
            check('cookie secure and HttpOnly',cookie['secure'] and cookie['httpOnly'] and cookie['name']=='__Host-ISEGYE' and cookie['sameSite']=='Lax')
            check('ordinary signup does not close site',guest.request.get(url+'/').status==200)
            check('member is not administrator',member.request.get(url+'/auth/status').json()['administrator'] is False)
            bad=prepare(op,'owner-subject','owner.fixture@gmail.com',email_verified=False)
            csrf=op.locator('#google-signin').get_attribute('data-csrf')
            response=owner.request.post(url+'/auth/google',headers={'Origin':url,'X-CSRF-Token':csrf},data={'credential':bad})
            check('unverified administrator email rejected',response.status==401)
            check('failed Google identity cannot close site',guest.request.get(url+'/auth/status').json()['maintenance'] is False)
            good=prepare(op,'owner-subject','owner.fixture@gmail.com');csrf=op.locator('#google-signin').get_attribute('data-csrf')
            bad_origin=owner.request.post(url+'/auth/google',headers={'Origin':'https://evil.test','X-CSRF-Token':csrf},data={'credential':good})
            check('cross-origin login rejected',bad_origin.status==401)
            bad_csrf=owner.request.post(url+'/auth/google',headers={'Origin':url,'X-CSRF-Token':'wrong'},data={'credential':good})
            check('forged csrf rejected',bad_csrf.status==401)
            injected=owner.request.post(url+'/auth/google',headers={'Origin':url,'X-CSRF-Token':csrf},data={'credential':good,'role':'admin'})
            check('client-supplied privilege field rejected',injected.status==401)
            op.evaluate('(t)=>window.__credential=t',good);op.locator('#fixture-signin').click();op.wait_for_url(url+'/')
            check('designated verified administrator sees site','PROTECTED_SITE_FIXTURE' in op.content())
            status=owner.request.get(url+'/auth/status').json()
            check('first administrator signup enables construction',status['administrator'] and status['maintenance'] and status['allowed'])
            response=gp.goto(url+'/')
            check('anonymous maintenance HTTP status',response.status==503)
            check('anonymous receives construction wording','현재 사이트는 공사중입니다.' in ' '.join(gp.locator('h1').inner_text().split()))
            check('construction background loads',guest.request.get(url+'/auth/background.webp').status==200)
            check('maintenance omits legal navigation',gp.locator('a[href="/auth/terms"],a[href="/auth/privacy"]').count()==0)
            check('maintenance keeps Google login',gp.locator('a[href="/auth/login"]').count()==1)
            check('signed-in member maintenance also omits legal links','href="/auth/terms"' not in member.request.get(url+'/').text() and 'href="/auth/privacy"' not in member.request.get(url+'/').text())
            check('member is blocked after owner signup',member.request.get(url+'/').status==503)
            check('schedule API blocked for anonymous during maintenance',guest.request.get(url+'/api/schedule').status==503)
            check('schedule API blocked for member during maintenance',member.request.get(url+'/api/schedule').status==503)
            check('schedule API authorized administrator can read fallback',owner.request.get(url+'/api/schedule').json()==schedule_fixture)
            folder=base/'.schedule-feed';folder.mkdir(mode=0o700)
            current={**schedule_fixture,'generatedAt':'2026-10-30T01:00:00Z'}
            (folder/'current.json').write_text(json.dumps(current))
            check('schedule serves stored hourly feed',owner.request.get(url+'/api/schedule').json()==current)
            (folder/'current.json').write_text('broken')
            check('corrupt hourly feed falls back to built snapshot',owner.request.get(url+'/api/schedule').json()==schedule_fixture)
            (folder/'current.json').unlink();(folder/'current.json').symlink_to(private/'accounts.json')
            check('schedule symlink not served',owner.request.get(url+'/api/schedule').json()==schedule_fixture)
            (folder/'current.json').unlink()
            check('private feed file cannot be opened directly',owner.request.get(url+'/.schedule-feed/current.json').status==404)
            for path in ('/src/app.js','/_isegye_releases/'+release+'/src/app.js','/_isegye_idol/_isegye_releases/'+release+'/index.html','/.auth-private/accounts.json','/.auth-private/config.json','/access.php'):
                r=guest.request.get(url+path);check('no content leak '+path,r.status in (403,404,503) and 'PROTECTED_SITE_FIXTURE' not in r.text() and 'PROTECTED_DATA_FIXTURE' not in r.text() and config['siteKey'] not in r.text())
            check('owner can still fetch protected data',owner.request.get(url+'/src/app.js').status==200)
            check('owner direct legacy release URL also blocked',owner.request.get(url+'/_isegye_releases/'+release+'/src/app.js').status==404)
            check('privacy publicly reachable during maintenance',guest.request.get(url+'/auth/privacy').status==200)
            check('no-cache on maintenance','no-store' in response.headers['cache-control'])
            for ctx in (guest,member,owner):
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
                # Enlarge only the test DOM through CSSOM; keep the production CSP unchanged.
                gp.locator('.legal-document').evaluate("(x)=>{x.style.fontSize='32px'}")
                check('policy 200 percent body text applied '+kind,gp.locator('.legal-document').evaluate('(x)=>parseFloat(getComputedStyle(x).fontSize)===32'))
                check('policy 200 percent no overflow '+kind,gp.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            gp.goto(url+'/')

            for width in (320,390,768,1440):
                gp.set_viewport_size({'width':width,'height':900});gp.goto(url+'/')
                check(f'maintenance {width} no overflow',gp.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                check(f'maintenance {width} Google login remains reachable',gp.locator('a[href="/auth/login"]').is_visible())
            gp.set_viewport_size({'width':1440,'height':1000});gp.screenshot(path=str(OUT/'maintenance-desktop.png'),full_page=True)
            gp.set_viewport_size({'width':390,'height':844});gp.screenshot(path=str(OUT/'maintenance-mobile.png'),full_page=True)
            gp.goto(url+'/auth/login');gp.screenshot(path=str(OUT/'login-fixture.png'),full_page=True)
            check('maintenance page hides private owner email','owner.fixture@gmail.com' not in guest.request.get(url+'/').text())
            op.goto(url+'/auth/login');csrf=op.locator('input[name=csrf]').input_value()
            check('logout GET cannot end session',owner.request.get(url+'/auth/logout').status==403 and owner.request.get(url+'/auth/status').json()['administrator'])
            r=owner.request.post(url+'/auth/logout',form={'csrf':csrf},headers={'Origin':url},max_redirects=0)
            check('logout POST clears session',r.status==303 and not owner.request.get(url+'/auth/status').json()['authenticated'])
            check('logout never disables maintenance',guest.request.get(url+'/').status==503)
            saved=(private/'accounts.json').read_text()
            raw=saved+'\n'+''.join(x.read_text(errors='ignore') for x in (private/'sessions').glob('*'))
            for forbidden in ('owner.fixture@gmail.com','member.fixture@gmail.com','owner-subject','member-subject','DO_NOT_STORE',credential,good):check('identity not persisted '+forbidden[:24],forbidden not in raw)
            check('only two actual fixture accounts created',len(json.loads(saved)['accounts'])==2)
            (private/'accounts.json').write_text('invalid')
            check('legal disclosure survives corrupt account data',guest.request.get(url+'/auth/privacy').status==200 and guest.request.get(url+'/auth/terms').status==200)
            check('corrupt store never fails open',guest.request.get(url+'/').status==503 and 'PROTECTED_SITE_FIXTURE' not in guest.request.get(url+'/').text())
            (private/'accounts.json').write_text(saved)
            browser.close()
        (OUT/'browser.json').write_text(json.dumps({'scope':'loopback TLS; synthetic RSA-signed Google-claim fixtures only; no real Google users','passed':len(checks),'total':len(checks),'checks':checks},ensure_ascii=False,indent=2))
        print(json.dumps({'passed':len(checks),'total':len(checks)}))
    finally:
        php.terminate();php.wait(timeout=5);server.shutdown()
        (ROOT/'auth/background.webp').unlink(missing_ok=True)
