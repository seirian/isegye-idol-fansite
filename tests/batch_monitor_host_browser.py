"""Exercise the exact generated gateway and UI using local synthetic identities."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'tests/auth/browser.py').read_text()
def once(old,new):
    global source
    if source.count(old)!=1:raise ValueError('Auth fixture anchor changed: '+old[:60])
    source=source.replace(old,new,1)
once("OUT=ROOT/'test-results/auth'","OUT=ROOT/'test-results/batch-monitor'")
once("str(ROOT/'tests/auth/fixture_router.php')","str(ROOT/'tests/review_host_fixture.php')")
once("    signing=base/'signing.pem';cert=base/'cert.pem'",'''    sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'tests'))
    from playwright.sync_api import expect
    from test_batch_monitor import fixture_snapshot
    from deploy_batch_monitor import release_payload
    from datetime import datetime,timedelta,timezone
    monitor_doc=fixture_snapshot()
    def install_monitor(doc):
        rel,files,point=release_payload(doc)
        directory=base/'.batch-monitoring'/'releases'/rel;directory.mkdir(parents=True,exist_ok=True)
        for name,raw in files.items():(directory/name).write_bytes(raw)
        (base/'.batch-monitoring/active.json').write_bytes(point)
        return directory
    monitor_directory=install_monitor(monitor_doc)
    signing=base/'signing.pem';cert=base/'cert.pem' ''')
once("            check('public visit does not create member cookie',not guest.cookies())",'''            check('public visit does not create member cookie',not guest.cookies())
            for path in ('/ops/batches/','/ops/batches/data.json','/ops/batches/monitor.js','/ops/batches/monitor.css'):
                check('monitor anonymous blocked '+path,guest.request.get(url+path,max_redirects=0).status==(303 if path=='/ops/batches/' else 401))
            check('monitor guest read does not create cookie',not guest.cookies())''')
once("            check('member is not administrator',member.request.get(url+'/auth/status').json()['administrator'] is False)",'''            check('member is not administrator',member.request.get(url+'/auth/status').json()['administrator'] is False)
            for path in ('/ops/batches','/ops/batches/','/ops/batches/data.json','/ops/batches/monitor.js','/ops/batches/monitor.css'):
                check('monitor ordinary member denied while public site open '+path,member.request.get(url+path,max_redirects=0).status==(303 if path in ('/ops/batches','/ops/batches/') else 403))
                check('monitor query role cannot grant access '+path,member.request.get(url+path+'?role=admin',max_redirects=0).status==(303 if path in ('/ops/batches','/ops/batches/') else 403))
            check('monitor forged role header denied',member.request.get(url+'/ops/batches/data.json',headers={'X-Role':'admin','X-Admin':'true'}).status==403)''')
once("            op.goto(url+'/auth/login');csrf=op.locator('input[name=csrf]').input_value()",'''            for path in ('/ops/batches/','/ops/batches/data.json','/ops/batches/monitor.js','/ops/batches/monitor.css'):
                check('monitor member blocked '+path,member.request.get(url+path,max_redirects=0).status==(303 if path in ('/ops/batches','/ops/batches/') else 403))
                check('monitor administrator allowed '+path,owner.request.get(url+path).status==200)
            response=owner.request.get(url+'/ops/batches/data.json')
            check('monitor no-store','no-store' in response.headers['cache-control'])
            check('monitor robots exclusion','noindex' in response.headers['x-robots-tag'])
            check('monitor exact snapshot',response.json()==monitor_doc)
            check('monitor HEAD empty',owner.request.head(url+'/ops/batches/data.json').body()==b'')
            check('monitor POST denied',owner.request.post(url+'/ops/batches/data.json',data={}).status==405)
            check('monitor private data blocked',owner.request.get(url+'/.batch-monitoring/active.json').status==404)
            errors=[];op.on('pageerror',lambda error:errors.append(str(error)))
            op.goto(url+'/ops/batches/');op.locator('#rows tr').nth(7).wait_for()
            check('monitor displays eight real categories',op.locator('#rows tr').count()==8)
            check('monitor scheduled production notice visible','10분 간격' in op.locator('.notice').inner_text())
            check('monitor heatmap generated',op.locator('.cell').count()>=144)
            op.screenshot(path=str(OUT/'desktop.png'),full_page=True)
            op.locator('button[data-filter="attention"]').click()
            check('monitor attention filter',0<op.locator('#rows tr').count()<8)
            op.locator('button[data-filter="all"]').click()
            op.locator('.detail-btn').first.click()
            check('monitor accessible detail modal',op.locator('#detail').evaluate('(e)=>e.open'))
            op.screenshot(path=str(OUT/'detail.png'),full_page=True)
            op.keyboard.press('Escape');check('monitor Escape closes modal',not op.locator('#detail').evaluate('(e)=>e.open'))
            op.set_viewport_size({'width':390,'height':844});op.screenshot(path=str(OUT/'mobile.png'),full_page=True)
            check('monitor mobile has no page overflow',op.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            op.set_viewport_size({'width':1440,'height':1000})
            op.route(url+'/ops/batches/data.json',lambda route:route.abort())
            op.locator('#refresh').click();expect(op.locator('#health')).to_contain_text('모니터링 상태 조회 실패')
            expect(op.locator('#summary [data-state="healthy"] strong')).to_have_text('0')
            check('monitor failed fetch not green',op.locator('#summary [data-state="healthy"] strong').inner_text()=='0')
            op.unroute(url+'/ops/batches/data.json')
            stale=fixture_snapshot(datetime.now(timezone.utc)-timedelta(hours=2));install_monitor(stale)
            op.locator('#refresh').click();expect(op.locator('#summary [data-state="unknown"] strong')).to_have_text('8')
            check('monitor stale data never green',op.locator('#summary [data-state="healthy"] strong').inner_text()=='0')
            malicious=fixture_snapshot();malicious['batches'][0]['note']='<img src=x onerror=alert(1)>'
            install_monitor(malicious);op.locator('#refresh').click();expect(op.locator('#refresh')).to_be_enabled()
            op.locator('button[aria-label="음반 · 멜론 차트 상세"]').click()
            check('monitor report text cannot inject markup',op.locator('#detail img').count()==0)
            op.keyboard.press('Escape')
            (monitor_directory/'data.json').write_text('broken');(base/'.batch-monitoring/active.json').write_bytes(release_payload(monitor_doc)[2])
            check('monitor corrupt snapshot fails closed',owner.request.get(url+'/ops/batches/data.json').status==503)
            install_monitor(monitor_doc)
            import batch_monitor_ux_checks
            batch_monitor_ux_checks.verify(check,owner,member,op,url,new,token,OUT)
            import batch_monitor_reliability_checks
            batch_monitor_reliability_checks.verify(check,op,install_monitor,fixture_snapshot,OUT)
            check('monitor no browser exceptions',not errors)
            check('monitor leaves production UI intact','PROTECTED_SITE_FIXTURE' in owner.request.get(url+'/').text())
            op.goto(url+'/auth/login');csrf=op.locator('input[name=csrf]').input_value()''')
exec(compile(source,str(ROOT/'tests/auth/browser.py'),'exec'),{'__name__':'__main__','__file__':str(ROOT/'tests/auth/browser.py')})
