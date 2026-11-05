"""Two owner-requested community shortcuts in the operating navigation row.

Uses original official PNG bytes, embedded at build time. No third-party image
requests, credentials, runtime collection, public maintenance or review edits.
"""
import base64
import hashlib
import json
from pathlib import Path
from review_2nd_polish import one

ROOT = Path(__file__).resolve().parents[1]
DESTINATIONS = (
    ('waktree', '왁물원 · 네이버 카페', 'https://cafe.naver.com/steamindiegame'),
    ('berriz', '베리즈 · 이세계아이돌 팬클럽', 'https://berriz.in/ko/isegyeidol'),
)


def markup():
    assets = json.loads((ROOT / 'site/community-logos.json').read_text())
    if assets.get('schemaVersion') != 1 or set(assets['logos']) != {'waktree', 'berriz'}:
        raise ValueError('Unexpected community logo manifest')
    buttons = []
    for key, label, href in DESTINATIONS:
        asset = assets['logos'][key]
        encoded = ''.join(asset['base64Parts'])
        raw = base64.b64decode(encoded, validate=True)
        if (not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw) > 20000
                or hashlib.sha256(raw).hexdigest() != asset['sha256']):
            raise ValueError('Official logo bytes changed: ' + key)
        image = 'data:image/png;base64,' + encoded
        buttons.append(f'<a class="community-link" data-community="{key}" href="{href}" '
                       f'target="_blank" rel="noopener noreferrer" aria-label="{label} (새 탭)" '
                       f'title="{label} (새 탭)"><img src="{image}" width="28" height="28" '
                       'alt="" decoding="async" draggable="false"></a>')
    return '<div class="community-shortcuts" role="group" aria-label="커뮤니티 바로가기">' + ''.join(buttons) + '</div>'


def adapt_app(code):
    # Insert literal markup so the same pure shell also renders member documents.
    # Do not add anchors to the seven-item primary navigation or the public gate.
    code = one(code, '<div class="wrap"><nav class="desktop-nav"',
               '<div class="wrap community-menu-row"><nav class="desktop-nav"')
    return one(code, '</nav></div></header>', '</nav>' + markup() + '</div></header>')


def css():
    return (ROOT / 'site/community-shortcuts.css').read_text()
