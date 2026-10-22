#!/usr/bin/env python3
"""Prepare checksum-pinned public Genie profiles for the readability review.

No credentials, hotlinking, old-image fallback, production access, or arbitrary URL
fetching. On any source change the build stops for review. Runtime serves local
WebP files; filenames and source checksums remain internal.
"""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
GROUP = 'https://www.genie.co.kr/detail/artistInfo?xxnm=81287268'
MEMBERS = {'ine': ('아이네','82604076'), 'jingburger': ('징버거','82604068'),
           'lilpa': ('릴파','82604072'), 'jururu': ('주르르','82064570'),
           'gosegu': ('고세구','82604071'), 'viichan': ('비챤','82604070')}
LIMIT = 8 * 1024 * 1024

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def validate_manifest(manifest: dict) -> list[dict]:
    records = manifest.get('members', [])
    if len(records) != 6 or {r.get('id') for r in records} != set(MEMBERS):
        raise ValueError('Exactly six distinct Genie member records required')
    for r in records:
        name, aid = MEMBERS[r['id']]
        if r.get('name') != name or r.get('artistId') != aid or r.get('status') != 'verified':
            raise ValueError('Member identity mismatch')
        expected_page = 'https://www.genie.co.kr/detail/artistInfo?xxnm=' + aid
        pattern = (r'https://image\.genie\.co\.kr/Y/IMAGE/IMG_ARTIST/\d{3}/\d{3}/\d{3}/'
                   + aid + r'_\d+_\d+_600x600\.JPG')
        if r.get('sourcePage') != expected_page or not re.fullmatch(pattern, r.get('sourceImage','')):
            raise ValueError('Only the selected member Genie enlarge-view URL is allowed')
        if r.get('file') != 'review/portraits/' + r['id'] + '.webp':
            raise ValueError('Unexpected output path')
        if not r.get('verifiedAt') or (r.get('width'), r.get('height')) != (600, 600):
            raise ValueError('Missing source verification/dimensions')
        for key in ('sourceSha256', 'sha256'):
            if not re.fullmatch(r'[0-9a-f]{64}', r.get(key,'')):
                raise ValueError('Missing checksum')
    return records

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None

def download(record: dict) -> bytes:
    request = urllib.request.Request(record['sourceImage'], headers={
        'User-Agent': 'Mozilla/5.0 (compatible; IsegyeFanReview/1.0)', 'Referer': GROUP})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=25) as response:
        if response.status != 200 or response.url != record['sourceImage']:
            raise ValueError('Unexpected source response')
        raw = response.read(LIMIT + 1)
    return raw

def prepare(raw: bytes, record: dict) -> bytes:
    if len(raw) > LIMIT or digest(raw) != record['sourceSha256']:
        raise ValueError('Original changed; review required: ' + record['id'])
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(raw)) as im:
        if im.format != 'JPEG' or im.size != (600, 600):
            raise ValueError('Expected original 600x600 JPEG')
        image = ImageOps.exif_transpose(im).convert('RGB')
        output = io.BytesIO()
        image.save(output, 'WEBP', quality=92, method=6)
    data = output.getvalue()
    if digest(data) != record['sha256']:
        raise ValueError('Prepared image changed; use pinned Pillow/libwebp build')
    return data

def main() -> None:
    manifest = json.loads((ROOT/'review/portraits.json').read_text(encoding='utf-8'))
    records = validate_manifest(manifest)
    folder = ROOT/'review/portraits'
    if (ROOT/'review').is_symlink() or folder.is_symlink():
        raise ValueError('Symlink asset directory refused')
    folder.mkdir(exist_ok=True)
    for r in records:
        target = ROOT/r['file']
        if target.is_symlink():
            raise ValueError('Symlink asset refused')
        if target.exists():
            if digest(target.read_bytes()) != r['sha256']:
                raise ValueError('Unexpected existing portrait; no automatic replacement')
            continue
        data = prepare(download(r), r)
        with target.open('xb') as handle:
            handle.write(data)
        print(r['id'] + ': verified 600x600 Genie portrait')

if __name__ == '__main__':
    main()
