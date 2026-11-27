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
MAX_ARTIFACT_PAGES = 12
MAX_CANDIDATES = 80


class CaptureSelectionError(ValueError):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def capture_document(raw, digest):
    """Validate the container only; its run/attempt still needs API binding."""
    if digest != 'sha256:' + hashlib.sha256(raw).hexdigest():
        raise ValueError('Capture ZIP checksum mismatch')
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        files = [r for r in archive.infolist() if r.filename == 'melon-chart-capture.json']
        if (len(files) != 1 or not 0 < files[0].file_size <= MAX_CAPTURE_BYTES
                or stat.S_ISLNK(files[0].external_attr >> 16)):
            raise ValueError('Missing, duplicate or unsafe capture')
        return json.loads(archive.read(files[0]))


def read_capture(raw, digest, run_id, attempt, at=None):
    at = at or now()
    data = capture_document(raw, digest)
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
    report['captureMissingAfter'] = {kind: len(hours) for kind, hours in wanted.items()}
    stats = {'targetSourceWindowStartAt': (at-timedelta(days=2)).isoformat(),
             'targetSourceWindowEndAt': at.isoformat(), 'listingScope': 'repository_artifacts',
             'pageBudget': MAX_ARTIFACT_PAGES, 'candidateBudget': MAX_CANDIDATES,
             'remainingSecondsAtStart': max(0, int(deadline-time.monotonic())),
             'apiCalls': 0, 'pagesRead': 0, 'artifactsSeen': 0, 'candidates': 0,
             'processedCandidates': 0, 'listingComplete': False, 'runArtifactQueries': 0}
    report['captureInspection'] = stats
    def request(url, *, binary=False):
        if time.monotonic() > deadline:
            raise CaptureSelectionError('capture_inspection_budget_exceeded')
        stats['apiCalls'] += 1
        return getter(url, token, binary=True) if binary else getter(url, token)
    run_lists = {}
    def run_artifacts(run_id):
        # A truncated repository listing cannot prove absence or uniqueness.
        # Captures have small per-run inventories; one complete page is required.
        if run_id not in run_lists:
            run_lists[run_id] = None
            stats['runArtifactQueries'] += 1
            try:
                result = request(API + '/actions/runs/' + str(run_id) + '/artifacts?per_page=100')
                rows, total = result.get('artifacts'), result.get('total_count')
                if (not isinstance(rows, list) or len(rows) > 100 or type(total) is not int
                        or total != len(rows) or any(not isinstance(row, dict)
                            or type(row.get('id')) is not int or row['id'] <= 0
                            or not isinstance(row.get('name'), str) for row in rows)
                        or len({row['id'] for row in rows}) != len(rows)):
                    raise ValueError('Incomplete run artifact listing')
                run_lists[run_id] = rows
            except Exception:
                raise CaptureSelectionError('capture_run_artifact_listing_unverified') from None
        if run_lists[run_id] is None:
            raise CaptureSelectionError('capture_run_artifact_listing_unverified')
        return run_lists[run_id]
    candidates, seen, named_attempts = [], set(), set()
    names, expected_total = {}, None
    for page in range(1, MAX_ARTIFACT_PAGES+1):
        if time.monotonic() > deadline:
            report['errors'].append({'source': ARTIFACT, 'error': 'InspectionBudgetExceeded'})
            report['captureMissingAfter'] = {kind: len(hours) for kind, hours in wanted.items()}
            return
        # The REST name filter is exact, so it cannot discover attempt-suffixed
        # names. Bound the repository listing and report incomplete coverage.
        response = request(API + '/actions/artifacts?per_page=100&page=' + str(page))
        stats['pagesRead'] += 1
        entries = response.get('artifacts')
        if not isinstance(entries, list) or len(entries) > 100:
            raise ValueError('Invalid capture artifact listing')
        total = response.get('total_count')
        if type(total) is not int or total < 0 or (expected_total is not None and total != expected_total):
            raise ValueError('Changed capture artifact listing')
        expected_total = stats['expectedArtifacts'] = total
        for artifact in entries:
            if not isinstance(artifact, dict):
                raise ValueError('Invalid capture artifact')
            ident = artifact.get('id')
            if type(ident) is not int or ident <= 0 or ident in seen:
                raise ValueError('Invalid or duplicate capture artifact')
            seen.add(ident)
            stats['artifactsSeen'] = len(seen)
            name = artifact.get('name', '')
            named = re.fullmatch(re.escape(ARTIFACT)+r'-([1-9][0-9]*)-([1-9][0-9]*)', name)
            if name != ARTIFACT and named is None:
                continue
            created = clock(artifact['created_at'])
            if named:
                named_attempts.add((int(named[1]), int(named[2])))
            key = (name, None if named else artifact.get('workflow_run', {}).get('id'))
            names[key] = names.get(key, 0)+1
            if (artifact.get('expired')
                    or not 0 < artifact.get('size_in_bytes', 0) <= 8_000_000
                    or not timedelta(0) <= at - created <= timedelta(days=2)):
                continue
            if any(-timedelta(minutes=15) <= created - hour <= timedelta(hours=2)
                   for hours in wanted.values() for hour in hours):
                candidates.append(artifact)
        if len(entries) < 100 or len(seen) >= expected_total:
            stats['listingComplete'] = len(seen) == expected_total
            break
    if not stats['listingComplete']:
        report['errors'].append({'source': ARTIFACT, 'error': 'CaptureListingIncomplete'})
    stats['candidates'] = len(candidates)
    stats['candidateLimitReached'] = len(candidates) > MAX_CANDIDATES
    # Explicit attempts take priority over legacy copies, without deleting any
    # old evidence or changing the original source hour of an earlier attempt.
    ordered = sorted(candidates, key=lambda row: (row['name'] != ARTIFACT, row['created_at']), reverse=True)
    for artifact in ordered[:MAX_CANDIDATES]:
        if not allowed(at) or time.monotonic() > deadline:
            report['errors'].append({'source': ARTIFACT, 'error': 'InspectionBudgetExceeded'})
            break
        if not any(wanted.values()):
            break
        stats['processedCandidates'] += 1
        try:
            run_id = artifact['workflow_run']['id']
            if type(run_id) is not int or run_id <= 0:
                raise ValueError('Invalid capture run identity')
            if names[(artifact['name'], run_id if artifact['name'] == ARTIFACT else None)] != 1:
                raise CaptureSelectionError('capture_artifact_name_ambiguous')
            inventory = None if stats['listingComplete'] else run_artifacts(run_id)
            if inventory is not None:
                matches = [row for row in inventory if row['name'] == artifact['name']]
                if len(matches) != 1:
                    raise CaptureSelectionError('capture_artifact_name_ambiguous')
                if any(matches[0].get(key) != artifact.get(key)
                       for key in ('id', 'digest', 'size_in_bytes', 'expired', 'workflow_run')):
                    raise CaptureSelectionError('capture_artifact_listing_mismatch')
            named = re.fullmatch(re.escape(ARTIFACT)+r'-([1-9][0-9]*)-([1-9][0-9]*)', artifact['name'])
            raw = None
            if named:
                if int(named[1]) != run_id:
                    raise ValueError('Capture artifact name/run mismatch')
                attempt = int(named[2])
            else:
                raw = request(API + '/actions/artifacts/' + str(artifact['id']) + '/zip', binary=True)
                attempt = capture_document(raw, artifact['digest']).get('runAttempt')
                if type(attempt) is not int or attempt <= 0:
                    raise ValueError('Invalid legacy capture attempt')
                if ((run_id, attempt) in named_attempts or (inventory is not None
                        and any(row['name'] == f'{ARTIFACT}-{run_id}-{attempt}' for row in inventory))):
                    report.setdefault('skippedArtifacts', []).append({'id': artifact['id'],
                        'reason': 'explicit_attempt_artifact_present'})
                    continue
            run = request(API + '/actions/runs/' + str(run_id) + '/attempts/' + str(attempt))
            if (run.get('id') != run_id or run.get('head_branch') != 'main'
                    or run.get('path') != WORKFLOW
                    or run.get('event') not in ('schedule', 'workflow_dispatch', 'push')
                    or run.get('status') != 'completed'
                    or type(run.get('run_attempt')) is not int or run['run_attempt'] != attempt
                    or run.get('repository', {}).get('full_name') != REPO
                    or (run.get('head_repository') is not None and run['head_repository'].get('full_name') != REPO)
                    or not re.fullmatch(r'[0-9a-f]{40}', str(run.get('head_sha', '')))
                    or artifact['workflow_run'].get('head_sha') != run.get('head_sha')
                    or not re.fullmatch(r'sha256:[0-9a-f]{64}', artifact.get('digest', ''))):
                raise ValueError('Untrusted capture workflow provenance')
            if raw is None:
                raw = request(API + '/actions/artifacts/' + str(artifact['id']) + '/zip', binary=True)
            if len(raw) != artifact['size_in_bytes']:
                raise ValueError('Capture archive size mismatch')
            captured = read_capture(raw, artifact['digest'], run_id, attempt, at)
            started = run.get('run_started_at') or run.get('created_at')
            if started and clock(captured['checkedAt']) < clock(started)-timedelta(minutes=2):
                raise ValueError('Capture predates the bound attempt')
            if not any(clock(chart['sourceAt']) in wanted[kind]
                       for kind, chart in captured['charts'].items()):
                continue
            count, conflicts = add_capture(current, captured, at)
            report['addedPoints'] += count
            report['conflicts'] += conflicts
            report['artifacts'].append({
                'id': artifact['id'], 'runId': run_id, 'runAttempt': attempt,
                'artifactName': artifact['name'], 'digest': artifact['digest'],
                'sourceType': SOURCE_TYPE,
                'sourceHours': {kind: chart['sourceAt'] for kind, chart in captured['charts'].items()},
                'sourceUrls': {kind: chart['source'] for kind, chart in captured['charts'].items()},
                'addedPoints': count})
            wanted = missing_hours(current, at)
        except Exception as exc:
            report['errors'].append({'artifactId': artifact['id'], 'source': ARTIFACT,
                                     'error': type(exc).__name__,
                                     'reason': exc.reason if isinstance(exc, CaptureSelectionError)
                                               else 'capture_evidence_rejected'})
    report['captureMissingAfter'] = {kind: len(hours) for kind, hours in wanted.items()}
