"""The exact promoted legal UI: shared shell, canonical text, theme and navigation."""
from pathlib import Path
import json, os
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test-results/member-legal-ui';OUT.mkdir(parents=True,exist_ok=True)
checks=[];errors=[]
def check(name,ok):
 checks.append({'name':name,'passed':bool(ok)});assert ok,name
with sync_playwright() as pw:
 browser=pw.chromium.launch(**({'executable_path':os.environ['CHROMIUM_PATH']} if os.getenv('CHROMIUM_PATH') else {}))
 try:
  page=browser.new_page(viewport={'width':1440,'height':1000},locale='ko-KR')
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.route('https://**/*',lambda r:r.abort())
  page.route('**/api/*',lambda r:r.fulfill(status=503,content_type='application/json',body='{}'))
  url=os.environ['PROMOTED_URL']
  page.goto(url+'#/guide',wait_until='load')
  menus=page.locator('.desktop-nav>a').all_text_contents()
  footer=page.locator('.footer-links a').all_text_contents()
  for theme in ('dark','light'):
   for width in (320,390,768,1440):
    page.set_viewport_size({'width':width,'height':1000})
    page.evaluate('(t)=>{prefs.theme=t;persist();location.hash="#/guide";render()}',theme)
    for kind,label in [('terms','이용약관'),('privacy','개인정보처리방침')]:
     page.locator('.footer-links a[href="#/'+kind+'"]').click()
     expect(page.locator('[data-policy]')).to_have_attribute('data-policy',kind)
     check(f'{theme}/{width}/{kind} in app route',page.url.startswith(url+'#/'+kind))
     check(f'{theme}/{width}/{kind} same main menu',page.locator('.desktop-nav>a').all_text_contents()==menus)
     check(f'{theme}/{width}/{kind} same footer',page.locator('.footer-links a').all_text_contents()==footer)
     check(f'{theme}/{width}/{kind} theme retained',page.locator('html').get_attribute('data-theme')==theme)
     check(f'{theme}/{width}/{kind} active tab',page.locator('.legal-tabs [aria-current=page]').inner_text()==label)
     check(f'{theme}/{width}/{kind} no public theme radios',page.locator('.legal-public-theme').count()==0)
     check(f'{theme}/{width}/{kind} no overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
     body=(ROOT/'auth'/f'{kind}.html').read_text()
     check(f'{theme}/{width}/{kind} exact policy text',page.locator('.legal-document').evaluate('(el,body)=>{const t=document.createElement("div");t.innerHTML=body;const n=x=>x.replace(/\\s+/g," ").trim();return n(el.textContent)===n(t.textContent)}',body))
     page.reload(wait_until='load');expect(page.locator('[data-policy]')).to_have_attribute('data-policy',kind)
     check(f'{theme}/{width}/{kind} reload keeps theme',page.locator('html').get_attribute('data-theme')==theme)
     toc=page.locator('.legal-toc a').nth(5);toc.click()
     expect(page.locator('#'+kind+'-06')).to_be_focused()
     page.wait_for_timeout(65)
     check(f'{theme}/{width}/{kind} anchor visible below header',page.locator('#'+kind+'-06').bounding_box()['y']>=40)
     page.locator('.legal-bottom a').click();expect(page.locator('#document-top')).to_be_focused()
     page.wait_for_timeout(40)
     if width in (390,1440):page.screenshot(path=str(OUT/f'{kind}-{theme}-{width}.png'),full_page=True)
    page.locator('.legal-tabs a[href="#/about"]').click();expect(page.locator('[data-operating-page=about]')).to_be_visible()
    check(f'{theme}/{width} about stays themed',page.locator('html').get_attribute('data-theme')==theme)
    page.locator('.legal-tabs a[href="#/terms"]').click();expect(page.locator('[data-policy=terms]')).to_be_visible()
    page.locator('.legal-tabs a[href="#/privacy"]').click();expect(page.locator('[data-policy=privacy]')).to_be_visible()
    page.go_back();expect(page.locator('[data-policy=terms]')).to_be_visible()
    check(f'{theme}/{width} back history supported',page.url.endswith('#/terms'))
  page.goto(url+'#/terms?section=terms-14',wait_until='load');expect(page.locator('#terms-14')).to_be_focused()
  page.locator('#terms-14').locator('..').locator('a[href="#/privacy"]').click();expect(page.locator('[data-policy=privacy]')).to_be_visible()
  check('cross-policy body link stays in app',page.url.endswith('#/privacy'))
  check('no browser errors',not errors)
 finally:
  (OUT/'result.json').write_text(json.dumps({'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks,'browserErrors':errors,'scope':'exact production artifact; external API reads blocked'},ensure_ascii=False,indent=2)+'\n')
  browser.close()
