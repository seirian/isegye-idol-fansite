#!/usr/bin/env python3
"""Verify the exact final bundle keeps every audited unavailable link disabled."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from music_video_sources import selections
from music_source_availability import digest, load_candidate, public_evidence


def extract(path, name):
    text = path.read_text()
    match = re.search(r'^const ' + re.escape(name) + r'=(.+);$', text, re.M)
    if not match:
        raise ValueError('Final bundle lacks ' + name)
    return json.loads(match[1])


def verify_bundle(directory):
    directory = Path(directory)
    config, rows = selections()
    candidate = load_candidate(config, rows)
    if candidate is None:
        raise ValueError('Explicit source audit verification is required before publication')
    metadata = json.loads((directory/'build-info.json').read_text())
    evidence = public_evidence(candidate)
    if (metadata.get('commit') != candidate['provenance']['commit']
            or metadata.get('musicVideoAudit', {}).get('availability') != evidence):
        raise ValueError('Final bundle source-audit provenance mismatch')
    data = extract(directory/'src/data.js', 'REVIEW_DATA')
    legacy = extract(directory/'src/production-ui.js', 'CATALOG')
    unavailable = {row['songId'] for row in candidate['unavailableSelections']}
    for name, songs in [('rendered catalogue', data['songs']), ('runtime feed baseline', legacy['music']['songs'])]:
        by_id = {song['id']: song for song in songs}
        if len(by_id) != len(songs) or not set(rows) <= set(by_id):
            raise ValueError('Missing or duplicate song history in ' + name)
        for sid, row in rows.items():
            song = by_id[sid]
            source = song.get('videoSource', {})
            if source.get('kind') != row['kind']:
                raise ValueError('Source classification changed in ' + name)
            if not row['videoId'] or sid in unavailable:
                if song.get('videoId') or song.get('url'):
                    raise ValueError('Unavailable playback was reintroduced in ' + name)
            else:
                if (song.get('videoId') != row['videoId']
                        or song.get('url') != 'https://www.youtube.com/watch?v=' + row['videoId']):
                    raise ValueError('Audited selection changed in ' + name)
            if row['videoId']:
                if (source.get('reviewedVideoId') != row['videoId']
                        or source.get('availability') != ('unavailable' if sid in unavailable else 'available')
                        or source.get('availabilityCheckedAt') != candidate['checkedAt']):
                    raise ValueError('Availability state changed in ' + name)
    app = (directory/'src/app.js').read_text()
    if 'function sourceAvailabilityAction(' not in app or 'sourceAvailabilityNotice(s)' not in app:
        raise ValueError('Final UI lacks the source availability adapter')
    return {'schemaVersion': 1, 'checkedAt': datetime.now(timezone.utc).isoformat(),
            'verified': True, 'publicationClaimed': False, 'availability': evidence,
            'quarantinedSongs': len(unavailable), 'existingUnresolvedSongs': len(candidate['unresolved']),
            'bundleFiles': {name: digest((directory/name).read_bytes()) for name in
                            ('build-info.json', 'src/data.js', 'src/production-ui.js', 'src/app.js')}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', default='dist')
    args = parser.parse_args()
    result = verify_bundle(Path(args.bundle))
    print(json.dumps(result, ensure_ascii=False))
