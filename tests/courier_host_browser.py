"""Exercise the exact game route through the real TLS/PHP gate with local fake identities."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'tests/auth/browser.py').read_text()

def once(old,new):
    global source
    if source.count(old)!=1:raise ValueError('Authentication fixture anchor moved: '+old[:60])
    source=source.replace(old,new,1)

once("OUT=ROOT/'test-results/auth'","OUT=ROOT/'test-results/courier-auth'")
once("str(ROOT/'tests/auth/fixture_router.php')","str(ROOT/'tests/review_host_fixture.php')")
once("    signing=base/'signing.pem';cert=base/'cert.pem'",'''    import sys
    sys.path.insert(0,str(ROOT/'scripts'))
    import build_courier_production as courier
    (app/'build-info.json').write_text(json.dumps({'mode':'preview','commit':'local-fixture'}))
    courier_meta=courier.build(app)
    courier_file=app/courier.HTML_PATH
    courier_raw=courier_file.read_bytes()
    signing=base/'signing.pem';cert=base/'cert.pem' ''')
once("            check('public visit does not create member cookie',not guest.cookies())",'''            check('public visit does not create member cookie',not guest.cookies())
            check('courier follows ordinary public-before-maintenance policy',guest.request.get(url+courier.ROUTE).body()==courier_raw)
            check('courier does not create a member cookie',not guest.cookies())
            canonical=guest.request.get(url+'/games/starlight-courier',max_redirects=0)
            check('courier canonical slash route',canonical.status==308 and canonical.headers.get('location')==courier.ROUTE)
            check('courier exact HTML alias',guest.request.get(url+'/'+courier.HTML_PATH).body()==courier_raw)
            check('courier HEAD omits body',guest.request.head(url+courier.ROUTE).body()==b'')
            check('courier POST rejected',guest.request.post(url+courier.ROUTE,data={}).status==405)
            check('courier unknown game is unavailable',guest.request.get(url+'/games/other/index.html').status==404)''')
once("            check('member is not administrator',member.request.get(url+'/auth/status').json()['administrator'] is False)",'''            check('member is not administrator',member.request.get(url+'/auth/status').json()['administrator'] is False)
            check('courier ordinary member allowed while site is open',member.request.get(url+courier.ROUTE).body()==courier_raw)''')
once("            op.goto(url+'/auth/login');csrf=op.locator('input[name=csrf]').input_value()",'''            for game_path in (courier.ROUTE,'/'+courier.HTML_PATH,*('/'+p for p in courier_meta['cardAssets'])):
                for who,context in (('guest',guest),('member',member)):
                    response=context.request.get(url+game_path)
                    check('courier maintenance blocks '+who+' '+game_path,response.status==503 and 'const COURIER_ART=' not in response.text())
            response=owner.request.get(url+courier.ROUTE)
            check('courier administrator exact artifact',response.status==200 and response.body()==courier_raw)
            check('courier HTML MIME',response.headers.get('content-type')=='text/html; charset=utf-8')
            check('courier keeps no-store policy','no-store' in response.headers.get('cache-control',''))
            check('courier keeps iframe denial',response.headers.get('x-frame-options')=='DENY')
            check('courier standalone omits duplicate account injection',b'/auth/client.js' not in response.body())
            check('courier private release bypass blocked',owner.request.get(url+'/_isegye_releases/'+release+'/'+courier.HTML_PATH).status==404)
            for unknown in ('/games/starlight-courier/extra.html','/games/starlight-courier/app.js','/games/another/'):
                check('courier exact file whitelist '+unknown,owner.request.get(url+unknown).status==404)
            for asset in courier_meta['cardAssets']:
                response=owner.request.get(url+'/'+asset)
                check('courier card art preserved '+asset,response.status==200 and response.body()==(app/asset).read_bytes())
            courier_file.unlink();courier_file.symlink_to(private/'accounts.json')
            response=owner.request.get(url+courier.ROUTE)
            check('courier symlink cannot expose member data',response.status==404 and 'accounts' not in response.text())
            courier_file.unlink();courier_file.write_bytes(courier_raw)
            op.goto(url+'/')
            op.evaluate("localStorage.setItem('isegye:review:courier:v2','KEEP_PREVIEW');localStorage.setItem('isegye:playground:v1','KEEP_QUIZ')")
            courier_errors=[]
            op.on('pageerror',lambda error:courier_errors.append(str(error)))
            op.goto(url+courier.ROUTE)
            op.locator('#start-button:not([disabled])').wait_for()
            check('courier generated art loads under real host CSP',op.locator('.member-card').count()==6)
            check('courier has no duplicate site header',op.locator('header').count()==1 and op.locator('iframe').count()==0)
            op.get_by_role('button',name='고세구 선택',exact=True).click()
            check('courier uses operating storage only',op.evaluate("JSON.parse(localStorage.getItem('isegye:playground:courier:v2'))?.selected==='gosegu' && localStorage.getItem('isegye:review:courier:v2')==='KEEP_PREVIEW' && localStorage.getItem('isegye:playground:v1')==='KEEP_QUIZ'"))
            check('courier has no JavaScript exceptions',not courier_errors)
            op.locator('a.wordmark').click();op.wait_for_url(url+'/#/playground')
            check('courier returns to existing site document','PROTECTED_SITE_FIXTURE' in op.content())
            op.goto(url+'/auth/login');csrf=op.locator('input[name=csrf]').input_value()''')
exec(compile(source,str(ROOT/'tests/auth/browser.py'),'exec'),{'__name__':'__main__','__file__':str(ROOT/'tests/auth/browser.py')})
