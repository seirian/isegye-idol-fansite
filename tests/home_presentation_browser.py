"""Exercise final built search and image-only autoplay with public-data mocks."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import parse_qs
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
URL = os.getenv('PRESENTATION_URL', 'http://127.0.0.1:4199/').rstrip('/') + '/'
OUT = Path(os.getenv('PRESENTATION_OUT', ROOT / 'test-results/home-presentation'))
OUT.mkdir(parents=True, exist_ok=True)
checks, errors = [], []


def check(name, condition):
    checks.append({'name': name, 'passed': bool(condition)})
    assert condition, name


def prepare(page):
    page.on('pageerror', lambda err: errors.append(str(err)))
    page.route('https://chapi.sooplive.co.kr/**', lambda r: r.fulfill(status=503, body='test offline'))
    page.route('**/api/schedule', lambda r: r.fulfill(json=json.loads((ROOT / 'schedule/snapshot.json').read_text())))
    page.route('**/api/music', lambda r: r.fulfill(status=503, body='test offline'))
    page.clock.install(time=datetime.now(timezone.utc))


with sync_playwright() as pw:
    options = {'executable_path': os.environ['CHROMIUM_PATH']} if os.getenv('CHROMIUM_PATH') else {}
    browser = pw.chromium.launch(**options)
    try:
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce', locale='ko-KR')
        page = context.new_page()
        prepare(page)
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
        expect(page.locator('#search-input')).to_have_value('아이네')
        check('search button sends another query', field.input_value() == '아이네')
        page.go_back(wait_until='networkidle')
        expect(page.locator('#search-input')).to_have_value('리와인드')
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
        expect(page.locator('#search-input')).to_have_value(special)
        check('special characters round-trip safely', field.input_value() == special and page.locator('#main img[src=x]').count() == 0)
        page.goto(URL + '#/home', wait_until='networkidle')
        check('copyright contains FAN ARCHIVE once', page.locator('.footer small').inner_text().count('FAN ARCHIVE') == 1)
        gallery = page.locator('.hm-gallery')
        check('caption arrows play pause count and source are removed from DOM', gallery.locator('figcaption,button,a,[data-gallery],.hm-gallery-controls,.hm-gallery-count,.hm-gallery-source').count() == 0)
        check('only the image stage remains', gallery.locator(':scope > *').count() == 1 and gallery.locator('.hm-gallery-stage > img').count() == 1)
        check('gallery starts automatically without a control', gallery.get_attribute('data-autoplay') == 'playing')
        check('reduced motion has no animated transition', page.locator('.hm-group').evaluate('(im)=>getComputedStyle(im).transitionDuration==="0s"'))
        images = {page.locator('.hm-group').get_attribute('src')}
        for i in range(1, 6):
            page.clock.run_for(10000)
            expect(gallery).to_have_attribute('data-index', str(i))
            page.locator('.hm-group').evaluate('(im)=>im.decode()')
            images.add(page.locator('.hm-group').get_attribute('src'))
            check('photo ' + str(i) + ' decodes at HD or above automatically', page.locator('.hm-group').evaluate('(im)=>im.naturalWidth>=1280&&im.naturalHeight>=720'))
            check('photo ' + str(i) + ' stays same-origin and uncropped', page.locator('.hm-group').evaluate('(im)=>new URL(im.src).origin===location.origin&&getComputedStyle(im).objectFit==="contain"'))
        check('all six different photos are retained', len(images) == 6)
        page.clock.run_for(10000)
        expect(gallery).to_have_attribute('data-index', '0')
        check('automatic wrap returns to existing artwork', page.locator('.hm-group').evaluate('(im)=>im.src.includes("isegye-group-hero")'))
        for theme in ('light', 'dark'):
            for width in (320, 390, 640, 768, 1440):
                page.set_viewport_size({'width': width, 'height': 1100})
                page.evaluate('(t)=>document.documentElement.dataset.theme=t', theme)
                check(f'{theme}/{width} no horizontal overflow', page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                check(f'{theme}/{width} usable header input', field.bounding_box()['width'] >= 120)
                check(f'{theme}/{width} visible uncropped photo', page.locator('.hm-group').bounding_box()['width'] >= 200)
                frame = gallery.locator('.hm-gallery-stage').bounding_box()
                figure = gallery.bounding_box()
                check(f'{theme}/{width} no reserved caption height', abs(frame['height'] - figure['height']) < 1 and abs(frame['y'] - figure['y']) < 1)
                photo = page.locator('.hm-group').bounding_box()
                check(f'{theme}/{width} photo centered vertically inside frame', abs(photo['y'] + photo['height']/2 - frame['y'] - frame['height']/2) < 1)
                if width > 640:
                    card = page.locator('.hm-intro.hm-brief').bounding_box()
                    check(f'{theme}/{width} photo centered vertically in official news card', abs(figure['y'] + figure['height']/2 - card['y'] - card['height']/2) < 1)
                if width in (390, 1440):
                    page.screenshot(path=str(OUT / f'home-{theme}-{width}.png'), full_page=True)
                    page.locator('.hm-intro.hm-brief').screenshot(path=str(OUT / f'official-news-{theme}-{width}.png'))
        auto = context.new_page();auto.emulate_media(reduced_motion='no-preference')
        prepare(auto)
        auto.goto(URL + '#/home', wait_until='networkidle')
        ag = auto.locator('.hm-gallery')
        auto.clock.run_for(9000)
        check('no automatic change before ten seconds', ag.get_attribute('data-index') == '0')
        auto.clock.run_for(1500)
        expect(ag).to_have_attribute('data-index', '1')
        check('automatic rotation starts at ten seconds', ag.get_attribute('data-index') == '1')
        ag.hover();auto.clock.run_for(10000)
        expect(ag).to_have_attribute('data-index', '2')
        check('hover does not stop automatic rotation', ag.get_attribute('data-autoplay') == 'playing')
        ag.click();auto.clock.run_for(10000)
        expect(ag).to_have_attribute('data-index', '3')
        check('click does not stop or manually change rotation', ag.get_attribute('data-autoplay') == 'playing')
        auto.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'))")
        auto.clock.run_for(35000)
        check('hidden tab suspends rotation without losing photo', ag.get_attribute('data-index') == '3' and ag.get_attribute('data-autoplay') == 'paused')
        auto.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'))")
        auto.clock.run_for(9000)
        check('returning tab restarts a full interval', ag.get_attribute('data-index') == '3')
        auto.clock.run_for(1500)
        expect(ag).to_have_attribute('data-index', '4')
        check('visible tab resumes automatic rotation', ag.get_attribute('data-autoplay') == 'playing')
        auto.evaluate('location.hash="#/members"');auto.wait_for_selector('.catalog-member-card')
        auto.clock.run_for(30000)
        check('navigation disposes gallery timers', ag.count() == 0)
        auto.goto(URL + '#/home', wait_until='networkidle')
        expect(ag).to_have_attribute('data-index', '0')
        auto.clock.run_for(10500)
        expect(ag).to_have_attribute('data-index', '1')
        check('returning home has only one rotation timer', ag.count() == 1)
        broken = context.new_page();prepare(broken)
        broken.route('**/assets/group-gallery/mafia.webp*', lambda r: r.abort())
        broken.goto(URL + '#/home', wait_until='networkidle')
        broken.clock.run_for(10000)
        expect(broken.locator('.hm-gallery')).to_have_attribute('data-index', '2')
        check('failed image is skipped without rendering a broken image', broken.locator('.hm-group').evaluate('(im)=>im.complete&&im.naturalWidth>0'))
        check('no JavaScript errors', not errors)
    finally:
        (OUT / 'result.json').write_text(json.dumps({'url': URL, 'passed': sum(c['passed'] for c in checks), 'total': len(checks), 'checks': checks, 'browserErrors': errors}, ensure_ascii=False, indent=2) + '\n')
        browser.close()
print('Home presentation checks passed:', len(checks))
