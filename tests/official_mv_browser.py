"""Regression for the user-specified official MV; no mocked thumbnail responses."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import quote, urlencode
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
URL = os.environ.get('MV_URL', 'http://127.0.0.1:4197/').rstrip('/') + '/'
OUT = ROOT / os.environ.get('MV_OUT', 'test-results/visual/official-mv')
OUT.mkdir(parents=True, exist_ok=True)
VIDEO_ID = 'zGOzGcEbd-s'
VIDEO_URL = 'https://www.youtube.com/watch?v=' + VIDEO_ID
THUMB = 'https://i.ytimg.com/vi/' + VIDEO_ID + '/hqdefault.jpg'
checks, errors = [], []
server = None
report = {'url': URL, 'commit': os.environ.get('GITHUB_SHA'), 'intercepted': False}

def check(name, ok, detail=None):
    checks.append({'name': name, 'passed': bool(ok), 'detail': detail})
    if not ok:
        raise AssertionError(name + ': ' + str(detail))

def image_ready(page, selector):
    image = page.locator(selector)
    expect(image).to_have_count(1)
    image.scroll_into_view_if_needed()
    expect(image).to_have_attribute('src', THUMB)
    page.wait_for_function('''s=>{const i=document.querySelector(s);return i&&i.complete&&i.naturalWidth>=320&&!i.hidden;}''', arg=selector, timeout=20000)
    return image.evaluate('(i)=>({src:i.src,width:i.naturalWidth,height:i.naturalHeight,hidden:i.hidden})')

try:
    if 'MV_URL' not in os.environ:
        server = subprocess.Popen(['python', '-m', 'http.server', '4197', '--bind', '127.0.0.1', '--directory', 'live-dist'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(30):
            try:
                urlopen(URL, timeout=1).close()
                break
            except Exception:
                time.sleep(.1)
    with sync_playwright() as p:
        opts = {'headless': True}
        if os.environ.get('CHROMIUM_PATH'):
            opts['executable_path'] = os.environ['CHROMIUM_PATH']
        browser = p.chromium.launch(**opts)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='ko-KR', timezone_id='Asia/Seoul', reduced_motion='reduce')
        page = context.new_page()
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.goto(URL + '#/song/cat-save-world', wait_until='domcontentloaded')
        expect(page.locator('#main h1')).to_have_text('고양이가 세상을 구한다!')
        meta = context.request.get(URL + 'build-info.json').json()
        check('served commit matches review commit', meta['commit'] == os.environ.get('GITHUB_SHA', meta['commit']))
        action = page.locator('.catalog-song-detail .catalog-profile-actions a[href="' + VIDEO_URL + '"]')
        expect(action).to_have_count(1)
        check('song action opens the supplied official MV safely', action.get_attribute('target') == '_blank' and 'noopener' in action.get_attribute('rel'))
        check('official MV is listed as a source', page.locator('.catalog-detail-sources a[href="' + VIDEO_URL + '"]').count() == 1)
        report['detailThumbnail'] = image_ready(page, '.catalog-song-detail-visual .music-video-art>img')
        check('actual official MV thumbnail loads on song detail', report['detailThumbnail']['width'] >= 320)
        page.screenshot(path=str(OUT / 'cat-mv-detail-desktop.png'), full_page=True)
        page.goto(URL + '#/music?q=' + quote('고양이가 세상을 구한다'), wait_until='domcontentloaded')
        report['listThumbnail'] = image_ready(page, '[data-song="cat-save-world"] .music-video-art>img')
        check('music list uses the same MV thumbnail', report['listThumbnail']['src'] == THUMB)
        page.screenshot(path=str(OUT / 'cat-mv-music-list.png'), full_page=True)
        page.goto(URL + '#/record/gosegu', wait_until='domcontentloaded')
        report['memberThumbnail'] = image_ready(page, '[data-song="cat-save-world"] .music-video-art>img')
        check('Gosegu related music uses the same MV thumbnail', report['memberThumbnail']['src'] == THUMB)
        page.set_viewport_size({'width': 390, 'height': 844})
        page.goto(URL + '#/song/cat-save-world', wait_until='domcontentloaded')
        image_ready(page, '.catalog-song-detail-visual .music-video-art>img')
        check('mobile song detail has no horizontal overflow', page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.screenshot(path=str(OUT / 'cat-mv-detail-mobile.png'), full_page=True)
        # Optional metadata observation is separate from successful image/link tests.
        try:
            response = context.request.get('https://www.youtube.com/oembed?' + urlencode({'url': VIDEO_URL, 'format': 'json'}), timeout=15000)
            report['oembed'] = {'httpStatus': response.status}
            if response.ok:
                data = response.json()
                report['oembed'].update(title=data.get('title'), author=data.get('author_name'), authorUrl=data.get('author_url'))
        except Exception as exc:
            report['oembed'] = {'errorType': type(exc).__name__}
        check('no uncaught browser exceptions', not errors, errors)
        browser.close()
finally:
    report.update(checkedAt=datetime.now(timezone.utc).isoformat(), checks=checks, passed=sum(x['passed'] for x in checks), total=len(checks), browserErrors=errors)
    (OUT / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if server:
        server.terminate()
        server.wait(timeout=5)
print('Official MV checks passed:', len(checks))
