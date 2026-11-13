"""Load exact approved profile derivatives without public HTTP requests."""
from pathlib import Path
import hashlib
import io
import json

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = {'ine', 'jingburger', 'lilpa', 'jururu', 'gosegu', 'viichan'}
LIMIT = 100_000

def load_soop(row):
    ident = row.get('id')
    if ident not in MEMBERS:
        raise ValueError('Unknown profile cache identity')
    parent = ROOT/'home-review'
    folder = parent/'soop-cache'
    manifest = parent/'soop-cache.json'
    path = folder/(ident+'.webp')
    if any(p.is_symlink() for p in (parent, folder, manifest, path)):
        raise ValueError('Profile cache symlink refused')
    metadata = json.loads(manifest.read_text())
    if metadata.get('schemaVersion') != 1 or set(metadata.get('images', {})) != MEMBERS:
        raise ValueError('Invalid profile cache manifest')
    entry = metadata['images'][ident]
    if row != entry['source']:
        raise ValueError('Profile source identity changed; review required')
    if not 0 < path.stat().st_size <= LIMIT:
        raise ValueError('Oversized profile cache')
    raw = path.read_bytes()
    if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
        raise ValueError('Profile cache digest mismatch')
    from PIL import Image
    with Image.open(io.BytesIO(raw)) as image:
        if (image.format != 'WEBP' or image.size != (entry['width'], entry['height'])
                or not all(1 <= value <= 144 for value in image.size)):
            raise ValueError('Profile cache dimensions changed')
        image.verify()
    return raw
