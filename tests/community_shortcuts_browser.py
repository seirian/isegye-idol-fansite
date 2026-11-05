"""Check exact production bundle community buttons without visiting third parties.

CI uses the promoted local HTTP artifact. Offline mode composes those files
in memory; neither mode visits third parties or bypasses real authentication.
"""
from pathlib import Path
import json, os, re, base64, hashlib
from playwright.sync_api import sync_playwright, expect
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'test-results/community-shortcuts'; OUT.mkdir(parents=True, exist_ok=True)
URL = os.getenv('PROMOTED_URL', 'http://preview.test/')
checks, errors = [], []
TARGETS = [('waktree','https://cafe.naver.com/steamindiegame'),('berriz','https://berriz.in/ko/isegyeidol')]

def check(name, ok):
    checks.append({'name':name,'passed':bool(ok)})
    assert ok, name

with sync_playwright() as pw:
    browser = pw.chromium.launch(**({'executable_path':os.environ['CHROMIUM_PATH']} if os.getenv('CHROMIUM_PATH') else {}))
    try:
        ctx = browser.new_context(viewport={'width':1440,'height':1000},locale='ko-KR',reduced_motion='reduce')
        ctx.route('https://**/*', lambda r:r.abort())
        ctx.route('**/api/*', lambda r:r.fulfill(status=503,content_type='application/json',body='{}'))
        page = ctx.new_page(); page.on('pageerror',lambda e:errors.append(str(e)))
        if os.getenv('PROMOTED_URL'):
            page.goto(URL+'#/home',wait_until='load')
        else:
            # In-memory rendering only: no attempt to work around disabled navigation.
            page.evaluate("""()=>{const d=new Map();Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>d.get(k)||null,setItem:(k,v)=>d.set(k,String(v)),removeItem:k=>d.delete(k)}})}""")
            dist=ROOT/'dist';html=(dist/'index.html').read_text();data=(dist/'src/data.js').read_text()
            def embed(m):
                return json.dumps('data:image/webp;base64,'+base64.b64encode((dist/m.group(1).split('?')[0]).read_bytes()).decode())
            data=re.sub(r'"(assets/[^" ]+\.webp(?:\?[^" ]*)?)"',embed,data)
            code='\n'.join(data if rel=='src/data.js' else (dist/rel).read_text() for rel in re.findall(r'<script src="([^"]+)"></script>',html))
            css=(dist/'src/styles.css').read_text()
            sha=lambda text:base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
            html=re.sub(r'<script src="[^"]+"></script>','',html)
            html=re.sub(r'<link rel="icon"[^>]+>','',html).replace('<link rel="stylesheet" href="src/styles.css">','<style>'+css+'</style>')
            html=html.replace("script-src 'self'", "script-src 'sha256-"+sha(code)+"'").replace("style-src 'self'", "style-src 'sha256-"+sha(css)+"'")
            page.set_content(html.replace('</body>','<script>'+code+'</script></body>'),wait_until='load')
        for theme in ('dark','light'):
            for width in (320,390,640,768,1024,1440,1920):
                page.set_viewport_size({'width':width,'height':1000})
                for route in ('home','members','schedule','music','live','content','history','guide','terms','privacy'):
                    prefix=f'{theme}/{width}/{route}'
                    page.evaluate('([theme,route])=>{prefs.theme=theme;persist();location.hash="#/"+route;render();scrollTo(0,0)}',[theme,route])
                    links=page.locator('.community-shortcuts a')
                    check(prefix+' exactly two shortcuts',links.count()==2)
                    check(prefix+' seven main menus unchanged',page.locator('.desktop-nav>a').count()==7)
                    check(prefix+' no horizontal document overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                    page.locator('.community-shortcuts img').evaluate_all('(xs)=>Promise.all(xs.map(x=>x.decode()))')
                    check(prefix+' decoded original logos',page.locator('.community-shortcuts img').evaluate_all('(xs)=>xs.every(x=>x.complete&&x.naturalWidth>=32&&x.width===28)'))
                    boxes=[]
                    for key,target in TARGETS:
                        el=page.locator('[data-community='+key+']');box=el.bounding_box();boxes.append(box)
                        check(prefix+'/'+key+' visible touch target',el.is_visible() and box['width']>=44 and box['height']>=44 and box['x']>=0 and box['x']+box['width']<=width)
                        check(prefix+'/'+key+' correct safe target',el.get_attribute('href')==target and el.get_attribute('target')=='_blank' and set(el.get_attribute('rel').split())=={'noopener','noreferrer'})
                    check(prefix+' separated buttons',boxes[0]['x']+boxes[0]['width']<boxes[1]['x'])
                    if width>640:
                        nav=page.locator('.desktop-nav').bounding_box()
                        check(prefix+' right of menu',boxes[0]['x']>=nav['x']+nav['width'])
                if width in (390,768,1440):
                    page.evaluate('()=>{location.hash="#/home";render();scrollTo(0,0)}')
                    page.locator('.site-header').screenshot(path=str(OUT/f'header-{theme}-{width}.png'))
                    if width==1440:page.screenshot(path=str(OUT/f'home-{theme}-{width}.png'))
        page.set_viewport_size({'width':1440,'height':1000})
        page.evaluate('()=>{location.hash="#/home";render();scrollTo(0,0)}')
        original=page.url
        for key,target in TARGETS:
            ctx.route(target,lambda r:r.fulfill(content_type='text/html',body='<title>External destination test</title>'))
            link=page.locator('[data-community='+key+']')
            link.focus();expect(link).to_be_focused()
            check(key+' visible keyboard focus',link.evaluate('el=>getComputedStyle(el).outlineStyle')!='none')
            if os.getenv('PROMOTED_URL'):
                with page.expect_popup() as pop:link.press('Enter')
                popup=pop.value;popup.wait_for_load_state('domcontentloaded')
                check(key+' new tab reaches requested URL',popup.url==target)
                check(key+' opener isolated',popup.evaluate('window.opener===null'))
                check(key+' fan page unchanged',page.url==original);popup.close()
        # Member legal documents reuse the same shell, without catalogue/API reads.
        docs=json.loads((ROOT/'dist/src/member-legal.json').read_text())['documents']
        base=URL.rstrip('/')
        ctx.route(base+'/account/legal.css',lambda r:r.fulfill(content_type='text/css',body=(ROOT/'dist/src/styles.css').read_text()))
        ctx.route(base+'/account/legal.js',lambda r:r.fulfill(content_type='text/javascript',body=(ROOT/'dist/src/member-legal.js').read_text()))
        ctx.route(base+'/auth/account.css',lambda r:r.fulfill(content_type='text/css',body=(ROOT/'auth/account.css').read_text()))
        for kind in ('terms','privacy'):
            ctx.route(base+'/account/'+kind,lambda r,kind=kind:r.fulfill(content_type='text/html',body=docs[kind]))
            for width in (390,1440):
                page.set_viewport_size({'width':width,'height':1000})
                if os.getenv('PROMOTED_URL'):
                    page.goto(base+'/account/'+kind,wait_until='load')
                else:
                    doc=docs[kind].replace('<script src="/account/legal.js"></script>','<script>'+(ROOT/'dist/src/member-legal.js').read_text()+'</script>')
                    doc=doc.replace('<link rel="stylesheet" href="/account/legal.css">','<style>'+(ROOT/'dist/src/styles.css').read_text()+'</style>')
                    doc=doc.replace('<link rel="stylesheet" href="/auth/account.css">','<style>'+(ROOT/'auth/account.css').read_text()+'</style>')
                    page.set_content(doc,wait_until='load')
                check(f'member/{kind}/{width} shared shortcuts',page.locator('.community-shortcuts a').count()==2)
                check(f'member/{kind}/{width} no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                check(f'member/{kind}/{width} logos decoded',page.locator('.community-shortcuts img').evaluate_all('(xs)=>xs.every(x=>x.complete&&x.naturalWidth>=32)'))
        check('no JavaScript errors',not errors)
    finally:
        (OUT/'result.json').write_text(json.dumps({'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'browserErrors':errors,'scope':('exact HTTP production bundle; popup destinations intercepted' if os.getenv('PROMOTED_URL') else 'exact artifact composed in memory; real navigation/popups deferred to CI')+'; member documents layout only, no real login'},ensure_ascii=False,indent=2)+'\n')
        browser.close()
print('Community shortcut checks:',len(checks))
