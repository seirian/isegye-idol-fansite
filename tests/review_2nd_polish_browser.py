"""Check shared menu headings against the unmodified calendar and operating footer.

Uses the exact generated artifact. HTTPS data is denied, never auth-bypassed.
CI uses its normal local HTTP server; container-only verification is in-memory.
"""
from pathlib import Path
import json, os
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'test-results/review-2nd-polish'
OUT.mkdir(parents=True, exist_ok=True)
URL = os.getenv('REVIEW_URL')
checks, errors = [], []
HEAD = '#main :is(.page-heading,.heading-row,.live-page-heading)'
ROUTES = ['members', 'schedule', 'music', 'live', 'content', 'history',
          'search', 'saved', 'guide', 'about', 'status', 'review']
METRICS = '''h=>{const out={};for(const [key,el] of [
 ['container',h],['label',h.querySelector('.eyebrow,.live-onair')],
 ['title',h.querySelector('h1')],['description',h.querySelector('h1+p')]]){
 const s=getComputedStyle(el);out[key]=Object.fromEntries([
 'fontFamily','fontSize','fontWeight','lineHeight','letterSpacing','marginTop',
 'marginBottom','paddingTop','paddingBottom'].map(k=>[k,s[k]]));}
 const title=h.querySelector('h1').getBoundingClientRect();
 const label=h.querySelector('.eyebrow,.live-onair').getBoundingClientRect();
 const desc=h.querySelector('h1+p').getBoundingClientRect();
 out.gaps=[Math.round((title.top-label.bottom)*100)/100,Math.round((desc.top-title.bottom)*100)/100];return out}'''

def check(name, condition, detail=None):
    checks.append({'name': name, 'passed': bool(condition), **({'detail': detail} if detail is not None else {})})
    assert condition, name + (': ' + str(detail) if detail is not None else '')

def go(page, route):
    page.evaluate('(r)=>{location.hash="#/"+r;render();scrollTo({top:0,behavior:"instant"})}', route)
    expect(page.locator('#main h1')).to_be_visible()

with sync_playwright() as pw:
    options = {'executable_path': os.environ['CHROMIUM_PATH']} if os.getenv('CHROMIUM_PATH') else {}
    browser = pw.chromium.launch(**options)
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce', locale='ko-KR')
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.route('https://**/*', lambda r: r.abort())
        if URL:
            page.goto(URL, wait_until='domcontentloaded')
        else:
            page.evaluate("""()=>{const values=new Map();Object.defineProperty(window,'localStorage',{
             configurable:true,value:{getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,String(v)),removeItem:k=>values.delete(k)}})}""")
            page.set_content((ROOT / 'review-2nd-dist/review.html').read_text(), wait_until='domcontentloaded')
        for theme in ('dark', 'light'):
            page.evaluate('(t)=>{prefs.theme=t;persist()}', theme)
            for width in (320, 390, 640, 768, 1440, 1920):
                page.set_viewport_size({'width': width, 'height': 1000})
                go(page, 'schedule')
                reference = page.locator(HEAD).first.evaluate(METRICS)
                expected_size = 28 if width <= 640 else min(38, max(27, .027 * width))
                check(f'{theme}/{width} calendar retains original title size',
                      abs(float(reference['title']['fontSize'][:-2]) - expected_size) < .01)
                check(f'{theme}/{width} calendar retains original spacing', reference['gaps'] == [8, 10])
                for route in ROUTES:
                    go(page, route)
                    actual = page.locator(HEAD).first.evaluate(METRICS)
                    check(f'{theme}/{width}/{route} heading matches calendar', actual == reference,
                          {'reference': reference, 'actual': actual} if actual != reference else None)
                    check(f'{theme}/{width}/{route} no horizontal overflow',
                          page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                    footer = page.locator('footer')
                    check(f'{theme}/{width}/{route} four operating footer links',
                          footer.locator('.footer-links a').all_text_contents() == ['이용약관', '개인정보처리방침', '팬가이드', '사이트소개'])
                    check(f'{theme}/{width}/{route} no review label in copyright',
                          footer.locator('small').inner_text().endswith('ISEGYE FAN ARCHIVE'))
                    if theme == 'dark' and width in (390, 1440) and route in ('schedule', 'members', 'live', 'content', 'music', 'history', 'guide', 'about'):
                        page.evaluate('scrollTo({top:0,behavior:"instant"})')
                        page.wait_for_timeout(80)
                        page.screenshot(path=str(OUT / f'{route}-{theme}-{width}.png'), full_page=True)
                print('Checked headings:', theme, width, flush=True)
                go(page, 'home')
                check(f'{theme}/{width} footer aligned to main content', page.evaluate('Math.abs(document.querySelector("footer").getBoundingClientRect().left-(document.querySelector("#main").getBoundingClientRect().left+parseFloat(getComputedStyle(document.querySelector("#main")).paddingLeft)))<1'))
                check(f'{theme}/{width} operating home footer is compact', not page.locator('footer .footer-brand').is_visible())
                page.locator('footer a[href="#/guide"]').click()
                expect(page.locator('#main h1')).to_have_text('좋아하는 마음이 오래 가도록')
                check(f'{theme}/{width} guide restores operating introduction',
                      '안전한 참여와 정확한 정보, 함께 지키는 팬 가이드.' in page.locator('#main').inner_text())
                check(f'{theme}/{width} guide restores three operating cards', page.locator('.legal-guide .text-card').count() == 3)
                check(f'{theme}/{width} discarded guide tabs are absent', page.locator('#main .tabbar').count() == 0)
                check(f'{theme}/{width} guide details link to operating records',
                      page.locator('.text-card').evaluate_all('(es)=>es.every(e=>e.getAttribute("href").startsWith("/#/record/"))'))
                page.locator('footer a[href="#/about"]').click()
                expect(page.locator('#main [data-operating-page="about"]')).to_be_visible()
                # Layout regression supports both the immutable offline reference
                # and the updated production introduction.
                check(f'{theme}/{width} about is operating page not review guide',
                      page.locator('.legal-about').count() == 1
                      and page.locator('.review2-summary').count() == 0
                      and '비공식' in page.locator('#main').inner_text())
                check(f'{theme}/{width} policy destinations unchanged',
                      page.locator('footer .footer-links a').evaluate_all('(es)=>es.slice(0,2).map(e=>e.getAttribute("href"))') ==
                      ['https://isegye-idol.kr/auth/terms', 'https://isegye-idol.kr/auth/privacy'])
        check('no JavaScript errors', not errors, errors)
    finally:
        (OUT / 'result.json').write_text(json.dumps({'passed': sum(c['passed'] for c in checks), 'total': len(checks),
          'checks': checks, 'browserErrors': errors, 'scope': 'exact review artifact; external sources denied; local navigation' if URL else
          'exact standalone artifact in memory; external sources denied; synthetic localStorage'}, ensure_ascii=False, indent=2) + '\n')
        browser.close()
print('Heading/footer checks:', len(checks))
