"""Shared menu typography, deleted top links and live administrator-only references."""
import http.server,socketserver,threading,json,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'test-results/playground-polish';OUT.mkdir(parents=True,exist_ok=True)
role={'value':'guest','fail':False};checks=[];requests=[]
def check(name,ok):
 checks.append({'name':name,'passed':bool(ok)})
 if not ok:raise AssertionError(name)
class Handler(http.server.SimpleHTTPRequestHandler):
 def __init__(self,*a,**k):super().__init__(*a,directory=str(ROOT/'dist'),**k)
 def log_message(self,*a):pass
 def do_GET(self):
  path=self.path.split('?')[0];requests.append(path)
  if path=='/auth/status':
   data={'authenticated':role['value']!='guest','administrator':role['value']=='admin','allowed':True}
   raw=json.dumps(data).encode();self.send_response(503 if role['fail'] else 200);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw);return
  if path in ('/src/playground-admin.js','/src/admin-operations.js') and role['value']!='admin':self.send_error(401 if role['value']=='guest' else 403);return
  if path.startswith('/api/'):
   if path=='/api/playground':
    d=json.loads((ROOT/'dist/src/playground-seed.json').read_text());raw=json.dumps({'schemaVersion':1,'feed':'playground','baseVersion':d['version'],'generatedAt':'2026-11-16T12:00:00Z','catalog':d}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw);return
   self.send_error(503);return
  return super().do_GET()
server=socketserver.ThreadingTCPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://127.0.0.1:'+str(server.server_address[1])
try:
 with sync_playwright() as p:
  args={'headless':True}
  if os.getenv('CHROMIUM_PATH'):args['executable_path']=os.environ['CHROMIUM_PATH']
  b=p.chromium.launch(**args);ctx=b.new_context(viewport={'width':1440,'height':1000},locale='ko-KR');page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.route('https://**',lambda route:route.abort())
  def go(route):
   page.goto(url+'/#/'+route,wait_until='networkidle');page.wait_for_timeout(80)
  def metrics(selector):
   return page.locator(selector).evaluate('''e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return {top:r.top,left:r.left,font:s.fontFamily,size:s.fontSize,weight:s.fontWeight,line:s.lineHeight,spacing:s.letterSpacing,color:s.color}}''')
  for width in (390,1440):
   page.set_viewport_size({'width':width,'height':1000})
   for theme in ('light','dark'):
    go('content')
    if page.evaluate('document.documentElement.dataset.theme')!=theme:page.locator('button[data-action=theme]').click()
    page.wait_for_timeout(100)
    content={k:metrics('#main .page-heading '+sel) for k,sel in [('title','h1'),('label','.eyebrow'),('description','h1+p')]}
    go('playground');expect(page.locator('.playground-component h1')).to_have_text('놀이터');page.wait_for_timeout(100)
    pg={k:metrics('.playground-component .page-heading '+sel) for k,sel in [('title','h1'),('label','.eyebrow'),('description','h1+p')]}
    (OUT/f'heading-{width}-{theme}.json').write_text(json.dumps({'content':content,'playground':pg,'rootTheme':page.evaluate('document.documentElement.dataset.theme')},ensure_ascii=False,indent=2))
    page.screenshot(path=str(OUT/f'home-{width}-{theme}.png'),full_page=True)
    check(f'{width} {theme} persisted theme',page.evaluate('document.documentElement.dataset.theme')==theme)
    for k in content:
     for prop in ('top','left'):check(f'{width} {theme} {k} {prop}',abs(content[k][prop]-pg[k][prop])<0.6)
     for prop in ('font','size','weight','line','spacing','color'):check(f'{width} {theme} {k} {prop}',content[k][prop]==pg[k][prop])
    check(f'{width} {theme} no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    check('top tools removed',page.locator('.pg-tools').count()==0)
    home=page.locator('.playground-component')
    for selector in ('[data-courier-launch]','[data-rpg-launch]','[data-start=daily]'):
     expect(home.locator(selector)).to_be_visible()
    removed_launchers='a[href="#/playground/quiz"], [data-start=order], [data-start=retry]'
    check(f'{width} {theme} redundant quiz launchers removed',home.locator(removed_launchers).count()==0)
    home_text=home.locator('#main').inner_text()
    for label in ('어떤 재미를 골라볼까요?', '취향대로 퀴즈', '먼저일까, 나중일까?', '한 번 더 만나면 기억날 거예요',
                  '기록은 이 브라우저에만 저장됩니다.', '오늘의 문제는 한국 시간 기준으로 바뀝니다.'):
     check(f'{width} {theme} removed home text {label}',label not in home_text)
    page.screenshot(path=str(OUT/f'home-{width}-{theme}.png'),full_page=True)
  check('guest has no reference footer',page.locator('.pg-admin-footer').count()==0)
  check('guest never downloaded reference module','/src/playground-admin.js' not in requests)
  role['value']='member';go('playground/sources');expect(page.locator('.playground-component h1')).to_have_text('관리자 전용 페이지입니다')
  check('member cannot show sources by URL',page.locator('.source-grid').count()==0)
  page.evaluate("localStorage.setItem('role','admin');localStorage.setItem('administrator','true');window.dispatchEvent(new Event('focus'))")
  page.wait_for_timeout(200);check('local flags do not grant references',page.locator('.source-grid,.pg-admin-footer').count()==0)
  role['value']='admin';go('playground');page.evaluate("window.dispatchEvent(new Event('focus'))");expect(page.locator('.pg-admin-footer')).to_be_visible()
  box=page.locator('.pg-admin-footer a').bounding_box();outer=page.locator('#playground-mount').bounding_box();daily=page.locator('.playground-component .hero').bounding_box()
  check('admin link right aligned',abs(box['x']+box['width']-outer['x']-outer['width'])<1)
  check('admin link below daily quiz',box['y']>daily['y']+daily['height'])
  page.screenshot(path=str(OUT/'admin-home-1440.png'),full_page=True)
  page.locator('.pg-admin-footer a').click();expect(page.locator('.source-grid')).to_be_visible();check('admin overview available',page.locator('.source-grid .panel').count()>30)
  role['value']='member';page.evaluate("window.dispatchEvent(new Event('focus'))");expect(page.locator('.playground-component h1')).to_have_text('관리자 전용 페이지입니다');check('revocation removes existing overview',page.locator('.source-grid,.pg-admin-footer').count()==0)
  role['value']='admin';go('playground/sources');page.evaluate("window.dispatchEvent(new Event('focus'))");expect(page.locator('.source-grid')).to_be_visible();role['fail']=True;page.evaluate("window.dispatchEvent(new Event('focus'))");expect(page.locator('.source-grid')).to_have_count(0);check('role request failure fails closed',True)
  check('no JavaScript errors',not errors);b.close()
except Exception as error:
 try:
  (OUT/'failure.json').write_text(json.dumps({'error':str(error),'errors':errors,'requests':requests},ensure_ascii=False,indent=2))
 except Exception:pass
 raise
finally:
 server.shutdown();(OUT/'report.json').write_text(json.dumps({'checks':checks},ensure_ascii=False,indent=2))
print(json.dumps({'passed':len(checks),'mode':'real local HTTP'}))
