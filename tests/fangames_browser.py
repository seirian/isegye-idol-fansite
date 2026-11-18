#!/usr/bin/env python3
"""Exact offline HTTP build: real UI controls, read-only game diagnostics."""
from pathlib import Path
import hashlib, http.server, json, math, os, socketserver, threading, time
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'fangames-dist'
OUT=ROOT/'test-results/fangames'
OUT.mkdir(parents=True,exist_ok=True)
BUILD_HASH=hashlib.sha256((DIST/'review.html').read_bytes()).hexdigest()
report={'checks':[],'errors':[],'externalRequests':[],'screenshots':[],
        'inputPolicy':'Keyboard, mouse and CDP touch; CourierApp state only read',
        'visibilityCheck':'Synthetic window blur and hidden-document events',
        'storageFixtures':'Invalid localStorage and simulated denied Storage API','htmlSha256':BUILD_HASH}
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*a,**k):super().__init__(*a,directory=str(DIST),**k)
    def log_message(self,*a):pass
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=True
    daemon_threads=True
def ok(value,label):
    assert value,label
    report['checks'].append(label)
def shot(page,name,full_page=True):
    page.screenshot(path=str(OUT/(name+'.png')),full_page=full_page)
    report['screenshots'].append(name+'.png')
def state(page):
    return page.evaluate('''() => {const s=CourierApp.state;return s?{x:s.x,y:s.y,mode:s.mode,
      elapsed:s.elapsed,timeLeft:s.timeLeft,cargo:s.cargo,required:s.required,score:s.score,
      deliveries:s.deliveries,dashCooldown:s.dashCooldown,skillCooldown:s.skillCooldown,
      stats:s.stats,stars:s.stars.map(p=>({x:p.x,y:p.y,availableAt:p.availableAt})),
      enemies:s.enemies.map(p=>({x:p.x,y:p.y})),member:s.member}:null}''')
def art(page,selector):
    return page.locator(selector).evaluate('''c=>{const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
      let hash=2166136261,filled=0;for(let i=0;i<d.length;i+=16){hash=Math.imul(hash^d[i],16777619);
      hash=Math.imul(hash^d[i+1],16777619);if(d[i+3])filled++;}return{hash:hash>>>0,filled}}''')
def fit(page,label):
    width=page.viewport_size['width']
    measured=page.evaluate('({scroll:document.documentElement.scrollWidth,inner:innerWidth})')
    ok(measured['scroll']<=width+1,label+' '+str(measured))
def open_page(browser,origin,width=1440,height=1000,init=None):
    context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=1,
                                has_touch=width<=768,is_mobile=width<=768)
    if init:context.add_init_script(init)
    page=context.new_page()
    page.on('pageerror',lambda e:report['errors'].append(str(e)))
    page.on('console',lambda m:report['errors'].append(m.text) if m.type=='error' and 'Content Security Policy' in m.text else None)
    def route(r):
        if r.request.url.startswith(origin+'/') or r.request.url.startswith('data:'):r.continue_()
        else:report['externalRequests'].append(r.request.url);r.abort()
    page.route('**/*',route)
    page.goto(origin+'/review.html',wait_until='domcontentloaded')
    page.wait_for_function('() => window.CourierApp?.ready===true',timeout=20000)
    page.locator('#start-button').wait_for(state='visible')
    return context,page
def start(page):
    page.locator('#start-button').click()
    page.wait_for_function('() => CourierApp.state?.elapsed>0',timeout=7000)
    ok(page.locator('#arena').evaluate('e=>document.activeElement===e'),'start focuses keyboard game board')
def touch(page,selector,direction=None):
    page.locator(selector).scroll_into_view_if_needed()
    b=page.locator(selector).bounding_box();x=b['x']+b['width']/2;y=b['y']+b['height']/2
    cdp=page.context.new_cdp_session(page)
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
    if direction:cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+direction[0]*b['width']*.32,'y':y+direction[1]*b['height']*.32}]})
    page.wait_for_timeout(300)
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});cdp.detach()
def autoplay(page):
    held=set();upgrades=0;deadline=time.monotonic()+85
    def release():
        for k in list(held):page.keyboard.up(k)
        held.clear()
    while time.monotonic()<deadline:
        s=state(page)
        if s['mode'] in ('won','lost'):
            release();page.locator('#retry-button').wait_for(state='visible');return s,upgrades
        if s['mode']=='upgrade':
            release();page.locator('.upgrade-option').first.wait_for(state='visible')
            if upgrades==0:
                remaining=s['timeLeft'];page.wait_for_timeout(350)
                ok(state(page)['timeLeft']==remaining,'upgrade choice freezes timer')
                ok(page.locator('.upgrade-option').count()==3,'delivery offers three upgrades')
                shot(page,'upgrade-1440')
            page.get_by_role('button',name='가벼운 운동화').click();upgrades+=1
            page.wait_for_function("() => CourierApp.state.mode==='playing'");continue
        candidates=[p for p in s['stars'] if p['availableAt']<=s['elapsed']]
        if s['cargo']>=s['required']:target={'x':480,'y':320}
        elif candidates:target=min(candidates,key=lambda p:math.hypot(p['x']-s['x'],p['y']-s['y']))
        else:page.wait_for_timeout(80);continue
        dx=target['x']-s['x'];dy=target['y']-s['y'];wanted=set()
        if abs(dx)>14:wanted.add('ArrowRight' if dx>0 else 'ArrowLeft')
        if abs(dy)>14:wanted.add('ArrowDown' if dy>0 else 'ArrowUp')
        for k in held-wanted:page.keyboard.up(k)
        for k in wanted-held:page.keyboard.down(k)
        held=wanted
        if s['skillCooldown']<=0:page.keyboard.press('e')
        if s['dashCooldown']<=0 and math.hypot(dx,dy)>135:page.keyboard.press('Space')
        page.wait_for_timeout(75)
    release();raise AssertionError('UI delivery did not finish within 85 seconds')
def run(browser,origin):
    # Capture all requested layouts before the longer play-through.
    for width,height in ((1440,1000),(390,844),(320,720),(768,1024)):
        context,page=open_page(browser,origin,width,height)
        try:
            ok(page.locator('.member-card').count()==6,f'six couriers at {width}')
            ok(art(page,'#hero-background')['filled']>50000,f'generated plaza painted at {width}')
            ok(art(page,'#hero-character')['filled']>1000,f'generated courier painted at {width}')
            fit(page,f'lobby fits {width}px');shot(page,f'lobby-{width}')
            start(page);fit(page,f'playfield fits {width}px');initial=state(page)
            if width<=768:
                touch(page,'#joystick',(1,0));ok(state(page)['x']>initial['x']+30,f'touch joystick moves at {width}')
                y=state(page)['y'];touch(page,'[data-direction="up"]')
                ok(state(page)['y']<y-30,f'touch dpad moves at {width}')
                a=state(page);page.wait_for_timeout(150);b=state(page)
                ok(math.hypot(b['x']-a['x'],b['y']-a['y'])<1,f'touch release stops movement at {width}')
            else:
                page.keyboard.down('ArrowRight');page.wait_for_timeout(350);page.keyboard.up('ArrowRight')
                ok(state(page)['x']>initial['x']+40,f'keyboard moves at {width}')
            shot(page,f'playing-{width}');page.locator('#pause-button').click();shot(page,f'paused-{width}')
        except Exception:shot(page,f'failure-{width}');raise
        finally:context.close()
    context,page=open_page(browser,origin)
    try:
        fingerprints=[]
        for name in ('아이네','징버거','릴파','주르르','고세구','비챤'):
            page.get_by_role('button',name=name+' 선택',exact=True).click()
            ok(page.locator('#member-name').inner_text()==name and name in page.locator('#hero-character').get_attribute('aria-label'),name+' selection updates identity')
            ok(page.locator('.member-card[aria-pressed=true]').count()==1,name+' has single active selection')
            fingerprints.append(art(page,'#hero-character')['hash'])
        ok(len(set(fingerprints))==6,'six selections paint different generated artwork')
        page.get_by_role('button',name='아이네 선택',exact=True).click()
        page.locator('#how-button').focus();page.keyboard.press('Enter')
        ok(page.locator('#how-dialog').is_visible(),'keyboard opens help dialog')
        page.keyboard.press('Escape');ok(not page.locator('#how-dialog').is_visible(),'Escape closes help')
        ok(page.locator('#how-button').evaluate('e=>document.activeElement===e'),'help restores opener focus')
        start(page)
        page.keyboard.press('Space');a=state(page)
        ok(a['dashCooldown']>0 and a['stats']['dashes']==1,'Space activates dash with cooldown')
        page.keyboard.press('Space');ok(state(page)['stats']['dashes']==1,'dash cannot repeat during cooldown')
        page.locator('#skill-button').click();a=state(page)
        ok(a['skillCooldown']>0 and a['stats']['skills']==1,'skill button activates member power')
        page.keyboard.press('e');ok(state(page)['stats']['skills']==1,'member skill respects cooldown')
        page.locator('#sound-button').focus();page.keyboard.press('Space')
        ok(page.locator('#sound-button').get_attribute('aria-pressed')=='true','Space activates focused sound button without gameplay shortcut')
        page.keyboard.press('Space')
        page.locator('#pause-button').focus();page.keyboard.press('Space');page.locator('#resume-button').wait_for(state='visible')
        a=state(page);page.wait_for_timeout(300);b=state(page)
        ok(a['elapsed']==b['elapsed'] and a['enemies']==b['enemies'],'pause freezes timer and enemies')
        ok(page.locator('#resume-button').evaluate('e=>document.activeElement===e'),'pause focuses resume button')
        page.keyboard.press('Enter');page.wait_for_function('() => CourierApp.state.elapsed>'+str(a['elapsed']))
        page.keyboard.down('ArrowRight');page.evaluate("window.dispatchEvent(new Event('blur'))");page.keyboard.up('ArrowRight')
        ok(page.locator('#resume-button').is_visible(),'window blur pauses active game')
        page.locator('#resume-button').click();a=state(page);page.wait_for_timeout(170)
        ok(state(page)['x']==a['x'],'resume clears keys held before blur')
        page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));delete document.hidden")
        ok(page.locator('#resume-button').is_visible(),'hidden-document event pauses active game')
        page.locator('#resume-button').click()
        result,upgrades=autoplay(page)
        report['gameplayOutcome']={'mode':result['mode'],'deliveries':result['deliveries'],'score':result['score'],'upgrades':upgrades}
        ok(result['mode'] in ('won','lost') and upgrades>=1,'UI gameplay reaches an upgrade and a real terminal result')
        ok(result['score']>0,'actual gameplay earns score');shot(page,'result-1440')
        for width,height in ((390,844),(320,720),(1280,720)):
            page.set_viewport_size({'width':width,'height':height})
            page.wait_for_timeout(150)
            page.locator('#result-home').scroll_into_view_if_needed()
            fit(page,f'result fits {width}px')
            bounds=page.locator('#arena-wrap').bounding_box();button=page.locator('#result-home').bounding_box()
            ok(button['y']+button['height']<=bounds['y']+bounds['height']+2,f'result actions are not clipped at {width}px')
            ok(page.locator('#result-home').evaluate('e=>{const r=e.getBoundingClientRect();const hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return e===hit||e.contains(hit)}'),f'result home button receives pointer at {width}px')
            shot(page,f'result-{width}',full_page=width!=1280)
        earned=result['score'];page.locator('#retry-button').click()
        ok(state(page)['score']==0 and state(page)['deliveries']==0,'retry button works in short 1280x720 viewport and resets run')
        page.set_viewport_size({'width':1440,'height':1000})
        page.reload(wait_until='domcontentloaded');page.wait_for_function('() => window.CourierApp?.ready')
        ok(str(earned) in page.locator('#best-label').inner_text().replace(',',''),'earned best score survives reload')
        page.get_by_role('button',name='고세구 선택',exact=True).click();page.reload(wait_until='domcontentloaded')
        page.wait_for_function('() => window.CourierApp?.ready');ok(page.locator('#member-name').inner_text()=='고세구','selected courier survives reload')
    except Exception:shot(page,'failure-playthrough');raise
    finally:context.close()
    fixtures=[('invalid',"localStorage.setItem('isegye:review:courier:v2',JSON.stringify({version:2,best:-9,runs:-2,selected:'unknown'}))"),
              ('denied',"Storage.prototype.getItem=function(){throw new DOMException('denied','SecurityError')};Storage.prototype.setItem=function(){throw new DOMException('denied','QuotaExceededError')}")]
    for label,init in fixtures:
        context,page=open_page(browser,origin,390,844,init)
        try:
            ok(page.locator('#member-name').inner_text()=='아이네',label+' storage uses valid default courier')
            ok('최고 기록 -' not in page.locator('#best-label').inner_text(),label+' storage avoids invalid score')
            if label=='denied':ok('사용할 수 없어요' in page.locator('#best-label').inner_text(),'blocked storage is explained')
            start(page);ok(state(page)['mode']=='playing',label+' storage does not prevent play')
        finally:context.close()
server=Server(('127.0.0.1',0),Handler);origin=f'http://127.0.0.1:{server.server_address[1]}'
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
    with sync_playwright() as p:
        launch={'headless':True,'args':['--no-sandbox']}
        if os.getenv('CHROMIUM_PATH'):launch['executable_path']=os.environ['CHROMIUM_PATH']
        browser=p.chromium.launch(**launch)
        try:
            run(browser,origin)
            ok(not report['externalRequests'],'offline game requests no external resources')
            ok(not report['errors'],'no JavaScript or CSP errors');report['status']='passed'
        finally:browser.close()
except Exception as error:
    report['status']='failed';report['failure']=str(error);raise
finally:
    server.shutdown();server.server_close()
    report['buildUnchanged']=BUILD_HASH==hashlib.sha256((DIST/'review.html').read_bytes()).hexdigest()
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'checks':len(report['checks']),'errors':report['errors'],'screenshots':len(report['screenshots'])},ensure_ascii=False))
