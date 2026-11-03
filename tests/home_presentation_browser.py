"""Exercise final built search/gallery with deterministic public-data mocks."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = os.getenv('PRESENTATION_URL', 'http://127.0.0.1:4199/').rstrip('/') + '/'
OUT = Path(os.getenv('PRESENTATION_OUT', ROOT / 'test-results/home-presentation'))
OUT.mkdir(parents=True, exist_ok=True)
checks, errors = [], []

def check(name, condition):
    checks.append({'name': name, 'passed': bool(condition)})
    assert condition, name

with sync_playwright() as pw:
    options = {'executable_path': os.environ['CHROMIUM_PATH']} if os.getenv('CHROMIUM_PATH') else {}
    browser = pw.chromium.launch(**options)
    try:
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce', locale='ko-KR')
        page = context.new_page()
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.route('https://chapi.sooplive.co.kr/**', lambda r: r.fulfill(status=503, body='test offline'))
        page.route('**/api/schedule', lambda r: r.fulfill(json=json.loads((ROOT / 'schedule/snapshot.json').read_text())))
        page.route('**/api/music', lambda r: r.fulfill(status=503, body='test offline'))
        page.goto(URL + '#/home', wait_until='networkidle')
        field = page.locator('#header-search-input')
        field.click()
        check('click focuses input without navigation', page.evaluate('location.hash==="#/home" && document.activeElement.id==="header-search-input"'))
        field.fill('  리와인드  ')
        check('typing does not navigate', page.evaluate('location.hash==="#/home"'))
        field.press('Enter')
        page.wait_for_url('**/#/search?*')
        page.wait_for_selector('#search-input')
        check('Enter sends trimmed Korean query', parse_qs(page.evaluate('location.hash').split('?', 1)[1])['q'] == ['리와인드'])
        check('result page retains query', page.locator('#search-input').input_value() == '리와인드')
        check('matching results are immediately present', page.locator('.result-row').count() > 0)
        page.reload(wait_until='networkidle')
        check('reload restores both search inputs', field.input_value() == '리와인드' and page.locator('#search-input').input_value() == '리와인드')
        field.fill('아이네');page.locator('#header-search button').click()
        page.wait_for_function('document.querySelector("#search-input")?.value==="아이네"')
        check('search button sends another query', field.input_value() == '아이네')
        page.go_back(wait_until='networkidle')
        check('back restores original query', page.locator('#search-input').input_value() == '리와인드' and field.input_value() == '리와인드')
        page.goto(URL + '#/home', wait_until='networkidle')
        field.fill('   ');field.press('Enter')
        check('blank input stays on home', page.evaluate('location.hash==="#/home"'))
        field.fill('아이네')
        field.dispatch_event('compositionstart')
        field.press('Enter')
        check('IME confirmation does not submit', page.evaluate('location.hash==="#/home"'))
        field.dispatch_event('compositionend');field.press('Enter')
        page.wait_for_url('**/#/search?*')
        check('completed IME query submits', page.locator('#search-input').input_value() == '아이네')
        special = '<img src=x onerror=alert(1)> & # +'
        field.fill(special);field.press('Enter')
        page.wait_for_function('(q)=>document.querySelector("#search-input")?.value===q', arg=special)
        check('special characters round-trip safely', field.input_value() == special and page.locator('#main img[src=x]').count() == 0)
        page.goto(URL + '#/home', wait_until='networkidle')
        check('copyright contains FAN ARCHIVE once', page.locator('.footer small').inner_text().count('FAN ARCHIVE') == 1)
        gallery = page.locator('.hm-gallery')
        check('six photos and pause control exist', page.locator('.hm-gallery-count').inner_text() == '1 / 6' and page.locator('[data-gallery=pause]').count() == 1)
        check('reduced motion disables automatic playback', gallery.get_attribute('data-autoplay') == 'paused')
        for i in range(1, 6):
            page.locator('[data-gallery=next]').click()
            page.wait_for_function('(i)=>document.querySelector(".hm-gallery").dataset.index===String(i)', arg=i)
            page.wait_for_function('document.querySelector(".hm-group").complete')
            check('photo ' + str(i) + ' decodes at HD or above', page.locator('.hm-group').evaluate('(im)=>im.naturalWidth>=1280&&im.naturalHeight>=720'))
            check('photo ' + str(i) + ' stays same-origin and uncropped', page.locator('.hm-group').evaluate('(im)=>new URL(im.src).origin===location.origin&&getComputedStyle(im).objectFit==="contain"'))
        page.locator('[data-gallery=next]').click()
        page.wait_for_function('document.querySelector(".hm-gallery").dataset.index==="0"')
        check('manual wrap returns to existing artwork', page.locator('.hm-group').evaluate('(im)=>im.src.includes("isegye-group-hero")'))
        for theme in ('light', 'dark'):
            for width in (320, 390, 640, 768, 1440):
                page.set_viewport_size({'width': width, 'height': 1100})
                page.evaluate('(t)=>document.documentElement.dataset.theme=t', theme)
                check(f'{theme}/{width} no horizontal overflow', page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                check(f'{theme}/{width} usable header input', field.bounding_box()['width'] >= 120)
                check(f'{theme}/{width} visible uncropped photo', page.locator('.hm-group').bounding_box()['width'] >= 200)
                if width in (390, 1440):
                    page.screenshot(path=str(OUT / f'home-{theme}-{width}.png'), full_page=True)
        # Use a fresh page so pointer/focus cannot pause the automatic-rotation test.
        auto = context.new_page();auto.emulate_media(reduced_motion='no-preference')
        auto.on('pageerror', lambda err: errors.append(str(err)))
        auto.route('https://chapi.sooplive.co.kr/**', lambda r: r.fulfill(status=503, body='test offline'))
        auto.route('**/api/schedule', lambda r: r.fulfill(json=json.loads((ROOT / 'schedule/snapshot.json').read_text())))
        auto.route('**/api/music', lambda r: r.fulfill(status=503, body='test offline'))
        auto.clock.install(time=datetime.now(timezone.utc))
        auto.goto(URL + '#/home', wait_until='networkidle')
        auto.clock.run_for(9900)
        check('no automatic change before ten seconds', auto.locator('.hm-gallery').get_attribute('data-index') == '0')
        auto.clock.run_for(500)
        auto.wait_for_function('document.querySelector(".hm-gallery").dataset.index==="1"')
        check('automatic rotation starts at ten seconds', auto.locator('.hm-gallery-count').inner_text() == '2 / 6')
        auto.locator('[data-gallery=pause]').click();auto.mouse.move(0, 0);auto.locator('[data-gallery=pause]').blur()
        auto.clock.run_for(20000)
        check('explicit pause holds the photo', auto.locator('.hm-gallery').get_attribute('data-index') == '1')
        auto.locator('[data-gallery=pause]').click();auto.mouse.move(0, 0);auto.locator('[data-gallery=pause]').blur()
        auto.clock.run_for(10500)
        auto.wait_for_function('document.querySelector(".hm-gallery").dataset.index==="2"')
        check('resume restarts rotation', auto.locator('.hm-gallery-count').inner_text() == '3 / 6')
        auto.locator('.hm-gallery').hover();auto.clock.run_for(20000)
        check('hover pauses rotation', auto.locator('.hm-gallery').get_attribute('data-index') == '2')
        auto.evaluate('location.hash="#/members"');auto.wait_for_selector('.member-card')
        auto.clock.run_for(30000)
        check('navigation disposes gallery timers', auto.locator('.hm-gallery').count() == 0)
        check('no JavaScript errors', not errors)
    finally:
        (OUT / 'result.json').write_text(json.dumps({'url': URL, 'passed': sum(c['passed'] for c in checks), 'total': len(checks), 'checks': checks, 'browserErrors': errors}, ensure_ascii=False, indent=2) + '\n')
        browser.close()
print('Home presentation checks passed:', len(checks))
