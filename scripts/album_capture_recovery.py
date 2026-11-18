"""Recover only real missing Melon chart hours from trusted lightweight captures.

No third-party scraping, current-chart mutation or credential forwarding.
Every candidate is bound to its original same-repository main workflow run, ZIP
digest, source URL, source clock and complete 100-rank chart.
"""
from copy import deepcopy
from datetime import timedelta
from io import BytesIO
import hashlib
import json
import re
import stat
import time
import zipfile

from album_hourly import KINDS, allowed, clock, coverage, now

REPO = 'seirian/isegye-idol-fansite'
API = 'https://api.github.com/repos/' + REPO
ARTIFACT = 'melon-chart-capture'
WORKFLOW = '.github/workflows/melon-chart-capture.yml'
SOURCE_TYPE = 'melon_public_full_chart'
SOURCES = {'melon_top100': 'https://www.melon.com/chart/index.htm',
           'melon_hot100': 'https://www.melon.com/chart/hot100/index.htm?chartType=D100'}
MAX_CAPTURE_BYTES = 100_000


def read_capture(raw, digest, run_id, attempt, at=None):
    at = at or now()
    if digest != 'sha256:' + hashlib.sha256(raw).hexdigest():
        raise ValueError('Capture ZIP checksum mismatch')
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        files = [r for r in archive.infolist() if r.filename == 'melon-chart-capture.json']
        if (len(files) != 1 or not 0 < files[0].file_size <= MAX_CAPTURE_BYTES
                or stat.S_ISLNK(files[0].external_attr >> 16)):
            raise ValueError('Missing, duplicate or unsafe capture')
        data = json.loads(archive.read(files[0]))
    if (not isinstance(data, dict) or data.get('schemaVersion') != 1
            or data.get('repository') != REPO or data.get('workflow') != 'melon-chart-capture.yml'
            or data.get('sourceType') != SOURCE_TYPE
            or type(data.get('runId')) is not int or data['runId'] != run_id
            or type(data.get('runAttempt')) is not int or data['runAttempt'] != attempt
            or not isinstance(data.get('charts'), dict)
            or not data['charts'] or set(data['charts']) - set(KINDS)):
        raise ValueError('Untrusted capture metadata')
    checked = clock(data['checkedAt'])
    if not timedelta(0) <= at - checked <= timedelta(days=2):
        raise ValueError('Capture outside recovery window')
    if data.get('status') != ('complete' if set(data['charts']) == set(KINDS) else 'partial'):
        raise ValueError('Capture health mismatch')
    for kind, chart in data['charts'].items():
        if not isinstance(chart, dict):
            raise ValueError('Invalid chart object')
        source_at = clock(chart['sourceAt'])
        rows = chart.get('rows')
        if (chart.get('source') != SOURCES[kind]
                or not isinstance(chart.get('responseSha256'), str)
                or not re.fullmatch(r'[0-9a-f]{64}', chart['responseSha256'])
                or source_at != source_at.replace(minute=0, second=0, microsecond=0)
                or source_at != checked.replace(minute=0, second=0, microsecond=0)
                or not timedelta(0) <= checked - source_at <= timedelta(hours=1)
                or not timedelta(0) <= at - source_at <= timedelta(days=2)
                or not allowed(source_at)
                or not isinstance(rows, list) or len(rows) != 100):
            raise ValueError('Invalid original chart clock, source or size')
        ids, ranks = set(), set()
        for row in rows:
            if (not isinstance(row, list) or len(row) != 2 or not isinstance(row[0], str)
                    or not re.fullmatch(r'[0-9]{1,12}', row[0])
                    or type(row[1]) is not int or not 1 <= row[1] <= 100
                    or row[0] in ids or row[1] in ranks):
                raise ValueError('Duplicate or invalid chart song/rank')
            ids.add(row[0])
            ranks.add(row[1])
        if ranks != set(range(1, 101)):
            raise ValueError('Chart does not contain exactly 1–100')
    return data


def missing_hours(current, at):
    return {kind: {clock(t) for t in row['missingSlots']}
            for kind, row in coverage(current, at, hours=48)['charts'].items()}


def add_capture(current, captured, at=None):
    """Use the already verified complete chart to prove both ranked and out."""
    at = at or now()
    added = conflicts = 0
    for kind, chart in captured['charts'].items():
        source_at = clock(chart['sourceAt'])
        if not timedelta(0) <= at - source_at <= timedelta(days=30) or not allowed(source_at):
            continue
        rankings = dict(chart['rows'])
        for item in current['tracks'].values():
            song_id = item.get('melon', {}).get('trackId')
            if not song_id:
                continue
            prior = item.setdefault('charts', {}).setdefault(kind, [])
            indexed = {clock(point['at']): point for point in prior}
            rank = rankings.get(song_id)
            point = {'at': source_at.isoformat(), 'trackId': song_id,
                     'rank': rank, 'status': 'ranked' if rank is not None else 'out'}
            old = indexed.get(source_at)
            if (old is not None and old.get('trackId') == song_id
                    and ((old.get('status') == 'ranked' and type(old.get('rank')) is int
                          and 1 <= old['rank'] <= 100)
                         or (old.get('status') == 'out' and old.get('rank') is None))):
                if old.get('rank') != rank or old.get('status') != point['status']:
                    conflicts += 1
                continue
            indexed[source_at] = point
            updated = sorted(indexed.values(), key=lambda p: clock(p['at']))[-1440:]
            item['charts'][kind] = updated
            item['melon'][kind.replace('melon_', '') + 'History'] = deepcopy(updated)
            added += 1
    return added, conflicts


def recover(current, report, token, deadline, getter, at=None):
    """Inspect a bounded 48h window. A missing or bad artifact is not evidence."""
    at = at or now()
    wanted = missing_hours(current, at)
    if not any(wanted.values()):
        return
    candidates, seen = [], set()
    for page in range(1, 4):
        if time.monotonic() > deadline:
            report['errors'].append({'source': ARTIFACT, 'error': 'InspectionBudgetExceeded'})
            return
        response = getter(API + '/actions/artifacts?name=' + ARTIFACT +
                          '&per_page=100&page=' + str(page), token)
        entries = response.get('artifacts')
        if not isinstance(entries, list) or len(entries) > 100:
            raise ValueError('Invalid capture artifact listing')
        for artifact in entries:
            if not isinstance(artifact, dict):
                raise ValueError('Invalid capture artifact')
            ident = artifact.get('id')
            if type(ident) is not int or ident <= 0 or ident in seen:
                raise ValueError('Invalid or duplicate capture artifact')
            seen.add(ident)
            created = clock(artifact['created_at'])
            if (artifact.get('name') != ARTIFACT or artifact.get('expired')
                    or not 0 < artifact.get('size_in_bytes', 0) <= 8_000_000
                    or not timedelta(0) <= at - created <= timedelta(days=2)):
                continue
            if any(-timedelta(minutes=15) <= created - hour <= timedelta(hours=2)
                   for hours in wanted.values() for hour in hours):
                candidates.append(artifact)
        if len(entries) < 100:
            break
    for artifact in sorted(candidates, key=lambda row: row['created_at'], reverse=True)[:80]:
        if not allowed() or time.monotonic() > deadline:
            report['errors'].append({'source': ARTIFACT, 'error': 'InspectionBudgetExceeded'})
            break
        if not any(wanted.values()):
            break
        try:
            run_id = artifact['workflow_run']['id']
            run = getter(API + '/actions/runs/' + str(int(run_id)), token)
            if (run.get('id') != run_id or run.get('head_branch') != 'main'
                    or run.get('path') != WORKFLOW
                    or run.get('event') not in ('schedule', 'workflow_dispatch')
                    or run.get('status') != 'completed'
                    or run.get('repository', {}).get('full_name') != REPO
                    or artifact['workflow_run'].get('head_sha') != run.get('head_sha')
                    or not re.fullmatch(r'sha256:[0-9a-f]{64}', artifact.get('digest', ''))):
                raise ValueError('Untrusted capture workflow provenance')
            raw = getter(API + '/actions/artifacts/' + str(artifact['id']) + '/zip',
                         token, binary=True)
            captured = read_capture(raw, artifact['digest'], run_id, run['run_attempt'], at)
            if not any(clock(chart['sourceAt']) in wanted[kind]
                       for kind, chart in captured['charts'].items()):
                continue
            count, conflicts = add_capture(current, captured, at)
            report['addedPoints'] += count
            report['conflicts'] += conflicts
            report['artifacts'].append({
                'id': artifact['id'], 'runId': run_id, 'digest': artifact['digest'],
                'sourceType': SOURCE_TYPE,
                'sourceHours': {kind: chart['sourceAt'] for kind, chart in captured['charts'].items()},
                'sourceUrls': {kind: chart['source'] for kind, chart in captured['charts'].items()},
                'addedPoints': count})
            wanted = missing_hours(current, at)
        except Exception as exc:
            report['errors'].append({'artifactId': artifact['id'], 'source': ARTIFACT,
                                     'error': type(exc).__name__})
    report['captureMissingAfter'] = {kind: len(hours) for kind, hours in wanted.items()}
