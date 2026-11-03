"""Requested header search, footer deduplication and six-member gallery.

Public sources are checksum-pinned, decoded and served locally. A changed image
fails the build rather than silently publishing an unreviewed replacement.
"""
from pathlib import Path
import base64
import hashlib
import io
import json
import re
import urllib.request
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 12 * 1024 * 1024
HOSTS = {'cdn.kpopping.com', 'legacy.kpopping.com', 'isegye-festival.com'}
SEARCH = '<button class="top-search" data-action="search">${icon(\'search\')}<span>멤버·음악 검색</span></button>'
FORM = '<form class="top-search" id="header-search" role="search" aria-label="사이트 검색"><label class="sr-only" for="header-search-input">멤버·음악 검색</label><input id="header-search-input" name="q" type="search" maxlength="160" placeholder="멤버·음악 검색" autocomplete="off" enterkeyhint="search"><button type="submit" aria-label="검색">${icon(\'search\')}</button></form>'
HERO = '<img class="hm-group" src="./assets/isegye-group-hero.webp?v=3ce98e06f795" width="800" height="450" alt="이세계아이돌 여섯 멤버의 단체 일러스트" decoding="async" fetchpriority="high">'


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Home presentation anchor changed: ' + before[:70])
    return text.replace(before, after, 1)


def validate(rows):
    if len(rows) != 5 or len({r.get('id') for r in rows}) != 5:
        raise ValueError('Exactly five additional unique group photos required')
    for row in rows:
        if not re.fullmatch('[a-z-]+', row.get('id', '')):
            raise ValueError('Unsafe gallery id')
        url = urlparse(row.get('url', ''))
        if url.scheme != 'https' or url.hostname not in HOSTS or url.username or url.password:
            raise ValueError('Unreviewed gallery host')
        if (not re.fullmatch('[0-9a-f]{64}', row.get('sha256', '')) or
                row.get('sixMembersReviewed') is not True or
                type(row.get('width')) is not int or type(row.get('height')) is not int or
                not 1280 <= row['width'] <= 8192 or not 720 <= row['height'] <= 8192):
            raise ValueError('Unverified or low-resolution group image')
    return rows


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def download(row):
    request = urllib.request.Request(row['url'], headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=25) as response:
        if response.status != 200 or response.url != row['url']:
            raise ValueError('Unexpected gallery response')
        return response.read(LIMIT + 1)


def prepare(raw, row):
    if len(raw) > LIMIT or hashlib.sha256(raw).hexdigest() != row['sha256']:
        raise ValueError('Group image changed; review required: ' + row['id'])
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(raw)) as image:
        if image.size != (row['width'], row['height']):
            raise ValueError('Unexpected group image dimensions')
        image = ImageOps.exif_transpose(image).convert('RGB')
        # Never upscale or crop. 1600px is sufficient for the 440px display at 3x.
        image.thumbnail((1600, 1200), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, 'WEBP', quality=92, method=6)
    return output.getvalue()


def compose(app, css, out, meta, fetcher=None):
    rows = validate(json.loads((ROOT / 'home-review/gallery.json').read_text()))
    folder = Path(out) / 'assets/group-gallery'
    if folder.is_symlink():
        raise ValueError('Refusing gallery directory symlink')
    folder.mkdir(parents=True, exist_ok=True)
    gallery = [{'id': 'original', 'src': './assets/isegye-group-hero.webp?v=3ce98e06f795',
                'alt': '이세계아이돌 여섯 멤버의 단체 일러스트', 'source': ''}]
    for row in rows:
        data = prepare((fetcher or download)(row), row)
        path = folder / (row['id'] + '.webp')
        if path.is_symlink():
            raise ValueError('Refusing gallery file symlink')
        path.write_bytes(data)
        gallery.append({'id': row['id'], 'src': './assets/group-gallery/' + path.name + '?v=' + hashlib.sha256(data).hexdigest()[:12],
                        'alt': row['alt'], 'source': row['url']})
    app = once(app, SEARCH, FORM)
    app = once(app, 'ISEGYE FAN ARCHIVE · FAN ARCHIVE</small>', 'ISEGYE FAN ARCHIVE</small>')
    app = once(app, HERO, '${homeGalleryView()}')
    start, end = app.index('function searchView(params){'), app.index('function savedView()')
    search = app[start:end].replace('result.length', 'total')
    search = once(search, "result.map(resultRow).join('')", "result.map(resultRow).join('')+musicMatches.map(headerMusicResult).join('')")
    search = once(search, 'const result=searchRecords(records,query,{kind,member});',
                  'const result=searchRecords(records,query,{kind,member});\n const musicMatches=headerCatalogMatches(query,{kind,member},result),total=result.length+musicMatches.length;')
    app = app[:start] + search + app[end:]
    app = once(app, "document.getElementById('main').innerHTML=html;", "document.getElementById('main').innerHTML=html;\n homePresentationMount();")
    code = 'const HOME_GROUP_GALLERY=' + json.dumps(gallery, ensure_ascii=False) + ';\n' + (ROOT / 'home-review/presentation.js').read_text()
    app = once(app, 'shell();render();', code + '\nshell();render();')
    css += '\n' + (ROOT / 'home-review/presentation.css').read_text()
    meta['homePresentation'] = {'headerSearch': 'inline-submit-query', 'duplicateFooterRemoved': True,
                                'galleryImages': 6, 'intervalMs': 10000, 'additionalSourceImages': rows,
                                'noCropOrUpscale': True, 'rightsPermissionVerified': False}
    return app, css


def inline_gallery(text, out):
    for path in sorted((Path(out) / 'assets/group-gallery').glob('*.webp')):
        data = 'data:image/webp;base64,' + base64.b64encode(path.read_bytes()).decode()
        text = re.sub(r'\./assets/group-gallery/' + re.escape(path.name) + r'\?v=[0-9a-f]+', lambda _: data, text)
    return text
