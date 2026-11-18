#!/usr/bin/env python3
"""Describe the exact built catalog, without fetching sources or claiming deployment.

The production deployer separately binds this report to uploaded payload hashes.
A successful build alone is never publication evidence.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re
from build_review_1st import extract
from refresh_catalog_videos import channels
ROOT = Path(__file__).resolve().parents[1]


def build_report(root=ROOT):
    root = Path(root); out = root/'dist'
    meta = json.loads((out/'build-info.json').read_text())
    raw = (out/'src/data.js').read_bytes()
    data = extract(raw.decode(), 'REVIEW_DATA')
    original = json.loads((root/'catalog/videos.json').read_text())
    if original.get('schemaVersion') != 2 or data.get('scope',{}).get('videoCheckedAt') != original.get('checkedAt'):
        raise ValueError('Built catalog clock differs from collected source')
    expected = {c['key']:c['channelId'] for c in channels()}
    selected = {c['key']:c for c in original['channels']}
    rendered = {c['key']:c for c in data['channels']}
    if len(selected) != len(original['channels']) or {k:v.get('channelId') for k,v in selected.items()} != expected:
        raise ValueError('Catalog channel identities differ')
    html = (out/'index.html').read_text()
    parts = re.findall(r'<script src="(src/video-part-[0-9]{3}\.js)"></script>', html)
    if not parts or len(parts) != len(set(parts)):
        raise ValueError('Catalog chunk references missing or duplicated')
    built_ids = {v['id'] for v in data.get('videos', [])}
    hashes = {'src/data.js':hashlib.sha256(raw).hexdigest()}
    for name in parts:
        file = out/name
        if file.is_symlink() or not file.is_file() or file.stat().st_size > 8_000_000:
            raise ValueError('Invalid catalog chunk')
        raw = file.read_bytes(); text = raw.decode()
        if not text.startswith('REVIEW_DATA.videos.push(...') or not text.endswith(');\n'):
            raise ValueError('Unknown catalog chunk format')
        rows = json.loads(text[len('REVIEW_DATA.videos.push(...'):-3])
        built_ids.update(v['id'] for v in rows)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    sources = []
    for key,cid in expected.items():
        source = selected[key]; view = rendered.get(key,{})
        if view.get('channelId') != cid or view.get('checkedAt') != source.get('checkedAt') or view.get('status') != source.get('status'):
            raise ValueError('Built channel source metadata differs')
        if not {v['id'] for v in source['videos']} <= built_ids:
            raise ValueError('Collected video absent from built application')
        sources.append({'name':key,'state':source.get('status','unknown'),
            'lastSuccessAt':source.get('checkedAt'), 'historicalComplete':source.get('coverageComplete') is True,
            'videoCount':len(source['videos'])})
    return {'schemaVersion':1,'buildCommit':meta['commit'],'mode':meta['mode'],
        'builtAt':datetime.now(timezone.utc).isoformat(),'sourceAt':original['checkedAt'],
        'sources':sources, 'channelCount':len(expected), 'videoCount':len(built_ids),
        'bundleFiles':hashes,'publicationClaimed':False}

if __name__ == '__main__':
    report=build_report()
    (ROOT/'catalog-publication.json').write_text(json.dumps(report,ensure_ascii=False,sort_keys=True)+'\n')
    print('Exact built catalog evidence prepared; publication not yet claimed')
