"""Recover missed schedules from VERIFIED outcomes, never from a green badge alone.

This controller only reads Actions evidence and dispatches fixed main workflows.
It never receives SFTP credentials, writes production files, cancels active jobs,
or invents historical chart observations. An independent caller may rerun this
workflow when GitHub's schedule event delivery itself is delayed.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import stat
import time
import zipfile
from batch_publication_evidence import (EvidenceUnavailable, read_json_artifact,
                                        read_capture_evidence, production_evidence_ok,
                                        read_production_evidence)

REPO = 'seirian/isegye-idol-fansite'
ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
UTC = timezone.utc
FIRST_WEEKLY = datetime(2026, 11, 15, tzinfo=KST)
SPECS = {
    'capture': ('melon-chart-capture.yml', 'melon-chart-capture', 'ISEGYE_ALBUMS_PAUSED'),
    'albums': ('albums-daily.yml', 'daily-albums', 'ISEGYE_ALBUMS_PAUSED'),
    'schedule': ('schedule-refresh.yml', 'schedule-publication', 'ISEGYE_SCHEDULE_PAUSED'),
    'music': ('music-daily.yml', 'daily-music', 'ISEGYE_MUSIC_PAUSED'),
    'history': ('history-monthly.yml', 'weekly-history', 'ISEGYE_HISTORY_PAUSED'),
    'playground': ('playground-daily.yml', 'daily-playground', 'ISEGYE_PLAYGROUND_PAUSED'),
    'catalog': ('video-catalog.yml', None, 'ISEGYE_VIDEO_CATALOG_PAUSED'),
    'production': ('production.yml', None, 'PRODUCTION_PAUSED'),
}
# A caller may inspect the controller itself without gaining a dispatch target.
READABLE_WORKFLOWS = frozenset(spec[0] for spec in SPECS.values()) | {'batch-watchdog.yml'}
MAX_ARCHIVE = 8_000_000
RUN_PAGE_SIZE = 100
MAX_RUN_PAGES = 20
MAX_ARTIFACT_PAGES = 10
MAX_HTTP_HEADERS = 32_768
COMPLETION_WORKFLOWS = {
    'Melon charts - independent lightweight evidence capture': 'melon-chart-capture.yml',
    'Albums - hourly verified metadata and chart refresh': 'albums-daily.yml',
    'Schedule - every 2 hours permitted-source refresh': 'schedule-refresh.yml',
    'Production - isolated inour SFTP deployment': 'production.yml',
}
ACTIVE = {'queued', 'pending', 'in_progress', 'waiting', 'requested'}
REQUIRED_SCHEDULE = {'cafe-members','cafe-agency','fan-roundup',
                     'parable-web','berriz-notice','berriz-calendar'}

REASON_CODES = frozenset({
    'unapproved_workflow', 'invalid_run_listing', 'run_history_changed',
    'run_history_incomplete', 'run_history_budget_exceeded', 'duplicate_run_id',
    'invalid_run_provenance', 'invalid_run_attempt', 'invalid_run_status',
    'invalid_run_clock', 'workflow_query_failed', 'invalid_inspection_budget',
    'github_timeout', 'github_request_failed', 'github_rate_limited',
    'github_http_error', 'github_response_too_large', 'github_invalid_headers',
    'github_invalid_json', 'inspection_validation_failed', 'inspection_api_unavailable',
    'inspection_internal_error',
    'inspection_budget_exceeded',
})
API_DIAGNOSTIC_LIMITS = {
    'httpStatus': 599, 'rateLimitLimit': 1_000_000_000,
    'rateLimitRemaining': 1_000_000_000, 'rateLimitReset': 999_999_999_999,
    'retryAfterSeconds': 604_800,
}


def safe_api_diagnostics(value):
    """Only bounded numeric response metadata may enter reports or incidents."""
    if not isinstance(value, dict):
        return {}
    return {key:value[key] for key, limit in API_DIAGNOSTIC_LIMITS.items()
            if type(value.get(key)) is int and 0 <= value[key] <= limit}


class InspectionError(ValueError):
    def __init__(self, reason_code, message, *, inspection=None, api_diagnostics=None):
        super().__init__(message)
        self.reason_code = reason_code if reason_code in REASON_CODES else 'inspection_validation_failed'
        self.inspection = inspection
        self.api_diagnostics = safe_api_diagnostics(api_diagnostics)


class GitHubAPIError(RuntimeError):
    def __init__(self, reason_code, *, api_diagnostics=None):
        # Never retain CLI stderr, response bodies, signed URLs, or request data.
        super().__init__('GitHub API request failed')
        self.reason_code = reason_code if reason_code in REASON_CODES else 'github_request_failed'
        self.inspection = None
        self.api_diagnostics = safe_api_diagnostics(api_diagnostics)


def error_details(exc):
    """Stable public diagnostics; unknown exception text is deliberately omitted."""
    fallback = ('inspection_validation_failed' if isinstance(exc, ValueError) else
                'inspection_api_unavailable' if isinstance(exc, RuntimeError) else 'inspection_internal_error')
    result = {'error':type(exc).__name__, 'reasonCode':fallback}
    if isinstance(exc, (InspectionError, GitHubAPIError)):
        result['reasonCode'] = exc.reason_code
        info = exc.inspection
        if isinstance(info, dict) and info.get('workflow') in READABLE_WORKFLOWS:
            clean = {'scope':'workflow', 'workflow':info['workflow'], 'complete':info.get('complete') is True}
            for key in ('pageSize','pageBudget','pagesRead','expectedRuns','observedRuns','mainRuns'):
                value = info.get(key)
                if value is None and key == 'expectedRuns':
                    clean[key] = None
                elif type(value) is int and 0 <= value <= 1_000_000_000:
                    clean[key] = value
            result['inspection'] = clean
        if exc.api_diagnostics:
            result['apiDiagnostics'] = safe_api_diagnostics(exc.api_diagnostics)
    return result


def http_response(raw):
    """Strip gh --include headers without ever decoding a binary archive body."""
    remaining = raw
    diagnostics = {}
    consumed = 0
    for _ in range(5):
        endings = [(remaining.find(marker), len(marker)) for marker in (b'\r\n\r\n', b'\n\n')]
        endings = [(offset, size) for offset, size in endings if offset >= 0]
        if not endings:
            raise InspectionError('github_invalid_headers', 'GitHub response headers missing')
        end, size = min(endings)
        consumed += end+size
        if consumed > MAX_HTTP_HEADERS:
            raise InspectionError('github_invalid_headers', 'GitHub response headers too large')
        lines = remaining[:end].splitlines()
        status = re.fullmatch(rb'HTTP/\d(?:\.\d)? ([1-5][0-9]{2})(?: [^\r\n]*)?', lines[0] if lines else b'')
        if not status:
            raise InspectionError('github_invalid_headers', 'Invalid GitHub response status')
        diagnostics = {'httpStatus':int(status[1])}
        names = {b'x-ratelimit-limit':'rateLimitLimit', b'x-ratelimit-remaining':'rateLimitRemaining',
                 b'x-ratelimit-reset':'rateLimitReset', b'retry-after':'retryAfterSeconds'}
        for line in lines[1:]:
            name, separator, value = line.partition(b':')
            key = names.get(name.strip().lower())
            value = value.strip()
            if separator and key and re.fullmatch(rb'[0-9]{1,12}', value):
                number = int(value)
                if number <= API_DIAGNOSTIC_LIMITS[key]:
                    diagnostics[key] = number
        remaining = remaining[end+size:]
        if not remaining.startswith(b'HTTP/'):
            return remaining, diagnostics
    raise InspectionError('github_invalid_headers', 'Too many GitHub response header blocks')


def clock(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone required')
    return result.astimezone(UTC)

def due_slot(kind, at):
    local = at.astimezone(KST)
    if kind in ('albums', 'capture'):
        if 1 <= local.hour < 7:
            return None
        return local.replace(minute=0, second=0, microsecond=0).astimezone(UTC)
    if kind == 'schedule':
        # Anchor to even KST hours, not UTC parity; before :05 use the prior slot.
        due = local.replace(hour=local.hour-local.hour%2, minute=5, second=0, microsecond=0)
        return (due if due <= local else due-timedelta(hours=2)).astimezone(UTC)
    if kind in ('music', 'catalog','playground'):
        hour, minute = (6, 0) if kind == 'music' else (8, 0) if kind == 'playground' else (7, 15)
        due = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return (due if due <= local else due-timedelta(days=1)).astimezone(UTC)
    if kind == 'history':
        if local < FIRST_WEEKLY:
            return None
        due = (local-timedelta(days=(local.weekday()+1)%7)).replace(hour=0, minute=0, second=0, microsecond=0)
        return due.astimezone(UTC)
    raise ValueError('Unknown batch')

def recent(value, due, at):
    try:
        return due <= clock(value) <= at+timedelta(minutes=2)
    except (ValueError, TypeError, AttributeError):
        return False

def evidence_ok(kind, files, due, at):
    """Publish and source clocks must both be current. Missing evidence is NOT success."""
    if kind == 'albums':
        from album_hourly import coverage
        data = files.get('albums/snapshot.json', {})
        cov = coverage(data, at)
        pub = files.get('albums-publication.json', {})
        restore = files.get('albums-restore.json', {})
        # A no-op run must have read the currently published server feed.
        persisted = ((pub.get('status') == 'published' and pub.get('verifiedReadback') is True)
                     or (restore.get('status') == 'restored' and restore.get('source') == 'cumulative-feed'))
        return persisted and cov['currentComplete']
    pub = files.get({'music':'music-publication.json','schedule':'schedule-publication.json',
                     'history':'history-publication.json','playground':'playground-publication.json'}[kind], {})
    if pub.get('status') != 'published' or not recent(pub.get('generatedAt'), due, at):
        return False
    if kind == 'schedule':
        health = pub.get('collectionHealth', {})
        sources = health.get('sources', {})
        return (files.get('schedule-health.json', {}).get('verified') is True
                and health.get('state') == 'complete'
                and schedule_readback_ok(pub, due, at)
                and all(sources.get(k, {}).get('state') == 'complete'
                        and recent(sources.get(k, {}).get('lastSuccessAt'), due, at)
                        for k in REQUIRED_SCHEDULE))
    if pub.get('verifiedReadback') is not True:
        return False
    if kind == 'playground':
        return (pub.get('bankVerified') is True and pub.get('questionCount',0)>=32 and recent(pub.get('readbackAt'),due,at))
    if kind == 'music':
        states = pub.get('sourceStates', {})
        audit = files.get('test-results/music-sources/source-audit.json', {})
        return (len(states) == 9 and all(v == 'ok' for v in states.values())
                and audit.get('selected', 0) > 0 and audit.get('passed') == audit.get('selected'))
    return (pub.get('cadence') == 'weekly'
            and pub.get('through') == (due.astimezone(KST)-timedelta(days=1)).date().isoformat()
            and not pub.get('coverage', {}).get('partial', True))

def schedule_readback_ok(pub, due, at):
    """Keep legacy reports compatible without mistaking them for explicit readback."""
    if pub.get('verifiedReadback', True) is not True:
        return False
    if 'evidenceVersion' not in pub:
        return True
    if type(pub['evidenceVersion']) is not int or pub['evidenceVersion'] != 2:
        return False
    if pub.get('verifiedReadback') is not True:
        return False
    try:
        generated = clock(pub['generatedAt'])
        published = clock(pub['publishedAt'])
        readback = clock(pub['readbackAt'])
        return due <= generated <= published <= readback <= at+timedelta(minutes=2)
    except (KeyError, ValueError, TypeError, AttributeError):
        return False


def api(path, method='GET', payload=None, binary=False):
    if not path.startswith(('actions/', 'git/ref/heads/main', 'issues')):
        raise ValueError('Unapproved endpoint')
    args = ['gh','api','--include','--method',method,'repos/'+REPO+'/'+path]
    if payload is not None:
        args += ['--input','-']
    try:
        result = subprocess.run(args, input=json.dumps(payload).encode() if payload is not None else None,
                                capture_output=True, timeout=70)
    except subprocess.TimeoutExpired:
        raise GitHubAPIError('github_timeout') from None
    except OSError:
        raise GitHubAPIError('github_request_failed') from None
    limit = MAX_ARCHIVE if binary else 2_000_000
    if len(result.stdout) > limit+MAX_HTTP_HEADERS:
        raise InspectionError('github_response_too_large', 'Oversized GitHub response')
    if result.returncode and not result.stdout.startswith(b'HTTP/'):
        raise GitHubAPIError('github_request_failed')
    raw, diagnostics = http_response(result.stdout)
    status = diagnostics['httpStatus']
    if result.returncode or not 200 <= status < 300:
        limited = status == 429 or (status == 403 and
                  (diagnostics.get('rateLimitRemaining') == 0 or 'retryAfterSeconds' in diagnostics))
        raise GitHubAPIError('github_rate_limited' if limited else 'github_http_error', api_diagnostics=diagnostics)
    if len(raw) > limit:
        raise InspectionError('github_response_too_large', 'Oversized GitHub response', api_diagnostics=diagnostics)
    if binary:
        return raw
    try:
        return json.loads(raw) if raw.strip() else {}
    except (ValueError, UnicodeError):
        raise InspectionError('github_invalid_json', 'Invalid GitHub JSON response', api_diagnostics=diagnostics) from None

def artifact_files(run, prefix, filename, getter=api):
    name = prefix+'-'+str(run['id'])+'-'+str(run['run_attempt'])
    matches = []
    seen = set()
    for page in range(1, MAX_ARTIFACT_PAGES+1):
        endpoint = f"actions/runs/{int(run['id'])}/artifacts?per_page=100"
        listing = getter(endpoint if page == 1 else endpoint+f'&page={page}')
        entries = listing.get('artifacts')
        if not isinstance(entries, list) or len(entries) > 100:
            raise ValueError('Invalid artifact listing')
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('Invalid artifact entry')
            ident = entry.get('id')
            # Some old empty/expired fixtures lack IDs; accepted only if unusable.
            if ident is not None:
                if type(ident) is not int or ident <= 0 or ident in seen:
                    raise ValueError('Duplicate or invalid artifact ID')
                seen.add(ident)
            if entry.get('name') == name and not entry.get('expired'):
                matches.append(entry)
        total = listing.get('total_count')
        if total is not None and (type(total) is not int or total < 0):
            raise ValueError('Invalid artifact count')
        if len(entries) < 100:
            if total is not None and total > len(seen):
                raise ValueError('Incomplete artifact listing')
            break
    else:
        raise ValueError('Artifact history exceeds inspection budget')
    if not matches:
        raise EvidenceUnavailable('Missing current-attempt evidence')
    if len(matches) != 1:
        raise ValueError('Duplicate current-attempt evidence')
    entry = matches[0]
    provenance = entry.get('workflow_run', {})
    if (run.get('head_branch') != 'main' or run.get('path') != '.github/workflows/'+filename
            or run.get('repository',{}).get('full_name') != REPO
            or provenance.get('id') != run['id'] or provenance.get('head_sha') != run['head_sha']
            or type(entry.get('id')) is not int or entry['id'] <= 0
            or not 0 < entry.get('size_in_bytes',0) <= MAX_ARCHIVE):
        raise ValueError('Untrusted evidence')
    raw = getter(f"actions/artifacts/{int(entry['id'])}/zip", binary=True)
    if len(raw) != entry['size_in_bytes'] or entry.get('digest') != 'sha256:'+hashlib.sha256(raw).hexdigest():
        raise ValueError('Evidence checksum mismatch')
    allowed = {'albums/snapshot.json','albums-restore.json','albums-publication.json',
               'schedule-publication.json','schedule-health.json','music-publication.json',
               'test-results/music-sources/source-audit.json','history-publication.json','playground-publication.json'}
    files = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if sum(info.file_size for info in z.infolist() if info.filename in allowed) > MAX_ARCHIVE:
            raise ValueError('Oversized expanded evidence')
        for info in z.infolist():
            if info.filename in allowed:
                if (info.filename in files or info.file_size > MAX_ARCHIVE
                        or stat.S_ISLNK(info.external_attr >> 16)):
                    raise ValueError('Duplicate or oversized evidence')
                value = json.loads(z.read(info))
                if not isinstance(value, dict):
                    raise ValueError('Evidence must be a JSON object')
                files[info.filename] = value
    return files

def started(run):
    if run.get('run_attempt', 1) > 1 and not run.get('run_started_at'):
        raise ValueError('Latest attempt start time required')
    return clock(run.get('run_started_at') or run['created_at'])


class EvidenceCache:
    """Cache immutable artifact bytes only; all mutable decisions are reread."""
    def __init__(self, getter, max_calls=200):
        self.getter, self.archives = getter, {}
        self.calls = self.cacheHits = self.bytes = 0
        self.max_calls = max_calls

    def __call__(self, path, method='GET', payload=None, binary=False):
        immutable = method == 'GET' and binary and re.fullmatch(r'actions/artifacts/[1-9][0-9]*/zip', path)
        if immutable and path in self.archives:
            self.cacheHits += 1
            return self.archives[path]
        if self.calls >= self.max_calls:
            raise InspectionError('inspection_budget_exceeded', 'Shared inspection call budget exceeded')
        self.calls += 1
        result = self.getter(path, method=method, payload=payload, binary=binary)
        if immutable and isinstance(result, bytes) and self.bytes+len(result) <= 16_000_000:
            self.archives[path] = result
            self.bytes += len(result)
        return result


def current_capture_evidence(runs, due, at, getter):
    """A later failed probe must not erase a real complete current-hour capture."""
    completed = [run for run in runs if run.get('status') == 'completed']
    candidates = [run for run in completed if started(run) >= due-timedelta(minutes=15)]
    if len(candidates) > 8:
        raise InspectionError('inspection_validation_failed', 'Capture evidence budget exceeded')
    candidates = candidates or completed[:1]
    latest = None
    for candidate in candidates:
        try:
            proof = read_capture_evidence(getter, candidate, due, at)
        except EvidenceUnavailable:
            continue
        if latest is None:
            latest = (candidate, proof)
        if proof['currentComplete']:
            return candidate, proof
    if latest:
        return latest
    raise EvidenceUnavailable('No capture evidence in the inspected attempts')


def production_failure_block(runs, at, getter):
    """Only exact, current-code failure evidence may stop repeated deployment.

Two consecutive matching deterministic failures open the circuit. An unknown
lock mutation blocks immediately. The normal active/cooldown/budget gates are
still checked first; no failure is relabeled healthy or user-paused.
"""
    from batch_failure_evidence import trusted_failure
    proofs = []
    for candidate in runs[:2]:
        if candidate.get('status') != 'completed' or candidate.get('conclusion') not in ('failure', 'cancelled'):
            return None
        report = None
        for prefix in ('isegye-production-evidence', 'isegye-production-prepare-evidence'):
            try:
                report = read_json_artifact(getter, candidate, prefix, 'batch-failure.json')
                break
            except EvidenceUnavailable:
                continue
        if report is None:
            return None  # Legacy absence does not authorize a fabricated block.
        proof = trusted_failure(report, candidate, at)
        if proof is None or proof['retryClass'] == 'transient':
            return None
        if proof['retryClass'] == 'unknown':
            mutation_unknown = proof['reasonCode'] == 'production_lock_request_unknown'
            return {'state': 'request_unknown' if mutation_unknown else 'inspection_failed',
                    'failureEvidence': [proof], 'reasonCode': proof['reasonCode'],
                    'requestOutcome': 'unconfirmed' if mutation_unknown else 'not_attempted'}
        proofs.append(proof)
    if len(proofs) != 2:
        return None
    fields = ('reasonCode', 'retryClass', 'stage', 'codeIdentity', 'inputIdentity')
    if any(proofs[0][key] != proofs[1][key] for key in fields):
        return None
    return {'state': 'blocked_dependency' if proofs[0]['retryClass'] == 'blocked' else 'blocked_permanent',
            'reasonCode': proofs[0]['reasonCode'], 'failureEvidence': proofs,
            'requiresResolutionEvidence': True}


def update_incident(getter, title, body, unhealthy, may_close, sleeper=time.sleep):
    """One bounded reporting retry, without replaying already-issued dispatches.

A create timeout/502 is reconciled by a read and never blindly POSTed again.
Existing issue PATCHes are idempotent exact-content writes after readback.
"""
    retried = False

    def retryable(exc):
        meta = getattr(exc, 'api_diagnostics', None) or {}
        return (isinstance(exc, GitHubAPIError) and meta.get('httpStatus') in (500, 502, 503, 504)
                and meta.get('retryAfterSeconds', 0) <= 2)

    try:
        issues = getter('issues?state=open&per_page=100')
    except GitHubAPIError as exc:
        if not retryable(exc):
            raise
        sleeper((exc.api_diagnostics or {}).get('retryAfterSeconds', 0))
        retried = True
        issues = getter('issues?state=open&per_page=100')
    if not isinstance(issues, list):
        raise ValueError('Invalid incident listing')
    matching = [item for item in issues if item.get('title') == title and not item.get('pull_request')]
    if len(matching) > 1:
        raise ValueError('Ambiguous recovery incident')
    issue = matching[0] if matching else None
    if not unhealthy and not (issue and may_close):
        return {'state': 'unchanged', 'reportRetries': int(retried)}
    payload = {'body': body}
    if not unhealthy:
        payload['state'] = 'closed'
    elif not issue:
        payload['title'] = title
    endpoint = 'issues/'+str(issue['number']) if issue else 'issues'
    method = 'PATCH' if issue else 'POST'
    try:
        getter(endpoint, method, payload)
    except GitHubAPIError as exc:
        if retried or not retryable(exc):
            raise
        sleeper((exc.api_diagnostics or {}).get('retryAfterSeconds', 0))
        retried = True
        if issue:
            latest = getter(endpoint)
            if all(latest.get(key) == value for key, value in payload.items()):
                return {'state': 'recorded', 'reportRetries': 1, 'reconciled': True}
            getter(endpoint, 'PATCH', payload)
        else:
            latest = getter('issues?state=open&per_page=100')
            matches = [item for item in latest if item.get('title') == title and item.get('body') == body
                       and not item.get('pull_request')]
            if len(matches) != 1:
                raise  # Unknown POST outcome remains unknown; no duplicate issue.
    return {'state': 'recorded', 'reportRetries': int(retried)}

def recovery_action(runs, at, due, healthy, grace=timedelta(minutes=5)):
    if healthy:
        return 'healthy'
    if any(r.get('status') in ACTIVE for r in runs):
        return 'active'
    if at < due+grace:
        return 'grace'
    if any(started(r) > at+timedelta(minutes=2) for r in runs):
        raise ValueError('Future workflow clock')
    # A run may start while this inspection is reading the API. Treat small
    # positive clock deltas conservatively, never as an expired cooldown.
    recent_runs = [r for r in runs if -timedelta(minutes=2) <= at-started(r) < timedelta(minutes=15)]
    if recent_runs:
        return 'cooldown'
    # At most two dispatch retries per rolling hour, independent of schedule arrivals.
    retries = [r for r in runs if r.get('event') == 'workflow_dispatch'
               and -timedelta(minutes=2) <= at-started(r) < timedelta(hours=1)]
    return 'retry_budget' if len(retries) >= 2 else 'dispatch'

def read_workflow_runs(filename, getter=None, max_pages=MAX_RUN_PAGES):
    """Return complete runs and their read coverage, never dispatch permission.

    Creation pages do not establish the latest attempt. Read every page within
    the unchanged budget, then order locally. This is not an atomic API snapshot;
    callers must still perform their fresh pre-dispatch decision and slot checks.
    An incomplete result is raised with coverage diagnostics, never returned as
    a partial list that could be mistaken for the absence of active/recent runs.
    """
    getter = getter or api
    if not isinstance(filename, str) or filename not in READABLE_WORKFLOWS:
        raise InspectionError('unapproved_workflow', 'Unapproved workflow')
    if type(max_pages) is not int or not 1 <= max_pages <= MAX_RUN_PAGES:
        raise InspectionError('invalid_inspection_budget', 'Invalid workflow inspection budget')
    inspection = {'scope':'workflow', 'workflow':filename, 'pageSize':RUN_PAGE_SIZE,
                  'pageBudget':max_pages, 'pagesRead':0, 'expectedRuns':None,
                  'observedRuns':0, 'mainRuns':0, 'complete':False}
    found = {}
    main = []
    expected_total = None

    def fail(code, message):
        raise InspectionError(code, message, inspection=dict(inspection))

    for page in range(1, max_pages+1):
        # Do not use branch/status/created filters: GitHub caps filtered searches
        # at 1,000 results, and an old run can have a new attempt. Filter locally.
        try:
            listing = getter('actions/workflows/'+filename+
                             f'/runs?per_page={RUN_PAGE_SIZE}&page={page}')
        except (InspectionError, GitHubAPIError) as exc:
            exc.inspection = dict(inspection)
            raise
        except Exception:
            fail('workflow_query_failed', 'Workflow run query failed')
        inspection['pagesRead'] += 1
        if not isinstance(listing, dict):
            fail('invalid_run_listing', 'Invalid workflow run listing')
        runs = listing.get('workflow_runs')
        total = listing.get('total_count')
        if (not isinstance(runs, list) or len(runs) > RUN_PAGE_SIZE
                or type(total) is not int or total < 0):
            fail('invalid_run_listing', 'Invalid workflow run listing')
        if expected_total is None:
            expected_total = total
            inspection['expectedRuns'] = total
        elif total != expected_total:
            fail('run_history_changed', 'Workflow run listing changed during inspection')
        for run in runs:
            if (not isinstance(run, dict) or type(run.get('id')) is not int or run['id'] <= 0
                    or not isinstance(run.get('repository'), dict)
                    or run['repository'].get('full_name') != REPO):
                fail('invalid_run_provenance', 'Untrusted workflow run')
            if run['id'] in found:
                fail('duplicate_run_id', 'Untrusted or duplicate workflow run')
            found[run['id']] = run
            inspection['observedRuns'] = len(found)
            if run.get('head_branch') != 'main':
                continue
            if (run.get('path') != '.github/workflows/'+filename
                    or not isinstance(run.get('head_repository'), dict)
                    or run['head_repository'].get('full_name') != REPO):
                fail('invalid_run_provenance', 'Untrusted workflow run')
            if type(run.get('run_attempt')) is not int or run['run_attempt'] < 1:
                fail('invalid_run_attempt', 'Untrusted workflow run attempt')
            if not isinstance(run.get('status'), str) or run['status'] not in ACTIVE | {'completed'}:
                fail('invalid_run_status', 'Untrusted workflow run status')
            try:
                started(run)
                clock(run['created_at'])
            except (KeyError, ValueError, TypeError, AttributeError):
                fail('invalid_run_clock', 'Invalid workflow attempt or creation clock')
            main.append(run)
            inspection['mainRuns'] = len(main)
        if len(runs) < RUN_PAGE_SIZE or total <= len(found):
            if total != len(found):
                fail('run_history_incomplete', 'Incomplete workflow run listing')
            inspection['complete'] = True
            return {'runs':sorted(main, key=started, reverse=True), 'inspection':inspection}
    fail('run_history_budget_exceeded', 'Workflow run history exceeds inspection budget')


def workflow_runs(filename, getter=None, max_pages=MAX_RUN_PAGES, *, inspection=None):
    """Compatibility list API for the unchanged set of recoverable workflows."""
    if not isinstance(filename, str) or filename not in {spec[0] for spec in SPECS.values()}:
        raise InspectionError('unapproved_workflow', 'Unapproved workflow')
    result = read_workflow_runs(filename, getter, max_pages)
    if inspection is not None:
        inspection.update(result['inspection'])
    return result['runs']


def require_trusted_completion(getter=None):
    """A workflow_run wake-up must never import PR/fork code or evidence."""
    if os.getenv('GITHUB_EVENT_NAME') != 'workflow_run':
        return
    getter = getter or api
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    source = event.get('workflow_run', {})
    if (event.get('action') != 'completed'
            or source.get('head_branch') != 'main'
            or source.get('head_repository', {}).get('full_name') != REPO
            or source.get('name') not in COMPLETION_WORKFLOWS
            or type(source.get('id')) is not int or source['id'] <= 0):
        raise ValueError('Untrusted completion event')
    run = getter('actions/runs/'+str(source['id']))
    filename = COMPLETION_WORKFLOWS[source['name']]
    if (run.get('id') != source['id'] or run.get('name') != source['name']
            or run.get('head_branch') != 'main'
            or run.get('repository', {}).get('full_name') != REPO
            or run.get('head_repository', {}).get('full_name') != REPO
            or run.get('path') != '.github/workflows/'+filename
            or run.get('event') not in ('push', 'schedule', 'workflow_dispatch')
            or run.get('status') != 'completed'):
        raise ValueError('Untrusted completion run')


def inspect_batch(kind, at, getter=None):
    """Recompute the due slot, pauses, active attempts, budget and evidence."""
    getter = getter or api
    filename, prefix, pause = SPECS[kind]
    row = {'batch':kind, 'workflow':filename, 'checkedAt':at.isoformat()}
    if os.getenv('PRODUCTION_PAUSED') == 'true' or os.getenv(pause) == 'true':
        row['state'] = 'paused'
        return row
    due = due_slot(kind, at) if kind != 'production' else at-timedelta(days=1)
    if due is None:
        row['state'] = 'night_pause' if kind in ('albums', 'capture') else 'not_due'
        return row
    row['dueAt'] = due.isoformat()
    inspection = {}
    runs = workflow_runs(filename, getter, inspection=inspection)
    row['inspection'] = inspection
    row['inspectedRuns'] = len(runs)
    if runs:
        last = runs[0]
        row['latestAttempt'] = {'runId':last['id'], 'attempt':last['run_attempt'],
                               'startedAt':started(last).isoformat(),
                               'status':last['status'], 'event':last['event']}
    scheduled = [r for r in runs if r.get('event') == 'schedule']
    if scheduled:
        last = max(scheduled, key=lambda r: clock(r['created_at']))
        # Creation is diagnostic for event delivery, NEVER the retry clock.
        row['lastScheduledEvent'] = {'runId':last['id'], 'createdAt':last['created_at']}
    if any(r.get('status') in ACTIVE for r in runs):
        row['state'] = 'active'
        row['activeRuns'] = [r['id'] for r in runs if r.get('status') in ACTIVE]
        return row
    success = next((r for r in runs if r.get('conclusion') == 'success'), None)
    good = False
    if kind == 'production':
        head = getter('git/ref/heads/main')['object']['sha']
        row['expectedHead'] = head
        # Inspect the latest completed attempt for this release, including an
        # ancillary monitor failure/cancellation after deployment was verified.
        success = next((r for r in runs if r.get('status') == 'completed'
                        and r.get('head_sha') == head), None)
    elif kind == 'capture':
        # Failed/partial captures are observed failures, not absent evidence.
        success = next((r for r in runs if r.get('status') == 'completed'), None)
    if success:
        row['evidenceRun'] = success['id']
        row['evidenceAttempt'] = success['run_attempt']
        if kind == 'production':
            evidence_run = success
            try:
                pub, evidence_run, lineage = read_production_evidence(getter, success, at)
                row['publicationLineage'] = lineage
                row['evidenceAttempt'] = evidence_run['run_attempt']
            except EvidenceUnavailable:
                pub = {}
                row['evidenceState'] = 'unavailable'
            good = production_evidence_ok(pub, evidence_run, row['expectedHead'], at)
            row['publicationEvidence'] = {key: pub[key] for key in
                ('status', 'commit', 'verifiedAt', 'lockRemoved', 'browserVerified', 'privatePathsBlocked')
                if key in pub}
            row['publicationVerified'] = good
            if good and success.get('conclusion') != 'success':
                row['ancillaryFailure'] = True
                row['workflowConclusion'] = success.get('conclusion')
        elif kind == 'capture':
            try:
                success, capture = current_capture_evidence(runs, due, at, getter)
                row['evidenceRun'] = success['id']
                row['evidenceAttempt'] = success['run_attempt']
            except EvidenceUnavailable:
                capture = {'currentComplete': False}
                row['evidenceState'] = 'unavailable'
            row['observationEvidence'] = capture
            good = capture['currentComplete']
        elif kind == 'catalog':
            good = recent(success.get('run_started_at'), due, at)
        else:
            try:
                files = artifact_files(success, prefix, filename, getter)
            except EvidenceUnavailable:
                files = {}
                row['evidenceState'] = 'unavailable'
            good = evidence_ok(kind, files, due, at)
            pub = files.get({'albums':'albums-publication.json',
                             'schedule':'schedule-publication.json',
                             'music':'music-publication.json',
                             'history':'history-publication.json','playground':'playground-publication.json'}[kind], {})
            row['publicationEvidence'] = {key:pub[key] for key in
                ('status','generatedAt','publishedAt','verifiedReadback','readbackAt','evidenceVersion') if key in pub}
            if kind == 'schedule':
                row['readbackEvidence'] = ('explicit' if pub.get('verifiedReadback') is True
                                           else 'legacy_report' if 'verifiedReadback' not in pub
                                           else 'failed')
            if kind == 'albums':
                from album_hourly import coverage
                cov = coverage(files.get('albums/snapshot.json', {}), at)
                row['missingHours'] = {k:len(v['missingSlots']) for k,v in cov['charts'].items()}
                row['historicalGapsOnly'] = bool(good and any(row['missingHours'].values()))
    row['state'] = recovery_action(runs, at, due, good)
    if kind == 'production' and row['state'] == 'dispatch':
        block = production_failure_block(runs, at, getter)
        if block:
            row.update(block)
    return row


def recover_batch(kind, apply=False, getter=None, now=None):
    getter = getter or api
    now = now or (lambda: datetime.now(UTC))
    row = inspect_batch(kind, now(), getter)
    if apply and row['state'] == 'dispatch':
        # A job can finish between reads. Rechecking only ACTIVE is insufficient:
        # a new successful/failed completion must also affect evidence/cooldown.
        row = inspect_batch(kind, now(), getter)
        row['recheckedBeforeDispatch'] = True
        if row['state'] == 'dispatch':
            at = now()
            filename, _, pause = SPECS[kind]
            if os.getenv('PRODUCTION_PAUSED') == 'true' or os.getenv(pause) == 'true':
                row['state'] = 'paused'
                return row
            due = due_slot(kind, at) if kind != 'production' else None
            if kind != 'production' and (due is None or due.isoformat() != row['dueAt']):
                # Do not act on an old decision if an API read crossed a slot/night boundary.
                row['state'] = ('night_pause' if kind in ('albums', 'capture') else 'not_due') if due is None else 'slot_changed'
                row['nextDueAt'] = due.isoformat() if due else None
                return row
            getter('actions/workflows/'+filename+'/dispatches', 'POST', {'ref':'main'})
            row['state'] = 'dispatched'
            row['dispatchedAt'] = now().isoformat()
    return row


def report_state(rows):
    if any(r['state'] in ('dispatch','dispatched','inspection_failed','retry_budget',
                          'blocked_permanent','blocked_dependency','request_unknown') for r in rows):
        return 'attention'
    if any(r['state'] in ('active','cooldown','grace','slot_changed') for r in rows):
        return 'pending'
    # Historical observation gaps stay in the report, not a perpetual live incident.
    return 'checked'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if (os.getenv('GITHUB_REPOSITORY') != REPO or os.getenv('GITHUB_REF') != 'refs/heads/main'
            or not os.getenv('GH_TOKEN')):
        raise ValueError('Main-only watchdog')
    at = datetime.now(UTC)
    report = {'schemaVersion':2, 'checkedAt':at.isoformat(),'mode':'apply' if args.apply else 'audit','batches':[]}
    client = EvidenceCache(api)
    if os.getenv('PRODUCTION_PAUSED') == 'true':
        report['state'] = 'paused'
    else:
        try:
            require_trusted_completion(client)
        except Exception as exc:
            report.update(state='inspection_failed', triggerError=type(exc).__name__)
            report['triggerFailure'] = error_details(exc)
            (ROOT/'batch-watchdog.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
            print(json.dumps(report, ensure_ascii=False))
            return 1
        for kind,(filename,prefix,pause) in SPECS.items():
            try:
                row = recover_batch(kind, args.apply, getter=client)
            except Exception as exc:
                row = {'batch':kind, 'workflow':filename, 'state':'inspection_failed', **error_details(exc)}
            report['batches'].append(row)
        report['state'] = report_state(report['batches'])
        if args.apply:
            try:
                title='[배치] 예약 누락·게시 지연·배포 복구 점검'
                unhealthy=report['state']=='attention'
                body='실제 성공 산출물 기준 점검입니다. 실행 요청은 게시 성공이 아닙니다.\n\n```json\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n```\n'
                report['incidentOutcome'] = update_incident(client, title, body, unhealthy,
                    all(r['state'] in ('healthy','night_pause','not_due','paused') for r in report['batches']))
            except Exception as exc:
                report['incidentError']=type(exc).__name__
                report['incidentFailure']=error_details(exc)
    report['apiCalls'] = client.calls
    report['apiCallBudget'] = client.max_calls
    report['evidenceCacheHits'] = client.cacheHits
    (ROOT/'batch-watchdog.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as out:
            out.write('```json\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n```\n')
    return int(bool(report.get('incidentError')) or any(r.get('state') in ('inspection_failed', 'request_unknown') for r in report['batches']))

if __name__ == '__main__':
    raise SystemExit(main())
