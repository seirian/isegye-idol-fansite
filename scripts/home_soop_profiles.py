"""Compile only the home shortcut portraits from verified public SOOP profiles.

These are channel/search profile images, not a choice of old or new avatars.
Runtime serves local images: no new browser tracking or profile API polling.
A changed public source requires review; it never silently replaces a member.
"""
from pathlib import Path
import hashlib
import io
import json
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = {'ine': ('아이네', 'inehine'), 'jingburger': ('징버거', 'jingburger1'),
           'lilpa': ('릴파', 'lilpa0309'), 'jururu': ('주르르', 'cotton1217'),
           'gosegu': ('고세구', 'gosegu2'), 'viichan': ('비챤', 'viichan6')}
LIMIT = 4 * 1024 * 1024

def validate(manifest):
    rows = manifest.get('members', [])
    if (manifest.get('source') != 'SOOP' or manifest.get('scope') != 'home-member-shortcuts-only'
            or len(rows) != 6 or {r.get('id') for r in rows} != set(MEMBERS)):
        raise ValueError('Exactly six home-only SOOP profiles required')
    for row in rows:
        name, channel = MEMBERS[row['id']]
        expected = 'https://profile.img.sooplive.co.kr/LOGO/' + channel[:2] + '/' + channel + '/' + channel + '.jpg'
        if (row.get('name') != name or row.get('channel') != channel or row.get('sourceImage') != expected
                or row.get('sourcePage') != 'https://www.sooplive.com/station/' + channel):
            raise ValueError('SOOP member or source mismatch')
        if row.get('sourceFormat') not in ('PNG','JPEG','WEBP') or not re.fullmatch('[0-9a-f]{64}', row.get('sourceSha256', '')) or not row.get('checkedAt'):
            raise ValueError('Missing verified profile checksum')
        if any(type(row.get(k)) is not int or not 48 <= row[k] <= 4096 for k in ('width','height')):
            raise ValueError('Invalid profile dimensions')
    return rows

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None

def download(row):
    request = urllib.request.Request(row['sourceImage'], headers={'User-Agent':'Mozilla/5.0', 'Referer':row['sourcePage']})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=25) as response:
        if response.status != 200 or response.url != row['sourceImage']:
            raise ValueError('Unexpected SOOP profile response')
        return response.read(LIMIT + 1)

def prepare(raw, row):
    if len(raw) > LIMIT or hashlib.sha256(raw).hexdigest() != row['sourceSha256']:
        raise ValueError('SOOP profile changed; review required: ' + row['id'])
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(raw)) as image:
        if image.format != row['sourceFormat'] or image.size != (row['width'], row['height']):
            raise ValueError('Unexpected SOOP profile image')
        image = ImageOps.exif_transpose(image).convert('RGB')
        image.thumbnail((144,144), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, 'WEBP', quality=92, method=6)
    return output.getvalue()

def build(output, fetcher=None):
    rows = validate(json.loads((ROOT/'home-review/soop-profiles.json').read_text()))
    folder = Path(output)/'assets/soop-profiles'
    if folder.is_symlink():
        raise ValueError('Refusing profile directory symlink')
    folder.mkdir(parents=True, exist_ok=True)
    profiles = {}
    for row in rows:
        data = prepare((fetcher or download)(row), row)
        target = folder/(row['id']+'.webp')
        if target.is_symlink():
            raise ValueError('Refusing profile file symlink')
        target.write_bytes(data)
        profiles[row['id']] = {'version':hashlib.sha256(data).hexdigest()[:12], 'source':'SOOP'}
    return profiles
