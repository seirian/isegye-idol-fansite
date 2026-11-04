"""Check real mobile header hit targets on the exact second-review artifact."""
from pathlib import Path
import json,os
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test-results/review-2nd-mobile';OUT.mkdir(parents=True,exist_ok=True)
checks=[];errors=[]
def check(name,value):
 checks.append({'name':name,'passed':bool(value)});assert value,name
with sync_playwright() as pw:
 opts={'executable_path':os.environ['CHROMIUM_PATH']} if os.getenv('CHROMIUM_PATH') else {}
 browser=pw.chromium.launch(**opts)
 try:
  page=browser.new_page(viewport={'width':390,'height':900},reduced_motion='reduce',locale='ko-KR')
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.route('https://**/*',lambda r:r.abort())
  if os.getenv('REVIEW_URL'):page.goto(os.environ['REVIEW_URL'],wait_until='domcontentloaded')
  else:
   page.evaluate("""()=>{const data=new Map();Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,String(v)),removeItem:k=>data.delete(k)}})}""")
   page.set_content((ROOT/'review-2nd-dist/review.html').read_text(),wait_until='domcontentloaded')
  for theme in ('dark','light'):
   for width in (320,390,640):
    page.set_viewport_size({'width':width,'height':900})
    page.evaluate('(t)=>{prefs.theme=t;persist();location.hash="#/home";render();scrollTo(0,0)}',theme)
    saved=page.locator('.top-actions>a.round-btn');toggle=page.locator('.top-actions>button[data-action=theme]')
    a=saved.bounding_box();b=toggle.bounding_box()
    check(f'{theme}/{width} separate hit targets',a['x']+a['width']<=b['x'] and b['x']+b['width']<=width)
    saved.click();expect(page.locator('h1')).to_contain_text('다시 보고')
    check(f'{theme}/{width} saved button opens saved page',page.evaluate('location.hash==="#/saved"'))
    page.evaluate('scrollTo(0,0)');toggle.click()
    check(f'{theme}/{width} theme button independently works',page.locator('html').get_attribute('data-theme')!=theme)
    toggle.click();check(f'{theme}/{width} theme restored',page.locator('html').get_attribute('data-theme')==theme)
    page.locator('[data-action=more]').click();page.locator('#more-menu a[href="#/content"]').click()
    expect(page.locator('h1')).to_have_text('콘텐츠')
    check(f'{theme}/{width} content reachable from More',page.locator('.tabbar .tab').count()==3)
  check('no browser errors',not errors)
 finally:
  (OUT/'result.json').write_text(json.dumps({'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks,'browserErrors':errors,'scope':'exact artifact; external sources denied'},ensure_ascii=False,indent=2)+'\n')
  browser.close()
print('Mobile header checks:',len(checks))
