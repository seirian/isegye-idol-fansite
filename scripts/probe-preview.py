"""Read-only public preview reachability check. Does not change Pages, DNS, or production.
A failed external preview is reported, not promoted as a successful deployment.
"""
import json
import os
import re
import socket
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
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
            page.wait_for_timeout(2500)
            row['status'] = response.status if response else None
            row['title'] = page.title()
            row['visibleText'] = page.locator('body').inner_text()[:1600]
            row['appLoaded'] = page.locator('#main h1').count() == 1
            row['menuCount'] = page.locator('.nav a').count()
            row['errors'] = errors
            page.screenshot(path=str(out / f'public-preview-{i}.png'), full_page=True)
        except Exception as error:
            row.update(error=str(error), appLoaded=False)
        report['browser'].append(row)
        context.close()
    browser.close()
text = json.dumps(report, ensure_ascii=False, indent=2)
(out/'preview-access.json').write_text(text, encoding='utf-8')
print(text)
