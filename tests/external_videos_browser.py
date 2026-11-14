"""Read-only browser checks of the exact composed operating bundle."""
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from datetime import datetime, timezone
import json, os, threading
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test-results/external-videos';OUT.mkdir(parents=True,exist_ok=True)
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
        page.on('pageerror',lambda e:errors.append(str(e)))
        ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith(url) else r.abort())
        for endpoint in ('schedule','music','history','albums'):
            ctx.route('**/api/'+endpoint,lambda r:r.fulfill(status=503,content_type='application/json',body='{}'))
        def go(route):
            page.goto(url+'#/'+route,wait_until='domcontentloaded');expect(page.locator('#main h1')).to_be_visible()
            page.evaluate('render()')
        go('content?tab=videos&category=external')
        check('three selected external videos',page.locator('[data-item-key^="video:"]').count()==3)
        check('source-labelled cards',page.locator('#main').inner_text().count('외부 채널 · STUDIO CHOOM')==2)
        check('newest Music Core stage first',page.locator('[data-item-key^="video:"]').first.get_attribute('data-item-key')=='video:sy40EGkSfRA')
        check('MBC source-labelled card',page.locator('#main').inner_text().count('외부 채널 · MBCkpop')==1)
        check('superseded upload absent',page.evaluate("!D.videos.some(v=>v.id==='z8AJgnTC52k')"))
        check('channel filter option',page.locator('option[value="studio-choom-selected"]').count()==1)
        go('content?tab=videos&channel=studio-choom-selected&q=레블스')
        check('channel and alias search',page.locator('[data-item-key^="video:"]').count()==2)
        go('content?tab=videos&channel=mbc-music-core-selected&q=음악중심')
        check('MBC channel and program search',page.locator('[data-item-key^="video:"]').count()==1)
        check('MBC exact selected ID',page.locator('[data-item-key^="video:"]').first.get_attribute('data-item-key')=='video:sy40EGkSfRA')
        go('content?tab=videos&category=group&q=MBCkpop')
        check('MBC not a group-owned upload',page.locator('[data-item-key^="video:"]').count()==0)
        go('content?tab=videos&category=group&q=STUDIO%20CHOOM')
        check('not mislabelled group-owned',page.locator('[data-item-key^="video:"]').count()==0)
        go('music?tab=videos&q=REBELS')
        check('Music Core stage in music videos',page.locator('[data-item-key="video:sy40EGkSfRA"]').count()==1)
        check('full performance in music videos',page.locator('[data-item-key="video:Mj7q8HU8ZXg"]').count()==1)
        check('external teaser not a full music video',page.locator('[data-item-key="video:_E9ZHH9R7o4"]').count()==0)
        go('song/rebels')
        related=page.locator('section[aria-label="관련 퍼포먼스 영상"]')
        expect(related).to_be_visible()
        check('both attached to existing song',related.locator('a[href="#/video/Mj7q8HU8ZXg"]').count()>0 and related.locator('a[href="#/video/_E9ZHH9R7o4"]').count()>0)
        check('MBC linked to existing song',related.locator('a[href="#/video/sy40EGkSfRA"]').count()>0)
        check('related section labels both publishers','MBCkpop' in related.locator('.ai-muted').inner_text() and 'STUDIO CHOOM' in related.locator('.ai-muted').inner_text())
        check('newest full performance first in related list',related.locator('a[href^="#/video/"]').first.get_attribute('href')=='#/video/sy40EGkSfRA')
        check('official MV stays primary',page.locator('.ai-platform-link[href="https://www.youtube.com/watch?v=y-klhPVFblg"]').count()==1)
        check('no extra songs or album tracks',page.evaluate("D.songs.filter(s=>s.id==='rebels').length===1 && !D.songs.some(s=>['_E9ZHH9R7o4','Mj7q8HU8ZXg','sy40EGkSfRA'].includes(s.videoId)) && D.albums.find(a=>a.title==='Across Dimensions').songIds.length===5"))
        for vid,duration in [('_E9ZHH9R7o4','0:31'),('Mj7q8HU8ZXg','3:12'),('sy40EGkSfRA','3:08')]:
            go('video/'+vid)
            check(vid+' direct original',page.locator('a.button.primary').get_attribute('href')=='https://www.youtube.com/watch?v='+vid)
            check(vid+' duration',duration in page.locator('.detail-meta').inner_text())
            check(vid+' source identification',('MBCkpop' if vid=='sy40EGkSfRA' else 'STUDIO CHOOM') in page.locator('#main .badges').first.inner_text())
            if vid=='sy40EGkSfRA':
                check('MBC stage is not falsely 4K','4K' not in page.locator('#main h1').inner_text() and page.evaluate("D.videos.find(v=>v.id==='sy40EGkSfRA').format==='음악방송 무대'"))
                check('Japan viewing restriction is visible','일본 지역에서 시청이 제한' in page.locator('#main').inner_text())
                check('MBC publication date visible','2026.11.14' in page.locator('.detail-meta').inner_text().replace(' ',''))
            check(vid+' existing song link',page.locator('a[href="#/song/rebels"]').count()>0)
            check(vid+' paired video link',page.locator('section[aria-label="관련 퍼포먼스 영상"] a[href^="#/video/"]').count()>0)
        feed={'schemaVersion':1,'feed':'daily-music','generatedAt':datetime.now(timezone.utc).isoformat(),'rows':[]}
        page.evaluate('(f)=>ProductionFeeds.applyMusic(f)',feed)
        check('daily refresh preserves all three',page.evaluate("D.videos.filter(v=>['_E9ZHH9R7o4','Mj7q8HU8ZXg','sy40EGkSfRA'].includes(v.id)).length===3"))
        check('daily refresh preserves original MV',page.evaluate("songs.get('rebels').videoId==='y-klhPVFblg'"))
        for width in (320,390,1440):
            page.set_viewport_size({'width':width,'height':1000})
            for route in ('content?tab=videos&category=external','video/Mj7q8HU8ZXg','video/sy40EGkSfRA','song/rebels'):
                go(route)
                check(str(width)+' no overflow '+route,page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            if width in (390,1440):
                page.locator('section[aria-label="관련 퍼포먼스 영상"]').screenshot(path=str(OUT/f'related-{width}.png'))
        check('full catalog retained',page.evaluate('D.videos.length')>26000)
        check('no Javascript errors',not errors)
        browser.close()
finally:
    server.shutdown()
    (OUT/'report.json').write_text(json.dumps({'checks':checks},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':len(checks)}))
