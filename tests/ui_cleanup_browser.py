"""Verify real built markup on desktop/mobile and preserved HOME polling.

SOOP responses in this suite are synthetic; no production account is used.
"""
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = os.environ.get('UI_CLEANUP_URL', 'http://127.0.0.1:4199/').rstrip('/') + '/'
OUT = Path(os.environ.get('UI_CLEANUP_OUT', ROOT / 'test-results/ui-cleanup'))
OUT.mkdir(parents=True, exist_ok=True)
MEMBERS = [('inehine', '아이네'), ('jingburger1', '징버거'), ('lilpa0309', '릴파'),
           ('cotton1217', '주르르'), ('gosegu2', '고세구'), ('viichan6', '비챤')]
checks, errors, calls = [], [], []


def check(name, ok):
    checks.append({'name': name, 'passed': bool(ok)})
    assert ok, name


try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 1000},
                                      locale='ko-KR', timezone_id='Asia/Seoul', reduced_motion='reduce')
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.clock.install(time=datetime.now(timezone.utc))

        def station(route):
            cid = route.request.url.split('/api/')[1].split('/')[0]
            name = dict(MEMBERS)[cid]
            calls.append(cid)
            stamp = datetime.fromtimestamp(page.evaluate('Date.now()') / 1000,
                                            timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')
            route.fulfill(json={'station': {'user_id': cid, 'user_nick': name},
                                'broad': None, 'current_timestamp': stamp},
                          headers={'Access-Control-Allow-Origin': '*'})

        page.route('https://chapi.sooplive.co.kr/**', station)
        page.route('**/api/schedule', lambda r: r.fulfill(json=json.loads((ROOT / 'schedule/snapshot.json').read_text())))
        page.route('**/api/music', lambda r: r.fulfill(status=503, body='unavailable'))
        page.goto(URL + '#/home', wait_until='networkidle')
        page.wait_for_function('document.querySelectorAll(".live-mini[data-state=offline]").length===6')
        check('initial HOME requests exactly six stations', len(calls) == 6)
        check('HOME refresh button is absent from DOM', page.locator('[data-live-key=home-refresh]').count() == 0)
        page.clock.run_for(31000)
        page.wait_for_function('document.querySelectorAll(".live-mini[data-state=offline]").length===6')
        page.wait_for_timeout(150)
        check('HOME still refreshes all six stations automatically after 30 seconds', len(calls) == 12)
        check('LIVE full-page link remains', page.locator('.live-top-actions a[href="#/live"]').count() == 1)
        page.locator('.top-search').click()
        check('search button still opens search', page.evaluate('location.hash.startsWith("#/search")'))
        page.goto(URL + '#/home', wait_until='networkidle')
        page.keyboard.press('/')
        check('keyboard search remains available without the visual hint', page.evaluate('location.hash.startsWith("#/search")'))
        page.goto(URL + '#/live', wait_until='networkidle')
        check('LIVE page keeps its manual refresh control', page.locator('[data-live-key=page-refresh]').count() == 1)
        for theme in ('light', 'dark'):
            for width in (320, 390, 768, 1440):
                page.set_viewport_size({'width': width, 'height': 1000})
                for route in ('home', 'music'):
                    page.goto(URL + '#/' + route, wait_until='networkidle')
                    page.evaluate('(theme)=>{document.documentElement.dataset.theme=theme;window.scrollTo(0,0)}', theme)
                    label = f'{theme}/{width}/{route}'
                    check(label + ' no archive badge', page.locator('.announcement a').count() == 0 and 'FAN ARCHIVE' not in page.locator('.announcement').inner_text())
                    check(label + ' no keyboard hint', page.locator('.top-search kbd').count() == 0)
                    check(label + ' no redundant members shortcut', page.locator('.nav-note').count() == 0)
                    check(label + ' no HOME manual refresh', page.locator('[data-live-key=home-refresh]').count() == 0)
                    check(label + ' original navigation retained', page.locator('[data-nav]').count() == 6)
                    check(label + ' no horizontal overflow', page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                    if route == 'home' and width in (390, 1440):
                        page.screenshot(path=str(OUT / f'home-{theme}-{width}.png'), full_page=False)
        check('no JavaScript exceptions', not errors)
        browser.close()
finally:
    (OUT / 'result.json').write_text(json.dumps({'url': URL, 'commit': os.getenv('GITHUB_SHA'),
        'scope': 'built UI with synthetic SOOP responses', 'passed': sum(x['passed'] for x in checks),
        'total': len(checks), 'checks': checks, 'browserErrors': errors}, ensure_ascii=False, indent=2) + '\n')
print('UI cleanup checks passed:', len(checks))
