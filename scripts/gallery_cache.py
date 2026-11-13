"""Read the exact previously approved WebP derivatives without network access.

Original source URLs/checksums stay in gallery.json. Cache bytes are pinned
independently, bounded and decoded; a missing/changed cache fails closed.
"""
from pathlib import Path
import hashlib
import io
import json
import re

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 1_000_000

def load(row):
    ident = row.get('id', '')
    if not re.fullmatch('[a-z-]+', ident):
        raise ValueError('Unsafe gallery cache identity')
    folder = ROOT/'home-review/gallery-cache'
    manifest = ROOT/'home-review/gallery-cache.json'
    path = folder/(ident+'.webp')
    if folder.is_symlink() or manifest.is_symlink() or path.is_symlink():
        raise ValueError('Gallery cache symlink refused')
    metadata = json.loads(manifest.read_text())
    if metadata.get('schemaVersion') != 1:
        raise ValueError('Unknown gallery cache schema')
    entry = metadata['images'][ident]
    for source, target in [('sha256','sourceSha256'),('url','sourceUrl'),
                           ('width','sourceWidth'),('height','sourceHeight')]:
        if row.get(source) != entry.get(target):
            raise ValueError('Gallery cache source identity changed')
    if not 0 < path.stat().st_size <= LIMIT:
        raise ValueError('Oversized gallery cache')
    raw = path.read_bytes()
    if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
        raise ValueError('Gallery cache digest mismatch')
    from PIL import Image
    with Image.open(io.BytesIO(raw)) as image:
        if image.format != 'WEBP' or image.size != (entry['width'],entry['height']):
            raise ValueError('Gallery cache dimensions or format changed')
        image.verify()
    return raw
