"""Exercise the exact hash-CSP HTML over HTTP (never real accounts)."""
from pathlib import Path
import os,json,threading,http.server,socketserver
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'test-results/playground';OUT.mkdir(parents=True,exist_ok=True)
checks=[];dom=os.getenv('PLAYGROUND_DOM_ONLY')=='true'
def check(name,ok):
 checks.append({'name':name,'ok':bool(ok)})
 if not ok:raise AssertionError(name)
class Handler(http.server.SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT/'playground-dist'),**kw)
 def log_message(self,*a):pass
server=socketserver.TCPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_address[1]}/review.html'
try:
 with sync_playwright() as p:
  options={'headless':True}
  if os.getenv('CHROMIUM_PATH'):options['executable_path']=os.getenv('CHROMIUM_PATH')
  b=p.chromium.launch(**options);ctx=b.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();errors=[];external=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('request',lambda r:external.append(r.url) if not r.url.startswith(url.rsplit('/',1)[0]) else None)
  if dom:page.set_content((ROOT/'playground-dist/review.html').read_text(),wait_until='load')
  else:page.goto(url,wait_until='networkidle')
  def go(path):page.evaluate('(p)=>location.hash=p','#/'+path);page.wait_for_timeout(80)
  def state():return page.evaluate("JSON.parse(localStorage.getItem('isegye:playground:review:v1'))")
  expect(page.locator('h1')).to_have_text('놀이터');check('home correct menu',page.locator('.desktop-nav a').count()==8)
  page.screenshot(path=str(OUT/'home-1440.png'),full_page=True)
  if not dom:page.evaluate("localStorage.setItem('isegye:archive:prefs:v1','KEEP');localStorage.setItem('isegye:bookmarks:v1','KEEP_BOOKMARKS')")
  page.locator('[data-start=daily]').click();expect(page.locator('[data-answer]')).to_have_count(4);check('question type badges',page.locator('.question-tags .badge').count()==3)
  page.locator('[data-action=hint]').click();expect(page.locator('.hint')).to_be_visible();page.screenshot(path=str(OUT/'question-1440.png'),full_page=True)
  def correct_answer():
   stem=page.locator('.question-panel h1').inner_text();return page.evaluate('(stem)=>PLAYGROUND_DATA.questions.find(q=>q.stem===stem).answer',stem)
  page.locator(f'[data-answer="{correct_answer()}"]').click();expect(page.locator('[data-action=next]')).to_be_visible();check('answer locks options',page.locator('[data-answer]:disabled').count()==4)
  page.locator('details summary').click();check('sources visible after answer',page.locator('.source-item a').count()>0)
  if not dom:
   check('correct score persisted',state()['session']['answers'][0]['correct']);ids=state()['session']['ids']
   page.reload(wait_until='networkidle');check('answered state survives reload',page.locator('[data-answer]:disabled').count()==4);check('no duplicate answer after reload',len(state()['session']['answers'])==1)
  page.locator('[data-action=next]').click();page.locator('[data-action=skip]').click();check('skipped question explained','새로운 이야기를 알아가요' in page.locator('.feedback h2').inner_text());page.locator('[data-action=next]').click()
  page.locator(f'[data-answer="{(correct_answer()+1)%4}"]').click();page.locator('[data-action=next]').click()
  page.locator(f'[data-answer="{correct_answer()}"]').click();page.locator('[data-action=next]').click()
  page.locator(f'[data-answer="{correct_answer()}"]').click();page.locator('[data-action=next]').click()
  expect(page.locator('.score')).to_contain_text('3');check('result has all five explanations',page.locator('.review-question').count()==5)
  page.screenshot(path=str(OUT/'result-1440.png'),full_page=True)
  if not dom:
   check('one completed round',len(state()['history'])==1);check('wrong plus skip queue',len(state()['wrong'])==2)
   page.reload(wait_until='networkidle');check('reload never doubles completion',len(state()['history'])==1)
  page.locator('[data-share-result]').click();expect(page.locator('#share')).to_be_visible();check('shared text has review-only URL','review-playground/' in page.locator('#share-text').input_value());check('shared text has no account fields','@' not in page.locator('#share-text').input_value());page.keyboard.press('Escape')
  expect(page.locator('#share')).not_to_be_visible()
  page.locator('[data-retry-result]').click();expect(page.locator('[data-answer]')).to_have_count(4)
  for i in range(2):page.locator(f'[data-answer="{correct_answer()}"]').click();page.locator('[data-action=next]').click()
  check('retry result only missed two',page.locator('.review-question').count()==2)
  if not dom:check('corrected questions leave notebook',state()['wrong']==[])
  go('playground');page.locator('[data-start=daily]').click()
  if not dom:check('same day keeps exact five questions',state()['session']['ids']==ids)
  go('quiz');page.locator('[data-category=stories]').click();check('10 available after stories expansion',not page.locator('[data-count="10"]').is_disabled());page.locator('[data-start=quiz]').click();expect(page.locator('#confirm')).to_be_visible();page.locator('#confirm button[value=cancel]').click();expect(page.locator('#confirm')).not_to_be_visible()
  if not dom:check('cancel retains previous active round',state()['session']['mode']=='daily')
  page.locator('[data-start=quiz]').click();page.locator('#confirm button[value=ok]').click();expect(page.locator('[data-answer]')).to_have_count(4)
  if not dom:check('selected category only',all(q.startswith('stories-') for q in state()['session']['ids']))
  go('playground');page.locator('[data-start=order]').click();page.locator('#confirm button[value=ok]').click();expect(page.locator('[data-answer]')).to_have_count(2)
  check('dates hidden until answer',page.locator('.option time').count()==0)
  page.screenshot(path=str(OUT/'order-1440.png'),full_page=True)
  if not dom:
   for i in range(5):
    pair=state()['session']['pairs'][i];dates=page.evaluate('(ids)=>ids.map(id=>PLAYGROUND_DATA.tracks.find(t=>t.id===id).date)',pair);correct=0 if dates[0]<dates[1] else 1
    page.locator(f'[data-answer="{correct}"]').click();check('both dates shown '+str(i),page.locator('.option time').count()==2);page.locator('[data-action=next]').click()
   check('order scores five correct',state()['history'][0]['answers']==[{'choice':a['choice'],'correct':True,'hint':False} for a in state()['history'][0]['answers']])
  else:page.locator('[data-answer]').first.click()
  for width in (320,390,768,1440):
   page.set_viewport_size({'width':width,'height':1000})
   for path in ('playground','quiz','records','sources','play'):
    go(path);check('no horizontal overflow '+str(width)+' '+path,page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    if width in (390,1440) and path in ('playground','records','play'):
     page.screenshot(path=str(OUT/f'{path}-{width}.png'),full_page=True)
  go('sources');check('sources disclose direct Namu access limit','보안 확인 화면' in page.locator('#main').inner_text());check('sources include both owner links',page.locator('a[href="https://cafe.naver.com/steamindiegame/21721901"]').count()==1 and page.locator('a[href="https://cafe.naver.com/steamindiegame/21741748"]').count()==1)
  page.locator('#theme').click();check('dark theme toggles',page.locator('body').evaluate('(e)=>e.classList.contains("dark")'));go('playground');page.screenshot(path=str(OUT/'home-dark-1440.png'),full_page=True);page.locator('#theme').click()
  if not dom:
   go('records');page.locator('[data-action=reset]').click();page.locator('#confirm button[value=ok]').click();expect(page.locator('.records-list .empty')).to_be_visible();check('reset clears only playground',page.evaluate("localStorage.getItem('isegye:archive:prefs:v1')==='KEEP'&&localStorage.getItem('isegye:bookmarks:v1')==='KEEP_BOOKMARKS'"))
   c=b.new_context();c.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new DOMException('blocked','SecurityError')}})");p2=c.new_page();p2.goto(url);expect(p2.locator('#storage-note')).to_be_visible();p2.locator('[data-start=daily]').click();p2.locator('[data-answer]').first.click();expect(p2.locator('[data-action=next]')).to_be_visible();check('storage blocked still plays',True);c.close()
   c=b.new_context();p2=c.new_page();p2.goto(url);p2.evaluate("localStorage.setItem('isegye:playground:review:v1','{')");p2.reload();expect(p2.locator('h1')).to_have_text('놀이터');expect(p2.locator('#storage-note')).to_be_visible();check('corrupt storage safe',True);c.close()
  go('unknown');expect(page.locator('h1')).to_have_text('찾을 수 없는 페이지예요');check('unknown route safe',True)
  check('zero JavaScript errors',not errors);check('no external requests during gameplay',not external)
  b.close()
finally:
 server.shutdown();(OUT/'browser.json').write_text(json.dumps({'mode':'DOM-only; persistence unverified' if dom else 'real local HTTP','checks':checks},ensure_ascii=False,indent=2))
print(json.dumps({'passed':len(checks),'mode':'DOM' if dom else 'HTTP'}))
