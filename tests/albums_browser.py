"""Offline browser checks of the actual feature artifact. No operating writes."""
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from functools import partial
from playwright.sync_api import sync_playwright,expect
import threading,json,re
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'test-results/albums-browser';OUT.mkdir(parents=True,exist_ok=True)
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path.split('?')[0]=='/review-albums/api/insights':
            raw=(ROOT/'albums-dist/insights.json').read_bytes();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
        else:
            self.path='/index.html';super().do_GET()
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'albums-dist')))
threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}/review-albums/'
checks=[]
def check(name,condition):
    checks.append({'name':name,'passed':bool(condition)})
    if not condition:raise AssertionError(name)
try:
 with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    context=browser.new_context();context.route(re.compile(r'https://'),lambda r:r.abort())
    page=context.new_page();errors=[];violations=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('console',lambda m:violations.append(m.text) if 'Content Security Policy' in m.text else None)
    page.goto(url,wait_until='domcontentloaded');expect(page.locator('.ai-card')).to_have_count(15)
    expect(page.locator('[data-ai-api]')).to_have_text('동일 출처 API 확인')
    check('default route is album list','tab=albums' in page.url)
    expect(page.locator('#main h1')).to_have_text('한 곡에서 시작되는 이야기')
    check('removed coverage selector',page.locator('[data-filter=coverage]').count()==0)
    check('domestic album covers present',page.locator('.ai-card .ai-cover img').count()>=13)
    page.goto(url+'#/music?tab=albums&coverage=connected',wait_until='domcontentloaded');expect(page.locator('.ai-card')).to_have_count(15)
    check('legacy coverage query no longer filters',True)
    page.locator('#music-q').fill('고양이가 세상을 구한다');page.locator('#music-q').press('Enter');expect(page.locator('.ai-card')).to_have_count(1)
    check('track name searches its album','NO CAT, NO LIFE!' in page.locator('.ai-card').inner_text())
    page.locator('.ai-card-top').click();expect(page.locator('#main h1')).to_have_text('NO CAT, NO LIFE!')
    page.locator('select[data-filter=track]').select_option('your-turn');expect(page.locator('select[data-filter=track]')).to_have_value('your-turn')
    page.get_by_role('link',name='선택 곡 자세히 보기').click();expect(page.locator('#main h1')).to_have_text('Your Turn')
    page.goto(url+'#/song/cat-save-world?demo=1&range=24h',wait_until='domcontentloaded');expect(page.locator('.ai-demo')).to_contain_text('실제 순위가 아닙니다')
    check('opt-in demo renders sixteen points',page.locator('.ai-chart .ai-dot').count()==16)
    page.locator('.ai-detail-toggle summary').first.click();check('accessible values table',page.locator('.ai-table tbody tr').count()==16)
    page.locator('.ai-chart .ai-dot').first.focus();check('keyboard-accessible points',page.locator('.ai-chart .ai-dot').first.get_attribute('aria-label') is not None)
    page.get_by_role('link',name='실제 데이터로 돌아가기').click();expect(page.locator('.ai-demo')).to_have_count(0)
    expect(page.locator('.ai-streaming h2')).to_have_text('음원 연결')
    check('eight first-party logos before platform names',page.locator('.ai-streaming .ai-platform-logo').count()==8)
    check('logos loaded and precede names',page.locator('.ai-platform-link').evaluate_all('(links)=>links.every(a=>a.firstElementChild.tagName===\"IMG\" && a.firstElementChild.complete && a.firstElementChild.naturalWidth>0)'))
    check('no trailing arrow icons on platform links',page.locator('.ai-streaming svg').count()==0)
    check('selected song has a domestic cover',page.locator('.ai-hero .ai-cover img').count()==1)
    check('three verified domestic direct track links',page.locator('.ai-streaming a[href*="songId="], .ai-streaming a[href*="xgnm="], .ai-streaming a[href*="/track/"]').count()>=3)
    page.locator('select[data-filter=metric]').select_option('genie');expect(page.locator('select[data-filter=metric]')).to_have_value('genie')
    check('Genie TOP200 selectable',True)
    check('demo does not overwrite embedded real data',page.evaluate('Object.values(albumInsights.tracks).every(t=>!(t.appleHistory||[]).some(p=>p.demo))'))
    for width in (320,390,768,1440):
      page.set_viewport_size({'width':width,'height':1000})
      for name,route in [('list','music?tab=albums'),('detail','song/cat-save-world?demo=1'),('real','song/cat-save-world')]:
        page.goto(url+'#/'+route,wait_until='domcontentloaded');expect(page.locator('#main h1')).to_be_visible()
        check(f'{name} no horizontal overflow {width}',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        if width in (390,1440):page.screenshot(path=str(OUT/f'{name}-{width}.png'),full_page=True)
    page.goto(url+'#/music?tab=albums&view=list',wait_until='domcontentloaded');expect(page.locator('.ai-list-view')).to_be_visible()
    check('list mode works',page.locator('.ai-list-view .ai-card').count()==15)
    page.locator('[data-action=theme]').click();check('light mode',page.locator('html').get_attribute('data-theme')=='light');page.screenshot(path=str(OUT/'list-light.png'),full_page=True)
    page.goto(url+'#/song/not-real',wait_until='domcontentloaded');expect(page.locator('#main h1')).to_contain_text('찾을 수 없는')
    keys=page.evaluate('Object.keys(localStorage)');check('preview preferences isolated',all(k.startswith('isegye:albums-review:') for k in keys))
    check('no JavaScript exceptions',not errors);check('no CSP violations',not violations)
    context.route('**/review-albums/api/insights',lambda r:r.fulfill(status=503,body='unavailable'))
    page.goto(url+'#/music?tab=albums',wait_until='domcontentloaded');page.reload(wait_until='domcontentloaded')
    expect(page.locator('[data-ai-api]')).to_have_text('API 응답 실패 · 내장 검토본 표시');check('API failure preserves list',page.locator('.ai-card').count()==15)
    browser.close()
finally:
 server.shutdown();(OUT/'report.json').write_text(json.dumps({'checks':checks},ensure_ascii=False,indent=2))
print(json.dumps({'passed':len(checks)},ensure_ascii=False))
