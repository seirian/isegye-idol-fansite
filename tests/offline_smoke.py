"""Verify the downloadable second-design HTML using file:// without a server."""
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
out = root / 'test-results'
out.mkdir(exist_ok=True)
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width':1440,'height':1100}, locale='ko-KR', color_scheme='light', reduced_motion='reduce')
    page = context.new_page()
    errors = []
    requests = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: requests.append(request.url))
    page.route('https://**', lambda route: route.abort())
    page.goto((root/'dist/review.html').as_uri(), wait_until='load')
    page.locator('#main h1').wait_for(timeout=5000)
    assert page.locator('.nav a').count() == 7
    simple = page.locator('.hm-page').count() == 1
    assert page.locator('.hm-member' if simple else '.stage-lineup .polaroid').count() == 6
    assert page.locator('.hm-members img' if simple else '.stage-lineup img').evaluate_all('(els)=>els.length===6&&els.every(e=>e.complete&&e.naturalWidth>100)')
    page.screenshot(path=str(out/'offline-desktop.png'), full_page=True)
    page.evaluate("location.hash='#/search?q=ㅇㅇㄴ'")
    page.wait_for_timeout(100)
    assert '아이네' in page.locator('.result-row').first.inner_text()
    page.evaluate("location.hash='#/record/no-cat-no-life'")
    page.wait_for_timeout(100)
    assert page.locator('.track-list li').count() == 3
    page.locator('.detail-actions .save-button').click()
    page.evaluate("location.hash='#/saved'")
    page.wait_for_timeout(100)
    assert page.locator('.result-row').count() == 1
    page.reload(wait_until='load')
    assert page.locator('.result-row').count() == 1
    page.evaluate("location.hash='#/home'")
    page.wait_for_timeout(100)
    page.set_viewport_size({'width':390,'height':844})
    page.wait_for_timeout(100)
    assert page.evaluate('document.documentElement.scrollWidth') <= 390
    assert page.locator('[data-action=menu]').get_attribute('aria-expanded') == 'false'
    page.screenshot(path=str(out/'offline-mobile.png'), full_page=True)
    assert not errors, errors
    from urllib.parse import urlsplit
    assert all(urlsplit(u).hostname in {'chapi.sooplive.co.kr','i.ytimg.com','liveimg.sooplive.com'} for u in requests if u.startswith(('http:','https:'))), 'Unexpected external request'
    assert page.locator('.live-mini[data-state=offline]').count() == 0, 'Unavailable services must not imply broadcast ended'
    context.close()
    browser.close()
print('PASS: standalone file://, 7 menus, six portraits, Korean initials, album tracks, bookmarks, mobile, external services blocked, local artwork retained.')
