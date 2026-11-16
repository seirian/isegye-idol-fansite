"""Exact standalone UI on local HTTP; no real accounts or network thumbnails."""
import os,json,threading,http.server,socketserver
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'test-results/fanmade';OUT.mkdir(parents=True,exist_ok=True)
checks=[];dom_only=os.getenv('FANMADE_DOM_ONLY')=='true'
html=(ROOT/'fanmade-dist/review.html').read_text()
def check(name,value):
 checks.append({'name':name,'ok':bool(value)})
 if not value:raise AssertionError(name)
class Handler(http.server.SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT/'fanmade-dist'),**kw)
 def log_message(self,*a):pass
server=socketserver.TCPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
url='http://127.0.0.1:'+str(server.server_address[1])+'/review.html'
try:
 with sync_playwright() as p:
  options={'headless':True}
  if os.getenv('CHROMIUM_PATH'):options['executable_path']=os.environ['CHROMIUM_PATH']
  b=p.chromium.launch(**options);ctx=b.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();errors=[];external=[]
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:external.append(r.url) if not r.url.startswith(url.split('/review.html')[0]) else None)
  def go(hash):page.evaluate('(h)=>location.hash=h',hash);page.wait_for_timeout(90)
  if dom_only:page.set_content(html,wait_until='load')
  else:page.goto(url,wait_until='networkidle')
  expect(page.locator('h1')).to_have_text('팬메이드')
  check('correct menu name throughout', '팬 창작관' not in page.locator('body').inner_text())
  check('12 clearly labelled synthetic works',page.locator('[data-work]').count()==9 and '12' in page.locator('.count').inner_text())
  check('no fake original link or video player',page.locator('iframe,video,audio').count()==0)
  page.locator('[data-more]').click();check('load more displays all 12',page.locator('[data-work]').count()==12)
  if not dom_only:page.evaluate("localStorage.setItem('isegye:archive:prefs:v1','KEEP');localStorage.setItem('isegye:bookmarks:v1','KEEP_BOOKMARKS')")
  page.locator('[data-kind=craft]').click();expect(page.locator('[data-work]')).to_have_count(3)
  page.locator('#member').select_option('lilpa');expect(page.locator('[data-work]')).to_have_count(1);check('type member combination',page.locator('[data-work]').first.get_attribute('data-work')=='small-stage')
  before=page.url;page.locator('.card-link').click();expect(page.locator('h1')).to_have_text('손으로 만든 작은 무대')
  check('original unregistered clearly disabled',page.locator('.detail-info button.primary').is_disabled())
  check('gallery has three frames',page.locator('[data-index]').count()==3)
  page.locator('[data-frame][data-delta="1"]').click();expect(page.locator('[data-index="1"]')).to_have_attribute('aria-pressed','true')
  page.locator('[data-zoom]').click();expect(page.locator('#zoom')).to_be_visible();page.keyboard.press('ArrowRight');check('zoom supports keyboard gallery', '3 / 3' in page.locator('#zoom .frame-controls').inner_text());page.keyboard.press('Escape');expect(page.locator('#zoom')).not_to_be_visible();check('zoom focus returns to work',page.locator('[data-zoom]').evaluate('(e)=>e===document.activeElement'))
  page.locator('.detail-actions [data-save]').click();expect(page.locator('.detail-actions [data-save]')).to_have_attribute('aria-pressed','true')
  page.locator('.detail-actions [data-save]').click();expect(page.locator('.detail-actions [data-save]')).to_have_attribute('aria-pressed','false');page.locator('.detail-actions [data-save]').click()
  page.locator('[data-share]').click();expect(page.locator('#share')).to_be_visible();check('share uses deep link',page.locator('#share-url').input_value().endswith('#/work/small-stage'));page.keyboard.press('Escape')
  page.locator('.breadcrumbs a').click();check('back link preserves filters',page.url==before)
  go('#/saved');expect(page.locator('[data-work]')).to_have_count(1)
  if not dom_only:
   page.reload(wait_until='networkidle');expect(page.locator('[data-work]')).to_have_count(1)
  if not dom_only:check('operating saved data untouched',page.evaluate("localStorage.getItem('isegye:archive:prefs:v1')==='KEEP'&&localStorage.getItem('isegye:bookmarks:v1')==='KEEP_BOOKMARKS'"))
  page.locator('[data-save]').click();expect(page.locator('.empty h2')).to_have_text('아직 담은 작품이 없어요')
  go('#/fanmade');page.locator('#query').fill('창작자 A 아이네');page.locator('#query').press('Enter');expect(page.locator('[data-work]')).to_have_count(1);check('search creator member text',page.locator('[data-work]').first.get_attribute('data-work')=='song-scene')
  page.locator('#query').fill('<script>alert(1)</script>');page.locator('#query').press('Enter');expect(page.locator('.empty')).to_be_visible();check('inert query',page.locator('[data-work]').count()==0)
  page.locator('[data-reset]').click();expect(page.locator('[data-work]')).to_have_count(9)
  go('#/work/six-colors');page.locator('.byline').click();expect(page.locator('h1')).to_have_text('예시 창작자 A');check('creator exposes only own works',page.locator('[data-work]').count()==3)
  go('#/exhibition/song-color');expect(page.locator('h1')).to_have_text('노래가 그림이 될 때');check('theme has explicit four works',page.locator('[data-work]').count()==4)
  go('#/work/not-a-work');expect(page.locator('h1')).to_have_text('찾을 수 없는 페이지예요')
  for width in (320,390,768,1440):
   page.set_viewport_size({'width':width,'height':1000})
   for path in ('fanmade','work/six-colors','work/small-stage','creator/sample-studio-a','exhibition/song-color','saved'):
    go('#/'+path);check('no overflow '+str(width)+' '+path,page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    if width in (390,1440) and path in ('fanmade','work/small-stage','exhibition/song-color'):
     page.locator('#status').evaluate('(e)=>e.textContent=""');page.screenshot(path=str(OUT/(str(width)+'-'+path.replace('/','-')+'.png')),full_page=True)
  go('#/fanmade');page.locator('.feature-button').click();expect(page.locator('h1')).to_have_text('노래가 그림이 될 때')
  if not dom_only:page.go_back();expect(page.locator('h1')).to_have_text('팬메이드');check('browser back restores list',page.locator('[data-work]').count()==9)
  check('no external requests',not external);check('no JS errors',not errors)
  if not dom_only:bad=b.new_context();bad.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new DOMException('blocked','SecurityError')}})");bp=bad.new_page();bp.goto(url,wait_until='networkidle');expect(bp.locator('.storage-note')).to_be_visible();bp.locator('[data-save]').first.click();check('blocked storage still supports in-tab saves',bp.locator('#saved-count').inner_text()=='1');bad.close()
  if not dom_only:broken=b.new_context();bp=broken.new_page();bp.goto(url,wait_until='networkidle');bp.evaluate("localStorage.setItem('isegye:fanmade:review:v1','{')");bp.reload(wait_until='networkidle');expect(bp.locator('.storage-note')).to_be_visible();check('corrupt storage does not crash',bp.locator('h1').inner_text()=='팬메이드');broken.close()
  b.close()
finally:
 server.shutdown();(OUT/'browser.json').write_text(json.dumps({'mode':'DOM only; storage and HTTP await CI' if dom_only else 'real local HTTP','checks':checks},ensure_ascii=False,indent=2))
print(json.dumps({'passed':len(checks),'mode':'DOM' if dom_only else 'HTTP'}))
