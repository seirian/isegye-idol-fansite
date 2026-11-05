"""Exercise requested removals on the exact artifact, without external data."""
from pathlib import Path
import json
import os
from playwright.sync_api import sync_playwright, expect
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'test-results/review-2nd-cleanup'
OUT.mkdir(parents=True, exist_ok=True)
checks, errors = [], []

def check(name, value):
    checks.append({'name': name, 'passed': bool(value)})
    assert value, name

def go(page, path):
    page.evaluate('(p)=>{location.hash="#/"+p;render();scrollTo(0,0)}', path)
    expect(page.locator('#main h1')).to_be_visible()

with sync_playwright() as pw:
    options = {'executable_path': os.environ['CHROMIUM_PATH']} if os.getenv('CHROMIUM_PATH') else {}
    browser = pw.chromium.launch(**options)
    try:
        context = browser.new_context(locale='ko-KR', viewport={'width': 1440, 'height': 1000})
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.route('https://**/*', lambda r: r.abort())
        old = {'theme': 'light', 'gallery': False, 'spoilers': True, 'density': 'list',
               'notifications': True, 'favorites': ['member:lilpa'], 'watched': ['video:test-existing']}
        seed = "localStorage.setItem('isegye:review2:prefs'," + json.dumps(json.dumps(old)) + ");"
        if os.getenv('REVIEW_URL'):
            page.add_init_script(seed)
            page.goto(os.environ['REVIEW_URL'], wait_until='domcontentloaded')
        else:
            page.evaluate("""()=>{const store=new Map();Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k)}})}""")
            page.evaluate(seed)
            page.set_content((ROOT / 'review-2nd-dist/review.html').read_text(), wait_until='domcontentloaded')
        check('returning visitor keeps theme and bookmarks', page.evaluate("prefs.theme==='light'&&prefs.favorites.includes('member:lilpa')&&prefs.watched.includes('video:test-existing')"))
        check('removed settings cannot leave hidden content or paused photos', page.evaluate("prefs.gallery===true&&prefs.spoilers===false&&prefs.density==='cards'&&prefs.notifications===false"))
        for theme in ('dark', 'light'):
            for width in (320, 390, 768, 1440):
                tag = f'{theme}/{width}'
                page.set_viewport_size({'width': width, 'height': 1000})
                page.evaluate('(t)=>{prefs.theme=t;persist()}', theme)
                go(page, 'home')
                check(tag+' no header guide/settings or empty tool wrapper', page.locator('.site-header a[href="#/guide"],.site-header a[href="#/settings"],.nav-tools').count() == 0)
                check(tag+' mobile More has no duplicated guide or settings', page.locator('#more-menu a[href="#/guide"],#more-menu a[href="#/settings"]').count() == 0)
                check(tag+' search saved theme controls retained', page.locator('#header-search,.top-actions a[aria-label="저장함"],.top-actions button[data-action="theme"]').count() == 3)
                page.locator('.top-actions button[data-action="theme"]').click()
                check(tag+' theme toggle works independently', page.locator('html').get_attribute('data-theme') != theme)
                page.locator('.top-actions button[data-action="theme"]').click()
                page.locator('footer a[href="#/guide"]').click()
                expect(page.locator('#main h1')).to_have_text('좋아하는 마음이 오래 가도록')
                check(tag+' operating guide available only as retained footer destination', page.locator('.legal-guide .text-card').count() == 3)
                go(page, 'settings')
                check(tag+' old settings bookmark redirects home', page.evaluate('location.hash==="#/home"') and page.locator('[data-setting]').count() == 0)
                go(page, 'content?tab=series')
                check(tag+' only three accepted content tabs', page.locator('.tabbar .tab').all_text_contents() == ['최근 영상','다시보기','시리즈·합방'])
                check(tag+' same-broadcast different-view panel absent', '같은 합방, 다른 시점' not in page.locator('#main').inner_text())
                check(tag+' both series cards retained', page.locator('#main a[href^="#/series/"]').count() == 2)
                for ident in ('festival-2025', 'music-beginning'):
                    page.locator('#main a[href="#/series/'+ident+'"]').click()
                    expect(page.locator('#main h1')).to_have_text('2025 이세계페스티벌' if ident=='festival-2025' else '처음 만나는 이세돌의 음악')
                    check(tag+'/'+ident+' context heading removed', '맥락을 더 살펴보기' not in page.locator('#main').inner_text())
                    check(tag+'/'+ident+' media and related records preserved', page.locator('.content-card').count() > 0 and page.locator('.row-card').count() == page.evaluate("D.history.filter(h=>h.title.includes('이세계페스티벌')).slice(-3).length"))
                    if theme == 'dark' and width in (390,1440):
                        page.screenshot(path=str(OUT / f'{ident}-{width}.png'), full_page=True)
                    go(page, 'content?tab=series')
                for path in ('content', 'content?tab=replay', 'event/'+page.evaluate('D.events[0].id'), 'home'):
                    go(page, path)
                    check(tag+'/'+path+' no dangling settings links', page.locator('a[href="#/settings"],[data-setting]').count() == 0)
                    check(tag+'/'+path+' no horizontal overflow', page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                if theme == 'dark' and width in (390,1440):
                    page.screenshot(path=str(OUT / f'home-{width}.png'), full_page=True)
                    go(page, 'content?tab=series')
                    page.screenshot(path=str(OUT / f'series-{width}.png'), full_page=True)
        check('no JavaScript errors', not errors)
    finally:
        (OUT / 'result.json').write_text(json.dumps({'passed': sum(x['passed'] for x in checks), 'total': len(checks), 'checks': checks, 'browserErrors': errors, 'scope': 'exact review artifact; external sources blocked; synthetic local preferences'}, ensure_ascii=False, indent=2)+'\n')
        browser.close()
print('Review cleanup checks:', len(checks))
