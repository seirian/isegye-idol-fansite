"""Real local TLS/PHP game authorization using synthetic fixture identities only."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'tests/auth/browser.py').read_text()
def once(old,new):
    global source
    if source.count(old)!=1:raise ValueError('RPG auth fixture anchor moved')
    source=source.replace(old,new,1)
once("OUT=ROOT/'test-results/auth'","OUT=ROOT/'test-results/rpg-auth'")
once("str(ROOT/'tests/auth/fixture_router.php')","str(ROOT/'tests/review_host_fixture.php')")
once("    signing=base/'signing.pem';cert=base/'cert.pem'",'''    import sys
    sys.path.insert(0,str(ROOT/'scripts'))
    import build_rpg_production as rpg
    (app/'build-info.json').write_text(json.dumps({'mode':'preview'}))
    game=rpg.build(app);raw=(app/rpg.HTML_PATH).read_bytes()
    signing=base/'signing.pem';cert=base/'cert.pem' ''')
once("            check('public visit does not create member cookie',not guest.cookies())",'''            check('public visit does not create member cookie',not guest.cookies())
            check('RPG follows existing open-site policy',guest.request.get(url+rpg.ROUTE).body()==raw)
            check('RPG does not create an account cookie',not guest.cookies())
            response=guest.request.get(url+rpg.ROUTE.rstrip('/'),max_redirects=0)
            check('RPG canonical slash',response.status==308 and response.headers.get('location')==rpg.ROUTE)
            check('RPG HEAD body omitted',guest.request.head(url+rpg.ROUTE).body()==b'')
            check('RPG POST denied',guest.request.post(url+rpg.ROUTE,data={}).status==405)''')
once("            op.goto(url+'/auth/login');csrf=op.locator('input[name=csrf]').input_value()",'''            for route in (rpg.ROUTE,'/'+rpg.HTML_PATH,*('/'+p for p in game['cardAssets'])):
                for who,context in (('guest',guest),('member',member)):
                    response=context.request.get(url+route)
                    check('RPG maintenance blocks '+who+' '+route,response.status==503 and b'const RPG_ART' not in response.body())
            response=owner.request.get(url+rpg.ROUTE)
            check('RPG admin receives exact artifact',response.status==200 and response.body()==raw)
            check('RPG MIME',response.headers.get('content-type')=='text/html; charset=utf-8')
            check('RPG no-store','no-store' in response.headers.get('cache-control',''))
            check('RPG iframe denial',response.headers.get('x-frame-options')=='DENY')
            check('RPG direct HTML alias',owner.request.get(url+'/'+rpg.HTML_PATH).body()==raw)
            for route in ('/_isegye_releases/'+release+'/'+rpg.HTML_PATH,'/games/ipari-chronicle/app.js','/games/ipari-chronicle/other.html'):
                check('RPG unlisted path blocked '+route,owner.request.get(url+route).status==404)
            game_file=app/rpg.HTML_PATH;game_file.unlink();game_file.symlink_to(private/'accounts.json')
            check('RPG symlink blocked',owner.request.get(url+rpg.ROUTE).status==404)
            game_file.unlink();game_file.write_bytes(raw)
            op.goto(url+'/');op.evaluate("localStorage.setItem('isegye:playground:v1','KEEP_QUIZ');localStorage.setItem('isegye:playground:courier:v2','KEEP_COURIER')")
            errors=[];op.on('pageerror',lambda e:errors.append(str(e)))
            op.goto(url+rpg.ROUTE);op.locator('[data-action=start]').click()
            for _ in range(4):op.locator('[data-action=dialogue-next]').click()
            check('RPG real host runs under CSP',op.locator('#game-main').get_attribute('data-mode')=='explore' and not errors)
            check('RPG one standalone document',op.locator('header').count()==1 and op.locator('iframe').count()==0)
            check('RPG preserves other games',op.evaluate("localStorage.getItem('isegye:playground:v1')==='KEEP_QUIZ'&&localStorage.getItem('isegye:playground:courier:v2')==='KEEP_COURIER'"))
            op.locator('[data-rpg-return]').click();op.wait_for_url(url+'/#/playground')
            check('RPG returns to existing app','PROTECTED_SITE_FIXTURE' in op.content())
            op.goto(url+'/auth/login');csrf=op.locator('input[name=csrf]').input_value()''')
exec(compile(source,str(ROOT/'tests/auth/browser.py'),'exec'),{'__name__':'__main__','__file__':str(ROOT/'tests/auth/browser.py')})
