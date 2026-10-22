"""Verify the uploaded group hero locally, offline, or on the published review."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / os.environ.get('GROUP_HERO_OUT_DIR', 'test-results/group-hero')
BUILD = Path(os.environ.get('GROUP_HERO_BUILD_DIR', 'readability-dist'))
MODE = os.environ.get('GROUP_HERO_EXPECT_MODE', 'preview')
OUT.mkdir(parents=True, exist_ok=True)
URL = os.environ.get('GROUP_HERO_URL', 'http://127.0.0.1:4182/').rstrip('/') + '/'
SHA = '3ce98e06f795aadbe983c12e7e04e74afa2dc6309402e6cc5b9e65750290a63a'
checks, errors, external = [], [], []
server = None

def check(name, passed):
    checks.append({'name': name, 'passed': bool(passed)})
    assert passed, name

try:
    if 'GROUP_HERO_URL' not in os.environ:
        server = subprocess.Popen(['python', '-m', 'http.server', '4182', '--bind', '127.0.0.1', '--directory', str(BUILD)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                urlopen(URL, timeout=1).close()
                break
            except OSError:
                time.sleep(.1)
    with sync_playwright() as p:
        launch = {'headless': True}
        if os.environ.get('CHROMIUM_PATH'):
            launch['executable_path'] = os.environ['CHROMIUM_PATH']
        browser = p.chromium.launch(**launch)
        context = browser.new_context(viewport={'width': 1440, 'height': 1050}, locale='ko-KR', timezone_id='Asia/Seoul', reduced_motion='reduce', color_scheme='light')
        page = context.new_page()
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.on('request', lambda req: external.append(req.url) if req.url.startswith('http') and urlparse(req.url).netloc != urlparse(URL).netloc else None)
        response = page.goto(URL, wait_until='networkidle')
        page.locator('.hero-group img').wait_for()
        check('HTTP 200', response.status == 200)
        check('group hero marker', page.locator('html').get_attribute('data-hero') == 'group-photo')
        check('correct indexing mode', page.locator('meta[name=robots]').get_attribute('content') == ('index,follow' if MODE == 'production' else 'noindex,nofollow'))
        check('old invitation removed', page.locator('.hero-message,.universe-ticket,.float-caption,.sticker-star').count() == 0)
        check('invitation text absent', 'YOU ARE INVITED TO' not in page.locator('#main').inner_text())
        check('six Genie profile cards retained', page.locator('.stage-lineup .portrait img').count() == 6)
        image = page.locator('.hero-group img')
        check('user illustration fully decoded', image.evaluate('(e)=>e.complete&&e.naturalWidth===800&&e.naturalHeight===450'))
        check('image is same-origin', urlparse(image.get_attribute('src')).netloc == '')
        body = context.request.get(image.evaluate('(e)=>e.src')).body()
        check('exact supplied prepared image bytes', hashlib.sha256(body).hexdigest() == SHA)
        meta = context.request.get(URL + 'build-info.json').json()
        check('group image metadata matches', meta.get('groupHero', {}).get('sha256') == SHA)
        check('six verified profiles remain', meta.get('verifiedPortraitCount') == 6)
        expected = os.environ.get('GITHUB_SHA')
        if expected:
            check('published commit matches', meta.get('commit') == expected)
        for width in (320, 390, 640, 768, 960, 1024, 1280, 1440, 1920):
            page.set_viewport_size({'width': width, 'height': 950})
            check(f'{width}px hero image remains visible', image.is_visible())
            check(f'{width}px no page overflow', page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            dimensions = image.evaluate('(e)=>({w:e.clientWidth,h:e.clientHeight,fit:getComputedStyle(e).objectFit,filter:getComputedStyle(e).filter})')
            check(f'{width}px full 16:9 uncropped image', dimensions['fit'] == 'contain' and abs(dimensions['w'] / dimensions['h'] - 16/9) < .025)
            if width <= 960:
                below_copy = page.evaluate("document.querySelector('.hero-group').getBoundingClientRect().top>=document.querySelector('.hero-copy').getBoundingClientRect().bottom")
                check(f'{width}px image follows copy on small screens', below_copy)
        page.set_viewport_size({'width': 1440, 'height': 1050})
        check('desktop photo sits right of copy', page.evaluate("document.querySelector('.hero-group').getBoundingClientRect().left>document.querySelector('.hero-copy').getBoundingClientRect().left"))
        page.screenshot(path=str(OUT / 'home-desktop.png'), full_page=True)
        page.locator('.hero').screenshot(path=str(OUT / 'hero-desktop.png'))
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(OUT / 'home-mobile.png'), full_page=True)
        page.locator('.hero-intro').screenshot(path=str(OUT / 'hero-mobile.png'))
        page.get_by_role('button', name='색상 테마 변경', exact=True).click()
        check('dark mode keeps original colors', image.evaluate('(e)=>getComputedStyle(e).filter') == 'none')
        page.screenshot(path=str(OUT / 'home-dark-mobile.png'), full_page=True)
        page.evaluate("document.documentElement.dataset.theme='light'")
        page.set_viewport_size({'width': 1280, 'height': 1050})
        page.evaluate("document.documentElement.style.fontSize='200%'")
        check('200% text enlargement has no overflow', page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.evaluate("document.documentElement.style.fontSize='100%'")
        if 'GROUP_HERO_URL' not in os.environ and MODE == 'preview':
            offline = context.new_page()
            offline.on('pageerror', lambda err: errors.append(str(err)))
            offline.goto((ROOT / BUILD / 'review.html').as_uri(), wait_until='load')
            offline.locator('.hero-group img').wait_for()
            check('offline illustration embedded and decoded', offline.locator('.hero-group img').evaluate('(e)=>e.src.startsWith("data:image/webp;base64,")&&e.complete&&e.naturalWidth===800'))
            check('offline portraits retained', offline.locator('.stage-lineup img').evaluate_all('(es)=>es.length===6&&es.every(e=>e.complete&&e.naturalWidth===600)'))
        check('no browser exceptions', not errors)
        check('no automatic external asset requests', not external)
        browser.close()
finally:
    (OUT / 'result.json').write_text(json.dumps({'url': URL, 'commit': os.environ.get('GITHUB_SHA', 'local'), 'passed': sum(c['passed'] for c in checks), 'total': len(checks), 'checks': checks, 'browser_errors': errors, 'external_requests': external}, ensure_ascii=False, indent=2), encoding='utf-8')
    if server:
        server.terminate()
        server.wait(timeout=5)
print('Group hero checks passed:', len(checks))
