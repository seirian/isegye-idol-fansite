"""Shared application policy routes and script-free public renderer regression."""
from pathlib import Path
import json,os,subprocess
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[1];OUT=Path(os.getenv('LEGAL_SHELL_OUT',str(R/'test-results/legal-shell')));OUT.mkdir(parents=True,exist_ok=True)
URL=os.getenv('LEGAL_SHELL_URL','http://127.0.0.1:4199/').rstrip('/')+'/'
checks=[];errors=[]
def check(name,ok):
 checks.append({'name':name,'passed':bool(ok)})
 if not ok:raise AssertionError(name)
def settle(p):p.wait_for_timeout(120)
def bg(p):return p.locator('.legal-document').evaluate('(x)=>getComputedStyle(x).backgroundColor')
def intact(p,k):
 return p.locator('.legal-document').evaluate('(el,source)=>{const x=document.createElement("article");x.innerHTML=source;return el.innerHTML===x.innerHTML}',(R/'auth'/f'{k}.html').read_text())
try:
 with sync_playwright() as pw:
  b=pw.chromium.launch(executable_path=os.getenv('BROWSER_EXECUTABLE') or None)
  c=b.new_context(viewport={'width':1440,'height':1000},locale='ko-KR')
  c.add_init_script("localStorage.setItem('isegye:theme:second','dark')")
  page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(URL+'#/guide',wait_until='networkidle');page.evaluate('window.__legalHeader=document.querySelector(".site-header")')
  page.locator('.footer-links a').filter(has_text='이용약관').click();settle(page)
  check('terms opens inside app',page.url==URL+'#/terms')
  check('site header survives policy navigation',page.evaluate('window.__legalHeader===document.querySelector(".site-header")'))
  check('shared navigation retained',page.locator('[data-nav]').count()==6)
  check('footer order retained',page.locator('.footer-links a').all_text_contents()==['이용약관','개인정보처리방침','팬가이드'])
  check('no iframe or separate access layout',page.locator('iframe,.access-page,.access-backdrop').count()==0)
  check('selected dark theme retained',page.locator('html').get_attribute('data-theme')=='dark' and bg(page)=='rgb(36, 33, 48)')
  for kind,count in [('terms',16),('privacy',13)]:
   if kind=='privacy':page.locator('.legal-tabs a[href="#/privacy"]').click();settle(page)
   check(kind+' canonical text and markup unchanged',intact(page,kind))
   check(kind+' complete clauses',page.locator('.legal-body>section').count()==count+1)
   check(kind+' one document title',page.locator('#main h1').count()==1)
   check(kind+' title is correct',kind=='terms' and '이용약관' in page.title() or kind=='privacy' and '개인정보처리방침' in page.title())
   check(kind+' dark table and toc',page.locator('.legal-toc').evaluate('(x)=>getComputedStyle(x).backgroundColor')=='rgb(25, 23, 35)')
   page.locator('.legal-toc a').first.click();settle(page)
   check(kind+' contents stay inside route',page.url.endswith('#/'+kind+'?section='+kind+'-01'))
   check(kind+' contents target receives focus',page.evaluate('document.activeElement.id')==kind+'-01')
   check(kind+' contents target visible',page.locator('#'+kind+'-01').bounding_box()['y']>=0)
   page.go_back();settle(page);check(kind+' back restores document route',page.url.endswith('#/'+kind))
   page.go_forward();settle(page);check(kind+' forward restores section',page.url.endswith('section='+kind+'-01'))
   page.locator('[data-action=theme]').click();settle(page)
   check(kind+' switches to light without leaving document',bg(page)=='rgb(255, 255, 255)' and page.locator('[data-policy="'+kind+'"]').count()==1)
   page.locator('[data-action=theme]').click();settle(page)
   check(kind+' switches back to dark',bg(page)=='rgb(36, 33, 48)')
   page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/(kind+'-dark-desktop.png')),full_page=False)
   for width in [320,390,768,1440]:
    page.set_viewport_size({'width':width,'height':900});settle(page)
    check(kind+' no document overflow '+str(width),page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    check(kind+' body stays readable '+str(width),page.locator('.legal-document').evaluate('(x)=>parseFloat(getComputedStyle(x).fontSize)>=16'))
   page.set_viewport_size({'width':390,'height':844});page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/(kind+'-dark-mobile.png')),full_page=False)
   page.locator('[data-action=theme]').click();settle(page);page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/(kind+'-light-mobile.png')),full_page=False)
   page.locator('[data-action=theme]').click();settle(page)
   page.evaluate('document.documentElement.style.fontSize="200%"');settle(page)
   check(kind+' enlarged text reflows',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
   page.evaluate('document.documentElement.style.fontSize=""');page.set_viewport_size({'width':1440,'height':1000})
  check('privacy browser settings action retained',page.locator('[data-action=clear-data]').count()==1)
  page.locator('.legal-tabs a[href="#/guide"]').click();settle(page)
  check('fan guide still works',page.locator('#main a[href="#/record/fan-policy"]').count()>0)
  page.locator('.footer-links a').filter(has_text='개인정보처리방침').click();settle(page)
  check('footer privacy stays inside app',page.url==URL+'#/privacy')
  page.reload(wait_until='networkidle');check('direct privacy route and theme survive reload',bg(page)=='rgb(36, 33, 48)' and intact(page,'privacy'))
  # The real PHP renderer is used; this isolated fixture does not read production accounts.
  pub=b.new_context(viewport={'width':1440,'height':1000},locale='ko-KR',color_scheme='dark')
  for kind in ('terms','privacy'):
   html=subprocess.check_output(['php','-r',"require 'auth/View.php';echo Isegye\\Access\\View::"+kind+'();'],cwd=R).decode()
   pub.route('**/auth/'+kind,lambda route,body=html:route.fulfill(body=body,content_type='text/html; charset=utf-8'))
  pub.route('**/auth/legal.css',lambda r:r.fulfill(body=(R/'auth/legal.css').read_text(),content_type='text/css'))
  p=pub.new_page();p.on('pageerror',lambda e:errors.append(str(e)))
  for kind in ('terms','privacy'):
   p.goto(URL+'auth/'+kind,wait_until='networkidle')
   check('public '+kind+' uses site branding',p.locator('.legal-site-header').count()==1 and p.locator('.access-backdrop').count()==0)
   check('public '+kind+' no scripts or account actions',p.locator('script,a[href="/auth/login"]').count()==0)
   check('public '+kind+' OS dark mode',bg(p)=='rgb(36, 33, 48)')
   p.get_by_role('radio',name='라이트',exact=True).check();check('public '+kind+' light control',bg(p)=='rgb(255, 255, 255)')
   p.get_by_role('radio',name='다크',exact=True).check();check('public '+kind+' dark control',bg(p)=='rgb(36, 33, 48)')
   check('public '+kind+' body unchanged',intact(p,kind))
   check('public '+kind+' no cookies',not pub.cookies())
   p.screenshot(path=str(OUT/(kind+'-public-dark.png')),full_page=False)
   for w in [320,390,768]:
    p.set_viewport_size({'width':w,'height':844});check('public '+kind+' reflow '+str(w),p.evaluate('document.documentElement.scrollWidth<=innerWidth'))
   p.set_viewport_size({'width':1440,'height':1000})
  check('no browser exceptions',not errors);b.close()
finally:
 (OUT/'result.json').write_text(json.dumps({'url':URL,'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks,'browserErrors':errors},ensure_ascii=False,indent=2)+'\n')
