"""Original auth suite plus album feed/image tests using synthetic loopback identities."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'tests/auth/browser.py').read_text()
def once(before,after):
    global source
    assert source.count(before)==1,'Auth fixture anchor changed: '+before[:60]
    source=source.replace(before,after,1)
once("OUT=ROOT/'test-results/auth'", "OUT=ROOT/'test-results/albums-feed'")
once("str(ROOT/'tests/auth/fixture_router.php')", "str(ROOT/'tests/review_host_fixture.php')")
once("    signing=base/'signing.pem';cert=base/'cert.pem'", """    import io
    from PIL import Image
    image_buffer=io.BytesIO();Image.new('RGB',(2,2)).save(image_buffer,format='WEBP')
    image_raw=image_buffer.getvalue();image_sha=hashlib.sha256(image_raw).hexdigest()
    feed=base/'.albums-feed';feed.mkdir(mode=0o700);(feed/'assets').mkdir()
    (feed/'.owner').write_bytes(b'isegye-daily-albums:v1\\n')
    image_file=feed/'assets'/(image_sha+'.webp');image_file.write_bytes(image_raw)
    feed_raw=json.dumps({'schemaVersion':1,'feed':'daily-albums','generatedAt':'2026-11-09T17:00:00+00:00','tracks':{},'providers':{},'assets':{'covers':{image_sha:{'sha256':image_sha,'path':'albums/asset-cache/'+image_sha+'.webp'}}}}).encode()
    feed_file=feed/'current.json';feed_file.write_bytes(feed_raw)
    asset_route='/api/albums/assets/'+image_sha+'.webp'
    signing=base/'signing.pem';cert=base/'cert.pem'""")
once("            check('public visit does not create member cookie',not guest.cookies())", """            check('public visit does not create member cookie',not guest.cookies())
            check('album feed follows public mode before maintenance',guest.request.get(url+'/api/albums').body()==feed_raw)
            check('public album image readback',guest.request.get(url+asset_route).body()==image_raw)
            check('album read creates no member cookie',not guest.cookies())""")
once("            op.goto(url+'/auth/login');csrf=op.locator('input[name=csrf]').input_value()", """            for route in ['/api/albums',asset_route]:
                check('album maintenance anonymous '+route,guest.request.get(url+route).status==503)
                check('album maintenance member '+route,member.request.get(url+route).status==503)
                check('album HEAD no body '+route,owner.request.head(url+route).body()==b'')
                check('album POST denied '+route,owner.request.post(url+route,data={}).status==405)
            response=owner.request.get(url+'/api/albums')
            check('admin album exact snapshot',response.body()==feed_raw)
            check('album API no-store','no-store' in response.headers['cache-control'])
            check('admin album exact image',owner.request.get(url+asset_route).body()==image_raw)
            check('unknown album asset refused',owner.request.get(url+'/api/albums/assets/'+'0'*64+'.webp').status==404)
            check('direct private feed path refused',owner.request.get(url+'/.albums-feed/current.json').status==404)
            feed_file.write_bytes(b'{}')
            check('album malformed data fails closed',owner.request.get(url+'/api/albums').status==503)
            feed_file.unlink();feed_file.symlink_to(private/'accounts.json')
            check('album symlink fails closed',owner.request.get(url+'/api/albums').status==503)
            feed_file.unlink();feed_file.write_bytes(feed_raw)
            image_file.write_bytes(image_raw+b'changed')
            check('album image integrity enforced',owner.request.get(url+asset_route).status==503)
            image_file.write_bytes(image_raw)
            check('production root preserved','PROTECTED_SITE_FIXTURE' in owner.request.get(url+'/').text())
            op.goto(url+'/auth/login');csrf=op.locator('input[name=csrf]').input_value()""")
once("            check('logout never disables maintenance',guest.request.get(url+'/').status==503)", """            check('logout never disables maintenance',guest.request.get(url+'/').status==503)
            check('logged-out owner denied album feed',owner.request.get(url+'/api/albums').status==503)""")
exec(compile(source,str(ROOT/'tests/auth/browser.py'),'exec'),{'__name__':'__main__','__file__':str(ROOT/'tests/auth/browser.py')})
