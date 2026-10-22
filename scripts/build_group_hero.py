#!/usr/bin/env python3
"""Apply the user-supplied group illustration to the readability preview only."""
from __future__ import annotations
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'readability-dist'
IMAGE_NAME = 'isegye-group-hero.webp'
IMAGE_SHA = '3ce98e06f795aadbe983c12e7e04e74afa2dc6309402e6cc5b9e65750290a63a'
IMAGE_SIZE = (800, 450)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def patch_preview() -> None:
    if os.environ.get('DEPLOY_ENV') == 'production':
        raise RuntimeError('Group-photo change is review-only.')
    from PIL import Image
    asset = ROOT / 'review' / IMAGE_NAME
    if asset.is_symlink():
        raise RuntimeError('Symlink image refused')
    data = asset.read_bytes()
    if sha(data) != IMAGE_SHA:
        raise RuntimeError('User-supplied group image checksum mismatch')
    with Image.open(io.BytesIO(data)) as image:
        if image.format != 'WEBP' or image.size != IMAGE_SIZE:
            raise RuntimeError('Unexpected group illustration dimensions')
    image_url = './assets/' + IMAGE_NAME + '?v=' + IMAGE_SHA[:12]
    shutil.copyfile(asset, OUT / 'assets' / IMAGE_NAME)
    app_path = OUT / 'src/app.js'
    js = app_path.read_text(encoding='utf-8')
    start_marker = '<div class="hero-message" aria-hidden="true">'
    end_marker = '<div class="lineup-heading">'
    if js.count(start_marker) != 1 or js.count(end_marker) != 1:
        raise RuntimeError('Hero template changed; refusing an ambiguous replacement')
    start, end = js.index(start_marker), js.index(end_marker)
    if end <= start:
        raise RuntimeError('Hero template order changed')
    markup = ('<figure class="hero-group">'
              '<div class="hero-group-frame">'
              f'<img src="{image_url}" width="800" height="450" '
              'alt="함께 모여 웃고 있는 이세계아이돌 여섯 멤버의 단체 일러스트" '
              'decoding="async" loading="eager" fetchpriority="high">'
              '</div><figcaption><span aria-hidden="true">✦</span> 함께라서 더 빛나는 우리.</figcaption>'
              '</figure>')
    js = js[:start] + markup + '</div>' + js[end:]
    js = js.replace('가독성 개선 검토', '디자인 개선 검토')
    if 'YOU ARE INVITED TO' in js or 'OUR<br>UNIVERSE' in js:
        raise RuntimeError('Old invitation text remains')
    app_path.write_text(js, encoding='utf-8')
    css_path = OUT / 'src/styles.css'
    css = css_path.read_text(encoding='utf-8') + '\n' + (ROOT / 'review/group-hero.css').read_text(encoding='utf-8')
    css_path.write_text(css, encoding='utf-8')
    html_path = OUT / 'index.html'
    html = html_path.read_text(encoding='utf-8')
    if 'data-hero=' in html:
        raise RuntimeError('Group hero already applied')
    html = html.replace('<html ', '<html data-hero="group-photo" ', 1)
    html_path.write_text(html, encoding='utf-8')
    meta_path = OUT / 'build-info.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    meta['groupHero'] = {'source': 'user-provided illustration', 'sha256': IMAGE_SHA,
                         'width': 800, 'height': 450, 'cropped': False}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Rebuild the offline artifact with all images and exact CSP hashes.
    images = {p.stem: 'data:image/webp;base64,' + base64.b64encode(p.read_bytes()).decode()
              for p in (OUT / 'assets/portraits').glob('*.webp')}
    parts = []
    for name in ('data.js', 'lib.js', 'portraits.js', 'app.js'):
        part = (OUT / 'src' / name).read_text(encoding='utf-8')
        part = re.sub(r'^import .*;\r?\n', '', part, flags=re.M)
        parts.append(re.sub(r'^export ', '', part, flags=re.M))
    inline_js = 'const INLINE_PORTRAITS=' + json.dumps(images) + ';\nconst e=escapeHtml;\n' + '\n'.join(parts)
    inline_js = inline_js.replace('src="./assets/portraits/${m.id}.webp?v=${PORTRAITS[m.id].version}"', 'src="${INLINE_PORTRAITS[m.id]}"')
    inline_js = inline_js.replace(image_url, 'data:image/webp;base64,' + base64.b64encode(data).decode())
    offline = html.replace('<link rel="stylesheet" href="./src/styles.css">', '<style>' + css + '</style>')
    offline = offline.replace('<script type="module" src="./src/app.js"></script>', '<script type="module">' + inline_js + '</script>')
    icon = 'data:image/svg+xml;base64,' + base64.b64encode((OUT / 'assets/favicon.svg').read_bytes()).decode()
    offline = offline.replace('href="./assets/favicon.svg"', 'href="' + icon + '"')
    for kind, text in [('script', inline_js), ('style', css)]:
        digest = base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
        offline = offline.replace(kind + "-src 'self'", kind + "-src 'self' 'sha256-" + digest + "'")
    (OUT / 'review.html').write_text(offline, encoding='utf-8')
    subprocess.run(['node', '--check', str(app_path)], check=True)
    print(json.dumps({'groupHeroApplied': True, 'sha256': IMAGE_SHA, 'cropped': False}))

def main() -> None:
    if os.environ.get('DEPLOY_ENV') == 'production':
        raise RuntimeError('Review is not approved for production.')
    runpy.run_path(str(ROOT / 'scripts/build_readability.py'), run_name='__main__')
    patch_preview()

if __name__ == '__main__':
    main()
