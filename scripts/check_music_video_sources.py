#!/usr/bin/env python3
"""Read-only identity/availability audit of the fixed reviewed video list.

The default remains strict. Production may explicitly quarantine a metadata
404 for an unchanged reviewed fan backup; it does not enable a broken link.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse
import io
import json
import os
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error

from music_video_sources import selections
from music_source_availability import (
    POLICY, REVIEWED_SELECTION_SHA256, availability_candidate, context,
    selection_digest, summarize,
)

ROOT = Path(__file__).resolve().parents[1]


def get(url, limit):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'ko-KR,ko;q=0.9'})
    with urllib.request.urlopen(request, timeout=15) as response:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Response limit exceeded')
        return data


def inspect(job, config):
    sid, row = job
    vid = row['videoId']
    result = {'songId': sid, 'videoId': vid, 'kind': row['kind'],
              'channelKey': row['channelKey'], 'ok': False, 'stage': 'metadata'}
    try:
        url = 'https://www.youtube.com/watch?v=' + vid
        data = json.loads(get('https://www.youtube.com/oembed?' + urllib.parse.urlencode(
            {'url': url, 'format': 'json'}), 128000))
        expected = config['channels'][row['channelKey']]
        result.update(title=data.get('title'), author=data.get('author_name'),
                      authorUrl=data.get('author_url'), metadataStatus=200)
        result['stage'] = 'identity'
        if data.get('author_url', '').rstrip('/').lower() != expected['url'].rstrip('/').lower():
            result['reasonCode'] = 'uploader_identity_changed'
            raise ValueError('Uploader identity changed')
        from PIL import Image
        result['stage'] = 'thumbnail'
        raw = get('https://i.ytimg.com/vi/' + vid + '/hqdefault.jpg', 1500000)
        with Image.open(io.BytesIO(raw)) as im:
            result.update(thumbnailWidth=im.width, thumbnailHeight=im.height)
            if im.width < 320 or im.height < 180:
                result['reasonCode'] = 'unverified_thumbnail'
                raise ValueError('Generic/unavailable thumbnail')
        result.update(ok=True, stage='complete')
    except urllib.error.HTTPError as error:
        result.update(error='HTTP ' + str(error.code),
                      reasonCode=result['stage'] + '_http_' + str(error.code))
        result['metadataStatus' if result['stage'] == 'metadata' else 'thumbnailStatus'] = error.code
    except Exception as error:
        result.update(error=type(error).__name__ + ': ' + str(error))
        result.setdefault('reasonCode', 'inspection_unknown')
    return result


def make_report(config, rows, results, allow_unavailable=False, checked_at=None):
    states, counts = summarize(results, config, rows, allow_unavailable)
    sources = {}
    for result in results:
        result['availability'] = states[result['songId']]
        source = sources.setdefault(result['channelKey'], {'available': 0, 'unavailable': 0, 'blocked': 0})
        source[result['availability']] += 1
    return {'schemaVersion': 2, 'checkedAt': checked_at or datetime.now(timezone.utc).isoformat(),
            'commit': os.getenv('GITHUB_SHA', 'local'), 'provenance': context(),
            'policy': POLICY if allow_unavailable else 'strict-all-selected-v1',
            'selectionSha256': selection_digest(config, rows),
            'scope': 'public metadata, uploader identity and thumbnail dimensions; not full video playback',
            'fullPlaybackVerified': False, 'catalogue': len(rows), 'selected': len(states),
            'passed': counts['available'], 'failed': counts['unavailable'] + counts['blocked'],
            'unavailable': counts['unavailable'], 'blockingFailures': counts['blocked'],
            'unresolved': sorted(sid for sid, row in rows.items() if not row['videoId']),
            'state': 'blocked' if counts['blocked'] else 'partial' if counts['unavailable'] else 'complete',
            'deploymentAllowed': counts['blocked'] == 0,
            'sourceStates': sources, 'results': results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-reviewed-backup-unavailable', action='store_true')
    args = parser.parse_args(argv)
    config, rows = selections()
    if args.allow_reviewed_backup_unavailable and selection_digest(config, rows) != REVIEWED_SELECTION_SHA256:
        raise ValueError('New or changed video selections require review; availability exception refused')
    jobs = [(sid, row) for sid, row in rows.items() if row['videoId']]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda job: inspect(job, config), jobs))
    report = make_report(config, rows, results, args.allow_reviewed_backup_unavailable)
    out = ROOT / 'test-results/music-sources'
    out.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode()
    (out / 'source-audit.json').write_bytes(raw)
    if args.allow_reviewed_backup_unavailable:
        candidate = availability_candidate(report, raw, config, rows)
        (out / 'source-availability.json').write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'results'}, ensure_ascii=False))
    failed = [result for result in results if not result['ok']]
    if failed:
        print(json.dumps(failed, ensure_ascii=False, indent=2))
    if not report['deploymentAllowed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
