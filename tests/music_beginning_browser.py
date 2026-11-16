"""Browser checks of the final operating series bundle; no real account writes."""
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from datetime import datetime,timezone
import json,os,threading
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test-results/music-beginning';OUT.mkdir(parents=True,exist_ok=True)
DOC=json.loads((ROOT/'catalog/music-beginning.json').read_text())
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'dist')))
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}/';checks=[]
def check(name,value):
    checks.append({'name':name,'passed':bool(value)})
    if not value:raise AssertionError(name)
try:
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=os.getenv('BROWSER_PATH') or None)
        ctx=browser.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith(url) else r.abort())
        for endpoint in ('schedule','music','history','albums'):
            ctx.route('**/api/'+endpoint,lambda r:r.fulfill(status=503,content_type='application/json',body='{}'))
        def go(route):
            page.goto(url+'#/'+route,wait_until='domcontentloaded')
            expect(page.locator('#main h1')).to_be_visible();page.evaluate('render()')
        go('content?tab=series')
        card=page.locator('a.series-card[href="#/series/music-beginning"]')
        expect(card.locator('h3')).to_have_text(DOC['title'])
        check('series listing exact requested copy',card.count()==1)
        check('old listing copy removed','처음 만나는 이세돌의 음악' not in page.locator('#main').inner_text())
        check('other series preserved',page.locator('a.series-card[href="#/series/festival-2025"]').count()==1)
        card.click();expect(page.locator('#main h1')).to_have_text(DOC['title'])
        check('old series URL retained',page.url.endswith('#/series/music-beginning'))
        cards=page.locator('[data-music-beginning-video]')
        check('exactly six video cards',cards.count()==6)
        check('ordered canonical video IDs',cards.evaluate_all('(nodes)=>nodes.map(n=>n.dataset.musicBeginningVideo)')==[r['videoId'] for r in DOC['videos']])
        check('no album or song primary links',page.locator('#main a[href^="#/album/"],#main a[href^="#/song/"]').count()==0)
        for row in DOC['videos']:
            item=page.locator('[data-music-beginning-video="'+row['videoId']+'"]')
            links=item.locator('a[target="_blank"]')
            check(row['songId']+' direct official originals',links.count()==3 and all(links.nth(i).get_attribute('href')==row['url'] for i in range(3)))
            check(row['songId']+' safe new tab',all(set((links.nth(i).get_attribute('rel') or '').split())>={'noopener','noreferrer'} for i in range(3)))
            check(row['songId']+' original channel and thumbnail',row['channelName'] in item.inner_text() and item.locator('img').get_attribute('src')=='https://i.ytimg.com/vi/'+row['videoId']+'/mqdefault.jpg')
        check('five MVs and correctly labelled special clip',page.locator('#main .badge').filter(has_text='Official MV').count()==5 and page.locator('#main .badge').filter(has_text='Official Special Clip').count()==1)
        check('no album records in sequence',page.evaluate("D.series.find(s=>s.id==='music-beginning').songIds.length===0"))
        page.locator('[data-music-beginning-video="JY-gJkMuJ94"] [data-save]').click()
        check('existing video bookmark identity',page.evaluate("prefs.favorites.includes('video:JY-gJkMuJ94')"))
        page.reload(wait_until='domcontentloaded');expect(page.locator('#main h1')).to_have_text(DOC['title'])
        check('bookmark remains after reload',page.evaluate("prefs.favorites.includes('video:JY-gJkMuJ94')"))
        for i,row in enumerate(DOC['videos']):
            go('video/'+row['videoId'])
            check(row['songId']+' video detail original',page.locator('#main a.button.primary').get_attribute('href')==row['url'])
            check(row['songId']+' sequence backlink',page.locator('#main a.series-card[href="#/series/music-beginning"]').count()==1)
            if i>0:check(row['songId']+' previous video',page.get_by_role('link',name='이전 연결 영상',exact=True).get_attribute('href')=='#/video/'+DOC['videos'][i-1]['videoId'])
            if i<5:check(row['songId']+' next video',page.get_by_role('link',name='다음 연결 영상',exact=True).get_attribute('href')=='#/video/'+DOC['videos'][i+1]['videoId'])
        feed={'schemaVersion':1,'feed':'daily-music','generatedAt':datetime.now(timezone.utc).isoformat(),'rows':[]}
        page.evaluate('(f)=>ProductionFeeds.applyMusic(f)',feed)
        check('daily feed preserves sequence',page.evaluate("D.series.find(s=>s.id==='music-beginning').videoIds")==[r['videoId'] for r in DOC['videos']])
        for width in (320,390,1440):
            page.set_viewport_size({'width':width,'height':1000})
            for route in ('content?tab=series','series/music-beginning'):
                go(route)
                check(str(width)+' no overflow '+route,page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            if width in (390,1440):page.locator('#main').screenshot(path=str(OUT/f'series-{width}.png'))
        page.evaluate("prefs.theme='light';render()")
        check('light theme retains all six',page.locator('[data-music-beginning-video]').count()==6)
        page.locator('#main').screenshot(path=str(OUT/'series-light.png'))
        check('no JavaScript errors',not errors)
        check('full catalog retained',page.evaluate('D.videos.length')>26000)
        browser.close()
finally:
    server.shutdown()
    (OUT/'report.json').write_text(json.dumps({'checks':checks,'passed':sum(c['passed'] for c in checks),'total':len(checks)},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':sum(c['passed'] for c in checks),'total':len(checks)}))
