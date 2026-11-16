"""Run unchanged auth tests plus the real protected quiz-bank route using synthetic accounts."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'tests/auth/browser.py').read_text()
def once(old,new):
 global source
 assert source.count(old)==1,'Fixture anchor moved: '+old[:60]
 source=source.replace(old,new,1)
once("OUT=ROOT/'test-results/auth'","OUT=ROOT/'test-results/playground-bank-auth'")
once("str(ROOT/'tests/auth/fixture_router.php')","str(ROOT/'tests/review_host_fixture.php')")
once("    signing=base/'signing.pem';cert=base/'cert.pem'",'''    import sys
    sys.path.insert(0,str(ROOT/'scripts'))
    import playground_bank as bank
    from datetime import datetime,timezone
    seed=bank.seed();(app/'src/playground-seed.json').write_bytes(bank.encoded(seed))
    (app/'src/playground-admin.js').write_text('export const administratorOnly=true;')
    folder=base/'.playground-bank';folder.mkdir(mode=0o700);(folder/'.owner').write_bytes(b'isegye-playground-bank:v1'+bytes([10]))
    bank_doc,_=bank.assemble(None,[],datetime.now(timezone.utc));bank_raw=bank.encoded(bank_doc)
    bank_file=folder/'current.json';bank_file.write_bytes(bank_raw)
    signing=base/'signing.pem';cert=base/'cert.pem' ''')
once("            check('public visit does not create member cookie',not guest.cookies())",'''            check('public visit does not create member cookie',not guest.cookies())
            check('quiz API follows public-before-maintenance policy',guest.request.get(url+'/api/playground').body()==bank_raw)
            check('quiz API never creates member cookie',not guest.cookies())
            check('quiz reference module guest blocked',guest.request.get(url+'/src/playground-admin.js').status==401)
            check('quiz HEAD no body',guest.request.head(url+'/api/playground').body()==b'')
            check('quiz POST blocked',guest.request.post(url+'/api/playground',data={}).status==405)''')
once("            op.goto(url+'/auth/login');csrf=op.locator('input[name=csrf]').input_value()",'''            check('quiz reference module member blocked',member.request.get(url+'/src/playground-admin.js').status==403)
            check('quiz reference module administrator allowed',owner.request.get(url+'/src/playground-admin.js').status==200)
            check('quiz maintenance anonymous denied',guest.request.get(url+'/api/playground').status==503)
            check('quiz maintenance member denied',member.request.get(url+'/api/playground').status==503)
            response=owner.request.get(url+'/api/playground')
            check('quiz administrator exact catalog',response.body()==bank_raw)
            check('quiz API no-store','no-store' in response.headers['cache-control'])
            check('quiz raw private bank denied',owner.request.get(url+'/.playground-bank/current.json').status==404)
            tampered=json.loads(bank_raw);tampered['sha256']='0'*64;bank_file.write_bytes(bank.encoded(tampered))
            check('quiz invalid digest uses seed',owner.request.get(url+'/api/playground').json()['fallback'] is True)
            bank_file.write_bytes(b'{')
            check('quiz corruption uses compiled seed',owner.request.get(url+'/api/playground').json()['fallback'] is True)
            bank_file.unlink();bank_file.symlink_to(private/'accounts.json')
            fallback=owner.request.get(url+'/api/playground').json()
            check('quiz symlink never exposes accounts',fallback['fallback'] is True and len(fallback['catalog']['questions'])==80 and 'accounts' not in fallback)
            bank_file.unlink();bank_file.write_bytes(bank_raw)
            check('quiz route leaves production root intact','PROTECTED_SITE_FIXTURE' in owner.request.get(url+'/').text())
            op.goto(url+'/auth/login');csrf=op.locator('input[name=csrf]').input_value()''')
exec(compile(source,str(ROOT/'tests/auth/browser.py'),'exec'),{'__name__':'__main__','__file__':str(ROOT/'tests/auth/browser.py')})
