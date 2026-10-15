"""Verify the actual downloadable single HTML file using file://, without a server."""
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
out = root / 'test-results'
out.mkdir(exist_ok=True)
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width':1440,'height':1100}, locale='ko-KR', color_scheme='light')
    page = context.new_page()
    errors = []
    requests = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: requests.append(request.url))
    page.goto((root/'dist/review.html').as_uri(), wait_until='load')
    page.locator('#main h1').wait_for(timeout=5000)
    assert page.locator('.nav a').count() == 8
    points = page.locator('.orbit-dot').evaluate_all('(nodes) => nodes.map(n => { const r=n.getBoundingClientRect(); return [Math.round(r.x),Math.round(r.y)]; })')
    assert len({tuple(p) for p in points}) == 6, 'Six orbital symbols must have distinct positions'
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
    assert page.evaluate('document.documentElement.scrollWidth') <= 390
    page.screenshot(path=str(out/'offline-mobile.png'), full_page=True)
    assert not errors, errors
    assert not [url for url in requests if url.startswith(('http:', 'https:'))], 'Offline review must not load external assets'
    context.close()
    browser.close()
print('PASS: standalone file://, 8 menus, six symbols, Korean initials, album tracks, bookmarks, mobile, no network assets.')
