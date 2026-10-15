"""Read-only public preview check. No Pages, DNS, server, or production modifications.
Only the hosting service's explicit Open the page notice is acknowledged for our own public code.
"""
import json
import os
import re
import socket
from pathlib import Path
from urllib.request import Request, urlopen
from playwright.sync_api import sync_playwright

out = Path('test-results')
out.mkdir(exist_ok=True)
sha = os.environ.get('GITHUB_SHA', '')
if not re.fullmatch(r'[0-9a-f]{40}', sha):
    raise ValueError('Expected a commit SHA from the Actions context')
urls = [
    'https://raw.githack.com/seirian/isegye-idol-fansite/develop/index.html',
    f'https://rawcdn.githack.com/seirian/isegye-idol-fansite/{sha}/index.html',
    'https://seirian.github.io/isegye-idol-fansite/',
]
report = {'commit': sha, 'http': [], 'browser': [], 'dns': {}}
for host in ['isegye-idol.kr', 'mir.yeop.net']:
    try:
        report['dns'][host] = sorted({r[4][0] for r in socket.getaddrinfo(host, 443)})
    except OSError as error:
        report['dns'][host] = str(error)
for url in urls:
    row = {'url': url}
    try:
        with urlopen(Request(url, headers={'User-Agent': 'ISEGYE-Archive-Review/0.1'}), timeout=15) as response:
            body = response.read(200000).decode('utf-8', errors='replace')
            title = re.search(r'<title>(.*?)</title>', body, re.S | re.I)
            row.update(status=response.status, contentType=response.headers.get('Content-Type'), title=title.group(1).strip() if title else None)
    except Exception as error:
        row.update(error=str(error))
    report['http'].append(row)
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    for i, url in enumerate(urls[:2]):
        context = browser.new_context(viewport={'width':1440,'height':1100}, locale='ko-KR')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        row = {'url': url}
        try:
            response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(1000)
            row['externalNoticeShown'] = 'External Content Notice' in page.title()
            if row['externalNoticeShown']:
                # Explicitly open only this known repository's own preview, no credentials supplied.
                opener = page.get_by_role('button', name='Open the page', exact=True)
                if opener.count() == 0:
                    opener = page.get_by_role('link', name='Open the page', exact=True)
                opener.click(timeout=5000)
            page.locator('#main h1').wait_for(timeout=15000)
            row['status'] = response.status if response else None
            row['title'] = page.title()
            row['appLoaded'] = page.locator('#main h1').count() == 1
            row['menuCount'] = page.locator('.nav a').count()
            page.screenshot(path=str(out/f'public-preview-{i}.png'), full_page=True)
            page.evaluate("location.hash='#/search?q=ㅇㅇㄴ'")
            page.wait_for_timeout(250)
            row['initialSearchResults'] = page.locator('.result-row h3').all_text_contents()
            row['errors'] = errors
            row['passed'] = row['menuCount'] == 8 and '아이네' in row['initialSearchResults'] and not errors
        except Exception as error:
            row.update(error=str(error), appLoaded=False, passed=False)
            try:
                row['visibleText'] = page.locator('body').inner_text()[:1600]
                page.screenshot(path=str(out/f'public-preview-{i}-error.png'), full_page=True)
            except Exception:
                pass
        report['browser'].append(row)
        context.close()
    browser.close()
text = json.dumps(report, ensure_ascii=False, indent=2)
(out/'preview-access.json').write_text(text, encoding='utf-8')
print(text)
