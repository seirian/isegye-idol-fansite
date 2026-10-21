"""Verify the deployed develop site, not a third-party HTML proxy."""
import json
import os
from pathlib import Path
import time
from playwright.sync_api import sync_playwright

URL = 'https://seirian.github.io/isegye-idol-fansite/'
output = Path('test-results/pages')
output.mkdir(parents=True, exist_ok=True)
report = {'url': URL, 'expected_commit': os.environ['GITHUB_SHA']}
with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={'width': 1440, 'height': 1080})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    for attempt in range(12):
        response = context.request.get(URL + 'build-info.json?commit=' + report['expected_commit'])
        if response.ok and response.json().get('commit') == report['expected_commit']:
            report['build'] = response.json()
            break
        time.sleep(5)
    else:
        raise AssertionError('Pages has not published the expected commit')
    response = page.goto(URL, wait_until='networkidle')
    assert response.status == 200
    assert page.locator('.nav a').count() == 8
    page.locator('#main h1').wait_for()
    assert page.locator('meta[name="robots"]').get_attribute('content') == 'noindex,nofollow'
    page.screenshot(path=str(output / 'home-desktop.png'), full_page=True)
    page.goto(URL + '#/search?q=%E3%85%87%E3%85%87%E3%84%B4', wait_until='networkidle')
    page.locator('#main .result-row').get_by_role('heading', name='아이네', exact=True).wait_for()
    page.screenshot(path=str(output / 'search.png'), full_page=True)
    page.goto(URL + '#/music', wait_until='networkidle')
    page.wait_for_function("document.querySelectorAll('.music-card').length === 6")
    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto(URL + '#/home', wait_until='networkidle')
    page.locator('.hero').wait_for()
    page.wait_for_timeout(300)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(output / 'home-mobile.png'), full_page=True)
    page.get_by_role('button', name='메뉴 열기', exact=True).click()
    menu = page.locator('[data-action="menu"]')
    assert menu.get_attribute('aria-expanded') == 'true'
    assert menu.get_attribute('aria-label') == '메뉴 닫기'
    assert not errors, errors
    report.update(status='passed', navigation_items=8, music_items=6, korean_initial_search=True,
                  mobile_horizontal_overflow=False, browser_exceptions=errors)
    browser.close()
(output / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False, indent=2))
