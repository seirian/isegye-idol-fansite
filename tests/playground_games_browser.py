"""Real HTTP preview tests: input, simulation time, persistence, export and responsive UI."""
from pathlib import Path
import json,os,http.server,socketserver,threading,sys
from datetime import datetime,timezone
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'test-results/playground-games';OUT.mkdir(parents=True,exist_ok=True)
checks=[]
def check(name,condition):
    checks.append({'name':name,'passed':bool(condition)})
    if not condition:raise AssertionError(name)
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT/'playground-games-dist'),**kw)
    def log_message(self,*a):pass
server=socketserver.TCPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://127.0.0.1:'+str(server.server_address[1])
errors=[];external=[]
try:
 with sync_playwright() as p:
  launch={'headless':True}
  if os.getenv('CHROMIUM_PATH'):launch['executable_path']=os.environ['CHROMIUM_PATH']
  browser=p.chromium.launch(**launch);ctx=browser.new_context(viewport={'width':1440,'height':1050},accept_downloads=True)
  page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('request',lambda r:external.append(r.url) if not r.url.startswith(url) and not r.url.startswith('blob:') else None)
  page.goto(url);expect(page.get_by_role('heading',name='놀이터',exact=True)).to_be_visible();check('three complete game cards',page.locator('.cards .card').count()==3)
  page.screenshot(path=str(OUT/'home-1440-dark.png'),full_page=True)
  page.evaluate("localStorage.setItem('isegye:playground:v1','unchanged'); localStorage.setItem('bookmarks','untouched')")
  page.locator('[data-launch=link]').click();expect(page.locator('[data-cell]')).to_have_count(36)
  original=page.locator('[data-cell]').evaluate_all('(els)=>els.map(e=>Number(e.dataset.color))')
  path=page.evaluate('ARCADE_CORE.findLink(Array.from(document.querySelectorAll("[data-cell]"),b=>Number(b.dataset.color)))')
  for i in path:page.locator(f'[data-cell="{i}"]').press('Enter')
  expect(page.locator('#link-confirm')).to_be_enabled();page.locator('#link-confirm').click();expect(page.locator('#link-moves')).to_have_text('19');check('keyboard chain scores',int(page.locator('#link-score').inner_text())>=30)
  saved=page.evaluate("localStorage.getItem('isegye:review:playground-games:v1')");page.reload();expect(page.locator('#link-moves')).to_have_text('19');check('puzzle survives exact reload',page.evaluate("localStorage.getItem('isegye:review:playground-games:v1')")==saved)
  path=page.evaluate('ARCADE_CORE.findLink(Array.from(document.querySelectorAll("[data-cell]"),b=>Number(b.dataset.color)))')
  boxes=[page.locator(f'[data-cell="{i}"]').bounding_box() for i in path]
  page.mouse.move(boxes[0]['x']+boxes[0]['width']/2,boxes[0]['y']+boxes[0]['height']/2);page.mouse.down()
  for b in boxes[1:]:page.mouse.move(b['x']+b['width']/2,b['y']+b['height']/2,steps=4)
  page.mouse.up();expect(page.locator('#link-moves')).to_have_text('18');check('drag commits once',True)
  page.locator('#link-hint').click();expect(page.locator('.hinted')).to_have_count(3);expect(page.locator('#link-moves')).to_have_text('18');check('hint costs no move',True)
  page.locator('#link-restart').click();expect(page.locator('#dialog')).to_be_visible();page.locator('#dialog').get_by_role('button',name='취소',exact=True).click();expect(page.locator('#link-moves')).to_have_text('18');check('restart cancellation preserves state',True)
  page.locator('#link-restart').click();page.locator('#dialog').get_by_role('button',name='확인',exact=True).click();expect(page.locator('#link-moves')).to_have_text('20');check('same seed restart identical',page.locator('[data-cell]').evaluate_all('(els)=>els.map(e=>Number(e.dataset.color))')==original)
  page.screenshot(path=str(OUT/'link-1440.png'),full_page=True)
  for turn in range(20):
   path=page.evaluate('ARCADE_CORE.findLink(Array.from(document.querySelectorAll("[data-cell]"),b=>Number(b.dataset.color)))')
   for i in path:page.locator(f'[data-cell="{i}"]').press('Enter')
   page.locator('#link-confirm').click()
  expect(page.locator('#link-moves')).to_have_text('0');expect(page.locator('#result-retry')).to_be_visible();check('full 20-turn puzzle result',int(page.locator('#link-score').inner_text().replace(',',''))>0)
  page.goto(url+'/#/catch?s=browser-test');expect(page.locator('#sky-start')).to_be_visible();page.clock.install(time=datetime(2026,11,18,3,tzinfo=timezone.utc));page.locator('#sky-start').click();page.clock.run_for(3000)
  check('catch clock advances',float(page.locator('#catch-time').inner_text())<58)
  page.keyboard.down('ArrowRight');page.clock.run_for(600);page.keyboard.up('ArrowRight');page.locator('#catch-pause').click();paused_time=page.locator('#catch-time').inner_text();page.clock.run_for(5000);check('manual pause freezes time',page.locator('#catch-time').inner_text()==paused_time)
  page.locator('#sky-start').click();page.clock.run_for(1000);page.evaluate("window.dispatchEvent(new Event('blur'))");expect(page.locator('#catch-overlay')).to_be_visible();paused_time=page.locator('#catch-time').inner_text();page.clock.run_for(3000);check('blur freezes time',page.locator('#catch-time').inner_text()==paused_time)
  page.screenshot(path=str(OUT/'catch-paused-1440.png'),full_page=True);page.locator('#sky-start').click();page.clock.run_for(57000);expect(page.locator('#catch-overlay')).to_contain_text('빛나는 60초');check('60-second complete round',page.locator('#catch-time').inner_text()=='0.0');page.screenshot(path=str(OUT/'catch-result-1440.png'),full_page=True)
  page.goto(url+'/#/concert');expect(page.locator('#concert-title')).to_be_visible();song_count=page.locator('[data-add]').count();check('at least eight official selections',song_count>=8)
  page.locator('#song-search').fill('없는곡zzzz');expect(page.locator('.empty-search')).to_be_visible();page.locator('#song-search').fill('리와인드');check('aliases searchable',page.locator('[data-add]').count()==1);page.locator('#song-search').fill('')
  selected=[]
  for i in range(8):
   button=page.locator('[data-add]:not([disabled])').first;selected.append(button.get_attribute('data-add'));button.click()
  check('eight unique selected',len(set(selected))==8);expect(page.locator('#chosen-count')).to_have_text('8');expect(page.locator('[data-add]:not([disabled])')).to_have_count(0);expect(page.locator('#concert-preview')).to_be_enabled()
  page.locator('#concert-title').fill('우리의 빛나는 밤');page.locator('[data-poster-theme=mint]').click();page.locator('[data-down="0"]').click();draft=page.evaluate("JSON.parse(localStorage.getItem('isegye:review:playground-games:v1')).concert");check('reorder applied',draft['songs'][1]==selected[0]);page.reload();expect(page.locator('#chosen-count')).to_have_text('8');check('title retained',page.locator('#concert-title').input_value()=='우리의 빛나는 밤')
  page.screenshot(path=str(OUT/'concert-editor-1440.png'),full_page=True);page.locator('#concert-preview').click();expect(page.locator('#poster')).to_be_visible()
  with page.expect_download() as info:page.locator('#poster-download').click()
  download=info.value;dest=OUT/'my-concert.png';download.save_as(str(dest));check('real PNG exported',dest.read_bytes()[:8]==b'\x89PNG\r\n\x1a\n');page.screenshot(path=str(OUT/'concert-card-1440.png'),full_page=True)
  # Share codec is the same function called by the visible share action.
  encoded=page.evaluate("ARCADE_CORE.encodeConcert(JSON.parse(localStorage.getItem('isegye:review:playground-games:v1')).concert)")
  before=page.evaluate("localStorage.getItem('isegye:review:playground-games:v1')");page.goto(url+'/#/concert/shared?set='+encoded);expect(page.get_by_role('heading',name='공유받은 콘서트')).to_be_visible();check('shared view leaves draft unchanged',page.evaluate("localStorage.getItem('isegye:review:playground-games:v1')")==before)
  page.locator('#concert-edit').click();expect(page.locator('#dialog')).to_be_visible();page.locator('#dialog').get_by_role('button',name='취소',exact=True).click();check('import cancel keeps current draft',page.evaluate("localStorage.getItem('isegye:review:playground-games:v1')")==before)
  page.goto(url+'/#/concert/shared?set=not-a-valid-set');expect(page.get_by_role('heading',name='세트리스트 링크를 확인해 주세요')).to_be_visible();check('invalid share leaves draft unchanged',page.evaluate("localStorage.getItem('isegye:review:playground-games:v1')")==before)
  page.goto(url+'/#/home');page.locator('#reset-records').click();page.locator('#dialog').get_by_role('button',name='확인',exact=True).click();check('operating quiz records preserved',page.evaluate("localStorage.getItem('isegye:playground:v1')")=='unchanged');check('operating bookmarks preserved',page.evaluate("localStorage.getItem('bookmarks')")=='untouched')
  for width in (320,390,768,1440):
   for mode in ('dark','light'):
    page.set_viewport_size({'width':width,'height':1000});page.goto(url+'/#/home');page.evaluate('(theme)=>document.documentElement.dataset.theme=theme',mode)
    check(f'home no horizontal overflow {width} {mode}',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    page.screenshot(path=str(OUT/f'home-{width}-{mode}.png'),full_page=True)
   for name,route in [('link','/#/link?s=responsive'),('catch','/#/catch?s=responsive'),('concert','/#/concert')]:
    page.goto(url+route);check(f'{name} no horizontal overflow {width}',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    if width==390:page.screenshot(path=str(OUT/f'{name}-390.png'),full_page=True)
  check('no external media or API requests',not external);check('no JavaScript errors',not errors)
  # Touch tap selection and pointer cancellation in a genuinely mobile context.
  mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True);m=mobile.new_page();m.goto(url+'/#/link?s=touch');path=m.evaluate('ARCADE_CORE.findLink(Array.from(document.querySelectorAll("[data-cell]"),b=>Number(b.dataset.color)))')
  for i in path:m.locator(f'[data-cell="{i}"]').tap()
  m.locator('#link-confirm').tap();expect(m.locator('#link-moves')).to_have_text('19');check('mobile touch chain commits',True);mobile.close()
  blocked=browser.new_context(viewport={'width':390,'height':844});blocked.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}})");b=blocked.new_page();b.goto(url+'/#/concert');expect(b.locator('#storage-note')).to_be_visible();b.locator('[data-add]').first.click();expect(b.locator('#chosen-count')).to_have_text('1');check('blocked storage still permits editing',True);blocked.close();browser.close()
except Exception:
 try:
  page.screenshot(path=str(OUT/'failure.png'),full_page=True)
  (OUT/'failure-state.json').write_text(json.dumps({'url':page.url,'errors':errors,'body':page.locator('body').inner_text()[:12000]},ensure_ascii=False,indent=2))
 except Exception:pass
 raise
finally:
 server.shutdown();(OUT/'report.json').write_text(json.dumps({'passed':sum(x['passed'] for x in checks),'checks':checks,'javascriptErrors':errors,'externalRequests':external},ensure_ascii=False,indent=2))
print(json.dumps({'passed':len(checks),'mode':'real HTTP browser; virtual game clock; real PNG export'}))
